# Dataset for simulation

## Source of truth

`schemas/simulation_rules.json` is the single machine-readable recipe/delivery configuration for the simulation and tests. It stores resource IDs, per-resource delivery intervals and quantities, part IDs, station IDs, recipe quantities and job durations. The tables below mirror its current values; if they differ, the JSON file wins and this document must be updated. The frontend uses matching display labels. Kafka bootstrap settings and ports remain in server root `.env`.

These are the agreed starting values for the first working version. We will tune them as we learn. They represent a teaching simulation, not a physical robot bill of materials.

Start with empty inventories and simulated time zero, paused. Clicking Start begins every resource's first delivery cycle at time zero; each completes after its own interval.

## Resource deliveries

Each resource has its own independent delivery timer. A cycle starts (`gathering.started`), completes when the timer fires (`gathering.completed`) and adds its quantity to inventory, and the next cycle starts immediately.

| Resource | Units per delivery | Interval (sim seconds) |
| --- | ---: | ---: |
| Energy | 7 | 10 |
| Resin | 3 | 10 |
| Silicon | 3 | 10 |
| Metals | 2 | 10 |
| Copper | 5 | 10 |

Use lowercase resource IDs: `resin`, `silicon`, `metals`, `copper`, `energy`. Energy is an inventory item consumed by structural molding, electronics assembly, actuator fabrication and battery assembly; there is no background energy drain yet.

The simulation adds each completed delivery to its authoritative inventory and queues an outgoing observation event in memory. Kafka carries that observation to the dashboard; the consumer never changes simulation inventory.

## Manufacturing recipes

| Station | Inputs for one job | Output | Simulated time |
| --- | --- | --- | ---: |
| Structural molding | 1 energy, 3 resin, 1 metals | 1 chassis | 10 seconds |
| Electronics assembly | 1 energy, 3 silicon, 2 copper | 1 electronics | 10 seconds |
| Actuator fabrication | 1 energy, 2 metals, 1 copper | 1 actuator | 10 seconds |
| Battery assembly | 5 energy, 2 copper, 1 metals | 1 battery | 10 seconds |

Station IDs are `structural_molding`, `electronics_assembly`, `actuator_fabrication` and `battery_assembly`. Part IDs are `chassis`, `electronics`, `actuator` and `battery`.

## Robot assembly

| Station | Robot ID | Inputs for one job | Simulated time | Status |
| --- | --- | --- | ---: | --- |
| `worker_assembly` | `engineer` | 1 chassis, 3 electronics, 2 batteries, 8 actuators | 10 seconds | Active |
| `forager_assembly` | `forager` | 1 chassis, 3 electronics, 2 batteries, 8 actuators | 10 seconds | Placeholder |

Robot IDs are `engineer` and `forager`. Robots are identified by type, like parts; there is no per-robot UUID or display label. Completed robots are counted.

`forager_assembly` is a placeholder. It carries the same recipe and duration as `worker_assembly` for now and is declared in `simulation_rules.json`, but the simulation does not schedule it, emit forager events or include it in snapshots until a later specification enables it and sets its real recipe.

## Execution rules

`02_simulation.md` defines scheduling, time, controls, outage behavior and server restart limitations. Use its rotating tie-break for simultaneous station attempts; there is no fixed manufacturing priority. Each station has one slot and consumes inputs at start, then produces output at completion.

Use a 100 ms clock wake-up interval and 1x/5x speeds. Deliveries and jobs use simulated time. Dashboard snapshots use wall time: up to five per second while running, plus control/lifecycle snapshots and a one-second paused heartbeat.

## Conservation checks

For each run, delivered resources equal available resources plus resources consumed by jobs. Produced parts equal available parts plus parts consumed by assembly. Completed robots equal unique completed assembly jobs. Active jobs have already consumed their inputs. Restart at zero starts new per-run totals; abandoned old-run inputs do not transfer to the new run.
