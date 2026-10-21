# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.

- **Unified Dashboard Architecture**: Single UI install in `level-0-hive-dashboard/` with dropdown for Level 0, Level 1, Level 2, Level 3 progression.
- **Automated Validation**: Tests validate that attendees have completed steps for the selected level to function.
- **Levels Organization**:
  - `level-0-hive-dashboard/`: Unified dashboard (FastAPI backend + React/TypeScript/Vite frontend); credentials, launch, SSE events, factory controls, auto-connection.
  - `level-1-connect-simulation/`: Topic provisioning, raw event connectivity, and foundational simulation controls.
  - `level-2-intro-to-flink/`: Confluent Flink interval joins, job durations correlation (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`).
  - `backup_ui/`: Archived Level 3 prototype (real-time inventory reconciliation, material ledgers, Flink balances, Tableflow sync). Reference only — superseded by `level-0-hive-dashboard/`.
- **Simulation Server**: In `simulation-instructor-only/` (memory-only, instructor-managed authority).

## Working agreements

- **Keep the levels current.** Whenever the simulation, attendee backend/frontend code, or Flink SQL changes, update the matching level `.md` files in the same change:
  - `simulation-instructor-only/` specifications and README
  - `level-1-connect-simulation/` README and provisioning scripts
  - `level-2-intro-to-flink/` README and SQL comments
  - `backup_ui/` (archived — no active maintenance required)
  - `level-0-hive-dashboard/` (single unified frontend and backend)
- **Audience.**
  - **Simulation server (`simulation-instructor-only`) is written for instructors.** It describes hidden state, server internals, and the answer key.
  - **Levels 0, 1, 2, 3 are written for attendees.** They do not reveal the simulation's hidden counters or internals.
- **Hidden internal state stays out of the payloads.** Attendees receive only the events and the `factory.state` snapshot as currently defined in `spec-shared/schemas/event_payloads.json`. The simulation's internal counters (for example the per-station staging carts, see below) are not added to any event or snapshot, and are not recomputed in the attendee dashboard backend either. Do not add fields such as `staged_inputs` to the schema, the models, or the dashboard.
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
| `level-0-hive-dashboard/` | **Unified UI installed**. Levels 1–3 screens, inventory strips, spinners, blocked state, FlowDots, URL hash routing. Level 2 `isReady` gate shows "New simulation run required" / "Waiting for Flink…" prompt when stale. Schema Registry 5-byte magic prefix stripped in both Flink topic consumers. |
| `level-1-connect-simulation/` | **Complete.** Provisioning scripts, raw event streams, and real-time dashboard controls functional. `requirements.txt` restored (the rename had moved it to the dashboard backend, so both scripts failed); README now has the `hive_dev` environment setup step and a link to Level 2. |
| `level-2-intro-to-flink/` | **Complete.** Verified deployed in Confluent Cloud. Tables, jobs, and validation passing (`hive_job_durations` stream join). README links and step lettering fixed. |
| `level-3-hive-inventory/` | **Flink SQL written** (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`). CLI-first README done. Dashboard Level 3 screen built and gated on `hive_inventory_balances` topic. |
| `backup_ui/` | Archived Level 3 prototype. Superseded by `level-0-hive-dashboard/`. |

## Simulation scheduling: cart / staging logic (done)

Implemented in `simulation-instructor-only/server/simulation.py` (`SimulationRun.carts`, `_stage_inputs`, `_schedule_parts_manufacturing`, `_schedule_robot_assembly`).

- The old all-or-none check starved multi-unit recipes: stations needing only 1 of a shared resource (metals) consumed every single delivery on arrival, so a station needing several (actuator fabrication) never accumulated enough. Robot assembly had the same issue waiting for all its parts at once.
- Each station now has an internal cart. On every scheduling pass an idle station moves `min(still needed, available)` of each required input from factory stock into its cart, and starts its job (consuming the cart) once the cart holds the full recipe. Assembly does the same with finished parts.
- Manufacturing stations are served fewest-completed-parts first. A station keeps a partial cart until the recipe is complete.
- Staged items leave factory stock, so `resources` and `parts` in `factory.state` are net of carts. A station's `missing_inputs` (in `manufacturing.blocked` / `assembly.blocked` and in the snapshot) now means what its cart still lacks.
- **Carts are hidden from attendees.** There is no cart field in any event or snapshot, and none is derived in the dashboard (see Working agreements). Attendees can only reconstruct totals from events; the per-station breakdown stays internal.
- Tests added in `simulation-instructor-only/tests/test_simulation.py`; the resin conservation test counts resin held in carts.
- Docs updated: `02_simulation.md`, `03_data.md`, `INSTRUCTOR_GUIDE.md`, `simulation-instructor-only/README.md`. The old text described the rotating tie-break cursor from the last commit; the working tree had already replaced it with fewest-completed-first ordering, so the docs now describe that. The unused `SimulationRun.station_cursor` was removed.

## Mission: one UI per level (dashboard architecture)

Each workshop level gets its own dashboard UI, and each level's UI improves on the previous one. Adding Level N must never break Levels 1 to N-1.

**Done:** the Levels dropdown is in the sidebar of `level-0-hive-dashboard/frontend` and lists Level 1 and Level 2. The sidebar order is: Levels, a divider, then Simulation controls (a plain green dot with "Connected", then the buttons) and Simulation Time. Level 2 is currently an unchanged copy of Level 1 (`levels/level2/Level2Screen.tsx`), the starting point for its improvements. Level 1 is the current UI (Resources gathered, Parts manufactured, Robots assembled, with event panels).

### Architecture decision: a full screen per level

Two options were considered:

1. **A main screen per level** that contains all of its elements.
2. **Shared components** (Resource gathering, Parts manufacturing, Robot assembly, ...) that every level reuses.

We chose option 1 as the base. Reason: with shared components, improving a component for Level 3 changes what Level 1 shows, and each fix needs a regression check across levels. With a screen per level, a level is frozen once it ships and a new level starts from a copy of the previous one. The cost is some duplication. To limit it, only truly identical, presentation-only pieces are shared (for example `components/FlowDots.tsx`, `EventPanel.tsx`, `Sidebar.tsx`). If a shared piece needs a level-specific change, copy it into that level's folder instead of adding flags.

### Layout (`level-0-hive-dashboard/frontend/src/`)

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

- `simulation_rules.json` has a single `assembly` list (like `resources` and `manufacturing`) covering `worker_assembly` (engineer) and `forager_assembly` (forager). The forager placeholder is gone. The forager is scheduled with the same cart logic as manufacturing: each pass moves what is available into its cart until the recipe is complete. Both stations are in `factory.state`, so it now requires 6 stations.
- `duration_ms` was removed from every event and the snapshot. Durations stay internal to the simulation. Attendees derive elapsed time from the `started` and `completed` sim times (this is what the Level 2 `hive_job_durations` join does).
- Restart the simulation and the dashboard backend to pick these changes up.
- To check: the Level 3 backend and frontend with a sixth station.

## Sources of truth

Do not copy recipe quantities, delivery intervals or durations into these notes. Look them up in:

- `simulation-instructor-only/schemas/simulation_rules.json`: resources, delivery intervals and quantities, recipes, job durations.
- `spec-shared/schemas/event_payloads.json`: event and `factory.state` payload shapes.

## Open items & roadmap

1. [x] **Unified Dashboard Scaffolding**: Moved backend and frontend to the unified dashboard (now `level-0-hive-dashboard/`).
2. [x] **Folder Renaming**: Renamed `spec-1/2/3-*` to `level-1/2/3-*`; unified dashboard folder is `level-0-hive-dashboard/`.
3. [x] **Cart / Staging Logic**: Incremental per-station staging for manufacturing and robot assembly (see above).
4. [ ] **Level Selector & Validation Hook**: The dropdown is done (see Mission above). `isReady` per-run gate added to `LevelDefinition`. Still open: automated validation tests that confirm the attendee can run the selected level and warn otherwise (backend validation endpoint for level progress gates).
5. [x] **Inventory Flink SQL (`level-3-hive-inventory/`)**: `hive_inventory_balances` upsert topic. Three jobs: resources, parts, robots. CLI-first README done.
6. [ ] **Tableflow Runbook**: Iceberg sync and data lakehouse integration instructions for both `hive_job_durations` and `hive_inventory_balances`.
7. [x] **Fix `simulation-instructor-only/tests/test_api.py`**: import error on `topics`. Cause: `topics.py` lives in `spec-shared/`, which only `start_server.sh` added to `PYTHONPATH`. Fixed with `simulation-instructor-only/pytest.ini` (`pythonpath = . ../spec-shared`).

## Pending UI decisions

- **Progress spinner style**: `SegmentRingLegacy` in `level-0-hive-dashboard/frontend/src/components/StationStats.tsx` is the old arc-segment ring kept as backup. The active spinner is `DotSpinner` (12-dot comet style). **Delete `SegmentRingLegacy` once the new spinner is confirmed.**
