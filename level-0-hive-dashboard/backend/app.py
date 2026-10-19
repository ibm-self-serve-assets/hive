import asyncio
import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List, Any, Dict

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import BackendConfig
from backend.store import DashboardStore
from backend.consumer import EventConsumerManager

logger = logging.getLogger("hive.backend")

config: BackendConfig = BackendConfig.load_from_env()
store: DashboardStore = DashboardStore()
consumer_mgr: Optional[EventConsumerManager] = None
csrf_token: str = secrets.token_hex(16)
subscribers: List[asyncio.Queue] = []


async def notify_subscribers(snap: Dict[str, Any]):
    data = json.dumps(snap)
    for q in list(subscribers):
        try:
            q.put_nowait(data)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_mgr, csrf_token
    csrf_token = secrets.token_hex(16)

    consumer_mgr = EventConsumerManager(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_event_callback=notify_subscribers,
    )
    consumer_mgr.start()
    asyncio.create_task(auto_connect())
    yield
    if consumer_mgr:
        consumer_mgr.stop()


async def auto_connect():
    global consumer_mgr
    if not config.workshop_access_token:
        logger.warning("AUTO-CONNECT: WORKSHOP_ACCESS_TOKEN missing — skipping")
        return
    if not (config.confluent_bootstrap_server and config.confluent_api_key and config.confluent_api_secret):
        logger.warning("AUTO-CONNECT: Confluent credentials missing — skipping")
        return

    headers = {"Authorization": f"Bearer {config.workshop_access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Server epoch
            r = await client.get(f"{config.simulation_server_url}/v1/server", headers=headers)
            r.raise_for_status()
            epoch = r.json().get("server_epoch")
            store.server_epoch = epoch

            # Find or provision factory
            topics_map: Dict[str, str] = {}
            f_resp = await client.get(f"{config.simulation_server_url}/v1/factories", headers=headers)
            if f_resp.status_code == 200:
                facts = f_resp.json().get("factories", [])
                if facts:
                    f0 = facts[0]
                    if f0.get("lifecycle_status") == "expired":
                        logger.info(f"AUTO-CONNECT: Factory {f0['factory_id'][:8]} is expired; will provision fresh factory")
                        store.active_factory_id = None
                    else:
                        store.active_factory_id = f0["factory_id"]
                        store.server_epoch = f0["server_epoch"]
                        store.lifecycle_status = f0.get("lifecycle_status", store.lifecycle_status)
                        store.running = f0.get("running", store.running)
                        topics_map = f0.get("topics", {})
                        logger.info(f"AUTO-CONNECT: Reconnected to factory {f0['factory_id'][:8]}…")

            if not store.active_factory_id:
                logger.info("AUTO-CONNECT: Provisioning new factory…")
                prov_r = await client.post(
                    f"{config.simulation_server_url}/v1/factories",
                    json={
                        "bootstrap_server": config.confluent_bootstrap_server,
                        "producer_credentials": {
                            "api_key": config.confluent_api_key,
                            "api_secret": config.confluent_api_secret,
                        },
                    },
                    headers={
                        **headers,
                        "Idempotency-Key": str(uuid.uuid4()),
                        "X-Server-Epoch": epoch,
                    },
                )
                prov_r.raise_for_status()
                prov_data = prov_r.json()
                store.active_factory_id = prov_data["factory_id"]
                store.reset()
                logger.info(f"AUTO-CONNECT: Factory provisioned {store.active_factory_id[:8]}… waiting for probe verification")

                # Poll until verification probes pass and lifecycle leaves 'provisioning'
                for _ in range(30):  # poll up to 6 seconds (30 * 200ms)
                    await asyncio.sleep(0.2)
                    fdetail_r = await client.get(
                        f"{config.simulation_server_url}/v1/factories/{store.active_factory_id}",
                        headers=headers,
                    )
                    if fdetail_r.status_code == 200:
                        fdata = fdetail_r.json()
                        status = fdata.get("lifecycle_status")
                        if status not in ("provisioning", None):
                            topics_map = fdata.get("topics", {})
                            store.lifecycle_status = status
                            store.running = (status == "running")
                            logger.info(f"AUTO-CONNECT: Factory ready with status '{status}'")
                            break

            if topics_map:
                topic_list = list(topics_map.values())
                consumer_mgr.stop()
                consumer_mgr = EventConsumerManager(
                    store=store,
                    bootstrap_servers=config.confluent_bootstrap_server,
                    api_key=config.confluent_api_key,
                    api_secret=config.confluent_api_secret,
                    topics=topic_list,
                    on_event_callback=notify_subscribers,
                )
                consumer_mgr.start()
                logger.info(f"AUTO-CONNECT: Consumer started on {len(topic_list)} topics")
                await notify_subscribers(store.snapshot())
            else:
                logger.warning("AUTO-CONNECT: No topics — consumer not started")

    except Exception as e:
        logger.error(f"AUTO-CONNECT: {e}")


app = FastAPI(title="Hive Connect-Simulation Backend", version="1.0.0", lifespan=lifespan)

allowed_origins = [
    f"http://localhost:{config.local_frontend_port}",
    f"http://127.0.0.1:{config.local_frontend_port}",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_csrf(x_csrf_token: Optional[str] = Header(None)):
    if not x_csrf_token or x_csrf_token != csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "invalid_csrf_token", "message": "CSRF token mismatch"},
        )


class ControlCommandRequest(BaseModel):
    command: str
    start: Optional[bool] = True
    expected_generation: Optional[int] = None


@app.get("/api/csrf")
async def get_csrf():
    return {"csrf_token": csrf_token}


@app.get("/api/config")
async def get_config():
    fully_configured = bool(
        config.simulation_server_url
        and config.workshop_access_token
        and config.confluent_bootstrap_server
        and config.confluent_api_key
    )
    return {"fully_configured": fully_configured}


@app.get("/api/status")
async def get_status():
    return store.snapshot()


@app.post("/api/connect")
async def retry_connect(x_csrf_token: Optional[str] = Header(None)):
    verify_csrf(x_csrf_token)
    asyncio.create_task(auto_connect())
    return {"status": "connecting"}


@app.post("/api/controls")
async def send_control(
    req: ControlCommandRequest,
    x_csrf_token: Optional[str] = Header(None),
):
    verify_csrf(x_csrf_token)
    if not config.workshop_access_token:
        raise HTTPException(status_code=400, detail={"error_code": "not_connected", "message": "No access token configured"})

    if req.command not in ("start", "pause", "stop", "restart"):
        raise HTTPException(status_code=422, detail="Invalid command")

    if not store.active_factory_id:
        if req.command == "restart":
            logger.info("Restart requested with no active factory; provisioning fresh factory...")
            await auto_connect()
            if not store.active_factory_id:
                raise HTTPException(status_code=500, detail={"error_code": "provision_failed", "message": "Failed to provision new factory"})
            if req.start is not False:
                return await _send_server_command("start")
            return {"lifecycle_status": store.lifecycle_status, "factory_id": store.active_factory_id}
        raise HTTPException(status_code=400, detail={"error_code": "not_connected", "message": "No active factory"})

    cmd_url = f"{config.simulation_server_url}/v1/factories/{store.active_factory_id}/{req.command}"
    headers = {
        "Authorization": f"Bearer {config.workshop_access_token}",
        "Idempotency-Key": str(uuid.uuid4()),
        "X-Server-Epoch": store.server_epoch or "",
    }
    body: Dict[str, Any] = {}
    if req.expected_generation is not None:
        body["expected_generation"] = req.expected_generation
    elif store.run_generation > 0:
        body["expected_generation"] = store.run_generation
    if req.command == "restart":
        body["start"] = req.start if req.start is not None else True

    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(cmd_url, json=body, headers=headers)
        if (r.status_code in (404, 409)) or (r.status_code == 410 and req.command == "restart"):
            logger.info(f"Server returned {r.status_code}; refreshing connection and active factory...")
            store.active_factory_id = None
            await auto_connect()
            if not store.active_factory_id:
                raise HTTPException(status_code=500, detail={"error_code": "provision_failed", "message": "Failed to re-sync factory after server reload/restart"})
            target_cmd = "start" if (req.command == "restart" and req.start is not False) or req.command == "start" else req.command
            return await _send_server_command(target_cmd)

        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)

        receipt = r.json()
        if "lifecycle_status" in receipt:
            store.lifecycle_status = receipt["lifecycle_status"]
            store.running = (store.lifecycle_status == "running")
            await notify_subscribers(store.snapshot())
        return receipt


async def _send_server_command(command: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cmd_url = f"{config.simulation_server_url}/v1/factories/{store.active_factory_id}/{command}"
    headers = {
        "Authorization": f"Bearer {config.workshop_access_token}",
        "Idempotency-Key": str(uuid.uuid4()),
        "X-Server-Epoch": store.server_epoch or "",
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(cmd_url, json=body or {}, headers=headers)
        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)

        receipt = r.json()
        if "lifecycle_status" in receipt:
            store.lifecycle_status = receipt["lifecycle_status"]
            store.running = (store.lifecycle_status == "running")
            await notify_subscribers(store.snapshot())
        return receipt


@app.get("/api/stream")
async def event_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    subscribers.append(queue)

    async def generate():
        # Send initial snapshot
        initial = {"type": "init", "state": store.snapshot()}
        yield f"data: {json.dumps(initial)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps({'type': 'update', 'state': json.loads(data)})}\n\n"
                except asyncio.TimeoutError:
                    hb = {"type": "heartbeat", "state": store.snapshot()}
                    yield f"data: {json.dumps(hb)}\n\n"
        finally:
            if queue in subscribers:
                subscribers.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
