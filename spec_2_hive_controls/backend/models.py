from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class StationJobState(BaseModel):
    job_id: str
    output_id: str
    started_at_sim_ms: int
    completes_at_sim_ms: int
    duration_ms: int
    consumed_inputs: Dict[str, int]
    progress_percent: float


class StationState(BaseModel):
    station_id: str
    status: str  # idle, working, waiting_for_resources, waiting_for_parts
    missing_inputs: Dict[str, int] = Field(default_factory=dict)
    job: Optional[StationJobState] = None


class OperationalError(BaseModel):
    code: str
    message: str


class CompletedWorkersState(BaseModel):
    count: int = 0
    last_robot_id: Optional[str] = None


class FactoryStatePayload(BaseModel):
    lifecycle_status: str  # paused, running, stopped, expired
    running: bool
    operational_error: Optional[OperationalError] = None
    speed: int = 1
    next_delivery_sim_time_ms: int = 0
    next_delivery_in_ms: int = 0
    resources: Dict[str, int] = Field(default_factory=dict)
    parts: Dict[str, int] = Field(default_factory=dict)
    stations: List[StationState] = Field(default_factory=list)
    completed_workers: CompletedWorkersState = Field(default_factory=CompletedWorkersState)
    last_applied_command_id: Optional[str] = None


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    schema_version: int = 1
    factory_id: str
    server_epoch: str
    run_id: str
    run_generation: int
    event_sequence: int
    state_revision: int
    occurred_at: str
    sim_time_ms: int
    causation_id: Optional[str] = None
    payload: Dict[str, Any]


class ActivityEvent(BaseModel):
    event_id: str
    event_type: str
    occurred_at: str
    sim_time_ms: int
    run_generation: int
    event_sequence: int
    summary: str
    payload: Dict[str, Any]
