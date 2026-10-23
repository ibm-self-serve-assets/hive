"""Orders Calculator & Simulation Capacity Planning Engine.

Calculates realistic simulation throughput, optimal upgrade trajectories,
and grounded order generation based on simulation_rules.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_rules(rules_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load simulation rules from schemas/simulation_rules.json."""
    if rules_path is None:
        rules_path = (
            Path(__file__).resolve().parent.parent / "schemas" / "simulation_rules.json"
        )
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class StationSlot:
    id: int
    level: int


@dataclass
class SimulationConfiguration:
    resources: Dict[str, List[StationSlot]] = field(default_simulation=dict)
    manufacturing: Dict[str, List[StationSlot]] = field(default_simulation=dict)
    assembly: Dict[str, List[StationSlot]] = field(default_simulation=dict)

    def clone(self) -> SimulationConfiguration:
        return SimulationConfiguration(
            resources={
                k: [StationSlot(s.id, s.level) for s in v]
                for k, v in self.resources.items()
            },
            manufacturing={
                k: [StationSlot(s.id, s.level) for s in v]
                for k, v in self.manufacturing.items()
            },
            assembly={
                k: [StationSlot(s.id, s.level) for s in v]
                for k, v in self.assembly.items()
            },
        )


@dataclass
class UpgradeAction:
    category: str  # "resource", "manufacturing", "assembly"
    station_key: str
    action_type: str  # "upgrade" or "add_slot"
    target_slot_index: Optional[int]
    cost: int
    from_level: int
    to_level: int
    marginal_rate_increase_per_hour: float = 0.0
    roi: float = 0.0  # rate increase per 100 coins


@dataclass
class Order:
    order_id: str
    robot_type: str  # "engineer", "forager", "mixed"
    quantity_engineer: int
    quantity_forager: int
    total_quantity: int
    reward_coins: int
    created_at_sim_minute: int
    deadline_sim_minute: int
    difficulty: str  # "standard", "optimal", "challenging"


class CapacityCalculator:
    """Calculates BOM, station throughputs, and system bottlenecks."""

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        self.rules = rules or load_rules()
        self.meta_by_level: Dict[int, Dict[str, Any]] = {
            m["level"]: m for m in self.rules.get("station_metadata", [])
        }
        self.robot_prices: Dict[str, int] = {
            r["type"]: r["price_in_coins"] for r in self.rules.get("robot_metadata", [])
        }
        self.max_slots = 3
        self.max_sim_weeks = self.rules.get("simulation_time", {}).get(
            "max_sim_weeks", 2
        )
        self.max_sim_days = self.max_sim_weeks * 7
        self.max_sim_minutes = self.max_sim_days * 24 * 60

    def get_initial_configuration(self) -> SimulationConfiguration:
        config = SimulationConfiguration()
        for r in self.rules.get("resources", []):
            config.resources[r["name"]] = [StationSlot(id=1, level=r.get("level", 1))]
        for m in self.rules.get("manufacturing", []):
            station_key = m["name"].lower().replace(" ", "_")
            config.manufacturing[station_key] = [
                StationSlot(id=1, level=m.get("level", 1))
            ]
        for a in self.rules.get("assembly", []):
            station_key = a["name"].lower().replace(" ", "_")
            config.assembly[station_key] = [
                StationSlot(id=1, level=a.get("level", 1))
            ]
        return config

    def get_parts_per_robot(self, robot_type: str = "engineer") -> Dict[str, int]:
        for asm in self.rules.get("assembly", []):
            if asm.get("output_type") == robot_type or asm.get("name") == f"{robot_type}_assembly":
                return dict(asm.get("inputs", {}))
        # fallback default
        return {"chassis": 1, "electronics": 3, "battery": 2, "actuator": 8}

    def get_resources_per_part(self) -> Dict[str, Dict[str, int]]:
        res_map: Dict[str, Dict[str, int]] = {}
        for m in self.rules.get("manufacturing", []):
            part = m.get("output_type")
            res_map[part] = dict(m.get("inputs", {}))
        return res_map

    def get_raw_resources_per_robot(self, robot_type: str = "engineer") -> Dict[str, int]:
        parts_req = self.get_parts_per_robot(robot_type)
        part_inputs = self.get_resources_per_part()
        raw_totals: Dict[str, int] = {}
        for part, count in parts_req.items():
            inputs = part_inputs.get(part, {})
            for res, qty in inputs.items():
                raw_totals[res] = raw_totals.get(res, 0) + qty * count
        return raw_totals

    def get_interval_minutes(self, level: int) -> int:
        return self.meta_by_level.get(level, {}).get("interval_sim_minutes", 10)

    def get_upgrade_cost(self, current_level: int) -> int:
        return self.meta_by_level.get(current_level, {}).get("cost_upgrade", -1)

    def get_purchase_cost(self, level: int = 1) -> int:
        return self.meta_by_level.get(level, {}).get("cost_purchase", 100)

    def calculate_resource_rate_per_minute(
        self, slots: List[StationSlot], resource_name: str
    ) -> float:
        rate = 0.0
        for slot in slots:
            interval = self.get_interval_minutes(slot.level)
            rate += 1.0 / interval
        return rate

    def calculate_part_rate_per_minute(
        self, slots: List[StationSlot], part_name: str
    ) -> float:
        rate = 0.0
        for slot in slots:
            interval = self.get_interval_minutes(slot.level)
            rate += 1.0 / interval
        return rate

    def calculate_assembly_rate_per_minute(
        self, slots: List[StationSlot], station_key: str
    ) -> float:
        rate = 0.0
        for slot in slots:
            interval = self.get_interval_minutes(slot.level)
            rate += 1.0 / interval
        return rate

    def analyze_throughput(
        self, config: SimulationConfiguration
    ) -> Dict[str, Any]:
        """Calculates theoretical steady-state throughput and identifies bottlenecks."""
        raw_bom = self.get_raw_resources_per_robot("engineer")
        parts_bom = self.get_parts_per_robot("engineer")

        # 1. Resource limits in robots/minute
        res_limits: Dict[str, float] = {}
        for res_name, bom_qty in raw_bom.items():
            slots = config.resources.get(res_name, [])
            res_rate = self.calculate_resource_rate_per_minute(slots, res_name)
            res_limits[res_name] = res_rate / bom_qty if bom_qty > 0 else float("inf")

        # 2. Manufacturing limits in robots/minute
        mfg_limits: Dict[str, float] = {}
        mfg_map = {
            m["output_type"]: m["name"].lower().replace(" ", "_")
            for m in self.rules.get("manufacturing", [])
        }
        for part_name, bom_qty in parts_bom.items():
            st_key = mfg_map.get(part_name, part_name)
            slots = config.manufacturing.get(st_key, [])
            part_rate = self.calculate_part_rate_per_minute(slots, part_name)
            mfg_limits[part_name] = part_rate / bom_qty if bom_qty > 0 else float("inf")

        # 3. Assembly limits (total across worker and forager assembly)
        total_assembly_rate = 0.0
        for st_key, slots in config.assembly.items():
            total_assembly_rate += self.calculate_assembly_rate_per_minute(slots, st_key)

        # 4. Find global bottleneck
        all_limits: Dict[str, Tuple[str, float]] = {}
        for r, limit in res_limits.items():
            all_limits[f"Resource: {r}"] = ("resource", limit)
        for p, limit in mfg_limits.items():
            all_limits[f"Mfg: {p}"] = ("manufacturing", limit)
        all_limits["Assembly Lines"] = ("assembly", total_assembly_rate)

        bottleneck_name = min(all_limits.keys(), key=lambda k: all_limits[k][1])
        bottleneck_type, bottleneck_rate_per_min = all_limits[bottleneck_name]
        max_robots_per_hour = bottleneck_rate_per_min * 60.0
        max_robots_per_day = max_robots_per_hour * 24.0

        return {
            "max_robots_per_minute": bottleneck_rate_per_min,
            "max_robots_per_hour": max_robots_per_hour,
            "max_robots_per_day": max_robots_per_day,
            "bottleneck_name": bottleneck_name,
            "bottleneck_type": bottleneck_type,
            "resource_limits_per_hr": {k: v * 60.0 for k, v in res_limits.items()},
            "mfg_limits_per_hr": {k: v * 60.0 for k, v in mfg_limits.items()},
            "assembly_limit_per_hr": total_assembly_rate * 60.0,
        }


class UpgradeOptimizer:
    """Evaluates potential upgrades and returns prioritized actions based on ROI."""

    def __init__(self, calculator: CapacityCalculator):
        self.calc = calculator

    def get_candidate_actions(
        self, config: SimulationConfiguration, available_coins: int
    ) -> List[UpgradeAction]:
        current_analysis = self.calc.analyze_throughput(config)
        curr_rate_hr = current_analysis["max_robots_per_hour"]
        candidates: List[UpgradeAction] = []

        # Resources:
        for r_name, slots in config.resources.items():
            # Upgrades
            for idx, slot in enumerate(slots):
                if slot.level < 3:
                    cost = self.calc.get_upgrade_cost(slot.level)
                    if cost > 0:
                        temp_config = config.clone()
                        temp_config.resources[r_name][idx].level += 1
                        new_analysis = self.calc.analyze_throughput(temp_config)
                        new_rate_hr = new_analysis["max_robots_per_hour"]
                        gain = new_rate_hr - curr_rate_hr
                        roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                        candidates.append(
                            UpgradeAction(
                                category="resource",
                                station_key=r_name,
                                action_type="upgrade",
                                target_slot_index=idx,
                                cost=cost,
                                from_level=slot.level,
                                to_level=slot.level + 1,
                                marginal_rate_increase_per_hour=gain,
                                roi=roi,
                            )
                        )
            # Add slot
            if len(slots) < self.calc.max_slots:
                cost = self.calc.get_purchase_cost(1)
                temp_config = config.clone()
                temp_config.resources[r_name].append(
                    StationSlot(id=len(slots) + 1, level=1)
                )
                new_analysis = self.calc.analyze_throughput(temp_config)
                gain = new_analysis["max_robots_per_hour"] - curr_rate_hr
                roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                candidates.append(
                    UpgradeAction(
                        category="resource",
                        station_key=r_name,
                        action_type="add_slot",
                        target_slot_index=None,
                        cost=cost,
                        from_level=0,
                        to_level=1,
                        marginal_rate_increase_per_hour=gain,
                        roi=roi,
                    )
                )

        # Manufacturing:
        for m_key, slots in config.manufacturing.items():
            for idx, slot in enumerate(slots):
                if slot.level < 3:
                    cost = self.calc.get_upgrade_cost(slot.level)
                    if cost > 0:
                        temp_config = config.clone()
                        temp_config.manufacturing[m_key][idx].level += 1
                        new_analysis = self.calc.analyze_throughput(temp_config)
                        gain = new_analysis["max_robots_per_hour"] - curr_rate_hr
                        roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                        candidates.append(
                            UpgradeAction(
                                category="manufacturing",
                                station_key=m_key,
                                action_type="upgrade",
                                target_slot_index=idx,
                                cost=cost,
                                from_level=slot.level,
                                to_level=slot.level + 1,
                                marginal_rate_increase_per_hour=gain,
                                roi=roi,
                            )
                        )
            if len(slots) < self.calc.max_slots:
                cost = self.calc.get_purchase_cost(1)
                temp_config = config.clone()
                temp_config.manufacturing[m_key].append(
                    StationSlot(id=len(slots) + 1, level=1)
                )
                new_analysis = self.calc.analyze_throughput(temp_config)
                gain = new_analysis["max_robots_per_hour"] - curr_rate_hr
                roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                candidates.append(
                    UpgradeAction(
                        category="manufacturing",
                        station_key=m_key,
                        action_type="add_slot",
                        target_slot_index=None,
                        cost=cost,
                        from_level=0,
                        to_level=1,
                        marginal_rate_increase_per_hour=gain,
                        roi=roi,
                    )
                )

        # Assembly:
        for a_key, slots in config.assembly.items():
            for idx, slot in enumerate(slots):
                if slot.level < 3:
                    cost = self.calc.get_upgrade_cost(slot.level)
                    if cost > 0:
                        temp_config = config.clone()
                        temp_config.assembly[a_key][idx].level += 1
                        new_analysis = self.calc.analyze_throughput(temp_config)
                        gain = new_analysis["max_robots_per_hour"] - curr_rate_hr
                        roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                        candidates.append(
                            UpgradeAction(
                                category="assembly",
                                station_key=a_key,
                                action_type="upgrade",
                                target_slot_index=idx,
                                cost=cost,
                                from_level=slot.level,
                                to_level=slot.level + 1,
                                marginal_rate_increase_per_hour=gain,
                                roi=roi,
                            )
                        )
            if len(slots) < self.calc.max_slots:
                cost = self.calc.get_purchase_cost(1)
                temp_config = config.clone()
                temp_config.assembly[a_key].append(
                    StationSlot(id=len(slots) + 1, level=1)
                )
                new_analysis = self.calc.analyze_throughput(temp_config)
                gain = new_analysis["max_robots_per_hour"] - curr_rate_hr
                roi = (gain / cost) * 100.0 if cost > 0 else 0.0
                candidates.append(
                    UpgradeAction(
                        category="assembly",
                        station_key=a_key,
                        action_type="add_slot",
                        target_slot_index=None,
                        cost=cost,
                        from_level=0,
                        to_level=1,
                        marginal_rate_increase_per_hour=gain,
                        roi=roi,
                    )
                )

        # If no single action yields a strict global increase (e.g. multiple tied constraints),
        # score actions based on relieving the tightest individual constraints (shadow price)
        all_limits = {
            **current_analysis["resource_limits_per_hr"],
            **current_analysis["mfg_limits_per_hr"],
            "assembly": current_analysis["assembly_limit_per_hr"],
        }
        min_limit = current_analysis["max_robots_per_hour"]

        for cand in candidates:
            cand_limit_name = cand.station_key
            if cand.category == "manufacturing":
                for m in self.calc.rules.get("manufacturing", []):
                    if m["name"].lower().replace(" ", "_") == cand.station_key:
                        cand_limit_name = m.get("output_type", cand.station_key)
            elif cand.category == "assembly":
                cand_limit_name = "assembly"

            curr_st_limit = all_limits.get(cand_limit_name, min_limit)
            
            # If the candidate was a binding or near-binding constraint
            if curr_st_limit <= min_limit * 1.05:
                if cand.action_type == "upgrade":
                    old_rate = 60.0 / self.calc.get_interval_minutes(cand.from_level)
                    new_rate = 60.0 / self.calc.get_interval_minutes(cand.to_level)
                    delta_rate = new_rate - old_rate
                else:  # add_slot
                    delta_rate = 60.0 / self.calc.get_interval_minutes(1)

                if cand.category == "resource":
                    bom_qty = self.calc.get_raw_resources_per_robot("engineer").get(cand.station_key, 1)
                    capacity_lift = delta_rate / bom_qty
                elif cand.category == "manufacturing":
                    bom_qty = self.calc.get_parts_per_robot("engineer").get(cand_limit_name, 1)
                    capacity_lift = delta_rate / bom_qty
                else:
                    capacity_lift = delta_rate

                if cand.marginal_rate_increase_per_hour == 0.0:
                    cand.marginal_rate_increase_per_hour = capacity_lift * 0.5
                    cand.roi = (cand.marginal_rate_increase_per_hour / cand.cost) * 100.0

        # Sort by ROI descending, then by marginal rate gain descending, then by cost ascending
        candidates.sort(
            key=lambda a: (a.roi, a.marginal_rate_increase_per_hour, -a.cost),
            reverse=True,
        )
        return candidates

    def apply_action(
        self, config: SimulationConfiguration, action: UpgradeAction
    ) -> None:
        attr_name = "resources" if action.category == "resource" else action.category
        target_dict = getattr(config, attr_name)
        if action.action_type == "upgrade":
            target_dict[action.station_key][action.target_slot_index].level = action.to_level
        elif action.action_type == "add_slot":
            slots = target_dict[action.station_key]
            slots.append(StationSlot(id=len(slots) + 1, level=action.to_level))


class OptimalExpansionSimulator:
    """Simulates simulation expansion and production over the full simulation horizon."""

    def __init__(self, calculator: CapacityCalculator):
        self.calc = calculator
        self.optimizer = UpgradeOptimizer(calculator)

    def simulate_expansion(
        self, total_sim_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Simulates step-by-step simulation growth with greedy optimal upgrade purchases."""
        sim_limit = total_sim_minutes or self.calc.max_sim_minutes
        config = self.calc.get_initial_configuration()

        sim_minute = 0.0
        coins = 0
        total_robots_produced = 0
        coin_price_per_robot = self.calc.robot_prices.get("engineer", 250)

        history_upgrades: List[Dict[str, Any]] = []
        production_curve: List[Dict[str, Any]] = []

        # Record initial point
        curr_analysis = self.calc.analyze_throughput(config)
        production_curve.append(
            {
                "sim_minute": 0,
                "sim_day": 0.0,
                "cumulative_robots": 0,
                "coins": 0,
                "robots_per_hour": curr_analysis["max_robots_per_hour"],
                "bottleneck": curr_analysis["bottleneck_name"],
            }
        )

        fractional_robot_progress = 0.0

        while sim_minute < sim_limit:
            curr_analysis = self.calc.analyze_throughput(config)
            curr_rate_per_min = curr_analysis["max_robots_per_minute"]

            # Time needed to produce 1 robot
            time_for_next_robot = (
                (1.0 - fractional_robot_progress) / curr_rate_per_min
                if curr_rate_per_min > 0
                else float("inf")
            )

            # Check if we can purchase any upgrades right now with available coins
            candidates = self.optimizer.get_candidate_actions(config, coins)
            affordable_effective_actions = [
                c for c in candidates if c.cost <= coins and c.marginal_rate_increase_per_hour > 0
            ]

            if affordable_effective_actions:
                best_action = affordable_effective_actions[0]
                coins -= best_action.cost
                self.optimizer.apply_action(config, best_action)
                new_analysis = self.calc.analyze_throughput(config)
                history_upgrades.append(
                    {
                        "sim_minute": int(sim_minute),
                        "sim_day": round(sim_minute / 1440.0, 2),
                        "category": best_action.category,
                        "station": best_action.station_key,
                        "action": best_action.action_type,
                        "from_level": best_action.from_level,
                        "to_level": best_action.to_level,
                        "cost": best_action.cost,
                        "new_rate_hr": round(new_analysis["max_robots_per_hour"], 2),
                        "new_bottleneck": new_analysis["bottleneck_name"],
                    }
                )
                # Recalculate with new configuration
                continue

            # Advance time to the completion of the next robot
            if sim_minute + time_for_next_robot > sim_limit:
                # Fractional progress at simulation end
                elapsed = sim_limit - sim_minute
                fractional_robot_progress += elapsed * curr_rate_per_min
                sim_minute = sim_limit
                break

            sim_minute += time_for_next_robot
            fractional_robot_progress = 0.0
            total_robots_produced += 1
            coins += coin_price_per_robot

            # Checkpoint every 1440 sim minutes (1 sim day) or on upgrade
            if int(sim_minute) // 1440 > int(sim_minute - time_for_next_robot) // 1440:
                production_curve.append(
                    {
                        "sim_minute": int(sim_minute),
                        "sim_day": round(sim_minute / 1440.0, 2),
                        "cumulative_robots": total_robots_produced,
                        "coins": coins,
                        "robots_per_hour": round(curr_analysis["max_robots_per_hour"], 2),
                        "bottleneck": curr_analysis["bottleneck_name"],
                    }
                )

        # Final record
        final_analysis = self.calc.analyze_throughput(config)
        production_curve.append(
            {
                "sim_minute": int(sim_minute),
                "sim_day": round(sim_minute / 1440.0, 2),
                "cumulative_robots": total_robots_produced,
                "coins": coins,
                "robots_per_hour": round(final_analysis["max_robots_per_hour"], 2),
                "bottleneck": final_analysis["bottleneck_name"],
            }
        )

        return {
            "total_sim_minutes": int(sim_minute),
            "total_sim_days": round(sim_minute / 1440.0, 2),
            "total_robots_produced": total_robots_produced,
            "final_coins": coins,
            "final_robots_per_hour": round(final_analysis["max_robots_per_hour"], 2),
            "final_bottleneck": final_analysis["bottleneck_name"],
            "upgrades_applied_count": len(history_upgrades),
            "upgrade_history": history_upgrades,
            "production_curve": production_curve,
            "final_configuration": config,
        }


class OrderScheduleGenerator:
    """Generates realistic and balanced order schedules grounded in simulation capacity."""

    def __init__(self, calculator: CapacityCalculator):
        self.calc = calculator
        self.simulator = OptimalExpansionSimulator(calculator)

    def generate_order_schedule(
        self,
        sim_duration_weeks: int = 2,
        difficulty: str = "standard",  # "relaxed" (0.6), "standard" (0.8), "optimal" (0.95)
    ) -> List[Order]:
        """Generates realistic order batches across the simulation horizon."""
        difficulty_multipliers = {
            "relaxed": 0.60,
            "standard": 0.80,
            "optimal": 0.95,
        }
        mult = difficulty_multipliers.get(difficulty, 0.80)
        total_sim_minutes = sim_duration_weeks * 7 * 1440

        # Simulate expansion curve
        sim_result = self.simulator.simulate_expansion(total_sim_minutes)
        curve = sim_result["production_curve"]

        orders: List[Order] = []
        coin_price = self.calc.robot_prices.get("engineer", 250)

        # 1. Tutorial / Milestone 1 (Day 1): 1 Engineer
        orders.append(
            Order(
                order_id="ORD-001",
                robot_type="engineer",
                quantity_engineer=1,
                quantity_forager=0,
                total_quantity=1,
                reward_coins=int(1 * coin_price * 1.2),  # +20% milestone bonus
                created_at_sim_minute=100,
                deadline_sim_minute=1440,  # 1 full day
                difficulty=difficulty,
            )
        )

        # 2. Tutorial / Milestone 2 (Day 2): 2 Foragers
        orders.append(
            Order(
                order_id="ORD-002",
                robot_type="forager",
                quantity_engineer=0,
                quantity_forager=2,
                total_quantity=2,
                reward_coins=int(2 * coin_price * 1.2),
                created_at_sim_minute=1440,
                deadline_sim_minute=2880,  # Day 2
                difficulty=difficulty,
            )
        )

        # 3. Periodic orders scaled to simulation output for remaining days
        # Sample points every 2 simulation days (2880 minutes)
        step_minutes = 2880
        curr_min = 2880
        order_idx = 3

        while curr_min < total_sim_minutes:
            end_min = min(curr_min + step_minutes, total_sim_minutes)
            
            # Estimate capacity produced in this window from simulation curve
            # Interpolate cumulative robots at curr_min and end_min
            cum_start = self._interpolate_cumulative(curve, curr_min)
            cum_end = self._interpolate_cumulative(curve, end_min)
            delta_robots = max(1, int((cum_end - cum_start) * mult))

            # Alternate between engineer, forager, and mixed orders
            if order_idx % 3 == 0:
                q_eng = delta_robots // 2
                q_for = delta_robots - q_eng
                robot_type = "mixed"
            elif order_idx % 2 == 0:
                q_eng = 0
                q_for = delta_robots
                robot_type = "forager"
            else:
                q_eng = delta_robots
                q_for = 0
                robot_type = "engineer"

            orders.append(
                Order(
                    order_id=f"ORD-{order_idx:03d}",
                    robot_type=robot_type,
                    quantity_engineer=q_eng,
                    quantity_forager=q_for,
                    total_quantity=delta_robots,
                    reward_coins=int(delta_robots * coin_price * 1.15),
                    created_at_sim_minute=curr_min,
                    deadline_sim_minute=end_min,
                    difficulty=difficulty,
                )
            )
            order_idx += 1
            curr_min = end_min

        return orders

    def _interpolate_cumulative(
        self, curve: List[Dict[str, Any]], sim_minute: int
    ) -> float:
        if not curve:
            return 0.0
        if sim_minute <= curve[0]["sim_minute"]:
            return float(curve[0]["cumulative_robots"])
        if sim_minute >= curve[-1]["sim_minute"]:
            return float(curve[-1]["cumulative_robots"])

        for i in range(len(curve) - 1):
            p1 = curve[i]
            p2 = curve[i + 1]
            if p1["sim_minute"] <= sim_minute <= p2["sim_minute"]:
                denom = p2["sim_minute"] - p1["sim_minute"]
                if denom == 0:
                    return float(p1["cumulative_robots"])
                frac = (sim_minute - p1["sim_minute"]) / denom
                return p1["cumulative_robots"] + frac * (
                    p2["cumulative_robots"] - p1["cumulative_robots"]
                )
        return float(curve[-1]["cumulative_robots"])


def print_summary_report(
    sim_duration_weeks: int = 2,
    difficulty: str = "standard",
    export_json_path: Optional[str] = None,
):
    calc = CapacityCalculator()
    sim = OptimalExpansionSimulator(calc)
    order_gen = OrderScheduleGenerator(calc)

    print("=" * 80)
    print(" HIVE FACTORY CAPACITY & ORDERS ANALYSIS")
    print("=" * 80)

    # 1. BOM Analysis
    raw_bom = calc.get_raw_resources_per_robot("engineer")
    print("\n1. Bill of Materials (BOM) per Robot:")
    for res, qty in raw_bom.items():
        print(f"   - {res.title():<12}: {qty:>2} units")

    # 2. Initial Throughput Analysis
    init_config = calc.get_initial_configuration()
    init_analysis = calc.analyze_throughput(init_config)
    print("\n2. Initial Simulation State (Un-upgraded):")
    print(
        f"   - Bottleneck             : {init_analysis['bottleneck_name']} ({init_analysis['bottleneck_type']})"
    )
    print(
        f"   - Maximum Output Rate    : {init_analysis['max_robots_per_hour']:.3f} robots/hour "
        f"({init_analysis['max_robots_per_day']:.2f} robots/day)"
    )
    print(
        f"   - Cycle Time per Robot   : {60.0 / init_analysis['max_robots_per_hour']:.1f} simulation minutes"
    )

    # 3. 1-Week and 2-Week Expansion Simulations
    for weeks in [1, sim_duration_weeks]:
        minutes = weeks * 7 * 1440
        print(f"\n3. {weeks}-Week Simulation Growth Simulation ({minutes:,} sim minutes):")
        result = sim.simulate_expansion(minutes)
        print(f"   - Total Robots Produced  : {result['total_robots_produced']:,}")
        print(f"   - Final Output Rate      : {result['final_robots_per_hour']:.2f} robots/hour")
        print(f"   - Upgrades Applied       : {result['upgrades_applied_count']}")
        print(f"   - Final Bottleneck       : {result['final_bottleneck']}")

        print("   - Key Expansion Milestones (First 5 Upgrades):")
        for u in result["upgrade_history"][:5]:
            print(
                f"     * Day {u['sim_day']:>4.1f} ({u['sim_minute']:>5}m): {u['action']} on {u['category']}/{u['station']} "
                f"(L{u['from_level']}->L{u['to_level']}, {u['cost']} coins) -> New Rate: {u['new_rate_hr']} robots/hr"
            )

    # 4. Sample Order Schedule
    print(f"\n4. Recommended Grounded Order Schedule ({sim_duration_weeks}-Week, Difficulty: {difficulty}):")
    orders = order_gen.generate_order_schedule(
        sim_duration_weeks=sim_duration_weeks, difficulty=difficulty
    )
    print(
        f"   {'Order ID':<10} | {'Type':<10} | {'Qty':<6} | {'Reward':<8} | {'Window (Sim Days)':<20}"
    )
    print("   " + "-" * 62)
    for o in orders:
        day_start = o.created_at_sim_minute / 1440.0
        day_end = o.deadline_sim_minute / 1440.0
        print(
            f"   {o.order_id:<10} | {o.robot_type:<10} | {o.total_quantity:<6} | {o.reward_coins:<8} | "
            f"Day {day_start:4.1f} -> Day {day_end:4.1f}"
        )
    print("=" * 80)

    if export_json_path:
        export_data = {
            "bom_raw_resources": raw_bom,
            "initial_throughput": init_analysis,
            "orders": [
                {
                    "order_id": o.order_id,
                    "robot_type": o.robot_type,
                    "quantity_engineer": o.quantity_engineer,
                    "quantity_forager": o.quantity_forager,
                    "total_quantity": o.total_quantity,
                    "reward_coins": o.reward_coins,
                    "created_at_sim_minute": o.created_at_sim_minute,
                    "deadline_sim_minute": o.deadline_sim_minute,
                    "difficulty": o.difficulty,
                }
                for o in orders
            ],
        }
        with open(export_json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        print(f"\nSaved export JSON to: {export_json_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Hive Orders & Capacity Calculator")
    parser.add_argument("--weeks", type=int, default=2, help="Simulation duration in weeks (default: 2)")
    parser.add_argument(
        "--difficulty",
        type=str,
        default="standard",
        choices=["relaxed", "standard", "optimal"],
        help="Order schedule difficulty target",
    )
    parser.add_argument("--export-json", type=str, default=None, help="Export order schedule to JSON file")
    args = parser.parse_args()

    print_summary_report(
        sim_duration_weeks=args.weeks,
        difficulty=args.difficulty,
        export_json_path=args.export_json,
    )


if __name__ == "__main__":
    main()
