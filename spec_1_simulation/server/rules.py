import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class StationRecipe(BaseModel):
    station_id: str
    display_name: str
    inputs: Dict[str, int]
    output_id: str
    output_type: str  # "part" or "robot"
    duration_ms: int


class DeliveryConfig(BaseModel):
    interval_sim_seconds: int = 20
    resources: Dict[str, int]


class SimulationRules(BaseModel):
    resources: List[str]
    parts: List[str]
    delivery: DeliveryConfig
    stations: Dict[str, StationRecipe]
    station_order: List[str]


_cached_rules: Optional[SimulationRules] = None


def get_simulation_rules() -> SimulationRules:
    global _cached_rules
    if _cached_rules is None:
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "simulation_rules.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cached_rules = SimulationRules(**data)
    return _cached_rules
