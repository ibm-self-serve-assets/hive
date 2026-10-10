# Shared event contract — version 1.0

The server is producer; the attendee's local Python backend is consumer. The browser uses local HTTP/SSE and never connects to Kafka directly. Both packages use this identical contract. No Schema Registry is required.

## Topics and identity

An organizer assigns each enrollment a unique prefix, for example hive.<workshop>.<attendee>. The server returns the exact topic names. Neither side reconstructs them from a display name.

| Topic suffix | Primary event type | Use |
| --- | --- | --- |
| .resource-delivered | resource.delivered | Activity log |
| .job-started | job.started | Activity log |
| .part-produced | part.produced | Activity log |
| .robot-assembled | robot.assembled | Activity log |
| .factory-state | factory.state | Full observed factory snapshot |

Each topic has one partition. Four activity topics use 24-hour delete retention; factory-state uses compaction without time deletion, keyed by factory_id. Respect managed-cluster replication settings rather than requesting single-broker replication. Topics/ACLs are preprovisioned, not created by an attendee runtime key. Each factory remains in its assigned namespace across restart.

Send plain UTF-8 JSON values with UTF-8 factory_id keys. Schema validation uses checked-in JSON Schema files generated from this document. Contract version 1.0 here is the new two-package baseline, not a promise of wire compatibility with the prior local-only prototype.

## Envelope

Required fields: event_id (UUID), event_type, schema_version (integer 1), factory_id (UUID), run_id (UUID), run_generation (positive integer), event_sequence (positive factory-wide integer across all resets), state_revision (nonnegative integer within run), occurred_at (UTC RFC3339 timestamp), sim_time_ms (nonnegative integer), causation_id (UUID or null), payload (object).

Factory identity is server-assigned. Add required server_epoch UUID to the envelope; it identifies the current server process. Generation starts at 1 and increases at restart-at-zero; a server process restart loses the factory; re-registration creates a new factory_id. Producer retries retain event_id and event_sequence. Consumers require the assigned factory_id even inside an isolated topic. A mismatched factory is ignored/quarantined, never displayed.

## Activity payloads

- resource.delivered: delivery_id UUID, delivery_sequence positive within run, resources object (resin, silicon, metals, copper, energy; nonnegative integers, at least one positive).
- job.started: job_id UUID, station_id, output_id, inputs object of positive integer quantities, duration_ms positive integer.
- part.produced: job_id UUID, station_id, part_id, quantity=1.
- robot.assembled: job_id UUID, robot_id UUID, robot_type=worker, display_number positive integer, quantity=1.

Station IDs: structural_molding, electronics_assembly, actuator_fabrication, battery_assembly, worker_assembly. Part IDs: chassis, electronics, actuator, battery. Completion causation_id is its job.started event ID. Validate recipe combinations on the producer using the simulation data. Consumer validates shapes, ranges and identity.

For onboarding only, the four activity topics also allow connection.test with the same envelope and payload {"operation_id": "<UUID>", "probe": true}. Use one schema per topic with a oneOf for its primary event versus the probe. Consumers validate and ignore probes; they never create log rows, inventories or jobs. factory-state publish validation uses an actual empty paused snapshot. Probes use the allocated factory's run identity and consume sequence numbers, so sequence gaps in activity are normal.

## Complete snapshot payload

- lifecycle_status: paused, running, stopped or expired.
- running: boolean, true only when lifecycle_status=running and no blocking operational error.
- operational_error: null or {code, message}; never contains secrets.
- speed: 1 or 5; next_delivery_sim_time_ms and next_delivery_in_ms (nonnegative).
- resources: all five nonnegative available quantities.
- parts: all four nonnegative available quantities.
- stations: array of five objects, each station_id, status, missing_inputs, job.
- status: idle, working, waiting_for_resources or waiting_for_parts. Overall paused/stopped overrides whether an otherwise working job progresses.
- missing_inputs: object of item IDs to required shortfall quantities.
- job: null or {job_id, output_id, started_at_sim_ms, completes_at_sim_ms, duration_ms, consumed_inputs, progress_percent}; clamp progress to 0..100.
- completed_workers: {count, last_robot_id}, with UUID or null for last_robot_id.
- last_applied_command_id: UUID or null.

Publish full snapshots at most 5 per wall second while running, 1 per second while paused/stopped (until expiry), and immediately after lifecycle commands and factory creation. An expired final snapshot is best effort; authoritative expiry is also available on the control API. Snapshots never carry access tokens, Kafka secrets, owner PII or server configuration.

## In-memory producer and consumer

Apply each simulation transition and enqueue its outgoing records under a factory lock, after checking buffer capacity. No database or transactional outbox is used. A background publisher sends oldest first and removes records after acknowledgment. Retried records retain their IDs while the process lives. Calls to Kafka occur outside the lock. A crash loses pending records and factory state; do not promise crash-safe delivery.

The local consumer also uses an in-memory projection, activity ring buffer and duplicate-ID cache. Validate factory_id and server_epoch against the currently registered factory, then compare snapshots by (run_generation, state_revision, event_sequence). Replace state only with newer snapshots. Activity records may arrive before their run's snapshot; buffer them within a bounded history and show only the current observed run. Ignore onboarding connection.test events. Never update the factory itself.

A local app restart clears its view. Authenticate and obtain the current server epoch and owned factory again, then replay with a new session consumer group within the allowed prefix from earliest available records. The compacted state topic provides the latest observed snapshot; activity history is limited by topic retention and the local ring buffer. Broker offsets are not a durable local projection. Do not reuse an old group's end offsets and assume a cleared view can restore itself.

If the server has restarted, require registration with a new factory_id. Old Kafka records remain transport history and must not revive a lost simulation. No automatic server state reconstruction is implemented. Duplicate suppression is bounded and process-local; full-state replacement avoids additive inventory errors even after the cache evicts IDs. Invalid records are counted/logged in a bounded in-memory quarantine, not a persistent audit store.


## Observation health

Keep produced_at from occurred_at, consumed_at and latest valid snapshot age. Default stale threshold: 3 wall seconds, adjusted for known clock skew; warn if clocks differ materially. Receiving an old replay does not make it fresh. Show awaiting_events, live, stale or catching_up. Stop visual interpolation when stale; do not manufacture progress beyond consumed time. Transport health and command receipts can be shown separately from observed factory state.
