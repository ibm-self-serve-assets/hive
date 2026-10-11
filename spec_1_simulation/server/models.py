from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class ResourceQuantities(BaseModel):
    resin: int = 0
    silicon: int = 0
    metals: int = 0
    copper: int = 0
    energy: int = 0


class PartQuantities(BaseModel):
    chassis: int = 0
    electronics: int = 0
    actuator: int = 0
    battery: int = 0


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


class FactoryInitializedPayload(BaseModel):
    operation_id: str
    attendee_id: str
    topic_prefix: str
    expires_at: str


class ConnectionTestPayload(BaseModel):
    operation_id: str
    probe: bool = True


class ResourceDeliveredPayload(BaseModel):
    delivery_id: str
    delivery_sequence: int
    resources: Dict[str, int]


class JobStartedPayload(BaseModel):
    job_id: str
    station_id: str
    output_id: str
    inputs: Dict[str, int]
    duration_ms: int


class PartProducedPayload(BaseModel):
    job_id: str
    station_id: str
    part_id: str
    quantity: int = 1


class AssemblyStartedPayload(BaseModel):
    job_id: str
    station_id: str
    robot_type: str
    inputs: Dict[str, int]
    duration_ms: int


class RobotAssembledPayload(BaseModel):
    job_id: str
    robot_id: str
    robot_type: str = "worker"
    display_number: int
    quantity: int = 1


class ManufacturingBlockedPayload(BaseModel):
    station_id: str
    missing_inputs: Dict[str, int]


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
    speed: int
    next_delivery_sim_time_ms: int
    next_delivery_in_ms: int
    resources: Dict[str, int]
    parts: Dict[str, int]
    stations: List[StationState]
    completed_workers: CompletedWorkersState
    last_applied_command_id: Optional[str] = None
