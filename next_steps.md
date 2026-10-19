# Next steps (working notes for Anthony and Bob)

Running notes for us as the work progresses. Not for attendees or instructors.

- **Unified Dashboard Architecture**: Single UI install in `hive-dashboard/` with dropdown for Level 1, Level 2, Level 3 progression.
- **Automated Validation**: Tests validate that attendees have completed steps for the selected level to function.
- **Levels Organization**:
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
  - `hive-dashboard/` (single unified frontend and backend)
- **Audience.**
  - **Simulation server (`simulation-instructor-only`) is written for instructors.** It describes hidden state, server internals, and the answer key.
  - **Levels 1, 2, 3 are written for attendees.** They do not reveal the simulation's hidden counters or internals.
- **Attendee SQL is run in the Confluent Flink workspace, one statement per run.** Prefer a small number of files that each run once.

## Goal

Window-based stream processing in Confluent Flink that adds derived data to the stream, based on
`spec-shared/schemas/event_payloads.json`. First step: the time between each job's `started` and `completed` events.
Then attendees rebuild inventory themselves from the events (see Architecture).

## Current state

| Item | Status |
|---|---|
| `hive-dashboard/` | **Unified UI Installed**. Backend and Frontend running in unified structure with Level 1-3 support. |
| `level-1-connect-simulation/` | **Verified working**. Provisioning scripts, raw event streams, and real-time dashboard controls functional. |
| `level-2-implement-flink/` | **Verified deployed** in Confluent Cloud. Tables, jobs, and validation passing (`job_durations` stream join). |
| `level-3-hive-dashboard/` | Next active phase: Ledgers, balances, Tableflow sync, and level validation tests. |

## Open items & roadmap

1. [x] **Unified Dashboard Scaffolding**: Moved backend and frontend to `hive-dashboard/`.
2. [x] **Folder Renaming**: Renamed `spec-1/2/3-*` to `level-1/2/3-*`.
3. [ ] **Level Selector & Validation Hook**: Implement level dropdown in `hive-dashboard/frontend` and backend test validation endpoint for level progress gates.
4. [ ] **Ledger & Balances Flink SQL (`level-2` / `level-3`)**: Write attendee SQL for material ledgers and stateful balances in Confluent Cloud.
5. [ ] **Tableflow Runbook**: Iceberg sync and data lakehouse integration instructions.
