# Dataset for simulation

## Resources, recipes and simulation rules

These are the agreed starting values for the first working version. We will tune them as we learn. They represent a teaching simulation, not a physical robot bill of materials.

Start with empty inventories and simulated time zero, paused. The first delivery is due when Start is clicked; subsequent deliveries arrive every 20 simulated seconds.

| Resource | Units per delivery |
| --- | ---: |
| Resin | 4 |
| Silicon | 6 |
| Metals | 12 |
| Copper | 20 |
| Energy | 6 |

Use lowercase resource IDs: `resin`, `silicon`, `metals`, `copper`, `energy`. Energy is an inventory item consumed by battery assembly; there is no background energy drain yet.

The simulation adds each scheduled bundle to its authoritative inventory and queues an outgoing observation event in memory. Kafka carries that observation to the dashboard; the consumer never changes simulation inventory.

## Manufacturing recipes

| Station | Inputs for one job | Output | Simulated time |
| --- | --- | --- | ---: |
| Structural molding | 1 resin, 1 metals | 1 chassis | 6 seconds |
| Electronics assembly | 1 silicon, 1 copper | 1 electronics | 4 seconds |
| Actuator fabrication | 1 metals, 1 copper | 1 actuator | 2 seconds |
| Battery assembly | 1 energy, 1 copper, 1 metals | 1 battery | 5 seconds |

Station IDs are `structural_molding`, `electronics_assembly`, `actuator_fabrication` and `battery_assembly`. Part IDs are `chassis`, `electronics`, `actuator` and `battery`.

A worker requires **1 chassis, 3 electronics, 2 batteries and 8 actuators**. Assembly takes **10 simulated seconds**. Display workers as W-001, W-002 and so on, with a separate unique robot ID behind each label.

## Execution rules

`nn_simulation.md` defines scheduling, time, controls, outage behavior and server restart limitations. Use its rotating tie-break for simultaneous station attempts; there is no fixed manufacturing priority. Each station has one slot and consumes inputs at start, then produces output at completion.

Use a 100 ms clock wake-up interval and 1x/5x speeds. Deliveries and jobs use simulated time. Dashboard snapshots use wall time: up to five per second while running, plus control/lifecycle snapshots and a one-second paused heartbeat.

## Shared configuration

Create one machine-readable recipe/delivery configuration for the simulation and tests. Store resource IDs, part IDs, station IDs, recipe quantities and job durations there. The frontend uses matching display labels. Kafka bootstrap settings and ports remain in server root `.env`.

## Conservation checks

For each run, delivered resources equal available resources plus resources consumed by jobs. Produced parts equal available parts plus parts consumed by assembly. Completed workers equal unique completed assembly jobs. Active jobs have already consumed their inputs. Restart at zero starts new per-run totals; abandoned old-run inputs do not transfer to the new run.
