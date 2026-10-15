import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel


class ResourceConfig(BaseModel):
    name: str
    interval_sim_seconds: int
    quantity: int


class ManufacturingConfig(BaseModel):
    name: str                    # e.g. "structural_molding" — used as station_id
    output_id: str               # e.g. "chassis"
    interval_sim_seconds: int    # duration of one production cycle in sim-seconds
    inputs: Dict[str, int]

    @property
    def station_id(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def duration_ms(self) -> int:
        return self.interval_sim_seconds * 1000

    @property
    def output_type(self) -> str:
        return "part"


class RobotConfig(BaseModel):
    name: str
    duration_ms: int


class WorkerAssemblyConfig(BaseModel):
    name: str
    inputs: Dict[str, int]
    robots: List[RobotConfig]

    @property
    def station_id(self) -> str:
        return "worker_assembly"

    @property
    def output_type(self) -> str:
        return "robot"


class ForagerAssemblyConfig(WorkerAssemblyConfig):
    """Placeholder: declared in the rules but not scheduled by the simulation yet."""
    placeholder: bool = True

    @property
    def station_id(self) -> str:
        return "forager_assembly"


class SimulationRules(BaseModel):
    resources: List[ResourceConfig]
    parts: List[str]
    manufacturing: List[ManufacturingConfig]
    worker_assembly: WorkerAssemblyConfig
    forager_assembly: Optional[ForagerAssemblyConfig] = None

    @property
    def resource_names(self) -> List[str]:
        return [r.name for r in self.resources]

    @property
    def resource_map(self) -> Dict[str, ResourceConfig]:
        return {r.name: r for r in self.resources}

    @property
    def station_order(self) -> List[str]:
        """Manufacturing station IDs in definition order, followed by worker_assembly."""
        return [m.station_id for m in self.manufacturing] + [self.worker_assembly.station_id]

    def get_manufacturing(self, station_id: str) -> Optional[ManufacturingConfig]:
        for m in self.manufacturing:
            if m.station_id == station_id:
                return m
        return None


_cached_rules: Optional[SimulationRules] = None


def get_simulation_rules() -> SimulationRules:
    global _cached_rules
    if _cached_rules is None:
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "simulation_rules.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cached_rules = SimulationRules(**data)
    return _cached_rules
