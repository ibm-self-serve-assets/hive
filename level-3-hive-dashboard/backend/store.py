import collections
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from backend.models import FactoryStatePayload, ActivityEvent, EventEnvelope


class InMemProjectionStore:
    def __init__(self, max_activity_events: int = 1000):
        self.max_activity_events = max_activity_events
        self.active_factory_id: Optional[str] = None
        self.server_epoch: Optional[str] = None
        self.run_generation: int = 0
        self.state_revision: int = -1
        self.latest_event_sequence: int = 0
        self.latest_sim_time_minutes: int = 0

        self.latest_snapshot: Optional[FactoryStatePayload] = None
        self.latest_snapshot_occurred_at: Optional[str] = None
        self.latest_snapshot_received_at_mono: float = 0.0

        # Ring buffer for activity events
        self.activity_events: collections.deque[ActivityEvent] = collections.deque(maxlen=max_activity_events)

        # LRU-evicting dedup set: OrderedDict used as ordered set (value=None).
        # Evicts the oldest entry when the limit is reached, so we never clear
        # the entire set (which would cause old events to look new and flood the deque).
        self._seen_ids: collections.OrderedDict = collections.OrderedDict()
        self._seen_ids_max: int = 5000

        # Command receipts
        self.latest_command_receipt: Optional[Dict[str, Any]] = None

        # Station input recipes — populated once from factory.initialized payload.
        # Keyed by station_id; value is resource/part → quantity dict.
        self.station_recipes: Dict[str, Dict[str, int]] = {}

    def reset_view(self, factory_id: Optional[str], server_epoch: Optional[str]):
        self.active_factory_id = factory_id
        self.server_epoch = server_epoch
        self.run_generation = 0
        self.state_revision = -1
        self.latest_event_sequence = 0
        self.latest_sim_time_minutes = 0
        self.latest_snapshot = None
        self.latest_snapshot_occurred_at = None
        self.latest_snapshot_received_at_mono = 0.0
        self.activity_events.clear()
        self._seen_ids.clear()
        self.latest_command_receipt = None
        self.station_recipes = {}

    def ingest_envelope(self, env: EventEnvelope) -> bool:
        """
        Validates and ingests an incoming event envelope into memory.
        Returns True if state or activity updated, False otherwise.
        """
        # Validate factory_id & server_epoch
        if self.active_factory_id and env.factory_id != self.active_factory_id:
            return False
        if self.server_epoch and env.server_epoch != self.server_epoch:
            return False

        # Ignore probe connection.test
        if env.event_type == "connection.test":
            return False

        # Duplicate ID check — LRU-evicting to avoid a full clear() that would
        # cause every event to look new and flood the activity deque with old data.
        if env.event_id in self._seen_ids:
            self._seen_ids.move_to_end(env.event_id)  # refresh recency
            return False
        self._seen_ids[env.event_id] = None
        if len(self._seen_ids) > self._seen_ids_max:
            self._seen_ids.popitem(last=False)  # evict oldest

        # Absorb station recipes from factory.initialized — fires once, never again
        if env.event_type == "factory.initialized":
            recipes = env.payload.get("station_recipes", {})
            if recipes:
                self.station_recipes = recipes
            return True

        # Handle factory.state snapshot
        if env.event_type == "factory.state":
            # Compare by (run_generation, state_revision, event_sequence)
            is_newer = False
            if env.run_generation > self.run_generation:
                is_newer = True
            elif env.run_generation == self.run_generation:
                if env.state_revision > self.state_revision:
                    is_newer = True
                elif env.state_revision == self.state_revision and env.event_sequence > self.latest_event_sequence:
                    is_newer = True

            if is_newer:
                self.run_generation = env.run_generation
                self.state_revision = env.state_revision
                self.latest_event_sequence = env.event_sequence
                self.latest_sim_time_minutes = env.sim_time_minutes
                self.latest_snapshot = FactoryStatePayload(**env.payload)
                self.latest_snapshot_occurred_at = env.occurred_at
                self.latest_snapshot_received_at_mono = time.monotonic()
                return True
            return False

        # Handle activity log events
        summary = self._format_summary(env.event_type, env.payload)
        act = ActivityEvent(
            event_id=env.event_id,
            event_type=env.event_type,
            occurred_at=env.occurred_at,
            sim_time_minutes=env.sim_time_minutes,
            run_generation=env.run_generation,
            event_sequence=env.event_sequence,
            summary=summary,
            payload=env.payload,
        )
        self.activity_events.appendleft(act)
        return True

    def _format_summary(self, event_type: str, payload: Dict[str, Any]) -> str:
        if event_type == "gathering.started":
            return f"{payload.get('resource_id', '')} delivery started (+{payload.get('quantity', 0)})"
        elif event_type == "gathering.completed":
            return f"{payload.get('resource_id', '')} delivered (+{payload.get('quantity', 0)})"
        elif event_type == "gathering.blocked":
            return f"{payload.get('resource_id', '')} blocked: {payload.get('reason', '')}"
        elif event_type == "manufacturing.started":
            st = payload.get("station_id", "")
            out = payload.get("output_id", "")
            dur = payload.get("duration_ms", 0) // 1000
            return f"{st.replace('_', ' ').title()} → {out} ({dur}s)"
        elif event_type == "manufacturing.completed":
            st = payload.get("station_id", "")
            part = payload.get("part_id", "")
            return f"{st.replace('_', ' ').title()}: {part} +1"
        elif event_type == "manufacturing.blocked":
            st = payload.get("station_id", "")
            missing = payload.get("missing_inputs", {})
            items = ", ".join(f"{k}: need {v}" for k, v in missing.items())
            return f"{st.replace('_', ' ').title()} blocked: {items}"
        elif event_type == "assembly.completed":
            robot = payload.get("output_id", "")
            return f"{robot.title()} assembled"
        elif event_type == "assembly.blocked":
            missing = payload.get("missing_inputs", {})
            items = ", ".join(f"{k}: need {v}" for k, v in missing.items())
            return f"Assembly blocked: {items}"
        return f"{event_type}"

    def get_stream_health(self) -> str:
        if self.latest_snapshot is None:
            return "awaiting_events"
        now = time.monotonic()
        age = now - self.latest_snapshot_received_at_mono
        if age > 3.0:
            return "stale"
        return "live"

    def get_observed_state(self) -> Dict[str, Any]:
        return {
            "stream_health": self.get_stream_health(),
            "active_factory_id": self.active_factory_id,
            "server_epoch": self.server_epoch,
            "run_generation": self.run_generation,
            "state_revision": self.state_revision,
            "latest_event_sequence": self.latest_event_sequence,
            "snapshot_occurred_at": self.latest_snapshot_occurred_at,
            "sim_time_minutes": self.latest_sim_time_minutes,
            "snapshot": self.latest_snapshot.model_dump() if self.latest_snapshot else None,
            "latest_command_receipt": self.latest_command_receipt,
            "station_recipes": self.station_recipes,
        }

    def get_activity_log(self) -> List[Dict[str, Any]]:
        return [ev.model_dump() for ev in self.activity_events]
