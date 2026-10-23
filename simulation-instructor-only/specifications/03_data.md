# Dataset for simulation

## Source of truth

`schemas/simulation_rules.json` is the single machine-readable recipe/delivery configuration for the simulation and tests. It defines resource IDs, per-resource delivery intervals and quantities, part IDs, station IDs, recipe quantities, job durations and the robot types. Its values are not repeated in this document; read the JSON. Event and `simulation.state` payload shapes are in `spec-shared/schemas/event_payloads.json`. The frontend uses matching display labels. Kafka bootstrap settings and ports remain in server root `.env`.

The values are the agreed starting point for the first working version and will be tuned. They represent a teaching simulation, not a physical robot bill of materials.

Start with empty inventories and simulated time zero, paused. Clicking Start begins every resource's first delivery cycle at time zero; each completes after its own interval.

## Resource deliveries

Each resource has its own independent delivery timer. A cycle starts (`gathering.started`), completes when the timer fires (`gathering.completed`) and adds its quantity to inventory, and the next cycle starts immediately. Intervals and quantities are in `simulation_rules.json`.

Energy is an inventory item consumed by the manufacturing stations; there is no background energy drain yet.

The simulation adds each completed delivery to its authoritative inventory and queues an outgoing observation event in memory. Kafka carries that observation to the dashboard; the consumer never changes simulation inventory.

## Manufacturing and robot assembly

Manufacturing station recipes, outputs and durations, and the robot assembly recipe and duration, are in `simulation_rules.json`.

Robots are identified by type, like parts; there is no per-robot UUID or display label. Completed robots are counted.

`worker_assembly` (engineer) and `forager_assembly` (forager) are both defined in the `assembly` list in `simulation_rules.json`, scheduled, and included in snapshots and events. The forager carries the same recipe and duration as the engineer for now.

Durations are internal: no event or snapshot carries `duration_ms`.

## Execution rules

`02_simulation.md` defines scheduling, time, controls, outage behavior and server restart limitations. Stations are served fewest-completed-parts first and stage inputs incrementally into a per-station cart. Each station has one slot and consumes its full cart at start, then produces output at completion.

Use a 100 ms clock wake-up interval and 1x/5x speeds. Deliveries and jobs use simulated time. Dashboard snapshots use wall time: up to five per second while running, plus control/lifecycle snapshots and a one-second paused heartbeat.

A run is capped at one simulated week (`MAX_SIM_MS` in `server/simulation_manager.py`). When the clock reaches the cap the simulation expires, like a TTL expiry.

## Conservation checks

For each run, delivered resources equal available resources plus resources consumed by jobs. Produced parts equal available parts plus parts consumed by assembly. Completed robots equal unique completed assembly jobs. Active jobs have already consumed their inputs. Restart at zero starts new per-run totals; abandoned old-run inputs do not transfer to the new run.
