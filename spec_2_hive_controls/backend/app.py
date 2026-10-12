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

    # Placeholder consumer — replaced by auto_reconnect once topics/group are known
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

    # Always attempt auto-connect on startup — function self-guards if credentials missing
    asyncio.create_task(auto_reconnect())

    yield

    if consumer_mgr:
        consumer_mgr.stop()
    logger.info("Local Hive Controls Backend stopped.")


async def auto_reconnect():
    """
    Called on startup when all credentials are configured.
    1. Fetches server epoch.
    2. If a factory already exists for this attendee, reconnects the consumer to it.
    3. If no factory exists, provisions one and starts the consumer.

    The UI is a 1:1 view of this backend — it never needs to trigger connection itself.
    """
    global consumer_mgr
    if not config.workshop_access_token:
        logger.warning("AUTO-CONNECT: WORKSHOP_ACCESS_TOKEN not set in .env — skipping")
        return
    if not config.confluent_bootstrap_server:
        logger.warning("AUTO-CONNECT: CONFLUENT_BOOTSTRAP_SERVER not set in .env — skipping")
        return
    if not config.confluent_api_key or not config.confluent_api_secret:
        logger.warning("AUTO-CONNECT: CONFLUENT_API_KEY/SECRET not set in .env — skipping")
        return

    headers = {"Authorization": f"Bearer {config.workshop_access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Get server epoch
            try:
                r = await client.get(f"{config.simulation_server_url}/v1/server", headers=headers)
                r.raise_for_status()
            except Exception as e:
                logger.error(f"AUTO-CONNECT: Cannot reach sim server at {config.simulation_server_url}: {e}")
                return
            epoch = r.json().get("server_epoch")
            store.server_epoch = epoch
            logger.info(f"AUTO-CONNECT: Sim server epoch {epoch[:8]}…")

            # 2. Check for existing factory
            f_resp = await client.get(f"{config.simulation_server_url}/v1/factories", headers=headers)
            topics_map: Dict[str, str] = {}
            group_prefix: str = ""

            if f_resp.status_code == 200:
                facts = f_resp.json().get("factories", [])
                if facts:
                    f0 = facts[0]
                    store.active_factory_id = f0["factory_id"]
                    store.server_epoch = f0["server_epoch"]
                    topics_map = f0.get("topics", {})
                    group_prefix = f0.get("consumer_group_prefix", "")
                    logger.info(f"AUTO-CONNECT: Reconnected to existing factory {f0['factory_id'][:8]}…")

            # 3. No factory — provision one
            if not store.active_factory_id:
                logger.info("AUTO-CONNECT: No existing factory — provisioning…")
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
                    prov_r.raise_for_status()
                except Exception as e:
                    logger.error(f"AUTO-CONNECT: Factory provisioning failed: {e}")
                    return

                prov_data = prov_r.json()
                factory_id = prov_data["factory_id"]
                store.active_factory_id = factory_id
                logger.info(f"AUTO-CONNECT: Factory provisioned {factory_id[:8]}…")

                # Fetch detail for topics + group
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
                    logger.warning(f"AUTO-CONNECT: Could not fetch factory detail: {e}")

            # 4. Start consumer
            if topics_map and group_prefix:
                topic_list = list(topics_map.values())
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
                logger.info(f"AUTO-CONNECT: Consumer started on {len(topic_list)} topics")
            else:
                logger.warning("AUTO-CONNECT: No topics available — consumer not started")

    except Exception as e:
        logger.error(f"AUTO-CONNECT: Unexpected error: {e}")


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
async def retry_connect(x_csrf_token: Optional[str] = Header(None)):
    """
    Manual retry trigger — re-runs the same auto_reconnect logic that fires on startup.
    The UI calls this if it detects the backend is not yet connected (e.g. sim server
    was not up when the backend started). All credentials come from .env.
    """
    verify_csrf(x_csrf_token)
    asyncio.create_task(auto_reconnect())
    return {"status": "connecting"}


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
