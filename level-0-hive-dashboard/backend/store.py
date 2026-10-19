"""
In-memory store for the basic connect-simulation dashboard.

Tracks only what the design comp needs:
  - sim_time_minutes    from any event envelope
  - factory lifecycle    from factory.state
  - completed counts     from *.completed event payloads
  - in-progress flags    from *.started / *.completed pairing
  - stream health
"""

import time
from typing import Dict, Optional, Any

from backend.models import EventEnvelope


# ── Resource label / icon mapping ────────────────────────────────────────────
RESOURCE_IDS = ["copper", "energy", "metals", "resin", "silicon"]

# Parts manufacturing stations
STATION_IDS = [
    "actuator_fabrication",
    "battery_assembly",
    "structural_molding",
    "electronics_assembly",
]

# Assembly stations and their robot output
ASSEMBLY_STATIONS = {
    "worker_assembly": "engineer",
    "forager_assembly": "forager",
}


class DashboardStore:
    def __init__(self) -> None:
        self.active_factory_id: Optional[str] = None
        self.server_epoch: Optional[str] = None

        # sim time — updated from every envelope
        self.latest_sim_time_minutes: int = 0
        self.run_generation: int = 0

        # lifecycle — from factory.state
        self.lifecycle_status: str = "paused"
        self.running: bool = False

        # stream health tracking
        self._last_event_mono: float = 0.0

        # Completed counts: resource_id / station_id / robot_id → int
        self.gathering_completed: Dict[str, int] = {r: 0 for r in RESOURCE_IDS}
        self.manufacturing_completed: Dict[str, int] = {s: 0 for s in STATION_IDS}
        self.assembly_completed: Dict[str, int] = {}  # output_id → count

        # Active jobs: tracks currently in-progress jobs per "slot"
        # gathering: resource_id → bool
        # manufacturing / assembly: station_id → bool
        self.gathering_active: Dict[str, bool] = {r: False for r in RESOURCE_IDS}
        self.manufacturing_active: Dict[str, bool] = {s: False for s in STATION_IDS}
        self.assembly_active: Dict[str, bool] = {}

        # Dedup
        self._seen_ids: Dict[str, None] = {}
        self._seen_max = 5000

    def reset(self) -> None:
        self.latest_sim_time_minutes = 0
        self.run_generation = 0
        self.lifecycle_status = "paused"
        self.running = False
        self.gathering_completed = {r: 0 for r in RESOURCE_IDS}
        self.manufacturing_completed = {s: 0 for s in STATION_IDS}
        self.assembly_completed = {}
        self.gathering_active = {r: False for r in RESOURCE_IDS}
        self.manufacturing_active = {s: False for s in STATION_IDS}
        self.assembly_active = {}
        self._seen_ids.clear()

    def ingest(self, env: EventEnvelope) -> bool:
        """Returns True if something changed."""
        # Skip probes
        if env.event_type == "connection.test":
            return False

        # Factory identity guard
        if self.active_factory_id and env.factory_id != self.active_factory_id:
            return False
        if not self.active_factory_id and self.server_epoch and env.server_epoch != self.server_epoch:
            return False

        # Dedup
        if env.event_id in self._seen_ids:
            return False
        self._seen_ids[env.event_id] = None
        if len(self._seen_ids) > self._seen_max:
            # evict oldest
            oldest = next(iter(self._seen_ids))
            del self._seen_ids[oldest]

        # Always advance sim time and record activity
        if env.run_generation > self.run_generation:
            self.run_generation = env.run_generation
            self.latest_sim_time_minutes = env.sim_time_minutes
            self.gathering_completed = {r: 0 for r in RESOURCE_IDS}
            self.manufacturing_completed = {s: 0 for s in STATION_IDS}
            self.assembly_completed = {}
        elif env.sim_time_minutes > self.latest_sim_time_minutes:
            self.latest_sim_time_minutes = env.sim_time_minutes
        self._last_event_mono = time.monotonic()

        et = env.event_type
        p = env.payload

        if et == "factory.state":
            self.lifecycle_status = p.get("lifecycle_status", self.lifecycle_status)
            self.running = p.get("running", self.running)
            return True

        if et == "gathering.started":
            rid = p.get("resource_id")
            if rid:
                self.gathering_active[rid] = True
            return True

        if et == "gathering.completed":
            rid = p.get("resource_id")
            if rid:
                self.gathering_active[rid] = False
                self.gathering_completed[rid] = self.gathering_completed.get(rid, 0) + 1
            return True

        if et == "manufacturing.started":
            sid = p.get("station_id")
            if sid:
                self.manufacturing_active[sid] = True
            return True

        if et == "manufacturing.completed":
            sid = p.get("station_id")
            if sid:
                self.manufacturing_active[sid] = False
                self.manufacturing_completed[sid] = self.manufacturing_completed.get(sid, 0) + 1
            return True

        if et == "assembly.started":
            sid = p.get("station_id")
            if sid:
                self.assembly_active[sid] = True
            return True

        if et == "assembly.completed":
            sid = p.get("station_id")
            output_id = p.get("output_id", sid)
            if sid:
                self.assembly_active[sid] = False
            if output_id:
                self.assembly_completed[output_id] = self.assembly_completed.get(output_id, 0) + 1
            return True

        # factory.initialized, blocked events, etc. — still counted as activity
        return True

    def get_stream_health(self) -> str:
        if self._last_event_mono == 0.0:
            return "awaiting_events"
        age = time.monotonic() - self._last_event_mono
        return "live" if age <= 3.0 else "stale"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "stream_health": self.get_stream_health(),
            "active_factory_id": self.active_factory_id,
            "run_generation": self.run_generation,
            "sim_time_minutes": self.latest_sim_time_minutes,
            "lifecycle_status": self.lifecycle_status,
            "running": self.running,
            "gathering_completed": dict(self.gathering_completed),
            "manufacturing_completed": dict(self.manufacturing_completed),
            "assembly_completed": dict(self.assembly_completed),
            "gathering_active": dict(self.gathering_active),
            "manufacturing_active": dict(self.manufacturing_active),
            "assembly_active": dict(self.assembly_active),
        }
