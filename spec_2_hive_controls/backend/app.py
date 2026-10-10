import asyncio
import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.config import BackendConfig
from backend.models import FactoryStatePayload, EventEnvelope
from backend.store import InMemProjectionStore
from backend.consumer import EventConsumerManager

logger = logging.getLogger("hive.local_backend")

config: BackendConfig = BackendConfig.load_from_env()
store: InMemProjectionStore = InMemProjectionStore()
consumer_mgr: Optional[EventConsumerManager] = None
csrf_token: str = secrets.token_hex(16)
subscribers: List[asyncio.Queue] = []


async def notify_subscribers(event: Any):
    data = json.dumps(event if isinstance(event, dict) else event.model_dump())
    for q in list(subscribers):
        try:
            q.put_nowait(data)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_mgr, config, store, csrf_token
    logger.info("Initializing Local Hive Controls Backend...")
    csrf_token = secrets.token_hex(16)

    # Initialize consumer manager
    consumer_mgr = EventConsumerManager(
        store=store,
        sim_server_url=config.simulation_server_url,
        token=config.workshop_access_token,
        bootstrap_servers=config.confluent_bootstrap_servers,
        api_key=config.confluent_consumer_api_key,
        api_secret=config.confluent_consumer_api_secret,
        on_event_callback=notify_subscribers,
    )
    consumer_mgr.start()

    # Attempt auto-connection if token is already configured
    if config.workshop_access_token:
        asyncio.create_task(auto_reconnect())

    yield

    if consumer_mgr:
        consumer_mgr.stop()
    logger.info("Local Hive Controls Backend stopped.")


async def auto_reconnect():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"Authorization": f"Bearer {config.workshop_access_token}"}
            r = await client.get(f"{config.simulation_server_url}/v1/server", headers=headers)
            if r.status_code == 200:
                epoch = r.json().get("server_epoch")
                store.server_epoch = epoch

            f_resp = await client.get(f"{config.simulation_server_url}/v1/factories", headers=headers)
            if f_resp.status_code == 200:
                facts = f_resp.json().get("factories", [])
                if facts:
                    f = facts[0]
                    fid = f["factory_id"]
                    store.active_factory_id = fid
                    store.server_epoch = f["server_epoch"]
                    logger.info(f"Reconnected to existing factory {fid}")
    except Exception as e:
        logger.debug(f"Auto-reconnect skipped or failed: {e}")


app = FastAPI(
    title="Local Hive Controls Backend",
    version="1.0.0",
    description="Local backend bridging React UI and hosted/local Hive Simulation Server.",
    lifespan=lifespan,
)

# CORS restricted to local frontend
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
            detail={"error_code": "invalid_csrf_token", "message": "Anti-CSRF token mismatch"},
        )


# Request schemas
class ConnectRequest(BaseModel):
    simulation_server_url: str
    workshop_access_token: str
    connection_profile_id: str
    producer_api_key: str
    producer_api_secret: str
    consumer_bootstrap_servers: Optional[str] = None
    consumer_api_key: Optional[str] = None
    consumer_api_secret: Optional[str] = None


class ControlCommandRequest(BaseModel):
    command: str  # start, pause, stop, restart, speed
    start: Optional[bool] = True
    speed: Optional[int] = 1
    expected_generation: Optional[int] = None


@app.get("/api/csrf")
async def get_csrf_token():
    return {"csrf_token": csrf_token}


@app.get("/api/status")
async def get_status():
    observed = store.get_observed_state()
    return {
        "configured": bool(config.workshop_access_token),
        "simulation_server_url": config.simulation_server_url,
        "connection_profile_id": config.connection_profile_id,
        "active_factory_id": store.active_factory_id,
        "server_epoch": store.server_epoch,
        "stream_health": observed["stream_health"],
        "has_confluent_config": bool(config.confluent_bootstrap_servers and config.confluent_consumer_api_key),
        "observed_state": observed,
    }


@app.get("/api/events")
async def get_events():
    return {"events": store.get_activity_log()}


@app.post("/api/connect")
async def connect_and_provision(
    req: ConnectRequest,
    x_csrf_token: Optional[str] = Header(None),
):
    verify_csrf(x_csrf_token)
    global config, consumer_mgr

    # Update in-memory configuration
    config.simulation_server_url = req.simulation_server_url.rstrip("/")
    config.workshop_access_token = req.workshop_access_token
    config.connection_profile_id = req.connection_profile_id
    if req.consumer_bootstrap_servers:
        config.confluent_bootstrap_servers = req.consumer_bootstrap_servers
    if req.consumer_api_key:
        config.confluent_consumer_api_key = req.consumer_api_key
    if req.consumer_api_secret:
        config.confluent_consumer_api_secret = req.consumer_api_secret

    token = req.workshop_access_token or ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. Check server epoch
            srv_r = await client.get(f"{config.simulation_server_url}/v1/server", headers=headers)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail={"error_code": "simulation_server_unreachable", "message": f"Cannot connect to simulation server at {config.simulation_server_url}: {e}"}
            )

        if srv_r.status_code != 200:
            try:
                err_body = srv_r.json()
            except Exception:
                err_body = {"message": srv_r.text or f"Server returned HTTP {srv_r.status_code}"}
            raise HTTPException(status_code=srv_r.status_code, detail=err_body)
            
        epoch = srv_r.json().get("server_epoch")
        store.server_epoch = epoch

        # 2. Check if owner already has a factory
        try:
            f_list_r = await client.get(f"{config.simulation_server_url}/v1/factories", headers=headers)
            if f_list_r.status_code == 200:
                factories = f_list_r.json().get("factories", [])
                if factories:
                    f0 = factories[0]
                    store.active_factory_id = f0["factory_id"]
                    store.server_epoch = f0["server_epoch"]
                    return {
                        "status": "reconnected",
                        "factory_id": f0["factory_id"],
                        "server_epoch": f0["server_epoch"],
                        "topics": f0.get("topics", {}),
                    }
        except Exception as e:
            logger.debug(f"Factory list lookup error: {e}")

        # 3. Provision new factory
        prov_body = {
            "connection_profile_id": req.connection_profile_id,
            "producer_credentials": {
                "api_key": req.producer_api_key,
                "api_secret": req.producer_api_secret,
            },
        }
        try:
            prov_r = await client.post(
                f"{config.simulation_server_url}/v1/factories",
                json=prov_body,
                headers={
                    **headers,
                    "Idempotency-Key": str(uuid.uuid4()),
                    "X-Server-Epoch": epoch,
                },
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail={"error_code": "provision_failed", "message": f"Failed calling /v1/factories: {e}"}
            )

        if prov_r.status_code not in (200, 202):
            try:
                err_body = prov_r.json()
            except Exception:
                err_body = {"message": prov_r.text or f"Server returned HTTP {prov_r.status_code}"}
            raise HTTPException(status_code=prov_r.status_code, detail=err_body)

        prov_data = prov_r.json()
        factory_id = prov_data["factory_id"]
        store.active_factory_id = factory_id

        # Restart consumer manager with updated credentials
        if consumer_mgr:
            consumer_mgr.stop()
        consumer_mgr = EventConsumerManager(
            store=store,
            sim_server_url=config.simulation_server_url,
            token=config.workshop_access_token,
            bootstrap_servers=config.confluent_bootstrap_servers,
            api_key=config.confluent_consumer_api_key,
            api_secret=config.confluent_consumer_api_secret,
            on_event_callback=notify_subscribers,
        )
        consumer_mgr.start()

        return {
            "status": "provisioned",
            "factory_id": factory_id,
            "operation_id": prov_data.get("operation_id"),
            "server_epoch": epoch,
        }


@app.post("/api/controls")
async def send_control_command(
    req: ControlCommandRequest,
    x_csrf_token: Optional[str] = Header(None),
):
    verify_csrf(x_csrf_token)
    if not store.active_factory_id or not config.workshop_access_token:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "not_connected", "message": "No active factory connected"},
        )

    cmd = req.command
    if cmd not in ("start", "pause", "stop", "restart", "speed"):
        raise HTTPException(status_code=422, detail="Invalid command")

    cmd_url = f"{config.simulation_server_url}/v1/factories/{store.active_factory_id}/{cmd}"
    headers = {
        "Authorization": f"Bearer {config.workshop_access_token}",
        "Idempotency-Key": str(uuid.uuid4()),
        "X-Server-Epoch": store.server_epoch or "",
    }

    body = {}
    if req.expected_generation is not None:
        body["expected_generation"] = req.expected_generation
    elif store.run_generation > 0:
        body["expected_generation"] = store.run_generation

    if cmd == "restart":
        body["start"] = req.start if req.start is not None else True
    elif cmd == "speed":
        body["speed"] = req.speed or 1

    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(cmd_url, json=body, headers=headers)
        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)

        receipt = r.json()
        store.latest_command_receipt = {
            "command": cmd,
            "command_id": receipt.get("command_id"),
            "accepted": receipt.get("accepted", True),
            "lifecycle_status": receipt.get("lifecycle_status"),
            "applied_at": receipt.get("applied_at"),
            "status_label": "Accepted / awaiting observation",
        }
        await notify_subscribers({"type": "command_receipt", "receipt": store.latest_command_receipt})
        return receipt


@app.get("/api/stream")
async def event_stream(request: Request):
    """
    Server-Sent Events (SSE) streaming state and activity updates to the React UI.
    """
    queue: asyncio.Queue = asyncio.Queue()
    subscribers.append(queue)

    async def sse_generator():
        # Send initial state snapshot immediately
        initial_payload = {
            "type": "init",
            "observed_state": store.get_observed_state(),
            "events": store.get_activity_log(),
        }
        yield f"data: {json.dumps(initial_payload)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat — include latest activity log so direct-poll mode surfaces events
                    hb = {
                        "type": "heartbeat",
                        "stream_health": store.get_stream_health(),
                        "observed_state": store.get_observed_state(),
                        "events": store.get_activity_log(),
                    }
                    yield f"data: {json.dumps(hb)}\n\n"
        finally:
            if queue in subscribers:
                subscribers.remove(queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
