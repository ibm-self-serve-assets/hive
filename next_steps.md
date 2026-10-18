# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.
Flink work lives in `spec-2-implement-flink/`.

## Working agreements

- **Keep the specs current.** Whenever the simulation, the attendee backend/frontend code, or the Flink SQL changes, update the matching spec `.md` files in the same change:
  - `spec-0-simulation/` specifications and README
  - `spec-1-connect-simulation/` specifications and README
  - `spec-2-implement-flink/` README and the comments in the SQL files
  - `spec-3-hive-dashboard/` specifications and `attendee_get_started.md`
- **Audience.**
  - **Spec 0 (simulation) is written for instructors.** It can describe hidden state, server internals and the answer key.
  - **Specs 1, 2 and later are written for attendees.** They must not reveal the simulation's hidden counters or internals, and the SQL files must stay commented well enough to run without help.
- **Attendee SQL is run in the Confluent Flink workspace, one statement per run.** Prefer a small number of files that each run once.
- **Say what is untested.** Most Confluent behavior so far is confirmed only from workspace screenshots.

## Goal

Window-based stream processing in Confluent Flink that adds derived data to the stream, based on
`spec-shared/schemas/event_payloads.json`. First step: the time between each job's `started` and `completed` events.
Then attendees rebuild inventory themselves from the events (see Architecture).

## Current state

| Item | Status |
|---|---|
| `flink/01_create_sink.sql` | **Verified deployed** in Confluent Cloud. Table created successfully. |
| `flink/02_run_jobs.sql` | **Verified running** in Confluent Cloud (`EXECUTE STATEMENT SET` processing live factory events with 0 lag). |
| `flink/03_validate.sql` | **Verified passing** in Confluent Cloud (Checks A-C return expected derived durations and aggregations). |
| `README.md` | Updated with conceptual context, exact Flink pool creation steps (GCP/Dallas), SQL workspace renaming (`hive_job_durations`), cell deletion workflow, and Flink console monitoring screenshots (screenshots 1-8). |

Verified in the Confluent workspace (from screenshots):
- The six source tables appear as raw `VARBINARY` `key`/`val` plus `$rowtime`.
- Parsing works: `CAST(val AS STRING)` plus `JSON_VALUE` returns `job_id`, `sim_time_minutes` and `occurred_at`.
- A manufacturing-only preview join returned rows, with `elapsed` matching the planned duration (10000 ms).
- Topic event counts were roughly: gathering 1031/1026, manufacturing 534/531, assembly 11/11 (started/completed).

Done: Flink `job_durations` stream correlation verified live in Confluent Cloud.
Next immediate priority: Build the simplified foundation UI for Spec 1 (basic Confluent-to-UI connection & accelerated Days/Hours/Minutes sim clock).

## Design decisions (Flink)

- **Pairing key:** started and completed events share `payload.job_id`.
- **Source topics stay plain JSON.** The server and dashboard are unchanged for this step. Flink reads the raw bytes and parses them.
- **Output:** a Flink-owned table/topic `job_durations`. Do not create that topic in `provision_topics.py`.
- **Join window:** completed event from 5 s before to 1 min after the started event, on Kafka record time (typical gap is 5-15 s). Widen the upper bound if simulation speed is lowered.
- **Duration columns:** `elapsed_sim_minutes` (exact, speed-independent), `elapsed_wall_s` (whole seconds, coarse), `planned_duration_ms`.
- **Added columns:** `started_topic` and `completed_topic`, alongside `stage`.
- **Determinism:** no `NOW()`, `UUID()` or `RAND()`. Only source event fields are used.
- **Tableflow:** all topics are to be written to Tableflow via Flink-owned tables. Tableflow needs registered schemas, so Schema Registry is required for the Flink output tables. Changelog mode is fixed at first materialization: `job_durations` is `append`.
- **Format:** the sink uses `json-registry` (JSON_SR). JSON_SR was recommended because the repo's contract is already JSON Schema. Avro remains an option (smaller payloads, strong evolution support) at the cost of a second set of schemas. Both work with Tableflow.
- **Specs stay neutral on Schema Registry.** Statements saying it is not needed were removed (cost and complexity are still being weighed).

## Lessons learned in the Confluent workspace

- The workspace accepts **one statement per run**, so multiple `ALTER`s cannot be pasted together. The `ALTER TABLE ... MODIFY` step was dropped in favor of `CAST(val AS STRING)` inside the jobs.
- `JSON_VALUE ... RETURNING BIGINT` is unsupported. Use `CAST(JSON_VALUE(...) AS BIGINT)`.
- `occurred_at` is `2026-10-18T02:49:47.492738+00:00`. Flink cannot parse the `+00:00` suffix, so it is stripped and the value is read as `TIMESTAMP(3)` (UTC).
- The `CAST_BINARY_TO_STRING` warning is informational and safe to ignore. `CAST(val AS STRING)` is universally compatible with both `BYTES` and `STRING` columns, whereas `MAKE_VALID_UTF8` fails if `val` is already typed as `STRING`.
- `connection.test` probe rows appear on activity topics with a NULL `job_id`. They never match in the join.
- Streaming queries keep running until stopped. Click Stop to avoid using compute pool capacity.
- Topics hold 24 h of history, so the first deploy processes a backlog from earlier runs.

## Architecture decisions (inventory, coins, management)

**Principle: the simulation is the only authority.** The factory is a black box owned by the workshop instructors. It keeps hidden state, including its own internal counters, which are the answer key. Attendees can view its events but must rely on the event streams in their own Confluent instance. The simulation never reads from an attendee's Confluent, since attendees could cheat or break things.

- **Attendees rebuild the counts in Flink.** Resources, parts and robots (later coins) are derived from the events. If Flink, Tableflow and the simulation disagree, something is off, and finding it is part of the exercise.
- **Invalid commands are rejected by the simulation.** For example, selling a robot that does not exist returns an error and changes nothing.
- **Every state change needs an event.** Attendees can only rebuild what the events show. Any command that changes state (sell, upgrade, assign) must publish an event with the deltas. Rejections change nothing, and may publish a separate `*.rejected` event that has no effect on inventory.
- **The factory keeps its internal counters for scheduling** (option A1). Stations start based on its own inventory, and these counters are hidden. They are never published.
- **Hidden counters cannot be published to an attendee cluster,** because attendees hold the keys there. The check against the answer key has to run inside the simulation, or by instructors reading the simulation directly.

Events already carry every inventory change:

| Change | Event | Delta |
|---|---|---|
| Resource up | `gathering.completed` | `+quantity` |
| Resource consumed | `manufacturing.started` | `-inputs[resource]` |
| Part up | `manufacturing.completed` | `+1` |
| Part consumed | `assembly.started` | `-inputs[part]` |
| Robot up | `assembly.completed` | `+1` |

**Tables attendees build:**
- **Ledger** (append, one row per change, with `item_type` such as `resource`, `part`, `robot` and later `coin`, plus the reason and `job_id`). It answers "what changed, and why".
- **Balances** (upsert, `SUM(delta)` by `factory_id`, `run_id`, `item_type`, `item_id`). It answers "how many now". Keying on `run_id` makes a restart at zero reset the totals.
- **One ledger and one balances table for now,** with coins added later as extra `item_type` rows. Split them only if it gets awkward.
- Optional: windowed production and consumption over the ledger.

**Future layer (not started):**
- Robots are sellable for coins, and coins buy equipment upgrades.
- Robots can be assigned to factory components to raise productivity.
- Sales, upgrades and assignments are handled by a separate management component, the queen bee, to be plugged into an agent harness via MCP.
- Sales and upgrades fit the ledger as extra delta rows. Assignment modifiers need something the factory reads back, probably a separate command path to the simulation.

## Required changes (not started)

1. **Remove `resources`, `parts` and `completed_robots` from `factory.state`.** Today they are required in `spec-shared/schemas/event_payloads.json` and visible to attendees, which gives away the answer key.
2. **Dashboard:** `frontend/src/types.ts`, `frontend/src/components/ManufacturingFloor.tsx`, `backend/models.py` and `tests/test_store.py` use those fields. Decide whether the inventory panel disappears until attendees build their own, or reads their Flink balances.
3. **Server-side reconciliation:** decide between an instructor-side comparison (no new API) and an attendee verify call that answers match or mismatch without revealing counts. A verify call needs an exception to `05_event_contract.md`, which says no server inventory endpoint should bypass Kafka observations.
4. **Cluster setup:** `.env.example` has attendees bringing their own cluster and key, while `06_confluent.md` recommends organizer-managed clusters. Nothing in an attendee cluster can be trusted, which is fine as long as the simulation never reads from it.
5. **Check starting inventory.** The factory appears to start at zero. Confirm, and add an opening balance row if it does not.
6. **Check `state_revision` and `event_sequence`** so the instructor comparison can line up at the same point in time. Not verified that every transition increments them consistently.
7. **`factory.initialized`** is published to the state topic but is missing from `event_payloads.json`. `connection.test` probes also land on every activity topic. Both matter for Tableflow's one-schema-per-topic rule.
8. **Known mismatch causes:** a server crash loses unsent events (the buffer is in memory), and a restart at zero creates a new `run_id`.
9. [x] **Docs inconsistency:** `attendee_get_started.md` and `provision_topics.py` resolved to consistently describe all 10 topics defined in schema.

## Open items & roadmap

1. [ ] **Step 1 — Simplified Foundation UI (Spec 1 Hive Dashboard)**:
   - **Basic Confluent Connection**: Create a clean, simple UI that shows the direct stream connection from Confluent topics to the dashboard.
   - **Stream-Only Activity**: Display only the raw discrete `*.started` and `*.completed` events as they arrive from Kafka (no pre-calculated or leaked inventory answer keys).
   - **Simulation Clock (Days, Hours, Minutes)**: Update sim time formatting from raw milliseconds to an accelerated simulation calendar format: `Day X, HH:MM` (or `X days, Y hrs, Z mins`). The clock advances at the accelerated simulation rate rather than tracking real-world wall clock time.
2. Tableflow runbook: enable and teardown commands, storage (managed or own bucket), format (Iceberg or Delta). Teardown order: Tableflow topic, Flink statements, Flink table, Kafka topic, schemas.
3. Write the ledger and balances SQL for attendees in the same style as `job_durations` (few files, each run once, commented).
4. List the events the future sell, upgrade and assign commands need, so the contract is ready for the queen bee.
5. Windowed aggregation (window size and metrics not chosen).
6. Optionally filter probes explicitly, and decide between processing all history or only new events (or filtering by `run_id`).
7. After each change above, update the spec `.md` files per the working agreements.

## Caveat

Most of this has not been run end to end. The Confluent behavior above comes from workspace screenshots, and the rest is based on reading the code and the Confluent skill references.
