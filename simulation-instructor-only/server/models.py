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
    sim_time_minutes: int
    causation_id: Optional[str] = None
    payload: Dict[str, Any]


class FactoryInitializedPayload(BaseModel):
    operation_id: str
    attendee_id: str
    expires_at: str
    # Static station input recipes — keyed by station_id.
    # Published once so consumers know recipes without waiting for a job to start.
    station_recipes: Dict[str, Dict[str, int]] = Field(default_factory=dict)


class ConnectionTestPayload(BaseModel):
    operation_id: str
    probe: bool = True


class ResourceStartedPayload(BaseModel):
    job_id: str
    resource_id: str
    quantity: int


class ResourceCompletedPayload(BaseModel):
    job_id: str
    resource_id: str
    quantity: int


class ResourceBlockedPayload(BaseModel):
    # Placeholder: a resource supplier cannot deliver (e.g. broken equipment).
    resource_id: str
    reason: str


class JobStartedPayload(BaseModel):
    job_id: str
    station_id: str
    output_id: str
    inputs: Dict[str, int]


class PartProducedPayload(BaseModel):
    job_id: str
    station_id: str
    part_id: str
    quantity: int = 1


class AssemblyStartedPayload(BaseModel):
    job_id: str
    station_id: str
    output_id: str  # robot type being built: "engineer" or "forager"
    inputs: Dict[str, int]


class RobotAssembledPayload(BaseModel):
    job_id: str
    station_id: str
    output_id: str  # robot type completed: "engineer" or "forager"
    quantity: int = 1


class ManufacturingBlockedPayload(BaseModel):
    station_id: str
    missing_inputs: Dict[str, int]


class StationJobState(BaseModel):
    job_id: str
    output_id: str
    started_at_sim_ms: int
    completes_at_sim_ms: int
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
    last_robot_id: Optional[str] = None  # robot type of the latest completion


class ResourceDeliveryState(BaseModel):
    """Per-resource delivery countdown, included in every factory snapshot."""
    name: str
    interval_sim_ms: int              # full cycle length in sim-ms (internal)
    next_delivery_sim_time_ms: int    # absolute sim-ms when next delivery fires (internal)
    next_delivery_in_ms: int          # remaining sim-ms until next delivery (internal)
    quantity: int               # units delivered each cycle


class FactoryStatePayload(BaseModel):
    lifecycle_status: str  # paused, running, stopped, expired
    running: bool
    operational_error: Optional[OperationalError] = None
    resource_deliveries: List[ResourceDeliveryState] = Field(default_factory=list)
    resources: Dict[str, int]
    parts: Dict[str, int]
    stations: List[StationState]
    completed_robots: CompletedWorkersState
    last_applied_command_id: Optional[str] = None
