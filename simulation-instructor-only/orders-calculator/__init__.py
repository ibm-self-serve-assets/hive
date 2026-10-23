"""Orders Calculator Package."""

try:
    from .calculator import (
        CapacityCalculator,
        FactoryConfiguration,
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
        FactoryConfiguration,
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
    "FactoryConfiguration",
    "UpgradeAction",
    "Order",
    "CapacityCalculator",
    "UpgradeOptimizer",
    "OptimalExpansionSimulator",
    "OrderScheduleGenerator",
]
