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

    # Initialize consumer manager (topics/group wired in after auto_reconnect resolves)
    consumer_mgr = EventConsumerManager(
        store=store,
        sim_server_url=config.simulation_server_url,
        token=config.workshop_access_token,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
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
    """
    Called on startup when a workshop token is already configured.
    Fetches the current server epoch and any existing factory, then
    restarts the consumer manager with the correct topics and group.
    """
    global consumer_mgr
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

                    # Restart consumer with correct topics and consumer group
                    topic_list = list(f.get("topics", {}).values())
                    group_prefix = f.get("consumer_group_prefix", "")
                    if topic_list and group_prefix and config.confluent_bootstrap_server:
                        consumer_mgr.stop()
                        consumer_mgr = EventConsumerManager(
                            store=store,
                            sim_server_url=config.simulation_server_url,
                            token=config.workshop_access_token,
                            bootstrap_servers=config.confluent_bootstrap_server,
                            api_key=config.confluent_api_key,
                            api_secret=config.confluent_api_secret,
                            topics=topic_list,
                            consumer_group=group_prefix,
                            on_event_callback=notify_subscribers,
                        )
                        consumer_mgr.start()
                        logger.info(f"Consumer restarted with {len(topic_list)} Confluent topics")
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
    workshop_access_token: Optional[str] = None


class ControlCommandRequest(BaseModel):
    command: str  # start, pause, stop, restart, speed
    start: Optional[bool] = True
    speed: Optional[int] = 1
    expected_generation: Optional[int] = None


@app.get("/api/csrf")
async def get_csrf_token():
    return {"csrf_token": csrf_token}


@app.get("/api/config")
async def get_config():
    """
    Exposes non-secret connection config from .env so the frontend can determine
    whether all required credentials are present and auto-connect without a dialog.
    Secrets are never returned.
    """
    fully_configured = bool(
        config.simulation_server_url
        and config.workshop_access_token
        and config.confluent_bootstrap_server
        and config.confluent_api_key
    )
    return {
        "simulation_server_url": config.simulation_server_url,
        "fully_configured": fully_configured,
        "has_confluent_config": bool(config.confluent_bootstrap_server and config.confluent_api_key),
    }


@app.get("/api/status")
async def get_status():
    observed = store.get_observed_state()
    return {
        "configured": bool(config.workshop_access_token),
        "simulation_server_url": config.simulation_server_url,
        "active_factory_id": store.active_factory_id,
        "server_epoch": store.server_epoch,
        "stream_health": observed["stream_health"],
        "has_confluent_config": bool(config.confluent_bootstrap_server and config.confluent_api_key),
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

    # Simulation server URL may be overridden from the request (e.g. switching from local
    # to a hosted server). Workshop token and all Confluent credentials come from .env.
    config.simulation_server_url = req.simulation_server_url.rstrip("/") or config.simulation_server_url
    # Token from request takes precedence only if non-empty; otherwise use .env value
    if req.workshop_access_token:
        config.workshop_access_token = req.workshop_access_token

    if not config.confluent_bootstrap_server:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_confluent_config", "message": "CONFLUENT_BOOTSTRAP_SERVER is not set in .env"},
        )
    if not config.confluent_api_key or not config.confluent_api_secret:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_confluent_config", "message": "CONFLUENT_API_KEY / SECRET are not set in .env"},
        )

    token = config.workshop_access_token or ""
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

                    # Restart consumer with topics and group from existing factory
                    topic_list = list(f0.get("topics", {}).values())
                    group_prefix = f0.get("consumer_group_prefix", "")
                    if topic_list and group_prefix and config.confluent_bootstrap_server:
                        if consumer_mgr:
                            consumer_mgr.stop()
                        new_mgr = EventConsumerManager(
                            store=store,
                            sim_server_url=config.simulation_server_url,
                            token=config.workshop_access_token,
                            bootstrap_servers=config.confluent_bootstrap_server,
                            api_key=config.confluent_api_key,
                            api_secret=config.confluent_api_secret,
                            topics=topic_list,
                            consumer_group=group_prefix,
                            on_event_callback=notify_subscribers,
                        )
                        new_mgr.start()
                        consumer_mgr = new_mgr

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
            "bootstrap_server": config.confluent_bootstrap_server,
            "producer_credentials": {
                "api_key": config.confluent_api_key,
                "api_secret": config.confluent_api_secret,
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

        # Fetch the factory detail to get authoritative topics and consumer_group_prefix
        topics_map: Dict[str, str] = {}
        group_prefix: str = ""
        try:
            fdetail_r = await client.get(
                f"{config.simulation_server_url}/v1/factories/{factory_id}",
                headers=headers,
            )
            if fdetail_r.status_code == 200:
                fdetail = fdetail_r.json()
                topics_map = fdetail.get("topics", {})
                group_prefix = fdetail.get("consumer_group_prefix", "")
        except Exception as e:
            logger.debug(f"Could not fetch factory detail for topics: {e}")

        # Restart consumer manager with topics and group
        if consumer_mgr:
            consumer_mgr.stop()
        topic_list = list(topics_map.values()) if topics_map else []
        consumer_mgr = EventConsumerManager(
            store=store,
            sim_server_url=config.simulation_server_url,
            token=config.workshop_access_token,
            bootstrap_servers=config.confluent_bootstrap_server,
            api_key=config.confluent_api_key,
            api_secret=config.confluent_api_secret,
            topics=topic_list if (topic_list and group_prefix) else [],
            consumer_group=group_prefix or None,
            on_event_callback=notify_subscribers,
        )
        consumer_mgr.start()

        return {
            "status": "provisioned",
            "factory_id": factory_id,
            "operation_id": prov_data.get("operation_id"),
            "server_epoch": epoch,
            "topics": topics_map,
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
