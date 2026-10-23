# Orders Calculator & Factory Throughput Model

## Overview

The purpose of the **Orders Calculator** is to provide an analytical and simulation-based engine that determines the realistic output capacity of a Hive factory over time. Rather than generating random orders with arbitrary deadlines, orders must be directly grounded in the physical laws of the simulation—starting from initial conditions in `simulation-instructor-only/schemas/simulation_rules.json`, factoring in the economic expansion curve (reinvesting robot sale revenue into upgrades and station purchases), and projecting cumulative output across the simulation time horizon (1 to 2 weeks: 10,080 to 20,160 simulation minutes).

---

## 1. Production Model & Bill of Materials (BOM)

### 1.1 Station Levels & Metadata
From `simulation_rules.json`:
- **Level 1**: `interval_sim_minutes`: 10 min, `cost_purchase`: 100 coins, `cost_upgrade`: 100 coins
- **Level 2**: `interval_sim_minutes`: 5 min (2.0x speed), `cost_purchase`: 500 coins, `cost_upgrade`: 500 coins
- **Level 3**: `interval_sim_minutes`: 3 min (3.33x speed), `cost_purchase`: 1000 coins, `cost_upgrade`: -1 (max level)

### 1.2 Robot Recipes (Assembly)
Both **Engineer** (`worker_assembly`) and **Forager** (`forager_assembly`) require:
- `1 chassis`
- `3 electronics`
- `2 battery`
- `8 actuator`
- Station duration: Level 1 = 10 min, Level 2 = 5 min, Level 3 = 3 min.
- Unit sale price: **250 coins** per robot.

### 1.3 Part Recipes (Manufacturing)
- **Structural Molding** $\rightarrow$ `1 chassis`: 1 energy, 3 resin, 1 metals (10 min base)
- **Electronics Assembly** $\rightarrow$ `1 electronics`: 1 energy, 3 silicon, 2 copper (10 min base)
- **Actuator Fabrication** $\rightarrow$ `1 actuator`: 1 energy, 2 metals, 1 copper (10 min base)
- **Battery Assembly** $\rightarrow$ `1 battery`: 5 energy, 2 copper, 1 metals (10 min base)

### 1.4 Raw Resource Requirements per Single Robot
Expanding the BOM down to raw resources:

| Resource | Chassis (x1) | Electronics (x3) | Battery (x2) | Actuator (x8) | **Total per Robot** | Initial Gathering Level | Initial Interval | Initial Time to Gather 1 Robot Worth |
|---|---|---|---|---|---|---|---|---|
| **Energy** | 1 | 3 | 10 | 8 | **22** | Level 3 | 3 min | $22 \times 3 = 66\text{ min}$ |
| **Resin** | 3 | 0 | 0 | 0 | **3** | Level 2 | 5 min | $3 \times 5 = 15\text{ min}$ |
| **Silicon** | 0 | 9 | 0 | 0 | **9** | Level 2 | 5 min | $9 \times 5 = 45\text{ min}$ |
| **Metals** | 1 | 0 | 2 | 16 | **19** | Level 1 | 10 min | $19 \times 10 = \mathbf{190\text{ min}}$ |
| **Copper** | 0 | 6 | 4 | 8 | **18** | Level 2 | 5 min | $18 \times 5 = \mathbf{90\text{ min}}$ |

---

## 2. Bottleneck Analysis & Initial Constraints

### 2.1 Raw Resource Bottlenecks
At initial conditions:
1. **Metals Gathering (Binding Constraint)**: 19 metals per robot $\times$ 10 min/metal = **190 min per robot** (0.315 robots/hour).
2. **Copper Gathering**: 18 copper per robot $\times$ 5 min/copper = **90 min per robot** (0.667 robots/hour).
3. **Energy Gathering**: 22 energy per robot $\times$ 3 min/energy = **66 min per robot** (0.909 robots/hour).
4. **Silicon Gathering**: 9 silicon per robot $\times$ 5 min/silicon = **45 min per robot** (1.333 robots/hour).
5. **Resin Gathering**: 3 resin per robot $\times$ 5 min/resin = **15 min per robot** (4.000 robots/hour).

### 2.2 Manufacturing Station Bottlenecks (at 1 station each, Level 1)
- **Actuators (Binding Mfg Constraint)**: 8 actuators $\times$ 10 min = **80 min per robot**.
- **Electronics**: 3 electronics $\times$ 10 min = **30 min per robot**.
- **Battery**: 2 batteries $\times$ 10 min = **20 min per robot**.
- **Chassis**: 1 chassis $\times$ 10 min = **10 min per robot**.
- **Assembly**: 1 robot $\times$ 10 min = **10 min per robot**.

**Initial Factory Cycle Time**:
In the initial un-upgraded state, production is throttled by **Metals Gathering** (1 robot every 190 min) and **Actuator Fabrication** (1 station needs 80 min of machine time). The initial throughput is approximately **1 robot every ~190 to 200 simulation minutes** (~7.5 robots per 24-hour simulation day).

---

## 3. Economic Expansion & Optimal Upgrade Decisions

When a robot is assembled, it generates **250 coins**. These coins can be invested to expand capacity.

### 3.1 Upgrade Options & Return on Investment (ROI)

Costs come from `station_metadata`: an upgrade costs `cost_upgrade` of the station's *current* level (L1→L2 = 100, L2→L3 = 500, L3 is max), and an extra slot is always bought at Level 1 for `cost_purchase` of Level 1 (100). The calculator allows at most **3 slots** per station (`CapacityCalculator.max_slots`), every slot adds `1/interval` to the station's rate, and every resource, manufacturing and assembly station can be upgraded or multiplied.

| Action | Cost (Coins) | Effect | Capacity Impact on Binding Constraint |
|---|---|---|---|
| **Upgrade Metals Gathering to L2** | 100 | Delivery interval: 10m $\rightarrow$ 5m | Metals supply doubles (190m $\rightarrow$ 95m per robot). **Massive ROI.** |
| **Add 2nd Actuator Station (L1)** | 100 | Actuator stations: 1 $\rightarrow$ 2 | Actuator mfg time drops from 80m $\rightarrow$ 40m per robot. |
| **Add 2nd Metals Slot / Upgrade Metals to L3** | 100 (add) / 500 (L3) | Metals interval drops to 3m, or a parallel stream | Metals supply accelerates from 95m $\rightarrow$ 57m (L3). |
| **Upgrade Copper Gathering to L3** | 500 | Copper interval: 5m $\rightarrow$ 3m | Copper supply time drops from 90m $\rightarrow$ 54m per robot. |
| **Add 2nd Electronics Station (L1)** | 100 | Electronics stations: 1 $\rightarrow$ 2 | Electronics mfg time drops from 30m $\rightarrow$ 15m. |
| **Add 2nd Energy Slot** | 100 | Energy supply doubles (66m $\rightarrow$ 33m). | Prevents energy starvation as manufacturing scales up. |
| **Add 2nd Assembly Station** | 100 | Allows parallel assembly. | Eliminates line blocking. |

### 3.2 Marginal ROI Dynamic Decision Rule (as implemented)
At any state $S$:
1. Compute the supply rate for each resource $r$ (robots/min the resource can sustain):
   $$R_r(S) = \frac{\sum_{s \in \text{slots}(r)} 1/\text{interval}(s.\text{level})}{\text{BOM}(r)}$$
2. Compute the rate for each part $p$ the same way, dividing by the number of $p$ in one robot:
   $$M_p(S) = \frac{\sum_{s \in \text{slots}(p)} 1/\text{interval}(s.\text{level})}{\text{recipe}(p)}$$
3. Compute the assembly rate $A(S)$ as the **sum** over both assembly stations (`worker_assembly` and `forager_assembly`; the recipes are identical, so the engineer BOM is used for both).
4. The factory throughput capacity is:
   $$\Phi(S) = \min \left( \min_r R_r(S), \min_p M_p(S), A(S) \right)$$
5. Every possible single action $a$ (one upgrade or one added slot per station) is scored by marginal gain per coin:
   $$\frac{\Phi(S \oplus a) - \Phi(S)}{\text{Cost}(a)}$$
6. **Tie handling.** When several constraints are tied, no single action raises $\Phi$. For actions on a binding or near-binding constraint (within 5% of the minimum), the gain is estimated as half of that constraint's local lift, so the optimizer still makes progress.
7. **Greedy purchase policy.** `OptimalExpansionSimulator` buys the best-scoring affordable action with a positive gain as soon as it can pay for it. It never saves up for a more expensive action, and a purchase takes effect instantly.

---

## 4. Simulation Horizon & Output Envelopes

- **1 Week Simulation**: 7 days $\times$ 1,440 min/day = **10,080 simulation minutes**.
- **2 Week Simulation**: 14 days $\times$ 1,440 min/day = **20,160 simulation minutes**. This is `max_sim_weeks` (2) in `simulation_rules.json`.
- **Real time**: the clock is 1 real second = 1 sim minute, so 1 week takes 2.8 real hours and 2 weeks take 5.6 real hours (at 1x).

### 4.1 Hard capacity ceiling
With the rules as they are, the best possible factory is 3 slots at Level 3 for each station. Its ceiling per resource is $3 \times (1/3\text{ min}) / \text{BOM}(r)$ robots/min:

| Resource | Ceiling (robots/hour) |
|---|---|
| **Energy** | **2.73** (60 / 22) |
| Metals | 3.16 |
| Copper | 3.33 |

**Energy is the hard cap, at 2.73 robots/hour (about 65 robots/day).** No sequence of purchases can exceed it. The ceiling can only change by changing `simulation_rules.json` (recipes, intervals or the slot limit).

### 4.2 Greedy-optimal growth (output of the calculator)
| Measure | Value |
|---|---|
| Initial rate | 0.316 robots/hr (7.6/day), bound by metals |
| Ceiling reached | Sim minute 929 (about 15.5 sim hours, which is 15.5 real minutes at 1x) |
| Upgrades bought to reach the ceiling | 27 purchases, 5,500 coins (22 robots' worth) |
| Robots after 1 week | 437 |
| Robots after 2 weeks | 896 |
| Steady state | About 65 robots/day, bound by energy |

### Production Stages
- **Minute 0 to 929 (Bootstrap, compressed)**: Immediate reinvestment of every sale into Metals L2, 2nd Metals/Copper/Energy slots, Actuator L2, 2nd Actuator station, and so on.
- **After minute 929 (Steady state)**: The factory is maxed out and output is flat at the energy ceiling. All remaining growth is just time.

A human player will not play the greedy-optimal line, so a real run reaches the ceiling later (see section 7).

---

## 5. Order Generation Framework

Orders are generated to match the factory's capacity curve across the time horizon.

### 5.1 Order Schema
`Order` in `calculator.py`, exported by `--export-json` as:
```json
{
  "order_id": "ORD-003",
  "robot_type": "mixed",
  "quantity_engineer": 52,
  "quantity_forager": 52,
  "total_quantity": 104,
  "reward_coins": 29899,
  "created_at_sim_minute": 2880,
  "deadline_sim_minute": 5760,
  "difficulty": "standard"
}
```
`robot_type` is `engineer`, `forager` or `mixed`. `difficulty` records the profile the schedule was generated with.

### 5.2 Difficulty Profiles
The profile is a fraction of what the greedy-optimal curve produces in each order window (`--difficulty`):
- **relaxed (60%)**: Generous deadlines suitable for attendees learning to navigate and upgrade.
- **standard (80%)**: The default.
- **optimal (95%)**: Demands near-optimal reinvestment of earned coins into the true bottleneck.

### 5.3 Order Cadence
1. **Milestone Orders (Tutorial / Early Game)**:
   - `ORD-001`: 1 Engineer, created at minute 100, due at minute 1,440 (day 1). Reward = 1 $\times$ 250 $\times$ 1.2.
   - `ORD-002`: 2 Foragers, created at day 1, due at day 2. Reward = 2 $\times$ 250 $\times$ 1.2.
2. **Periodic Batches**:
   - One order per **2-day window** (2,880 sim minutes) from day 2 to the end of the horizon. Each is created at the start of its window and is due at the end.
   - Quantity = `max(1, int(robots the optimal curve produces in the window x difficulty fraction))`.
   - The type cycles through mixed, forager and engineer. Reward = quantity $\times$ 250 $\times$ 1.15.
3. **Fulfillment**: The target design is that the server places orders (`placeOrder()`, order-placed event) at times computed from this model, and each assembled robot is sold at once (`fulfillOrder()`, order-fulfilled event with the robot type and the coins from `robot_metadata`). Orders are always present, so the deadlines above need rethinking. See `next_steps.md`.

---

## 6. Implementation

Lives in `simulation-instructor-only/orders-calculator/`:
- `calculator.py`:
  - `load_rules`: Loads `simulation-instructor-only/schemas/simulation_rules.json`.
  - `CapacityCalculator`: BOM, per-station rates and the bottleneck analysis (`analyze_throughput`).
  - `UpgradeOptimizer`: Scores every upgrade and add-slot action by marginal gain per coin.
  - `OptimalExpansionSimulator`: Runs the greedy purchase policy over 1 to 2 weeks and returns the production curve and upgrade history.
  - `OrderScheduleGenerator`: Turns the production curve into an order schedule.
  - `main()`: The command-line entry point (there is no separate `cli.py`).
- `__init__.py`: Re-exports the classes above.
- `test_orders_calculator.py`: Tests. They run with the rest of the suite via `testpaths` and `pythonpath` in `simulation-instructor-only/pytest.ini`.
- `orders_1week.json`: A sample export.

Run from `simulation-instructor-only/`:
```bash
python3 orders-calculator/calculator.py --weeks 2 --difficulty standard
python3 orders-calculator/calculator.py --weeks 1 --export-json orders-calculator/orders_1week.json
```
The folder name contains a hyphen, so the package is not importable as `orders-calculator`; it works through the `pytest.ini` path entry or by running the script directly.

---

## 7. Status & Known Gaps

- **Purchases and upgrades are not a server concern.** `simulation_rules.json` defines station levels, intervals and costs, but the server does not use them. The Level 4 dashboard tracks spending client-side (`level4/Level4Context.tsx`). The growth curve in section 4 is a model of the player's spending, not something the server runs.
- **The server does not track orders yet.** There are no order events in `spec-shared/schemas/event_payloads.json`, and the admin page only shows assembled counts as "filled orders". The target design (`placeOrder()` / `fulfillOrder()`) is in `next_steps.md`; nothing here is loaded into a run yet.
- **The model is steady-state and analytic.** It ignores cart staging, the start-up transient before the first delivery and the effects of the fewest-completed-first ordering. Real throughput is at or below $\Phi(S)$, so any order schedule should be validated against a real run before use.
- **Orders are tied to optimal play.** Even `relaxed` is 60% of the greedy-optimal output. Only the ceiling in section 4.1 is guaranteed to be an upper bound.
- **Hard-coded numbers.** `max_slots = 3` and the 1.2x and 1.15x reward bonuses live in `calculator.py`, not in `simulation_rules.json`.
