import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse, HTMLResponse
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
        enrollment_config = load_enrollment_config()
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
    bootstrap_server: str
    producer_credentials: ProducerCredentials


class CommandRequest(BaseModel):
    expected_generation: Optional[int] = None


class RestartCommandRequest(BaseModel):
    expected_generation: Optional[int] = None
    start: bool = True


class RotateConnectionRequest(BaseModel):
    bootstrap_server: str
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
        "active_factories": len(factory_manager.factories),
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
        bootstrap_server=req.bootstrap_server,
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
            detail={"error_code": "expired", "message": "Simulation expired"},
        )

    return {
        "factory_id": factory.factory_id,
        "run_id": factory.current_run.run_id,
        "run_generation": factory.current_run.run_generation,
        "lifecycle_status": factory.current_run.lifecycle_status,
        "created_at": factory.created_at.isoformat(),
        "expires_at": factory.expires_at.isoformat(),
        "topics": factory.get_topics(),
        "server_epoch": factory_manager.get_server_epoch(),
        "pending_events_count": factory.buffer.total_events,
        "pending_events_bytes": factory.buffer.total_bytes,
        "operational_error": factory.current_run.operational_error.model_dump()
        if factory.current_run.operational_error
        else None,
    }


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
        bootstrap_server=req.bootstrap_server,
        producer_key=req.producer_credentials.api_key,
        producer_secret=req.producer_credentials.api_secret,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=status_code, content=body)


# ── Admin dashboard ───────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard():
    """
    Live operator view — no auth, intended for local / trusted-network use only.
    Refresh the page to update; auto-refreshes every 5 seconds.
    """
    now_utc = datetime.now(timezone.utc)

    # Build per-factory rows
    rows_html = ""
    factories = list(factory_manager.factories.values()) if factory_manager else []

    for f in factories:
        f.check_expiry()
        run = f.current_run
        status_class = {
            "running": "status-running",
            "paused":  "status-paused",
            "stopped": "status-stopped",
            "expired": "status-expired",
            "provisioning": "status-provisioning",
            "provisioning_failed": "status-error",
        }.get(run.lifecycle_status, "status-other")

        expires_in_s = max(0, int((f.expires_at - now_utc).total_seconds()))
        expires_str = f"{expires_in_s // 60}m {expires_in_s % 60}s" if not f.is_expired else "expired"

        op_err = run.operational_error.code if run.operational_error else "—"

        res = run.resources  # dict
        pts = run.parts      # dict

        r_str = (f"{res.get('resin',0)} / {res.get('silicon',0)} / "
                 f"{res.get('metals',0)} / {res.get('copper',0)} / {res.get('energy',0)}")
        p_str = (f"{pts.get('chassis',0)} / {pts.get('electronics',0)} / "
                 f"{pts.get('actuator',0)} / {pts.get('battery',0)}")

        rows_html += f"""
        <tr>
          <td class="mono">{f.enrollment_record.attendee_id}</td>
          <td><span class="badge {status_class}">{run.lifecycle_status}</span></td>
          <td>{run.run_generation}</td>
          <td class="mono small">{f.factory_id[:8]}…</td>
          <td>{f.buffer.total_events}</td>
          <td>{r_str}</td>
          <td>{p_str}</td>
          <td>{run.completed_robots_count}</td>
          <td>{expires_str}</td>
          <td>{op_err}</td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="10" class="empty">No active factories</td></tr>'

    total = len(factories)
    active = sum(1 for f in factories if not f.is_expired)
    enrolled = len(enrollment_config.enrollments) if enrollment_config else 0
    epoch = factory_manager.get_server_epoch() if factory_manager else "—"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Hive Robotics - Simulation Server</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
          font-size: 14px; background: #001141; color: #e8edf8; min-height: 100vh; }}
  header {{ background: #000d2e; border-bottom: 1px solid #0f3a80;
            padding: 14px 24px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 16px; font-weight: 600; color: #fff; letter-spacing: .04em; }}
  header .sub {{ font-size: 12px; color: #7a9cc8; }}
  .meta {{ margin: 16px 24px; display: flex; gap: 24px; flex-wrap: wrap; }}
  .kpi {{ background: #001f5c; border: 1px solid #0f3a80; border-radius: 6px;
           padding: 10px 18px; min-width: 130px; }}
  .kpi .label {{ font-size: 11px; color: #7a9cc8; text-transform: uppercase;
                  letter-spacing: .06em; margin-bottom: 4px; }}
  .kpi .value {{ font-size: 22px; font-weight: 700; color: #60a5fa; }}
  .wrap {{ padding: 0 24px 32px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #001f5c; color: #7a9cc8; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: .05em;
        padding: 8px 10px; text-align: left; border-bottom: 1px solid #0f3a80; white-space: nowrap; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #0a2560; vertical-align: middle; }}
  tr:hover td {{ background: #001a50; }}
  .mono {{ font-family: "SF Mono", "Fira Code", monospace; }}
  .small {{ font-size: 12px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px;
             font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
  .status-running     {{ background: #14532d; color: #4ade80; }}
  .status-paused      {{ background: #713f12; color: #fbbf24; }}
  .status-stopped     {{ background: #1f2937; color: #9ca3af; }}
  .status-expired     {{ background: #3b1a1a; color: #f87171; }}
  .status-provisioning{{ background: #1e3a5f; color: #93c5fd; }}
  .status-error       {{ background: #4a1942; color: #f0abfc; }}
  .status-other       {{ background: #1e293b; color: #94a3b8; }}
  .empty  {{ color: #4a6fa8; text-align: center; padding: 24px; font-style: italic; }}
  footer  {{ text-align: center; color: #2a4a7a; font-size: 11px; padding: 16px;
              border-top: 1px solid #0a2560; margin-top: 8px; }}
</style>
</head>
<body>
<header>
  <h1>🐝 HIVE — Simulation Server Admin</h1>
  <span class="sub">Auto-refreshes every 5 s</code></span>
</header>
<div class="meta">
  <div class="kpi"><div class="label">Active factories</div><div class="value">{total}</div></div>
  <div class="kpi"><div class="label">Active attendees</div><div class="value">{active}/{enrolled}</div></div>
</div>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>Attendee</th>
      <th>Status</th>
      <th>Gen</th>
      <th>Factory ID</th>
      <th>Buf events</th>
      <th>Resources (R/Si/M/Cu/E)</th>
      <th>Parts (Ch/El/Ac/Ba)</th>
      <th>Workers</th>
      <th>Expires in</th>
      <th>Error</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
<footer>Hive Robotics · {now_utc.strftime("%H:%M:%S UTC")}</footer>
</body>
</html>"""
    return HTMLResponse(content=html)


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
