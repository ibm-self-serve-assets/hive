# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.

- **Unified Dashboard Architecture**: Single UI install in `level-1-environment-setup/` with dropdown for Level 1, Level 2, Level 3 progression.
- **Automated Validation**: Tests validate that attendees have completed steps for the selected level to function.
- **Levels Organization**:
  - `level-1-environment-setup/`: Unified dashboard (FastAPI backend + React/TypeScript/Vite frontend); credentials, launch, SSE events, simulation controls, auto-connection.
  - `level-2-intro-to-flink/`: Confluent Flink interval joins, job durations correlation (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`).
  - `level-3-hive-inventory/`: Flink stateful aggregations into the `hive_inventory_balances` upsert topic.
  - `level-4-gamify/` (empty) and `level-5-tableflow/` (empty): folders created, nothing written yet. See "Level numbering" below.
  - `backup_ui/`: Archived Level 3 prototype (real-time inventory reconciliation, material ledgers, Flink balances, Tableflow sync). Reference only — superseded by `level-1-environment-setup/`.
- **Simulation Server**: In `simulation-instructor-only/` (memory-only, instructor-managed authority).

## Working agreements

- **Keep the levels current.** Whenever the simulation, attendee backend/frontend code, or Flink SQL changes, update the matching level `.md` files in the same change:
  - `simulation-instructor-only/` specifications and README
  - `level-2-intro-to-flink/` README and SQL comments
  - `backup_ui/` (archived — no active maintenance required)
  - `level-1-environment-setup/` (README, topic provisioning scripts in `scripts/`, single unified frontend and backend)
- **Audience.**
  - **Simulation server (`simulation-instructor-only`, including `orders-calculator/`) is written for instructors.** It describes hidden state, server internals, and the answer key.
  - **Levels 0, 1, 2, 3 (and the Level 4 screen) are written for attendees.** They do not reveal the simulation's hidden counters or internals.
- **Hidden internal state stays out of the payloads.** Attendees receive only the events and the `simulation.state` snapshot as currently defined in `spec-shared/schemas/event_payloads.json`. The simulation's internal counters (for example the per-station staging carts, see below) are not added to any event or snapshot, and are not recomputed in the attendee dashboard backend either. Do not add fields such as `staged_inputs` to the schema, the models, or the dashboard.
- **One source of truth.** Don't duplicate values that live in `simulation_rules.json` or `event_payloads.json` in notes or docs; point to the file instead.
- **Attendee SQL is run in the Confluent Flink workspace, one statement per run.** Prefer a small number of files that each run once.

## Goal

Window-based stream processing in Confluent Flink that adds derived data to the stream, based on
`spec-shared/schemas/event_payloads.json`. First step: the time between each job's `started` and `completed` events.
Then attendees rebuild inventory themselves from the events (see Architecture).

## Current state

| Item | Status |
|---|---|
| `simulation-instructor-only/` | **Cart / staging logic implemented** (see below). All 18 tests pass, including `tests/test_api.py` (run `python3 -m pytest` from this folder; `pytest.ini` puts `spec-shared` on the path). |
| `level-1-environment-setup/` | **Unified UI installed**. Levels 1–3 screens, inventory strips, spinners, blocked state, FlowDots, URL hash routing. Level 2 `isReady` gate shows "New simulation run required" / "Waiting for Flink…" prompt when stale. Schema Registry 5-byte magic prefix stripped in both Flink topic consumers. |
| `level-2-intro-to-flink/` | **Complete.** Verified deployed in Confluent Cloud. Tables, jobs, and validation passing (`hive_job_durations` stream join). README links and step lettering fixed. |
| `level-3-hive-inventory/` | **Flink SQL written** (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`). CLI-first README done. Dashboard Level 3 screen built and gated on `hive_inventory_balances` topic. |
| Level 4 dashboard screen (`levels/level4/`) | **In progress, uncommitted.** Orders and treasury sidebar, per-station add/upgrade controls, coins = robots sold × price − spent. Purchases are tracked client-side only (`Level4Context.tsx`); the server does not know about them. Gated on `hive_inventory_balances` like Level 3. |
| `simulation-instructor-only/orders-calculator/` | **Calculator done, not integrated.** Analytical capacity model, greedy upgrade simulator and order schedule generator. 7 tests pass (the whole suite is 25). Nothing in `server/` uses it. See `orders_calculator.md`. |
| `backup_ui/` | Archived Level 3 prototype. Superseded by `level-1-environment-setup/`. |

## Level numbering (needs a decision)

The docs and the dashboard disagree:

- `Hive_Workshop_Overview.md` plans **Level 4 = Tableflow**, Level 5 = headless agent and IBM Bob, Level 6 = Bob runs the simulation.
- The dashboard's **Level 4** is the gamified orders / treasury screen, and the folders on disk are `level-4-gamify/` and `level-5-tableflow/`.

Pick one numbering and update the overview, the folder names, the registry label and the Tableflow roadmap item together.

## Event and snapshot additions (uncommitted)

Both are in `spec-shared/schemas/event_payloads.json`:

- `manufacturing.resources.acquired` and `assembly.parts.acquired`: emitted each time a station's cart receives a delta of inputs. They carry only the delta (`inputs_grabbed`), not the cart total, so the hidden-cart rule still holds. The dashboard backend (`store.py`) accepts them with no state change. Check that they are included in `provision_topics` / `delete_topics` for Level 1 and in the Level 1 docs.
- `debug_mode_instructor_only` on `simulation.state`: ground-truth inventory, `null` unless the instructor turns debug mode on in `/admin`. It violates "hidden state stays out of the payloads" when on, so it must stay off in workshops. `store.py` already reads it to bypass Flink inventory. Document this in `INSTRUCTOR_GUIDE.md`.
- `simulation_rules.json` gained `simulation_time.max_sim_weeks` (2). The server (`rules.py`) and the orders calculator both read it.

## Orders calculator (new)

`simulation-instructor-only/orders-calculator/` (docs in `orders_calculator.md`) computes what the simulation can produce and builds an order schedule from it. Key results with the current rules:

- The energy supply is a hard cap on throughput (about 65 robots per sim day). Every station maxed, so no purchase plan beats it.
- Greedy-optimal play reaches that cap at sim minute 929 (about 15.5 sim hours; 15.5 real minutes at 1x). Output is flat after that.
- The calculator is an analytical model. It has not been compared with a real run.
- Timing: the sim clock is 1 real second = 1 sim minute, so 2 sim weeks (20,160 sim minutes) take **5.6 real hours** and 1 sim week takes 2.8 hours. There is no 5x speed in `server/` yet.

### Design decision: the simulation tracks orders, not purchases

- **The server owns orders.** Station purchases and upgrades are not a simulation concern (the dashboard keeps its own coin spending).
- **`placeOrder()`** runs at points computed with the logic in `calculator.py` (`OrderScheduleGenerator` and the capacity model). It emits an order-placed event.
- **`fulfillOrder()`** runs automatically whenever a robot is assembled. Orders are always present to accept the robot, so every robot is sold the moment it is built. It emits an order-fulfilled event with the **robot type** and the **coins received** (price from `robot_metadata` in `simulation_rules.json`, so the price is not duplicated).
- **Event names.** The brief says "order-placed" and "order-fulfilled". Existing events use dotted names (`manufacturing.resources.acquired`), so confirm `order.placed` / `order.fulfilled` before adding them to `event_payloads.json`, `provision_topics.sh` and `topics.py`.
- **Open conflict.** "An order is always present" removes the deadline pressure that `OrderScheduleGenerator` produces (`deadline_sim_minute`, 60/80/95% difficulty). Decide what an order now is: a standing demand slot whose `placeOrder()` timing keeps one open at all times, or a deadline order that can expire. The generator needs to change either way.

### Dashboard: replace Robot inventory with Orders and Treasury (Level 4 screen)

On the Level 4 screen (`levels/level4/Level4Screen.tsx`), the **Robot inventory** panel above **Robot assembly** must be replaced by **Orders** and **Treasury**.

- Move the Orders and Treasury sections out of the left sidebar (`components/Sidebar.tsx`, the "Level 4 Orders & Treasury" block) into that slot, then delete them from the sidebar.
- Delete the Robot-inventory code from Level 4: the panel, the `ROBOTS` inventory rendering and the `useLevel4` coin lookup in the sidebar.
- Drive Orders and Treasury from the new events, not from `state.inventory.robot`. Coins earned are the sum of `coins` in the order-fulfilled events, and spending stays in `Level4Context.tsx` (`coins = earned - spent`; the current `earnedCoins` multiplies robot counts by `ROBOT_PRICES`, which should go).
- Add the event types to the dashboard backend (`store.py`) and `types.ts` as optional fields, so Levels 1 to 3 are unaffected.
- Do not touch Level 3's Robot inventory (`levels/level3/Level3Screen.tsx`). A shipped level stays frozen, and it reads `hive_inventory_balances`.
- Replace the "filled orders" proxy in `simulation-instructor-only/server/app.py` (admin page) with real order data.

### Open questions

- [ ] Compare the model with a real simulation run (cart staging and start-up delays make real output lower). Start with a baseline run with no upgrades.
- [ ] Implement `placeOrder()` / `fulfillOrder()` in `server/simulation.py` and the two events in `event_payloads.json`, with tests in `simulation-instructor-only/tests/`.
- [ ] Decide the order model (see "Open conflict" above) and revisit the calculator output accordingly.
- [ ] Rename `orders-calculator/` (hyphen) if it must be imported as a package by the server.
- [ ] Move `max_slots` and the reward multipliers from `calculator.py` into `simulation_rules.json`.

## Simulation scheduling: cart / staging logic (done)

Implemented in `simulation-instructor-only/server/simulation.py` (`SimulationRun.carts`, `_stage_inputs`, `_schedule_parts_manufacturing`, `_schedule_robot_assembly`).

- The old all-or-none check starved multi-unit recipes: stations needing only 1 of a shared resource (metals) consumed every single delivery on arrival, so a station needing several (actuator fabrication) never accumulated enough. Robot assembly had the same issue waiting for all its parts at once.
- Each station now has an internal cart. On every scheduling pass an idle station moves `min(still needed, available)` of each required input from simulation stock into its cart, and starts its job (consuming the cart) once the cart holds the full recipe. Assembly does the same with finished parts.
- Manufacturing stations are served fewest-completed-parts first. A station keeps a partial cart until the recipe is complete.
- Staged items leave simulation stock, so `resources` and `parts` in `simulation.state` are net of carts. A station's `missing_inputs` (in `manufacturing.blocked` / `assembly.blocked` and in the snapshot) now means what its cart still lacks.
- **Carts are hidden from attendees.** There is no cart field in any event or snapshot, and none is derived in the dashboard (see Working agreements). Attendees can only reconstruct totals from events; the per-station breakdown stays internal.
- Tests added in `simulation-instructor-only/tests/test_simulation.py`; the resin conservation test counts resin held in carts.
- Docs updated: `02_simulation.md`, `03_data.md`, `INSTRUCTOR_GUIDE.md`, `simulation-instructor-only/README.md`. The old text described the rotating tie-break cursor from the last commit; the working tree had already replaced it with fewest-completed-first ordering, so the docs now describe that. The unused `SimulationRun.station_cursor` was removed.

## Mission: one UI per level (dashboard architecture)

Each workshop level gets its own dashboard UI, and each level's UI improves on the previous one. Adding Level N must never break Levels 1 to N-1.

**Done:** the Levels dropdown is in the sidebar of `level-1-environment-setup/frontend` and lists Level 1 and Level 2. The sidebar order is: Levels, a divider, then Simulation controls (a plain green dot with "Connected", then the buttons) and Simulation Time. Level 2 is currently an unchanged copy of Level 1 (`levels/level2/Level2Screen.tsx`), the starting point for its improvements. Level 1 is the current UI (Gather resources, Manufacture parts, Assemble robots, with event panels).

### Architecture decision: a full screen per level

Two options were considered:

1. **A main screen per level** that contains all of its elements.
2. **Shared components** (Resource gathering, Parts manufacturing, Robot assembly, ...) that every level reuses.

We chose option 1 as the base. Reason: with shared components, improving a component for Level 3 changes what Level 1 shows, and each fix needs a regression check across levels. With a screen per level, a level is frozen once it ships and a new level starts from a copy of the previous one. The cost is some duplication. To limit it, only truly identical, presentation-only pieces are shared (for example `components/FlowDots.tsx`, `EventPanel.tsx`, `Sidebar.tsx`). If a shared piece needs a level-specific change, copy it into that level's folder instead of adding flags.

### Layout (`level-1-environment-setup/frontend/src/`)

- `levels/types.ts`: `LevelScreenProps` (the contract every screen receives, currently `state: DashboardState`) and `LevelDefinition` (`id`, `label`, `Screen`).
- `levels/registry.ts`: the `LEVELS` list. The dropdown is built from it and `DEFAULT_LEVEL_ID` is its first entry.
- `levels/level1/Level1Screen.tsx`: Level 1's screen.
- `App.tsx` holds the selected `levelId` and renders the matching `Screen`, or the level's `Requirements` while the level is locked. `components/Sidebar.tsx` renders the dropdown from `LEVELS` and hides the simulation buttons and Simulation Time while the level is locked.

### To add a level

1. Copy the previous level folder, for example `levels/level1/` to `levels/level2/`, and rename the screen.
2. Change only the new copy.
3. Append one entry to `LEVELS` in `levels/registry.ts`.
4. If the level needs data the dashboard does not provide yet, add it to the backend store and `types.ts` as optional fields, so earlier levels are unaffected.
5. Update the matching level docs (see Working agreements).

### Mission to-do

- [x] Levels dropdown with Level 1 only; Level 1 uses the current UI.
- [x] Screen-per-level framework (`levels/types.ts`, `levels/registry.ts`, `levels/level1/`).
- [x] Level 2 added to the dropdown as a copy of Level 1.
- [x] Decide what each of Levels 2 and 3 adds to the UI (Level 2: job durations + blocked state + input chips from the Flink `hive_job_durations` stream; Level 3: ledger and balances). `levels/level2/` built.
- [x] Fold Level 3 into `levels/level3/` — `Level3Screen.tsx` and `Level3Requirements.tsx` built directly in the unified dashboard; `backup_ui/` is archived reference only.
- [x] Level 2 gate: while the `hive_job_durations` topic does not exist, the main area of Level 2 shows a centred lock message (`levels/level2/Level2Requirements.tsx`, icon `public/icons/svg/lock.svg`) instead of the Level 2 screen, and the sidebar hides the simulation buttons and Simulation Time. Only the Levels dropdown and the connection status remain. A level opts in via optional `isUnlocked` and `Requirements` on its `LevelDefinition`. The backend (`backend/topic_watch.py`, `CalculatedValuesWatcher`) polls Confluent for the existence of the `hive_job_durations` topic and sets `hive_job_durations_ready` in the dashboard snapshot. It stays set once true. It only lists topics; it never reads records, and the topic is empty until the simulation runs.
- [x] Gate Level 3 the same way: `hive_inventory_balances` topic existence sets `hive_inventory_balances_ready`; `Level3Requirements.tsx` shown until unlocked. Backend: `InventoryBalancesWatcher` + `InventoryBalancesConsumer` in `topic_watch.py` / `consumer.py`.
- [x] Persist the selected level: URL hash routing (`#level-1`, `#level-2`). A page refresh restores the level; browser back/forward buttons work. `localStorage` fallback not needed.
- [x] Level 2: dotted flow line (`components/FlowDots.tsx`) wired between the three lanes, animated when `state.running` is true.
- [x] Level 1 + Level 2: event panels start **collapsed** by default. The count badge in the header always shows the running total, so attendees see activity without the panels obscuring the main content. Click to expand.
- [x] Level 2 `isReady` gate: a second predicate on `LevelDefinition` (`isReady`) hides sim time and shows a contextual prompt when the level is unlocked but the current run has no Flink data yet. While `running` is true the prompt reads "Waiting for Flink…"; before restart it reads "New simulation run required". Sim time reappears as soon as `running` is true; floor UI appears once `job_durations` has data.
- [x] Schema Registry wire format fix: `hive_job_durations` and `hive_inventory_balances` use `json-registry` (Confluent Schema Registry JSON format). Records are prefixed with a 5-byte magic header (`0x00` + 4-byte schema ID). Both `CalculatedValuesConsumer` and `InventoryBalancesConsumer` now strip this prefix before JSON parsing. Previously the parse silently failed at `DEBUG` level, so no records were ever ingested.

- **Two Flink output topics are now the design:** `hive_job_durations` (append, durations) and `hive_inventory_balances` (upsert, live stock levels). These are intentionally separate — different changelog modes, different consumers, different dashboard levels. Do not merge them.

## Simulation notes: assembly and `duration_ms`

- `simulation_rules.json` has a single `assembly` list (like `resources` and `manufacturing`) covering `worker_assembly` (engineer) and `forager_assembly` (forager). The forager placeholder is gone. The forager is scheduled with the same cart logic as manufacturing: each pass moves what is available into its cart until the recipe is complete. Both stations are in `simulation.state`, so it now requires 6 stations.
- `duration_ms` was removed from every event and the snapshot. Durations stay internal to the simulation. Attendees derive elapsed time from the `started` and `completed` sim times (this is what the Level 2 `hive_job_durations` join does).
- Restart the simulation and the dashboard backend to pick these changes up.
- Checked: the Level 3 backend and frontend work with a sixth station.

## Sources of truth

Do not copy recipe quantities, delivery intervals or durations into these notes. Look them up in:

- `simulation-instructor-only/schemas/simulation_rules.json`: resources, delivery intervals and quantities, recipes, job durations.
- `spec-shared/schemas/event_payloads.json`: event and `simulation.state` payload shapes.
- `simulation-instructor-only/orders-calculator/orders_calculator.md`: throughput model and order generation (derived from `simulation_rules.json`; do not copy its numbers elsewhere).

## Open items & roadmap

1. [x] **Unified Dashboard Scaffolding**: Moved backend and frontend to the unified dashboard (now `level-1-environment-setup/`).
2. [x] **Folder Renaming**: Renamed `spec-1/2/3-*` to `level-1/2/3-*`; unified dashboard folder is `level-1-environment-setup/`.
3. [x] **Cart / Staging Logic**: Incremental per-station staging for manufacturing and robot assembly (see above).
4. [x] **Level Selector & Validation Hook**: The dropdown and the `isUnlocked` / `isReady` gates are done (see Mission above). A separate backend validation endpoint was dropped: the gates already tell attendees when a level is not configured.
5. [x] **Inventory Flink SQL (`level-3-hive-inventory/`)**: `hive_inventory_balances` upsert topic. Three jobs: resources, parts, robots. CLI-first README done.
6. [ ] **Tableflow Runbook** (see "Level numbering" above for which level this is): Iceberg sync and data lakehouse integration instructions for both `hive_job_durations` and `hive_inventory_balances`.
7. [x] **Fix `simulation-instructor-only/tests/test_api.py`**: import error on `topics`. Cause: `topics.py` lives in `spec-shared/`, which only `start_server.sh` added to `PYTHONPATH`. Fixed with `simulation-instructor-only/pytest.ini` (`pythonpath = . ../spec-shared`).
8. [ ] **Deploy the simulation server on Google Cloud Run, then load test it for 150 users.** Details in "Cloud Run deployment and load test" below.
9. [ ] **Move the simulation server to a separate repo, then deploy it to Google Cloud Run.** Do this before item 8's deploy step, so Cloud Run is set up from the new repo. Details in "Move the simulation server to its own repo" below.

## Move the simulation server to its own repo

Move `simulation-instructor-only/` out of this repo into a separate repo, then deploy it to Google Cloud Run (see "Cloud Run deployment and load test" below). The server is instructor-only, so a separate repo also keeps the hidden state and answer key out of the attendee repo.

- [ ] Create the new repo and decide its name and visibility (private, since it holds the answer key).
- [ ] Move the folder, keeping git history if possible (for example `git filter-repo --path simulation-instructor-only`).
- [ ] **Resolve the `spec-shared/` dependency.** The server imports `topics` from `spec-shared/` (`server/producer.py`, `server/simulation_manager.py`) and reads its schemas. These files currently depend on the sibling folder:
  - `start_server.sh` and `pytest.ini` (`PYTHONPATH` / `pythonpath` include `../spec-shared`)
  - `Dockerfile` (`COPY ../spec_shared/`, which is also broken, see Cloud Run item below)
  - `tests/test_schema_validation.py` and `specifications/scripts/setup_validation.py` (path to `spec-shared/schemas`)
  - Decide how the two repos share `spec-shared/`: a copy with a sync step, a git submodule, or a published package. Keep one source of truth (see Working agreements).
- [ ] Update the paths above to match the decision.
- [ ] Update references in this repo: Working agreements, "Sources of truth", "Current state" and the level docs that point at `simulation-instructor-only/`, plus `Hive_Workshop_Overview.md`.
- [ ] Check the new repo's `.gitignore` still excludes `.env` and `.venv`, and that no secrets are carried over.
- [ ] Add CI in the new repo that runs the tests (`python3 -m pytest`).
- [ ] Deploy the new repo to Google Cloud Run (the Cloud Run section below).
- [ ] Remove `simulation-instructor-only/` from this repo once the new repo and the deployment are verified.

## Cloud Run deployment and load test

### 1. Deploy `simulation-instructor-only/` on Google Cloud Run

The current deployment target is IBM Cloud Code Engine (`Dockerfile` header, `specifications/07_code_engine.md`). Cloud Run needs these decided or changed:

- **One instance only.** The server is memory-only, so set min instances = 1 and max instances = 1 (the Code Engine spec says the same). Cloud Run's default is to scale out, which would split the simulations across processes.
- **CPU always allocated.** The clock ticks and Kafka sends happen in a background task with no HTTP traffic. Cloud Run throttles CPU outside requests by default, so use "CPU always allocated" (instance-based billing), or the sim will stall between requests.
- **Request timeout.** Check any long-lived connection (the dashboard backend's event stream, if it holds one open to this server) against Cloud Run's request timeout (up to 60 minutes). A run lasts 2.8 to 5.6 real hours.
- **One worker process, no reload.** Same as the Code Engine spec.
- **Redeploy resets all simulations.** Cloud Run keeps old and new revisions overlapping while it shifts traffic, which the spec forbids. Send 100% of traffic to the new revision only after the old one is stopped, or accept a maintenance window.
- **Secrets.** Organizer enrollment/token hashes and cluster profiles go into Secret Manager, not the image.
- **Fix the image first.** The `Dockerfile` has `COPY ../spec_shared/ ./spec_shared/`, which cannot work (a Docker build context cannot read its parent, and the folder is `spec-shared`). Build from the repo root or copy the shared folder in.
- **Update the docs:** `07_code_engine.md` (or add a Cloud Run page), `README.md`, and `INSTRUCTOR_GUIDE.md`. Keep one deployment page per platform.
- **Open question:** TTL is 20160 seconds (5.6 hours) and a run is 2 sim weeks. Check that the Cloud Run instance outlives a full workshop day.

### 2. Load test for 150 users without 150 Confluent Cloud clusters

Goal: show that one instance holds 150 simulations running at once. Real Confluent connections are not needed to test the simulation and API load.

- **Replace the Kafka producer, not the server.** `SimulationKafkaProducer` (`server/producer.py`) already falls back to an in-memory mock when `confluent_kafka` is missing. Add an explicit switch, such as `KAFKA_MODE=mock` or `null`, that makes `SimulationKafkaProducer` discard messages (optionally after a fixed fake delay and a configurable failure rate). Use it only for load testing, and make sure it cannot be turned on in a workshop by accident.
- **Cover the rest of the connect path.** Provisioning calls `verify_permissions_and_topics`, which talks to Kafka. The mock must return success without a network call, so simulations reach the running state.
- **Simulate 150 users.** A script (Locust or k6, or plain asyncio) that, for each virtual user, creates a simulation, connects, starts it, polls the simulation status and the admin page, then restarts it. Include pause and stop, and the dashboard backend's usual request pattern.
- **Match real behaviour.** Use 1x speed and run for at least one full sim week (2.8 real hours), or a shorter window under load to find limits, then one long soak run.
- **Measure:**
  - Tick lag: does the sim clock stay at 1 sim minute per real second with 150 simulations? This is the key number.
  - CPU and memory per instance, and the memory growth over the soak.
  - Request latency (p50, p95, p99) and error rate.
  - The buffer fill and drops against `FACTORY_BUFFER_LIMIT_EVENTS` and `FACTORY_BUFFER_LIMIT_BYTES`.
  - Event volume per second across all simulations. This is also the load Confluent Cloud will see in a real workshop, so compare it with the cluster's throughput limits.
- **Check the guards.** `specifications/07_code_engine.md` calls for a maximum-simulations limit, but `server/config.py` has no such setting (only the buffer limits and the TTL). Add it, then test the TTL cleanup and the rejection of the 151st user.
- **What it will not show:** real Confluent latency, throttling, and authentication failures. Test those with a few real clusters (say 3 to 5 attendees) before the class.
- **Pass criteria (to agree):** for example, tick lag under 1 sim minute, p95 latency under 500 ms, no dropped events, and memory flat over the soak.
- **If it fails:** the server is single-process with in-process locks, so the fix is to make the tick loop cheaper or to shard simulations across servers, not to scale out one shared instance.

## Pending UI decisions

- **Progress spinner style**: `SegmentRingLegacy` in `level-1-environment-setup/frontend/src/components/StationStats.tsx` is the old arc-segment ring kept as backup. The active spinner is `DotSpinner` (12-dot comet style). **Delete `SegmentRingLegacy` once the new spinner is confirmed.**
