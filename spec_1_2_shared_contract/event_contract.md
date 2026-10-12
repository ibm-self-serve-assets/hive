# Shared event contract — version 2.0

The sim server is producer; the attendee's local Python backend is consumer. The browser uses local HTTP/SSE and never connects to Kafka directly. Both packages use this identical contract. No Schema Registry is required.

## Topics and identity

An organizer assigns each enrollment a topic prefix equal to the workshop ID, for example `hive-1`. The server returns the exact topic names at factory registration time. Neither side reconstructs topic names from a display name. Consumer group IDs include the attendee ID for isolation: `hive-1.<attendee_id>`.

| Topic suffix | Primary event type | Retention | Use |
| --- | --- | --- | --- |
| `.resource-delivered` | `resource.delivered` | 24 h delete | Activity log |
| `.manufacturing-started` | `manufacturing.started` | 24 h delete | Activity log |
| `.manufacturing-completed` | `manufacturing.completed` | 24 h delete | Activity log |
| `.manufacturing-blocked` | `manufacturing.blocked` | 24 h delete | Activity log |
| `.assembly-started` | `assembly.started` | 24 h delete | Activity log |
| `.assembly-completed` | `assembly.completed` | 24 h delete | Activity log |
| `.assembly-blocked` | `assembly.blocked` | 24 h delete | Activity log |
| `.factory-state` | `factory.state` | compact | Full observed factory snapshot |

Eight topics total: seven activity topics (delete retention, 24 h) and one state topic (log-compacted, no time deletion). Each topic has one partition. Confluent Cloud managed-cluster replication settings apply; do not request single-broker replication.

Topics are pre-provisioned by the attendee before factory registration (`provision_topics.sh`). The sim server verifies all eight topics are reachable via probe writes at registration time and rejects the request if any are missing.

Each factory remains in its assigned namespace across restarts. Topics/ACLs are never created at runtime by the server.

Send plain UTF-8 JSON values with UTF-8 `factory_id` keys. Schema validation uses checked-in JSON Schema files derived from this document.

## Envelope

Every event — activity and state — shares the same envelope. All fields are required unless noted.

| Field | Type | Description |
| --- | --- | --- |
| `event_id` | UUID string | Unique per event; retained across producer retries |
| `event_type` | string | See activity and state payloads below |
| `schema_version` | integer | Always `1` |
| `factory_id` | UUID string | Server-assigned; present on every event |
| `server_epoch` | UUID string | Identifies the current server process; changes on server restart |
| `run_id` | UUID string | Identifies the current simulation run; changes on restart-at-zero |
| `run_generation` | positive integer | Starts at 1; increments with each restart-at-zero |
| `event_sequence` | positive integer | Monotonically increasing, factory-wide, across all resets |
| `state_revision` | non-negative integer | Monotonically increasing within a run |
| `occurred_at` | RFC 3339 UTC timestamp | Wall time the event was created |
| `sim_time_ms` | non-negative integer | Simulation clock time in milliseconds |
| `causation_id` | UUID string or null | ID of the event or command that caused this event |
| `payload` | object | Event-specific payload; see below |

Factory identity is server-assigned. `server_epoch` identifies the current server process and changes on restart. `run_generation` starts at 1 and increments at restart-at-zero; a server process restart loses all factories, and re-registration creates a new `factory_id`. Consumers require the assigned `factory_id` even inside an isolated topic. A mismatched `factory_id` is ignored/quarantined, never displayed.

## Activity payloads

### `resource.delivered`

A single-resource delivery arrived at the factory. Each resource has its own independent delivery timer and fires its own event.

```json
{
  "delivery_id": "<UUID>",
  "delivery_sequence": 1,
  "resources": {
    "energy":  3,
    "resin":   0,
    "silicon": 0,
    "metals":  0,
    "copper":  0
  }
}
```

- `delivery_sequence`: positive integer, increments within a run across all resource deliveries.
- `resources`: all resource keys present; exactly one key is positive (the delivered resource); all others are zero.
- Each resource fires independently on its own `interval_sim_seconds` schedule defined in `simulation_rules.json`.

### `manufacturing.started`

A parts-fabrication station began a job.

```json
{
  "job_id": "<UUID>",
  "station_id": "structural_molding",
  "output_id": "chassis",
  "inputs": { "resin": 2, "metals": 1 },
  "duration_ms": 5000
}
```

- `station_id`: one of `structural_molding`, `electronics_assembly`, `actuator_fabrication`, `battery_assembly`.
- `output_id`: one of `chassis`, `electronics`, `actuator`, `battery`.
- `inputs`: object of resource IDs to positive integer quantities consumed.
- `duration_ms`: positive integer.

### `manufacturing.completed`

A fabrication job finished and a part was stored in inventory.

```json
{
  "job_id": "<UUID>",
  "station_id": "structural_molding",
  "part_id": "chassis",
  "quantity": 1
}
```

- `job_id`: matches the corresponding `manufacturing.started` event.
- `causation_id` on the envelope is the `job_id` of the `manufacturing.started` event.
- `quantity` is always `1`.

### `manufacturing.blocked`

A parts station cannot start a new job due to insufficient resources.

```json
{
  "station_id": "electronics_assembly",
  "missing_inputs": { "silicon": 3 }
}
```

- `missing_inputs`: object of resource IDs to required shortfall quantities.

### `assembly.started`

The robot assembly station started building a bee.

```json
{
  "job_id": "<UUID>",
  "station_id": "worker_assembly",
  "robot_type": "worker",
  "inputs": { "chassis": 1, "electronics": 3, "battery": 2, "actuator": 8 },
  "duration_ms": 8000
}
```

- `station_id`: `worker_assembly` for Spec 1.
- `robot_type`: `worker` for Spec 1.
- `inputs`: parts consumed; object of part IDs to positive integer quantities.

### `assembly.completed`

A complete bee robot rolled off the assembly line.

```json
{
  "job_id": "<UUID>",
  "station_id": "worker_assembly",
  "robot_id": "<UUID>",
  "robot_type": "worker",
  "display_number": 1,
  "quantity": 1
}
```

- `job_id`: matches the corresponding `assembly.started` event.
- `causation_id` on the envelope is the `job_id` of the `assembly.started` event.
- `display_number`: positive integer; human-readable count within the run.
- `quantity` is always `1`.

### `assembly.blocked`

Robot assembly cannot start because required parts are unavailable.

```json
{
  "station_id": "worker_assembly",
  "missing_inputs": { "chassis": 1, "actuator": 6 }
}
```

- `missing_inputs`: object of part IDs to required shortfall quantities.

## Station and part identifiers

| Station ID | Output |
| --- | --- |
| `structural_molding` | `chassis` |
| `electronics_assembly` | `electronics` |
| `actuator_fabrication` | `actuator` |
| `battery_assembly` | `battery` |
| `worker_assembly` | worker bee (assembly only, no part output) |

Part IDs: `chassis`, `electronics`, `actuator`, `battery`.

Resource IDs: `resin`, `silicon`, `metals`, `copper`, `energy`.

## Onboarding probe events

For provisioning verification only, all eight topics also accept a `connection.test` event with the standard envelope and payload `{"operation_id": "<UUID>", "probe": true}`. Use a `oneOf` per topic schema: primary event type or probe. Consumers validate and silently discard probes — they never create log rows, inventory entries, or jobs. The `.factory-state` probe uses an actual empty paused snapshot instead of a `connection.test` payload.

Probes consume event sequence numbers; sequence gaps in activity topics are normal.

## Factory state payload (`factory.state`)

Published to `.factory-state` (compacted). Full snapshot of observed factory state at a point in time.

| Field | Type | Description |
| --- | --- | --- |
| `lifecycle_status` | string | `provisioning`, `paused`, `running`, `stopped`, or `expired` |
| `running` | boolean | `true` only when `lifecycle_status == "running"` and no blocking error |
| `operational_error` | object or null | `{code, message}`; never contains secrets |
| `speed` | integer | `1` or `5` |
| `resource_deliveries` | array | Per-resource delivery state; see below |
| `resources` | object | All resource quantities (non-negative integers) |
| `parts` | object | All four part quantities (non-negative integers) |
| `stations` | array | Five station objects (four fabrication + one assembly); see below |
| `completed_robots` | object | `{count, last_robot_id}` |
| `last_applied_command_id` | UUID string or null | Last accepted lifecycle command |

Station object fields:

| Field | Type | Description |
| --- | --- | --- |
| `station_id` | string | One of the five station IDs above |
| `status` | string | `idle`, `working`, `waiting_for_resources`, or `waiting_for_parts` |
| `missing_inputs` | object | Resource or part IDs to required shortfall quantities; empty when not blocked |
| `job` | object or null | `{job_id, output_id, started_at_sim_ms, completes_at_sim_ms, duration_ms, consumed_inputs, progress_percent}` |

`progress_percent` is clamped to 0–100. Overall `paused`/`stopped` overrides whether an otherwise-working job progresses visually.

Resource delivery state object fields (one entry per resource):

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Resource ID (e.g. `energy`, `resin`) |
| `interval_sim_ms` | non-negative integer | Full delivery cycle length in sim-ms |
| `next_delivery_sim_time_ms` | non-negative integer | Absolute sim-ms when next delivery fires |
| `next_delivery_in_ms` | non-negative integer | Remaining sim-ms until next delivery |
| `quantity` | positive integer | Units delivered each cycle |

### Publish cadence

- At most 5 snapshots per wall second while running.
- At most 1 per wall second while paused or stopped (until expiry).
- Immediately after lifecycle commands and factory creation.
- One best-effort expired snapshot on factory expiry.

Snapshots never carry access tokens, Kafka secrets, owner PII, or server configuration.

## In-memory producer and consumer

Apply each simulation transition and enqueue its outgoing records under a factory lock, after checking buffer capacity. No database or transactional outbox is used. A background publisher sends oldest first and removes records after acknowledgment. Retried records retain their IDs while the process lives. Calls to Kafka occur outside the lock. A crash loses pending records and factory state; crash-safe delivery is not promised.

The local consumer also uses an in-memory projection, activity ring buffer, and duplicate-ID cache. Validate `factory_id` and `server_epoch` against the currently registered factory, then compare snapshots by `(run_generation, state_revision, event_sequence)`. Replace state only with a strictly newer snapshot. Activity records may arrive before their run's snapshot; buffer them within a bounded history and show only the current observed run. Ignore `connection.test` probe events. Never update the factory itself.

A local app restart clears its view. Authenticate and obtain the current server epoch and owned factory again, then replay with a new session consumer group from earliest available records. The compacted state topic provides the latest observed snapshot; activity history is limited by topic retention and the local ring buffer. Broker offsets are not a durable local projection. Do not reuse an old group's end offsets and assume a cleared view can restore itself.

If the server has restarted, require registration with a new `factory_id`. Old Kafka records remain transport history and must not revive a lost simulation. Duplicate suppression is bounded and process-local; full-state replacement avoids additive inventory errors even after the cache evicts IDs. Invalid records are counted and logged in a bounded in-memory quarantine, not a persistent audit store.

## Observation health

Track `produced_at` (from `occurred_at`), `consumed_at`, and latest valid snapshot age. Default stale threshold: 3 wall seconds, adjusted for known clock skew; warn if clocks differ materially. Receiving an old replay does not make it fresh. Show `awaiting_events`, `live`, `stale`, or `catching_up`. Stop visual interpolation when stale; do not manufacture progress beyond consumed sim time. Transport health and command receipts can be shown separately from observed factory state.
