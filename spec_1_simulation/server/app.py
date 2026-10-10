import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.config import ServerConfig, EnrollmentConfig, load_enrollment_config
from server.factory_manager import FactoryManager

logger = logging.getLogger("hive.app")

server_config: Optional[ServerConfig] = None
enrollment_config: Optional[EnrollmentConfig] = None
factory_manager: Optional[FactoryManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global server_config, enrollment_config, factory_manager
    # Load configuration
    try:
        server_config = ServerConfig.load_from_env()
        enrollment_config = load_enrollment_config(server_config.enrollment_config_path)
        factory_manager = FactoryManager(server_config, enrollment_config)
        await factory_manager.start()
        logger.info("Hive Simulation Server initialized and running.")
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise

    yield

    if factory_manager:
        await factory_manager.stop()
    logger.info("Hive Simulation Server shut down cleanly.")


app = FastAPI(
    title="Hive Simulation Server",
    version="1.0.0",
    description="Containerized in-memory robotic bee factory simulation server for workshops.",
    lifespan=lifespan,
)


def get_current_attendee(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Missing or invalid Bearer token"},
        )
    token = authorization.split(" ", 1)[1].strip()
    if not enrollment_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "service_unavailable", "message": "Server enrollment not initialized"},
        )
    rec = enrollment_config.find_by_token(token)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Invalid workshop access token"},
        )
    return rec.attendee_id


def require_epoch(x_server_epoch: Optional[str] = Header(None)):
    if not factory_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "service_unavailable", "message": "Factory manager not ready"},
        )
    if not x_server_epoch or x_server_epoch != factory_manager.get_server_epoch():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "server_restarted",
                "message": "Server epoch mismatch. The simulation server may have restarted.",
                "current_server_epoch": factory_manager.get_server_epoch(),
            },
        )


# Request schemas
class ProducerCredentials(BaseModel):
    api_key: str
    api_secret: str


class ProvisionFactoryRequest(BaseModel):
    connection_profile_id: str
    producer_credentials: ProducerCredentials


class CommandRequest(BaseModel):
    expected_generation: Optional[int] = None


class RestartCommandRequest(BaseModel):
    expected_generation: Optional[int] = None
    start: bool = True


class SpeedCommandRequest(BaseModel):
    expected_generation: Optional[int] = None
    speed: int


class RotateConnectionRequest(BaseModel):
    connection_profile_id: str
    producer_credentials: ProducerCredentials


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    if factory_manager is None or enrollment_config is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return {"status": "ready"}


@app.get("/v1/server")
async def get_server_info(attendee_id: str = Depends(get_current_attendee)):
    return {
        "server_epoch": factory_manager.get_server_epoch(),
        "contract_version": "1.0",
        "active_factories": factory_manager.get_active_factory_count(),
        "max_factories": server_config.max_factories,
    }


@app.get("/v1/factories")
async def list_factories(attendee_id: str = Depends(get_current_attendee)):
    factory_id = factory_manager.owner_factories.get(attendee_id)
    if not factory_id:
        return {"factories": []}
    factory = factory_manager.factories.get(factory_id)
    if not factory:
        return {"factories": []}

    factory.check_expiry()
    return {
        "factories": [
            {
                "factory_id": factory.factory_id,
                "run_id": factory.current_run.run_id,
                "run_generation": factory.current_run.run_generation,
                "lifecycle_status": factory.current_run.lifecycle_status,
                "created_at": factory.created_at.isoformat(),
                "expires_at": factory.expires_at.isoformat(),
                "connection_profile_id": factory.enrollment_record.connection_profile_id,
                "topic_prefix": factory.enrollment_record.topic_prefix,
                "consumer_group_prefix": factory.enrollment_record.consumer_group_prefix,
                "topics": factory.get_topics(),
                "server_epoch": factory_manager.get_server_epoch(),
            }
        ]
    }


@app.post("/v1/factories", status_code=202)
async def provision_factory(
    req: ProvisionFactoryRequest,
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    if x_server_epoch:
        require_epoch(x_server_epoch)

    status_code, body = await factory_manager.register_factory(
        attendee_id=attendee_id,
        connection_profile_id=req.connection_profile_id,
        producer_key=req.producer_credentials.api_key,
        producer_secret=req.producer_credentials.api_secret,
        idempotency_key=idempotency_key,
    )
    if status_code >= 400:
        return JSONResponse(status_code=status_code, content=body)
    return JSONResponse(status_code=status_code, content=body)


@app.get("/v1/factories/{factory_id}")
async def get_factory(factory_id: str, attendee_id: str = Depends(get_current_attendee)):
    factory = factory_manager.factories.get(factory_id)
    if not factory or factory.owner_attendee_id != attendee_id:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "not_found", "message": "Factory not found"},
        )

    if factory.check_expiry():
        raise HTTPException(
            status_code=410,
            detail={"error_code": "expired", "message": "Factory expired"},
        )

    return {
        "factory_id": factory.factory_id,
        "run_id": factory.current_run.run_id,
        "run_generation": factory.current_run.run_generation,
        "lifecycle_status": factory.current_run.lifecycle_status,
        "speed": factory.current_run.speed,
        "created_at": factory.created_at.isoformat(),
        "expires_at": factory.expires_at.isoformat(),
        "connection_profile_id": factory.enrollment_record.connection_profile_id,
        "topic_prefix": factory.enrollment_record.topic_prefix,
        "consumer_group_prefix": factory.enrollment_record.consumer_group_prefix,
        "topics": factory.get_topics(),
        "server_epoch": factory_manager.get_server_epoch(),
        "pending_events_count": factory.buffer.total_events,
        "pending_events_bytes": factory.buffer.total_bytes,
        "operational_error": factory.current_run.operational_error.model_dump()
        if factory.current_run.operational_error
        else None,
    }


@app.get("/v1/factories/{factory_id}/snapshot")
async def get_factory_snapshot(factory_id: str, attendee_id: str = Depends(get_current_attendee)):
    """
    Returns the current full factory.state EventEnvelope for this factory.

    This endpoint exists to support the local development mode where spec_2's consumer
    polls directly instead of consuming from Confluent Cloud. In production the simulation
    server publishes factory.state to Kafka; this endpoint is an equivalent direct read
    of the same snapshot data. It does NOT bypass the event contract — it returns the
    identical EventEnvelope structure that would be published to the .factory-state topic.
    """
    factory = factory_manager.factories.get(factory_id)
    if not factory or factory.owner_attendee_id != attendee_id:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "not_found", "message": "Factory not found"},
        )

    if factory.check_expiry():
        raise HTTPException(
            status_code=410,
            detail={"error_code": "expired", "message": "Factory expired"},
        )

    async with factory.lock:
        _, snapshot_event = factory.current_run.create_snapshot_event(
            event_seq_generator=factory.next_event_sequence,
        )

    return snapshot_event.model_dump()


@app.get("/v1/factories/{factory_id}/events")
async def get_factory_events(
    factory_id: str,
    attendee_id: str = Depends(get_current_attendee),
    limit: int = 200,
):
    """
    Returns recent activity events from the factory's pending buffer for local dev mode.

    In production these events are consumed from Confluent Kafka topics. This endpoint
    provides the same EventEnvelope payloads directly for the local direct-poll consumer
    path in spec_2. Only non-snapshot event types are returned (resource.delivered,
    job.started, part.produced, robot.assembled). Does not modify buffer state.
    """
    factory = factory_manager.factories.get(factory_id)
    if not factory or factory.owner_attendee_id != attendee_id:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "not_found", "message": "Factory not found"},
        )

    if factory.check_expiry():
        raise HTTPException(
            status_code=410,
            detail={"error_code": "expired", "message": "Factory expired"},
        )

    activity_types = {
        "resource.delivered",
        "job.started",
        "part.produced",
        "robot.assembled",
        "manufacturing.blocked",
    }
    # Read from the read-only event_log ring buffer — never drained by the producer,
    # so events are still available after acknowledgement.
    async with factory.lock:
        log_snapshot = list(factory.event_log)

    results = [ev for ev in log_snapshot if ev.get("event_type") in activity_types][:limit]
    return {"events": results}


@app.post("/v1/factories/{factory_id}/start")
async def start_factory(
    factory_id: str,
    req: CommandRequest = CommandRequest(),
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.execute_command(
        factory_id=factory_id,
        attendee_id=attendee_id,
        command="start",
        body=req.model_dump(),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.post("/v1/factories/{factory_id}/pause")
async def pause_factory(
    factory_id: str,
    req: CommandRequest = CommandRequest(),
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.execute_command(
        factory_id=factory_id,
        attendee_id=attendee_id,
        command="pause",
        body=req.model_dump(),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.post("/v1/factories/{factory_id}/stop")
async def stop_factory(
    factory_id: str,
    req: CommandRequest = CommandRequest(),
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.execute_command(
        factory_id=factory_id,
        attendee_id=attendee_id,
        command="stop",
        body=req.model_dump(),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.post("/v1/factories/{factory_id}/restart")
async def restart_factory(
    factory_id: str,
    req: RestartCommandRequest = RestartCommandRequest(),
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.execute_command(
        factory_id=factory_id,
        attendee_id=attendee_id,
        command="restart",
        body=req.model_dump(),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.post("/v1/factories/{factory_id}/speed")
async def set_factory_speed(
    factory_id: str,
    req: SpeedCommandRequest,
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.execute_command(
        factory_id=factory_id,
        attendee_id=attendee_id,
        command="speed",
        body=req.model_dump(),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.put("/v1/factories/{factory_id}/connection", status_code=202)
async def rotate_factory_connection(
    factory_id: str,
    req: RotateConnectionRequest,
    idempotency_key: Optional[str] = Header(None),
    x_server_epoch: Optional[str] = Header(None),
    attendee_id: str = Depends(get_current_attendee),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "missing_idempotency_key", "message": "Idempotency-Key header is required"},
        )
    require_epoch(x_server_epoch)

    status_code, body = await factory_manager.rotate_connection(
        factory_id=factory_id,
        attendee_id=attendee_id,
        connection_profile_id=req.connection_profile_id,
        producer_key=req.producer_credentials.api_key,
        producer_secret=req.producer_credentials.api_secret,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


@app.get("/v1/operations/{operation_id}")
async def get_operation(operation_id: str, attendee_id: str = Depends(get_current_attendee)):
    op = factory_manager.operations.get(operation_id)
    if not op or op.owner_attendee_id != attendee_id:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "not_found", "message": "Operation not found"},
        )

    return {
        "operation_id": op.operation_id,
        "factory_id": op.factory_id,
        "status": op.status,
        "error_code": op.error_code,
        "error_message": op.error_message,
        "created_at": op.created_at.isoformat(),
        "server_epoch": factory_manager.get_server_epoch(),
    }
