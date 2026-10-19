# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.

- **Unified Dashboard Architecture**: Single UI install in `level-0-hive-dashboard/` with dropdown for Level 0, Level 1, Level 2, Level 3 progression.
- **Automated Validation**: Tests validate that attendees have completed steps for the selected level to function.
- **Levels Organization**:
  - `level-0-hive-dashboard/`: Unified dashboard (FastAPI backend + React/TypeScript/Vite frontend); credentials, launch, SSE events, factory controls, auto-connection.
  - `level-1-connect-simulation/`: Topic provisioning, raw event connectivity, and foundational simulation controls.
  - `level-2-implement-flink/`: Confluent Flink interval joins, job durations correlation (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`).
  - `level-3-hive-dashboard/`: Real-time inventory reconciliation, material ledgers, Flink balances, and Tableflow sync.
- **Simulation Server**: In `simulation-instructor-only/` (memory-only, instructor-managed authority).

## Working agreements

- **Keep the levels current.** Whenever the simulation, attendee backend/frontend code, or Flink SQL changes, update the matching level `.md` files in the same change:
  - `simulation-instructor-only/` specifications and README
  - `level-1-connect-simulation/` README and provisioning scripts
  - `level-2-implement-flink/` README and SQL comments
  - `level-3-hive-dashboard/` README and guides
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
| `simulation-instructor-only/` | **Cart / staging logic implemented** (see below). 11 tests pass; `tests/test_api.py` fails at import (`ModuleNotFoundError: No module named 'topics'`), not yet investigated. |
| `level-0-hive-dashboard/` | **Unified UI installed**. Backend and frontend running in unified structure with Level 1-3 support. |
| `level-1-connect-simulation/` | **Verified working**. Provisioning scripts, raw event streams, and real-time dashboard controls functional. |
| `level-2-implement-flink/` | **Verified deployed** in Confluent Cloud. Tables, jobs, and validation passing (`job_durations` stream join). |
| `level-3-hive-dashboard/` | Next active phase: Ledgers, balances, Tableflow sync, and level validation tests. |

## Simulation scheduling: cart / staging logic (done)

Implemented in `simulation-instructor-only/server/simulation.py` (`SimulationRun.carts`, `_stage_inputs`, `_schedule_parts_manufacturing`, `_schedule_robot_assembly`).

- The old all-or-none check starved multi-unit recipes: stations needing only 1 of a shared resource (metals) consumed every single delivery on arrival, so a station needing several (actuator fabrication) never accumulated enough. Robot assembly had the same issue waiting for all its parts at once.
- Each station now has an internal cart. On every scheduling pass an idle station moves `min(still needed, available)` of each required input from factory stock into its cart, and starts its job (consuming the cart) once the cart holds the full recipe. Assembly does the same with finished parts.
- Manufacturing stations are served fewest-completed-parts first. A station keeps a partial cart until the recipe is complete.
- Staged items leave factory stock, so `resources` and `parts` in `factory.state` are net of carts. A station's `missing_inputs` (in `manufacturing.blocked` / `assembly.blocked` and in the snapshot) now means what its cart still lacks.
- **Carts are hidden from attendees.** There is no cart field in any event or snapshot, and none is derived in the dashboard (see Working agreements). Attendees can only reconstruct totals from events; the per-station breakdown stays internal.
- Tests added in `simulation-instructor-only/tests/test_simulation.py`; the resin conservation test counts resin held in carts.
- Docs updated: `02_simulation.md`, `03_data.md`, `INSTRUCTOR_GUIDE.md`, `simulation-instructor-only/README.md`. The old text described the rotating tie-break cursor from the last commit; the working tree had already replaced it with fewest-completed-first ordering, so the docs now describe that. The unused `SimulationRun.station_cursor` was removed.

## Sources of truth

Do not copy recipe quantities, delivery intervals or durations into these notes. Look them up in:

- `simulation-instructor-only/schemas/simulation_rules.json`: resources, delivery intervals and quantities, recipes, job durations.
- `spec-shared/schemas/event_payloads.json`: event and `factory.state` payload shapes.

## Open items & roadmap

1. [x] **Unified Dashboard Scaffolding**: Moved backend and frontend to the unified dashboard (now `level-0-hive-dashboard/`).
2. [x] **Folder Renaming**: Renamed `spec-1/2/3-*` to `level-1/2/3-*`; unified dashboard folder is `level-0-hive-dashboard/`.
3. [x] **Cart / Staging Logic**: Incremental per-station staging for manufacturing and robot assembly (see above).
4. [ ] **Level Selector & Validation Hook**: Add a dropdown for attendees to progress through the workshop levels within a single UI (`level-0-hive-dashboard/frontend`), and add automated validation tests that confirm the attendee can run the selected level and warn otherwise (backend validation endpoint for level progress gates).
5. [ ] **Ledger & Balances Flink SQL (`level-2` / `level-3`)**: Write attendee SQL for material ledgers and stateful balances in Confluent Cloud.
6. [ ] **Tableflow Runbook**: Iceberg sync and data lakehouse integration instructions.
7. [ ] **Fix `simulation-instructor-only/tests/test_api.py`**: import error on `topics`.
