# Factory simulation

## What the factory does

Build a server-side simulation of a small robotic-bee factory. Scheduled deliveries replenish five resources. Four independent stations consume those resources to make parts. Two assembly stations consume parts to assemble engineer and forager robots. Work starts automatically whenever a station is idle and its full recipe is available.

The simulation owns the factory. Kafka carries observations of what has happened, and the UI displays those observations. The complete observation path is:

**Simulation → Kafka producer → Kafka → Kafka consumer → UI**

The attendee's local API sits between the consumer and browser to serve the consumer's stored view through HTTP and server-sent events. It must not take an alternative route from the simulation objects to the dashboard.

## Responsibilities and isolation

Each hosted factory owns its clock, resources, jobs, robots and in-memory state. The Simulation Server creates these logical instances and enforces attendee ownership. Its producer sends observation events to that factory's authorized Confluent topics. The consumer and dashboard run on the attendee's laptop in the other package.

There is no dashboard projection in this server. HTTP lifecycle/status endpoints may return control metadata and stream health, but do not return factory inventory/progress as a replacement for event consumption. See ../../spec-shared/factory_api.md.

Scope every state lookup, locked update, scheduler task, credential lookup and pending-queue operation by factory_id. A failed producer for one factory cannot block the scheduler or publisher of another. No attendee can set another factory's topic names or owner.

## Factory components

### Resource supply

The resource store holds resin, silicon, metals, copper and energy. Quantities are whole units. Energy is used in battery assembly; there is no continuous power drain in this first version.

A new run begins paused, with no resources, parts or robots. Each resource has its own independent delivery cycle, defined by `interval_sim_minutes` and `quantity` in `schemas/simulation_rules.json` (see `03_data.md`). Clicking Start begins every resource's first cycle and emits `gathering.started` for each. When a cycle's timer fires, the quantity is added directly to the simulation's inventory and `gathering.completed` is recorded in the same locked in-memory update. The next cycle starts immediately with a new `gathering.started`.

A delivery does not depend on producer acknowledgment or consumer receipt. Its job ID is created once. A retry of its event is an observation retry, not a second delivery.

### Parts manufacturing

Each station has one active job slot. Structural molding makes chassis, electronics assembly makes electronics, actuator fabrication makes actuators, and battery assembly makes batteries.

Each station has an internal staging cart. On every scheduling pass an idle station moves whatever it can from factory stock into its cart: for each required input it takes `min(still needed, available)`. When the cart holds the complete recipe, the cart is consumed, a job is created with start/end times and the station begins work. Until then the station keeps what it has staged and waits for the rest; staged inputs are no longer in factory stock. On completion, it adds one output part and frees its slot. If inputs are still available, it may immediately stage and start another job at that simulated instant.

This prevents starvation of multi-unit recipes. Structural molding and battery assembly need only 1 metals, so under an all-or-none check they would consume every single metals delivery on arrival and actuator fabrication (2 metals) could never accumulate them.

Jobs do not compete for factory workers or shared machine capacity in this version. They compete only for inventory. Station cycles and recipes are in `schemas/simulation_rules.json`.

### Robot assembly

The `assembly` list in `simulation_rules.json` defines the assembly stations: `worker_assembly` builds the `engineer` robot and `forager_assembly` builds the `forager` robot. Each is an automatic station with one active slot and works like a manufacturing station: it incrementally moves finished parts into its own assembly cart and starts only when the cart holds the full recipe. The cart is consumed at job start. When the job duration elapses, add one robot of that type to completed inventory. The two stations compete for the same finished parts; the one with the fewest completed robots is served first.

Robots are identified by type (`robot_id`: `engineer` or `forager`), the same way parts are identified by `part_id`. There is no per-robot UUID or display label such as W-001; completed robots are counted. Completed robots remain in inventory. Shipping, commissioning, colony registration and task allocation are later features.

The forager currently uses the same provisional recipe and duration as the engineer. Snapshots list six stations.

Job durations are internal to the simulation. Events and `factory.state` snapshots never include a `duration_ms` field; attendees derive elapsed time from the `sim_time_minutes` of a job's `started` and `completed` events.

## Scheduling order

There is no production target or optimization policy. Each idle station attempts work as inputs become available. Actual state updates are serialized to prevent two jobs spending the same resources.

Implementation: parts manufacturing stations are served in order of fewest completed parts first, so the station that has produced the least stages inputs before the others. Assembly stages from finished-parts stock independently. This ordering is a fairness rule, not a promise that all stations always have enough stock; a station holding a partial cart does not release it.

Run a scheduling pass on initialization/resume and when a delivery or completion changes available inventory; do not run one merely because an otherwise uneventful clock tick occurred. This keeps outcomes independent of clock wake-up jitter.
- **Pass iteration cascade**: Within an instant $t$, starting one job or completing another can immediately enable further station starts. Loop the manufacturing pass until a complete pass starts no new jobs.

At a simulated instant:

1. Apply any due delivery.
2. Finish all jobs due at that instant and credit their outputs once.
3. Let idle stations attempt to start, in fewest-completed-parts order, staging from the inventory now available.
4. Apply state and enqueue events together under the factory lock.

A station consumes at start and produces at completion; never deduct its recipe a second time. A shortage leaves the station waiting and available for the next pass. Parts made at an instant can be used by assembly at that same instant.
- **Causation tracking**: When emitting `manufacturing.completed`, `assembly.completed` or `gathering.completed`, set the envelope `causation_id` to the `event_id` of the corresponding `*.started` event to allow strict traceability across activity streams.

## Clock and speed

The simulation has an in-memory logical clock measured in milliseconds. A background clock wakes every SIM_TICK_MILLISECONDS of wall time (default 100 ms). While running, advance by elapsed monotonic wall time multiplied by 1 or 5. These controls are speed multipliers, not a limit of one or five jobs per cycle.

Process every delivery and completion deadline between the old and new clock times in chronological order. Do not skip work if a tick is late or 5x crosses several deadlines. At equal deadlines, use the order above. New jobs start at the deadline being processed, not at the end of a delayed tick. Publish dashboard snapshots on a separate wall-time cadence so 5x does not multiply UI message volume.

Pause freezes simulated time, future deliveries and job progress. Already queued events continue through Kafka and can catch the UI up while paused. Changing speed affects only future elapsed time. Ordinary process downtime does not count as simulated time.

## A concrete first cycle

At time zero every resource starts its first delivery cycle (`gathering.started`) and inventory is empty, so no station can start yet and no scheduling pass runs at time zero. When the first cycles complete at their `interval_sim_minutes`, the quantities are added to inventory, the next cycles start, and any station whose full recipe is now available starts a job at that same simulated instant. A free station can begin its next job immediately if its inputs remain available. Assembly starts only once the complete engineer recipe is available. At 5x these same simulated deadlines occur faster in wall time; the recipes and manufacturing order do not change.

These are simulation results first. They become visible on the dashboard only after the corresponding snapshot has passed through producer, broker and consumer.

## Lifecycle controls

The shared factory API defines the state machine. A new provisioned factory is paused at zero. Start runs/resumes the same paused run; Pause is resumable; Stop freezes the run permanently for inspection; Restart at zero creates a new generation and normally starts it, with start=false available to leave it paused.

Restart discards the prior run's current work, not its pending event delivery history. Emit the new empty time-zero snapshot before admitting the first delivery. Completed-robot counts reset to zero. Command idempotency prevents repeated Restart on network retries. Expected-generation checking rejects old commands aimed at a prior run.

Keep control acknowledgment separate from event observation. The local application displays server receipts immediately but inventory/progress only after Kafka consumption. A broker outage does not disable Start, Pause, Stop or Restart of an already provisioned factory.

## State lifetime

Clock, generation, inventories, active jobs, completed robots, cursor and pending events exist only in server memory. Pause and Stop retain them while this process lives. Restart at zero is an API action that creates a new run within the existing factory object.

Restarting the server/container is different: all factory objects and submitted credentials are lost. The next process has a new server_epoch. Attendees must register again, receive a new factory_id and begin paused at zero. No crash recovery, database backup or event replay into the simulator is implemented.


## Events and dashboard snapshots

Record `resource.*`, `manufacturing.*` and `assembly.*` (started, completed, blocked) events for the activity log. Also publish a complete factory.state snapshot, because the UI needs clock, progress, waiting reasons, controls and a reliable bootstrap/reconnect view.

Queue snapshots at the SNAPSHOT_INTERVAL_MILLISECONDS wall-clock cadence during normal running (default 200 ms, or five per second), and immediately on initialization, pause, resume, speed change, restart-at-zero and restart. When paused, a one-second observation heartbeat is sufficient. Every snapshot describes a single applied factory revision.

The consumer stores the latest snapshot for the newest run_generation. It does not recalculate factory inventory from delivery events. It separately stores consumed activity events for the log. Full snapshots make an out-of-order or repeated delivery harmless to the displayed inventory, while event IDs prevent duplicate log rows.

## Kafka outages and memory limits

Existing factories keep running during broker or consumer outages. A per-factory memory queue retains unsent records for retry in this process. The UI remains on the last consumed snapshot and marks it stale. No direct inventory API bypass is allowed.

Before applying a transition, ensure its records fit the configured queue limits (both record count and bytes). When full, flag buffer_full and halt that factory without applying the transition; allow Stop/Pause and explicit resume after the producer drains the queue. Reserve a small control-record allowance. Retry oldest first. One factory's connection error must not block other factories.

A process crash loses queued records. Already-acknowledged Kafka events are unaffected. This is an accepted prototype limitation, not a durability guarantee.

## Completion checks

Verify automatic manufacturing and controls, isolation across factory objects, continued work during a bounded Kafka outage, catch-up within the same process, and explicit factory loss after server restart. The server never reconstructs simulation state from old Kafka records.


