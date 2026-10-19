# Hive Simulation Guide for Instructors

### Manufacturing simulation (hosted) and local controls

- The factory runs in the **Simulation Server** (Python/FastAPI, one containerized process on IBM Code Engine), with one in-memory logical factory per enrolled attendee. It is the authority for the clock, inventory and jobs.
- The attendee's laptop runs a **local Python backend and React dashboard** (the "Hive Controls" package). The backend consumes the factory's Confluent events, keeps an in-memory view, and sends lifecycle commands to the server. The browser never talks to Kafka or the server directly and never holds the workshop token.
- Observation path: Simulation Server → Kafka producer → Confluent → local consumer → local API/SSE → UI. Command path: UI → local backend → Simulation Server `/v1` API. A command receipt is not an observation; the UI shows them as separate facts.
- The factory receives resources, converts them into parts, and assembles robotic bees.
- Manufacturing is **automatic**. Resources arrive on a set schedule and parts are manufactured as inputs become available.
- Lifecycle controls: Start, Pause, Stop (final for that run), Restart at zero (new generation), and 1x/5x speed.
- State is memory-only. A server restart loses every factory; attendees must re-register and start from zero. A local app restart only loses the displayed view. Closing the laptop does not pause the hosted factory.
- The workshop's initial build is delivered by two repo packages that share one contract: `simulation-instructor-only/` (Simulation Server) and `spec-1-hive-dashboard/` (local backend and dashboard), with the shared API and event contracts in `spec-shared/`.
- No production-order form, quantity selector, or Queue Production button in the latest design.
- Manufacturing automation is distinct from the Queen. The Queen does not control manufacturing.

### Primary hive simulation

- Runs in **IBM Cloud**, with a separate logical simulation for each student.
- Owns the larger colony, environmental behavior, resource availability, robot activity, and hidden state.
- IBM-owned implementation/hidden behavior is private; earlier discussion placed its source in private `github.ibm.com`. Public workshop materials must not expose it.
- The system is a black box to attendees and their agent harness. They receive permitted observations and query results, not unrestricted internal state or source.
- Spec 3 connects the student's application to broader hive event streams hosted in Confluent.
- Attendees cannot directly edit resource supply, colony internals, environment parameters, or hidden state. Bee allocation is an allowed action whose consequences the server simulates.

### Queen harness

- Spec 4 deploys a provided base agent harness that attendees can tweak.
- Earlier deployment direction was headless **IBM Bob Shell containerized on GCP**; retain as the proposed hosting direction pending a concrete deployment design.
- The Queen receives events from the cloud hive stream.
- It can query permitted system data through supplied MCP tools.
- It can write and run scripts in its sandbox to help make allocation decisions.
- **Its only operational action is allocating bees to tasks.** It cannot change recipes, create production orders, manufacture robots, alter resource supply, or change hidden simulation rules.
- Its broader goal is colony longevity and productive growth through allocation decisions. Exact objective metrics and constraints still need definition.

## 5. Current four-spec progression

| Spec | Delivered capability | Visible result |
| --- | --- | --- |
| 1 | Complete automatic manufacturing simulation for one robot type (engineer), event integration, and validation | Resources → parts manufacturing → robot assembly, with parts and completed-robot inventory plus event log |
| 2 | Extend manufacturing to multiple robotic bee types (forager is the first addition) | Same screen; additional assembly progress rows and type/count entries in completed-robot inventory |
| 3 | Connect to the broader hive event streams, expose useful operational observations, and allow manual allocation | Separate Colony Operations tab with flat activity cards and a manual bee-assignment panel |
| 4 | Deploy the base Queen harness; allow tuning and automated allocation | Same colony screen with Manual/Queen selection, allocation objective/instructions, latest allocation, and agent activity |

The latest request explicitly allows manual assignment in Spec 3 and automated Queen allocation in Spec 4. One sentence also described Spec 4 as where manual and automated users gain access; the working interpretation used in the latest comps is manual in Spec 3, Queen in Spec 4. Confirm only if timing becomes material to implementation.

## 6. Manufacturing model

The machine-readable source of truth is `simulation-instructor-only/schemas/simulation_rules.json`. It defines the resources, per-resource delivery intervals and quantities, manufacturing recipes, robot assembly recipe and job durations; they are not repeated here. Event and snapshot shapes are in `spec-shared/schemas/event_payloads.json`.

Each resource has its own independent delivery timer (a `gathering.started` → `gathering.completed` cycle that repeats). `forager_assembly` is a **placeholder**: declared with the same recipe and duration as `worker_assembly`, but not scheduled, no events emitted, not shown yet.

Robots are identified by type (`robot_id`), like parts are by `part_id`. There is no per-robot UUID or "W-001" display label; completed robots are counted.

These are abstract simulation recipes, not claims about real electronics or battery manufacturing. Quantities, durations and energy semantics are tuning values. Capacities are not modelled: stations compete only for inventory. Each station has a staging cart and grabs whatever part of its recipe is in stock on each scheduling pass, holding it until the recipe is complete; the manufacturing station with the fewest completed parts is served first. This keeps multi-unit recipes from being starved by stations that need only one of a shared resource.

The four stations can work concurrently subject to inventory. Parts feed robot assembly. The recipe is a provisional mock recipe, not a finalized engineering BOM.

The robot reference assets show: head/torso/abdomen shells, central frame, face display, antennae, neck/gimbal, shoulder and elbow servos, arm/hand modules, wing assemblies and actuators, battery, NPU board, power distribution board, wiring, connectors, and compact actuator/damper modules. Group these into teachable simulation components rather than implementing every physical part separately.

## 7. Latest screen requirements

### Shared design system

- Blue is dominant: navy shell, bright blue controls and progress, white/pale-blue content panels.
- Use supplied IBM Plex Sans font files for deterministic UI/deck implementation. Generated comps approximate the typeface; they do not embed the fonts.
- Palette reference: navy `#001141`, primary blue `#0F62FE`, darker blue `#0043CE`, pale blue `#EDF5FF`/`#D0E2FF`, gray `#525252`, white `#FFFFFF`. Small orange `#FF832B` accents for exceptions. Supplied palette is authoritative.
- Persistent HIVE header with Manufacturing and Colony Operations tabs.
- Roughly left 20% for controls/state, right 80% for the working view.
- Flat, practical, professional UI. Avoid excessive isometric scenes, natural-bee art, large decorative mascots, or game-like detail.
- Preserve the base layout between specs. Leave breathing room for additions.
- The robot reference has a blue rounded mechanical head, black face display with cyan features, articulated arms, antennae, yellow/black abdomen, and translucent wings. Use small asset thumbnails or simplified mechanical icons.

