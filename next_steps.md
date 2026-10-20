# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.

- **Unified Dashboard Architecture**: Single UI install in `level-0-hive-dashboard/` with dropdown for Level 0, Level 1, Level 2, Level 3 progression.
- **Automated Validation**: Tests validate that attendees have completed steps for the selected level to function.
- **Levels Organization**:
  - `level-0-hive-dashboard/`: Unified dashboard (FastAPI backend + React/TypeScript/Vite frontend); credentials, launch, SSE events, factory controls, auto-connection.
  - `level-1-connect-simulation/`: Topic provisioning, raw event connectivity, and foundational simulation controls.
  - `level-2-implement-flink/`: Confluent Flink interval joins, job durations correlation (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`).
  - `backup_ui/`: Archived Level 3 prototype (real-time inventory reconciliation, material ledgers, Flink balances, Tableflow sync). Reference only — superseded by `level-0-hive-dashboard/`.
- **Simulation Server**: In `simulation-instructor-only/` (memory-only, instructor-managed authority).

## Working agreements

- **Keep the levels current.** Whenever the simulation, attendee backend/frontend code, or Flink SQL changes, update the matching level `.md` files in the same change:
  - `simulation-instructor-only/` specifications and README
  - `level-1-connect-simulation/` README and provisioning scripts
  - `level-2-implement-flink/` README and SQL comments
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
| `simulation-instructor-only/` | **Cart / staging logic implemented** (see below). 13 tests pass; `tests/test_api.py` fails at import (`ModuleNotFoundError: No module named 'topics'`), not yet investigated. |
| `level-0-hive-dashboard/` | **Unified UI installed**. Backend and frontend running in unified structure with Level 1-3 support. |
| `level-1-connect-simulation/` | **Verified working**. Provisioning scripts, raw event streams, and real-time dashboard controls functional. |
| `level-2-implement-flink/` | **Verified deployed** in Confluent Cloud. Tables, jobs, and validation passing (`calculated_values` stream join). |
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
- [x] Decide what each of Levels 2 and 3 adds to the UI (Level 2: job durations + blocked state + input chips from the Flink `calculated_values` stream; Level 3: ledger and balances). `levels/level2/` built.
- [ ] Fold `backup_ui/frontend`'s own `ManufacturingFloor.tsx` into `levels/level3/`, so there is one frontend.
- [x] Level 2 gate: while the `calculated_values` topic does not exist, the main area of Level 2 shows a centred lock message (`levels/level2/Level2Requirements.tsx`, icon `public/icons/svg/lock.svg`) instead of the Level 2 screen, and the sidebar hides the simulation buttons and Simulation Time. Only the Levels dropdown and the connection status remain. A level opts in via optional `isUnlocked` and `Requirements` on its `LevelDefinition`. The backend (`backend/topic_watch.py`, `CalculatedValuesWatcher`) polls Confluent for the existence of the `calculated_values` topic and sets `calculated_values_ready` in the dashboard snapshot. It stays set once true. It only lists topics; it never reads records, and the topic is empty until the simulation runs.
- [ ] Gate Level 3 the same way (needs its own topic or signal), and add the matching validation tests (roadmap item 4).
- [x] Persist the selected level: URL hash routing (`#level-1`, `#level-2`). A page refresh restores the level; browser back/forward buttons work. `localStorage` fallback not needed.
- [x] Level 2: dotted flow line (`components/FlowDots.tsx`) wired between the three lanes, animated when `state.running` is true.
- [x] Level 1 + Level 2: event panels start **collapsed** by default. The count badge in the header always shows the running total, so attendees see activity without the panels obscuring the main content. Click to expand.

- [ ] `calculated_values` is the single Flink output topic for all derived values (job durations first, more later). Its table is still shaped for job durations only (`01_create_sink.sql`). Before adding a second kind of value, decide on a shared shape, for example a `metric` column plus per-metric columns, and keep changelog mode `append`. Tableflow cannot change the mode later.

## Simulation notes: assembly and `duration_ms`

- `simulation_rules.json` has a single `assembly` list (like `resources` and `manufacturing`) covering `worker_assembly` (engineer) and `forager_assembly` (forager). The forager placeholder is gone. The forager is scheduled with the same cart logic as manufacturing: each pass moves what is available into its cart until the recipe is complete. Both stations are in `factory.state`, so it now requires 6 stations.
- `duration_ms` was removed from every event and the snapshot. Durations stay internal to the simulation. Attendees derive elapsed time from the `started` and `completed` sim times (this is what the Level 2 `calculated_values` join does).
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
4. [ ] **Level Selector & Validation Hook**: The dropdown is done (see Mission above). Still open: automated validation tests that confirm the attendee can run the selected level and warn otherwise (backend validation endpoint for level progress gates).
5. [ ] **Ledger & Balances Flink SQL (`level-2` / `level-3`)**: Write attendee SQL for material ledgers and stateful balances in Confluent Cloud.
6. [ ] **Tableflow Runbook**: Iceberg sync and data lakehouse integration instructions.
7. [ ] **Fix `simulation-instructor-only/tests/test_api.py`**: import error on `topics`.
