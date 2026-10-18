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
                    store.active_factory_id = f0["factory_id"]
                    store.server_epoch = f0["server_epoch"]
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
                logger.info(f"AUTO-CONNECT: Factory provisioned {store.active_factory_id[:8]}…")

                fdetail_r = await client.get(
                    f"{config.simulation_server_url}/v1/factories/{store.active_factory_id}",
                    headers=headers,
                )
                if fdetail_r.status_code == 200:
                    topics_map = fdetail_r.json().get("topics", {})

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
    if not store.active_factory_id or not config.workshop_access_token:
        raise HTTPException(status_code=400, detail={"error_code": "not_connected", "message": "No active factory"})

    if req.command not in ("start", "pause", "stop", "restart"):
        raise HTTPException(status_code=422, detail="Invalid command")

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
        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)
        return r.json()


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
