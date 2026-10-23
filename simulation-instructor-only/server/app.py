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

# Resource icon SVGs (inline, sized for the admin panel)
_RESOURCE_ICONS = {
    "copper":   '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><circle cx="12" cy="12" r="9" fill="#f97316"/><circle cx="12" cy="12" r="5" fill="#c2410c"/></svg>',
    "energy":   '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><polygon points="13,2 4,14 11,14 11,22 20,10 13,10" fill="#facc15"/></svg>',
    "metals":   '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><rect x="4" y="8" width="16" height="8" rx="2" fill="#94a3b8"/><rect x="7" y="5" width="10" height="3" rx="1" fill="#64748b"/></svg>',
    "resin":    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><ellipse cx="12" cy="14" rx="7" ry="6" fill="#fb923c"/><ellipse cx="12" cy="10" rx="5" ry="3" fill="#fed7aa"/></svg>',
    "silicon":  '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><rect x="5" y="5" width="14" height="14" rx="2" fill="#38bdf8"/><rect x="9" y="9" width="6" height="6" rx="1" fill="#0ea5e9"/></svg>',
}

_PART_ICONS = {
    "chassis":     '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><rect x="3" y="7" width="18" height="10" rx="2" fill="#64748b"/><rect x="6" y="4" width="12" height="4" rx="1" fill="#475569"/></svg>',
    "electronics": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><rect x="4" y="6" width="16" height="12" rx="2" fill="#1d4ed8"/><circle cx="9" cy="12" r="2" fill="#93c5fd"/><circle cx="15" cy="12" r="2" fill="#93c5fd"/></svg>',
    "actuator":    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><circle cx="12" cy="12" r="8" fill="#374151"/><circle cx="12" cy="12" r="4" fill="#6b7280"/><circle cx="12" cy="12" r="1.5" fill="#9ca3af"/></svg>',
    "battery":     '<svg viewBox="0 0 24 24" width="16" height="16" fill="none"><rect x="3" y="8" width="16" height="8" rx="2" fill="#166534"/><rect x="19" y="10" width="2" height="4" rx="1" fill="#166534"/><rect x="5" y="10" width="8" height="4" rx="1" fill="#4ade80"/></svg>',
}

_ROBOT_ICONS = {
    "engineer": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"><circle cx="12" cy="7" r="4" fill="#60a5fa"/><rect x="7" y="12" width="10" height="7" rx="2" fill="#3b82f6"/><rect x="3" y="14" width="4" height="5" rx="1" fill="#1d4ed8"/><rect x="17" y="14" width="4" height="5" rx="1" fill="#1d4ed8"/></svg>',
    "forager":  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"><circle cx="12" cy="7" r="4" fill="#a78bfa"/><rect x="7" y="12" width="10" height="7" rx="2" fill="#7c3aed"/><rect x="3" y="14" width="4" height="5" rx="1" fill="#5b21b6"/><rect x="17" y="14" width="4" height="5" rx="1" fill="#5b21b6"/></svg>',
}


def _icon_qty(icon_svg: str, qty: int, dim_zero: bool = True) -> str:
    """Render an icon + quantity chip. Dims when zero."""
    alpha = " dimmed" if (dim_zero and qty == 0) else ""
    return (
        f'<span class="icon-chip{alpha}" title="">'
        f'{icon_svg}'
        f'<span class="chip-num">{qty}</span>'
        f'</span>'
    )


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard():
    """
    Live operator view — no auth, intended for local / trusted-network use only.
    Binds to 0.0.0.0 so it's reachable from any interface; access via http://localhost:8080/admin
    Auto-refreshes every 5 seconds.
    """
    now_utc = datetime.now(timezone.utc)

    rules = None
    try:
        from server.rules import get_simulation_rules
        rules = get_simulation_rules()
    except Exception:
        pass

    robot_prices: Dict[str, int] = {}
    if rules:
        robot_prices = {rm.type: rm.price_in_coins for rm in rules.robot_metadata}

    # Build per-factory rows (summary + expandable detail)
    rows_html = ""
    factories = list(factory_manager.factories.values()) if factory_manager else []

    for idx, f in enumerate(factories):
        f.check_expiry()
        run = f.current_run
        row_id = f"row-{idx}"

        status_class = {
            "running":            "status-running",
            "paused":             "status-paused",
            "stopped":            "status-stopped",
            "expired":            "status-expired",
            "provisioning":       "status-provisioning",
            "provisioning_failed":"status-error",
        }.get(run.lifecycle_status, "status-other")

        expires_in_s = max(0, int((f.expires_at - now_utc).total_seconds()))
        expires_str  = f"{expires_in_s // 60}m {expires_in_s % 60}s" if not f.is_expired else "expired"
        op_err       = run.operational_error.code if run.operational_error else None

        # Sim time
        total_sim_min = run.sim_time_ms // 60_000
        sim_d = total_sim_min // (24 * 60)
        sim_h = (total_sim_min % (24 * 60)) // 60
        sim_m = total_sim_min % 60
        sim_str = f"{sim_d}d {sim_h:02d}h {sim_m:02d}m"

        # Robots by type
        robots_by_type: Dict[str, int] = {}
        for asm in (rules.assembly if rules else []):
            st_id = asm.station_id
            robots_by_type[asm.output_type] = (
                robots_by_type.get(asm.output_type, 0)
                + run.completed_robots_by_station.get(st_id, 0)
            )

        engineers = robots_by_type.get("engineer", 0)
        foragers  = robots_by_type.get("forager", 0)

        # Orders = pending order counts from the Level-4 context.  The server
        # doesn't track orders directly — it only tracks what's been assembled.
        # We surface assembled counts as "filled orders".
        # Treasury = robots sold × price
        treasury = sum(
            robots_by_type.get(rtype, 0) * price
            for rtype, price in robot_prices.items()
        )
        treasury_str = f"🪙 {treasury:,}"

        res = run.resources
        pts = run.parts

        # ── Summary bar ───────────────────────────────────────────────────────
        res_chips = "".join(
            _icon_qty(_RESOURCE_ICONS[k], res.get(k, 0))
            for k in ["copper", "energy", "metals", "resin", "silicon"]
        )
        robot_summary = (
            f'{_icon_qty(_ROBOT_ICONS["engineer"], engineers)}'
            f'{_icon_qty(_ROBOT_ICONS["forager"], foragers)}'
        )
        err_badge = (
            f'<span class="badge status-error">{op_err}</span>'
            if op_err else '<span class="muted">—</span>'
        )

        rows_html += f"""
        <tr class="summary-row" onclick="toggleDetail('{row_id}')" title="Click to expand">
          <td class="mono">{f.enrollment_record.attendee_id}</td>
          <td><span class="badge {status_class}">{run.lifecycle_status.upper()}</span></td>
          <td class="sim-time">{sim_str}</td>
          <td class="res-chips">{res_chips}</td>
          <td>{robot_summary}</td>
          <td class="treasury">{treasury_str}</td>
          <td>{expires_str}</td>
          <td>{err_badge}</td>
          <td class="expand-icon" aria-label="expand">▸</td>
        </tr>
        <tr class="detail-row" id="{row_id}" style="display:none">
          <td colspan="9">
            <div class="detail-card">
              <div class="detail-grid">

                <div class="detail-section">
                  <div class="detail-heading">Resources</div>
                  <div class="icon-row">
                    {"".join(_icon_qty(_RESOURCE_ICONS[k], res.get(k,0), dim_zero=False) + f'<span class="chip-label">{k.capitalize()}</span>' for k in ["copper","energy","metals","resin","silicon"])}
                  </div>
                </div>

                <div class="detail-section">
                  <div class="detail-heading">Parts</div>
                  <div class="icon-row">
                    {"".join(_icon_qty(_PART_ICONS[k], pts.get(k,0), dim_zero=False) + f'<span class="chip-label">{k.capitalize()}</span>' for k in ["chassis","electronics","actuator","battery"])}
                  </div>
                </div>

                <div class="detail-section">
                  <div class="detail-heading">Assemble robots</div>
                  <div class="icon-row">
                    {_icon_qty(_ROBOT_ICONS["engineer"], engineers, dim_zero=False)}
                    <span class="chip-label">Engineer</span>
                    {_icon_qty(_ROBOT_ICONS["forager"], foragers, dim_zero=False)}
                    <span class="chip-label">Forager</span>
                  </div>
                </div>

                <div class="detail-section">
                  <div class="detail-heading">Treasury</div>
                  <div class="treasury-large">{treasury_str}</div>
                  <div class="treasury-breakdown">
                    {"".join(f'<span>{rtype.capitalize()} × {robots_by_type.get(rtype,0)} @ {price} = {robots_by_type.get(rtype,0)*price:,}</span>' for rtype,price in robot_prices.items())}
                  </div>
                </div>

                <div class="detail-section">
                  <div class="detail-heading">Factory</div>
                  <table class="meta-table">
                    <tr><td>Factory ID</td><td class="mono small">{f.factory_id}</td></tr>
                    <tr><td>Generation</td><td>{run.run_generation}</td></tr>
                    <tr><td>Sim time</td><td>{sim_str}</td></tr>
                    <tr><td>Buf events</td><td>{f.buffer.total_events}</td></tr>
                    <tr><td>Expires in</td><td>{expires_str}</td></tr>
                    {f'<tr><td>Error</td><td class="err-text">{op_err}</td></tr>' if op_err else ''}
                  </table>
                </div>

              </div>
            </div>
          </td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="9" class="empty">No active factories — waiting for attendees to connect</td></tr>'

    total      = len(factories)
    active     = sum(1 for f in factories if not f.is_expired)
    enrolled   = len(enrollment_config.enrollments) if enrollment_config else 0
    debug_mode = factory_manager.debug_mode if factory_manager else False
    debug_js   = "true" if debug_mode else "false"
    debug_cls  = "dbg-on" if debug_mode else "dbg-off"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5" id="meta-refresh">
<title>HIVE Admin — Simulation Server</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
          font-size: 14px; background: #001141; color: #e8edf8; min-height: 100vh; }}

  /* ── Header ── */
  header {{ background: #000d2e; border-bottom: 1px solid #0f3a80;
            padding: 14px 24px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
  header h1 {{ font-size: 16px; font-weight: 600; color: #fff; letter-spacing: .04em; }}
  header .sub {{ font-size: 12px; color: #7a9cc8; }}
  header .url-hint {{ font-size: 11px; color: #3b82d4; background: #001a50; border: 1px solid #1e3a6e;
                      border-radius: 4px; padding: 2px 8px; margin-left: auto; }}

  /* ── KPI strip ── */
  .meta {{ margin: 16px 24px; display: flex; gap: 16px; flex-wrap: wrap; }}
  .kpi {{ background: #001f5c; border: 1px solid #0f3a80; border-radius: 6px;
           padding: 10px 18px; min-width: 120px; }}
  .kpi .label {{ font-size: 11px; color: #7a9cc8; text-transform: uppercase;
                  letter-spacing: .06em; margin-bottom: 4px; }}
  .kpi .value {{ font-size: 22px; font-weight: 700; color: #60a5fa; }}

  /* ── Table ── */
  .wrap {{ padding: 0 24px 32px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #001f5c; color: #7a9cc8; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: .05em;
        padding: 8px 10px; text-align: left; border-bottom: 1px solid #0f3a80; white-space: nowrap; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #0a2560; vertical-align: middle; }}
  .summary-row {{ cursor: pointer; }}
  .summary-row:hover td {{ background: #001a50; }}
  .expand-icon {{ color: #3b82d4; font-size: 14px; text-align: center; width: 24px; }}
  .summary-row.open .expand-icon {{ transform: rotate(90deg); display: inline-block; }}

  /* ── Detail card ── */
  .detail-row td {{ padding: 0; background: #000e35; }}
  .detail-card {{ padding: 16px 20px; border-top: 2px solid #0f3a80; }}
  .detail-grid {{ display: flex; flex-wrap: wrap; gap: 20px; }}
  .detail-section {{ background: #001a50; border: 1px solid #1e3a6e; border-radius: 6px;
                      padding: 12px 16px; min-width: 180px; flex: 1 1 180px; }}
  .detail-heading {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                      letter-spacing: .06em; color: #7a9cc8; margin-bottom: 8px; }}

  /* ── Icon chips ── */
  .icon-row {{ display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }}
  .icon-chip {{ display: inline-flex; align-items: center; gap: 4px;
                background: #002366; border: 1px solid #1e3a6e; border-radius: 4px;
                padding: 3px 7px 3px 5px; }}
  .icon-chip.dimmed {{ opacity: 0.35; }}
  .chip-num {{ font-weight: 700; font-size: 13px; color: #e8edf8; font-variant-numeric: tabular-nums; }}
  .chip-label {{ font-size: 11px; color: #7a9cc8; display: block; text-align: center; }}
  .res-chips {{ white-space: nowrap; }}

  /* ── Summary row layout ── */
  .sim-time {{ font-family: "SF Mono","Fira Code",monospace; font-size: 12px; color: #93c5fd; }}
  .treasury {{ font-size: 13px; font-weight: 600; color: #fde68a; }}
  .treasury-large {{ font-size: 22px; font-weight: 700; color: #fde68a; margin-bottom: 6px; }}
  .treasury-breakdown {{ font-size: 11px; color: #7a9cc8; display: flex; flex-direction: column; gap: 2px; }}

  /* ── Meta table inside detail ── */
  .meta-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .meta-table td {{ padding: 3px 0; color: #7a9cc8; }}
  .meta-table td:last-child {{ color: #e8edf8; padding-left: 8px; }}
  .err-text {{ color: #f87171 !important; }}

  /* ── Badges ── */
  .mono {{ font-family: "SF Mono","Fira Code",monospace; }}
  .small {{ font-size: 11px; }}
  .muted {{ color: #4a6fa8; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px;
             font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
  .status-running      {{ background: #14532d; color: #4ade80; }}
  .status-paused       {{ background: #713f12; color: #fbbf24; }}
  .status-stopped      {{ background: #1f2937; color: #9ca3af; }}
  .status-expired      {{ background: #3b1a1a; color: #f87171; }}
  .status-provisioning {{ background: #1e3a5f; color: #93c5fd; }}
  .status-error        {{ background: #4a1942; color: #f0abfc; }}
  .status-other        {{ background: #1e293b; color: #94a3b8; }}
  .empty  {{ color: #4a6fa8; text-align: center; padding: 32px; font-style: italic; }}
  footer  {{ text-align: center; color: #2a4a7a; font-size: 11px; padding: 16px;
              border-top: 1px solid #0a2560; margin-top: 8px; }}

  /* ── Debug toggle ── */
  .debug-wrap {{ display: flex; align-items: center; gap: 10px; margin-left: auto; }}
  .debug-label {{ font-size: 12px; color: #7a9cc8; font-weight: 600; letter-spacing: .03em; }}
  .debug-badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px;
                  text-transform: uppercase; letter-spacing: .04em; }}
  .debug-badge.dbg-on  {{ background: #14532d; color: #4ade80; }}
  .debug-badge.dbg-off {{ background: #1e293b; color: #6b7280; }}
  /* Toggle switch */
  .toggle {{ position: relative; display: inline-block; width: 40px; height: 22px; cursor: pointer; }}
  .toggle input {{ opacity: 0; width: 0; height: 0; }}
  .slider {{ position: absolute; inset: 0; background: #1e3a5f; border-radius: 22px;
             transition: background .2s; border: 1px solid #2a4a7a; }}
  .slider::before {{ content: ''; position: absolute; left: 3px; top: 3px;
                     width: 14px; height: 14px; border-radius: 50%;
                     background: #4a6fa8; transition: transform .2s, background .2s; }}
  .toggle input:checked + .slider {{ background: #166534; border-color: #14532d; }}
  .toggle input:checked + .slider::before {{ transform: translateX(18px); background: #4ade80; }}
</style>
</head>
<body>
<header>
  <h1>🐝 HIVE — Simulation Server Admin</h1>
  <span class="sub">Auto-refreshes every 5 s &nbsp;·&nbsp; {now_utc.strftime("%H:%M:%S UTC")}</span>
  <span class="url-hint">http://localhost:8080/admin</span>
  <div class="debug-wrap">
    <span class="debug-label">Debug inventory</span>
    <label class="toggle" title="When enabled, factory.state events carry ground-truth inventory so the attendee screen shows server values without Flink">
      <input type="checkbox" id="debug-toggle" {'checked' if debug_mode else ''} onchange="setDebugMode(this.checked)">
      <span class="slider"></span>
    </label>
    <span class="debug-badge {debug_cls}" id="debug-status">{'ON' if debug_mode else 'OFF'}</span>
  </div>
</header>
<div class="meta">
  <div class="kpi"><div class="label">Active factories</div><div class="value">{total}</div></div>
  <div class="kpi"><div class="label">Attendees online</div><div class="value">{active}/{enrolled}</div></div>
</div>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>Attendee</th>
      <th>Status</th>
      <th>Sim time</th>
      <th>Resources</th>
      <th>Robots</th>
      <th>Treasury</th>
      <th>Expires in</th>
      <th>Error</th>
      <th></th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
<footer>Hive Robotics Simulation Server &nbsp;·&nbsp; Serving on 0.0.0.0:8080, access via <strong>localhost:8080</strong></footer>
<script>
// ── Row expand/collapse ────────────────────────────────────────────────────
function toggleDetail(id) {{
  var row = document.getElementById(id);
  var summaryRow = row.previousElementSibling;
  if (row.style.display === 'none') {{
    row.style.display = '';
    summaryRow.classList.add('open');
  }} else {{
    row.style.display = 'none';
    summaryRow.classList.remove('open');
  }}
}}
// Re-open previously expanded rows after auto-refresh
(function() {{
  var openIds = [];
  try {{ openIds = JSON.parse(sessionStorage.getItem('hive-open') || '[]'); }} catch(e) {{}}
  openIds.forEach(function(id) {{
    var row = document.getElementById(id);
    if (row) {{
      row.style.display = '';
      var summaryRow = row.previousElementSibling;
      if (summaryRow) summaryRow.classList.add('open');
    }}
  }});
}})();
// Save open rows before unload (auto-refresh fires beforeunload)
window.addEventListener('beforeunload', function() {{
  var open = [];
  document.querySelectorAll('.detail-row').forEach(function(row) {{
    if (row.style.display !== 'none') open.push(row.id);
  }});
  try {{ sessionStorage.setItem('hive-open', JSON.stringify(open)); }} catch(e) {{}}
}});

// ── Debug mode toggle ──────────────────────────────────────────────────────
var _debugMode = {debug_js};

function setDebugMode(enabled) {{
  // Temporarily suppress auto-refresh while we POST so the page doesn't
  // reload mid-request and clobber the optimistic UI update.
  var metaRefresh = document.getElementById('meta-refresh');
  if (metaRefresh) metaRefresh.removeAttribute('content');

  _debugMode = enabled;
  _updateDebugUI(enabled);

  fetch('/admin/debug', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ enabled: enabled }}),
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    _updateDebugUI(data.debug_mode);
    // Re-enable auto-refresh
    if (metaRefresh) metaRefresh.setAttribute('content', '5');
  }})
  .catch(function() {{
    // On error revert optimistic update and restore refresh
    _debugMode = !enabled;
    _updateDebugUI(!enabled);
    document.getElementById('debug-toggle').checked = !enabled;
    if (metaRefresh) metaRefresh.setAttribute('content', '5');
  }});
}}

function _updateDebugUI(on) {{
  var badge = document.getElementById('debug-status');
  if (!badge) return;
  badge.textContent = on ? 'ON' : 'OFF';
  badge.className = 'debug-badge ' + (on ? 'dbg-on' : 'dbg-off');
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/admin/debug", response_class=JSONResponse, include_in_schema=False)
async def toggle_debug_mode(request: Request):
    """
    Toggle server-side debug mode on/off.
    No auth — admin-only endpoint, same trust level as /admin.
    Accepts optional JSON body: {"enabled": true|false}
    If no body (or missing key), toggles the current value.
    Returns the new state.
    """
    if factory_manager is None:
        raise HTTPException(status_code=503, detail="Factory manager not ready")

    try:
        body = await request.json()
        enabled = body.get("enabled")
    except Exception:
        enabled = None

    if enabled is None:
        factory_manager.debug_mode = not factory_manager.debug_mode
    else:
        factory_manager.debug_mode = bool(enabled)

    return JSONResponse({"debug_mode": factory_manager.debug_mode})


@app.get("/admin/debug", response_class=JSONResponse, include_in_schema=False)
async def get_debug_mode():
    """Return current debug mode state."""
    if factory_manager is None:
        raise HTTPException(status_code=503, detail="Factory manager not ready")
    return JSONResponse({"debug_mode": factory_manager.debug_mode})


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
