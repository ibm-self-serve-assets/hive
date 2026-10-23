"""Orders Calculator Package."""

try:
    from .calculator import (
        CapacityCalculator,
        SimulationConfiguration,
        OptimalExpansionSimulator,
        Order,
        OrderScheduleGenerator,
        StationSlot,
        UpgradeAction,
        UpgradeOptimizer,
        load_rules,
    )
except ImportError:
    from calculator import (  # type: ignore
        CapacityCalculator,
        SimulationConfiguration,
        OptimalExpansionSimulator,
        Order,
        OrderScheduleGenerator,
        StationSlot,
        UpgradeAction,
        UpgradeOptimizer,
        load_rules,
    )

__all__ = [
    "load_rules",
    "StationSlot",
    "SimulationConfiguration",
    "UpgradeAction",
    "Order",
    "CapacityCalculator",
    "UpgradeOptimizer",
    "OptimalExpansionSimulator",
    "OrderScheduleGenerator",
]
