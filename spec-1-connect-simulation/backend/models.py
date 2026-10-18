from typing import Dict, Optional, Any
from pydantic import BaseModel


class EventEnvelope(BaseModel):
    """Minimal envelope — only the fields this dashboard needs."""
    event_id: str
    event_type: str
    factory_id: str
    server_epoch: str
    run_generation: int
    event_sequence: int
    sim_time_minutes: int
    occurred_at: str
    payload: Dict[str, Any]

    # Optional envelope fields present on some events
    state_revision: Optional[int] = None
    run_id: Optional[str] = None
    schema_version: Optional[int] = None
    causation_id: Optional[str] = None
