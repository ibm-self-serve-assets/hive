import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel


class SimulationTimeConfig(BaseModel):
    max_sim_weeks: int = 2

    @property
    def max_sim_days(self) -> int:
        return self.max_sim_weeks * 7

    @property
    def max_sim_minutes(self) -> int:
        return self.max_sim_days * 24 * 60

    @property
    def max_sim_ms(self) -> int:
        return self.max_sim_minutes * 60_000


class StationMetadata(BaseModel):
    level: int
    cost_purchase: int
    cost_upgrade: int
    interval_sim_minutes: int


class RobotMetadata(BaseModel):
    type: str
    price_in_coins: int


class ResourceConfig(BaseModel):
    name: str
    level: int = 1
    quantity: int = 1
    interval_sim_minutes: Optional[int] = None

    @property
    def duration_ms(self) -> int:
        return (self.interval_sim_minutes or 10) * 60_000


class ManufacturingConfig(BaseModel):
    name: str                    # e.g. "structural_molding" — used as station_id
    output_type: str             # e.g. "chassis"
    level: int = 1
    inputs: Dict[str, int]
    interval_sim_minutes: Optional[int] = None

    @property
    def station_id(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def duration_ms(self) -> int:
        return (self.interval_sim_minutes or 10) * 60_000

    @property
    def kind(self) -> str:
        return "part"


class AssemblyConfig(BaseModel):
    name: str                    # e.g. "worker_assembly" — used as station_id
    output_type: str             # robot type, e.g. "engineer"
    level: int = 1
    inputs: Dict[str, int]
    interval_sim_minutes: Optional[int] = None

    @property
    def station_id(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def duration_ms(self) -> int:
        return (self.interval_sim_minutes or 10) * 60_000

    @property
    def kind(self) -> str:
        return "robot"


class SimulationRules(BaseModel):
    simulation_time: SimulationTimeConfig = SimulationTimeConfig()
    resources: List[ResourceConfig]
    parts: List[str]
    manufacturing: List[ManufacturingConfig]
    assembly: List[AssemblyConfig]
    station_metadata: List[StationMetadata] = []
    robot_metadata: List[RobotMetadata] = []

    def model_post_init(self, __context) -> None:
        meta_by_level = {m.level: m for m in self.station_metadata}
        for item in self.resources:
            if item.interval_sim_minutes is None and item.level in meta_by_level:
                item.interval_sim_minutes = meta_by_level[item.level].interval_sim_minutes
        for item in self.manufacturing:
            if item.interval_sim_minutes is None and item.level in meta_by_level:
                item.interval_sim_minutes = meta_by_level[item.level].interval_sim_minutes
        for item in self.assembly:
            if item.interval_sim_minutes is None and item.level in meta_by_level:
                item.interval_sim_minutes = meta_by_level[item.level].interval_sim_minutes

    @property
    def resource_names(self) -> List[str]:
        return [r.name for r in self.resources]

    @property
    def resource_map(self) -> Dict[str, ResourceConfig]:
        return {r.name: r for r in self.resources}

    @property
    def station_order(self) -> List[str]:
        """Manufacturing station IDs in definition order, followed by assembly station IDs."""
        return [m.station_id for m in self.manufacturing] + [a.station_id for a in self.assembly]

    def get_manufacturing(self, station_id: str) -> Optional[ManufacturingConfig]:
        for m in self.manufacturing:
            if m.station_id == station_id:
                return m
        return None

    def get_assembly(self, station_id: str) -> Optional[AssemblyConfig]:
        for a in self.assembly:
            if a.station_id == station_id:
                return a
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
