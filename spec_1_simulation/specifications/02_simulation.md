# Factory simulation

## What the factory does

Build a server-side simulation of a small robotic-bee factory. Scheduled deliveries replenish five resources. Four independent stations consume those resources to make parts. A fifth station consumes parts to assemble worker robots. Work starts automatically whenever a station is idle and its full recipe is available.

The simulation owns the factory. Kafka carries observations of what has happened, and the UI displays those observations. The complete observation path is:

**Simulation → Kafka producer → Kafka → Kafka consumer → UI**

The attendee's local API sits between the consumer and browser to serve the consumer's stored view through HTTP and server-sent events. It must not take an alternative route from the simulation objects to the dashboard.

## Responsibilities and isolation

Each hosted factory owns its clock, resources, jobs, robots and in-memory state. The Simulation Server creates these logical instances and enforces attendee ownership. Its producer sends observation events to that factory's authorized Confluent topics. The consumer and dashboard run on the attendee's laptop in the other package.

There is no dashboard projection in this server. HTTP lifecycle/status endpoints may return control metadata and stream health, but do not return factory inventory/progress as a replacement for event consumption. See ../../spec_1_2_shared_contract/factory_api.md and ../../spec_1_2_shared_contract/event_contract.md.

Scope every state lookup, locked update, scheduler task, credential lookup and pending-queue operation by factory_id. A failed producer for one factory cannot block the scheduler or publisher of another. No attendee can set another factory's topic names or owner.

## Factory components

### Resource supply

The resource store holds resin, silicon, metals, copper and energy. Quantities are whole units. Energy is used in battery assembly; there is no continuous power drain in this first version.

A new run begins paused, with no resources, parts or robots. Clicking Start makes the first delivery due at simulated time zero. Further deliveries occur every 20 simulated seconds. Each delivery adds the bundle defined in `nn_data.md` directly to the simulation's inventory and records a resource.delivered event in the same locked in-memory update.

A delivery does not depend on producer acknowledgment or consumer receipt. Its delivery ID and sequence are created once. A retry of its event is an observation retry, not a second delivery.

### Parts manufacturing

Each station has one active job slot. Structural molding makes chassis, electronics assembly makes electronics, actuator fabrication makes actuators, and battery assembly makes batteries.

An idle station checks that every required input is available. If so, it atomically consumes those inputs, creates a job with start/end times and begins work. If any input is missing, it consumes nothing and waits. On completion, it adds one output part and frees its slot. If inputs are still available, it may immediately start another job at that simulated instant.

Jobs do not compete for factory workers or shared machine capacity in this version. They compete only for inventory. Station cycles and recipes are in `nn_data.md`.

### Worker assembly

Worker assembly is another automatic station with one active slot. It starts only when 1 chassis, 3 electronics, 2 batteries and 8 actuators are available. Consume them together at job start. After 10 simulated seconds, add one worker to completed inventory.

Use an immutable UUID for each robot and a friendly label such as W-001. Completed workers remain in inventory. Shipping, commissioning, colony registration and task allocation are later features.

## Scheduling without manufacturing priorities

There is no preferred station, production target or optimization policy. Each idle station attempts work as inputs become available. Actual state updates are serialized to prevent two jobs spending the same resources.

Implementation choice for otherwise simultaneous attempts: use a deterministic rotating starting position through the five stations. Every scheduling pass considers each station once, beginning at the stored cursor, then advances the cursor by one. This gives a repeatable tie-break without permanently favoring the first station in a list. Keep the cursor with the factory object. It is not a production priority setting or a promise that all stations always have enough stock.

Run a scheduling pass on initialization/resume and when a delivery or completion changes available inventory; do not rotate the cursor merely because an otherwise uneventful clock tick occurred. This keeps outcomes independent of clock wake-up jitter.
- **Pass iteration cascade**: Within an instant $t$, starting one job or completing another can immediately enable further station starts. Loop the tie-break pass across all 5 stations until a complete pass starts no new jobs, advancing the cursor by 1 on each full pass.

At a simulated instant:

1. Apply any due delivery.
2. Finish all jobs due at that instant and credit their outputs once.
3. Let idle stations attempt to start, using the rotating tie-break and the inventory now available.
4. Apply state and enqueue events together under the factory lock.

A station consumes at start and produces at completion; never deduct its recipe a second time. A shortage leaves the station waiting and available for the next pass. Parts made at an instant can be used by assembly at that same instant.
- **Causation tracking**: When emitting `part.produced` or `robot.assembled`, set `causation_id` to the corresponding `job.started` event's `event_id` to allow strict traceability across activity streams.

## Clock and speed

The simulation has an in-memory logical clock measured in milliseconds. A background clock wakes every SIM_TICK_MILLISECONDS of wall time (default 100 ms). While running, advance by elapsed monotonic wall time multiplied by 1 or 5. These controls are speed multipliers, not a limit of one or five jobs per cycle.

Process every delivery and completion deadline between the old and new clock times in chronological order. Do not skip work if a tick is late or 5x crosses several deadlines. At equal deadlines, use the order above. New jobs start at the deadline being processed, not at the end of a delayed tick. Publish dashboard snapshots on a separate wall-time cadence so 5x does not multiply UI message volume.

Pause freezes simulated time, future deliveries and job progress. Already queued events continue through Kafka and can catch the UI up while paused. Changing speed affects only future elapsed time. Ordinary process downtime does not count as simulated time.

## A concrete first cycle

At time zero the first delivery supplies resin 4, silicon 6, metals 12, copper 20 and energy 6. There are enough inputs to start all four part stations. Once their recipes are deducted, available resources are resin 3, silicon 5, metals 9, copper 17 and energy 5. Assembly waits for parts.

The first actuator finishes at 2 seconds, electronics at 4, battery at 5 and chassis at 6. A free station can begin its next job immediately if its inputs remain available. Assembly starts only once the complete worker recipe is available. At 5x these same simulated deadlines occur faster in wall time; the recipes and manufacturing order do not change.

These are simulation results first. They become visible on the dashboard only after the corresponding snapshot has passed through producer, broker and consumer.

## Lifecycle controls

The shared factory API defines the state machine. A new provisioned factory is paused at zero. Start runs/resumes the same paused run; Pause is resumable; Stop freezes the run permanently for inspection; Restart at zero creates a new generation and normally starts it, with start=false available to leave it paused.

Restart discards the prior run's current work, not its pending event delivery history. Emit the new empty time-zero snapshot before admitting the first delivery. New worker display labels begin at W-001. Command idempotency prevents repeated Restart on network retries. Expected-generation checking rejects old commands aimed at a prior run.

Keep control acknowledgment separate from event observation. The local application displays server receipts immediately but inventory/progress only after Kafka consumption. A broker outage does not disable Start, Pause, Stop or Restart of an already provisioned factory.

## State lifetime

Clock, generation, inventories, active jobs, completed robots, cursor and pending events exist only in server memory. Pause and Stop retain them while this process lives. Restart at zero is an API action that creates a new run within the existing factory object.

Restarting the server/container is different: all factory objects and submitted credentials are lost. The next process has a new server_epoch. Attendees must register again, receive a new factory_id and begin paused at zero. No crash recovery, database backup or event replay into the simulator is implemented.


## Events and dashboard snapshots

Record delivery, job-start, part-completion and robot-completion events for the activity log. Also publish a complete factory.state snapshot, because the UI needs clock, progress, waiting reasons, controls and a reliable bootstrap/reconnect view.

Queue snapshots at the SNAPSHOT_INTERVAL_MILLISECONDS wall-clock cadence during normal running (default 200 ms, or five per second), and immediately on initialization, pause, resume, speed change, restart-at-zero and restart. When paused, a one-second observation heartbeat is sufficient. Every snapshot describes a single applied factory revision. The event contract is in `../contracts/event_contract.md`.

The consumer stores the latest snapshot for the newest run_generation. It does not recalculate factory inventory from delivery events. It separately stores consumed activity events for the log. Full snapshots make an out-of-order or repeated delivery harmless to the displayed inventory, while event IDs prevent duplicate log rows.

## Kafka outages and memory limits

Existing factories keep running during broker or consumer outages. A per-factory memory queue retains unsent records for retry in this process. The UI remains on the last consumed snapshot and marks it stale. No direct inventory API bypass is allowed.

Before applying a transition, ensure its records fit the configured queue limits (both record count and bytes). When full, flag buffer_full and halt that factory without applying the transition; allow Stop/Pause and explicit resume after the producer drains the queue. Reserve a small control-record allowance. Retry oldest first. One factory's connection error must not block other factories.

A process crash loses queued records. Already-acknowledged Kafka events are unaffected. This is an accepted prototype limitation, not a durability guarantee.

## Completion checks

Verify automatic manufacturing and controls, isolation across factory objects, continued work during a bounded Kafka outage, catch-up within the same process, and explicit factory loss after server restart. The server never reconstructs simulation state from old Kafka records.


