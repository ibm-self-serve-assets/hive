# HIVE workshop — context and decision handoff


## 1. Project and goals

HIVE is a four-hour workshop for hybrid cloud software developers interested in enterprise productivity, event-driven architecture, and spec-driven development. It can become a longer series delivered online and in person.

Attendees build a simulation of the software required to manufacture robotic bees. Those robots support a larger robotic colony. The factory must be small enough to run on an attendee's laptop and understandable enough to validate during the workshop.

The initial technical emphasis is **event-driven architecture using Confluent**, with **IBM Bob or Google Gemini** implementing supplied natural-language specifications. Agent harnesses enter later in the current four-spec progression. Keep enterprise concepts interwoven: inventory integrity, production capacity, resource constraints, asynchronous coordination, operational visibility, and productive allocation of limited assets.

The colony and bees are ROBOTIC. Use the supplied robot design, not drawings of biological bees or a natural beehive.

## 2. Teaching model: complete applications evolved by specifications

- Attendees do not write code. Bob/Gemini writes it.
- Attendees submit provided specifications, inspect the result, validate behavior, run tests, and direct corrections.
- Specifications are Markdown/NL files supplied through a public GitHub repository at the start.
- Initial inputs can include screen comps, the simulation description, initial event architecture, data schemas, recipes, and acceptance criteria.
- Bob uses provided skills in `.bob/skills` for implementation, provisioning/configuration, deployment where required, and validation.
- Bob should build the UI and simulation, configure the required Confluent resources and connections, and verify the working result as part of Spec 1.
- GCP setup through skills has been requested, but the exact first-workshop GCP responsibility remains unresolved. Do not silently move the local factory to GCP.
- **Spec 1 delivers a complete working factory with one bee type in its first 30-minute build block.** Do not return to the old approach where each 30-minute block adds only connectivity, then inventory, then manufacturing.
- Subsequent specs evolve that working application while preserving its layout and existing behavior.

## 3. Time budget

The workshop lasts four hours. The first 30 minutes are for environment setup. Allow for delays and introductory/debrief activity; budget only **150 minutes of attendee specification execution and validation**.

A proposed allocation, not a finalized agenda:

| Block | Time |
| --- | ---: |
| Environment setup | 30 minutes |
| Introduction and architecture walkthrough | 30 minutes |
| Spec 1 — automated worker factory | 30 minutes |
| Spec 2 — additional bee types | 30 minutes |
| Spec 3 — colony observations and manual allocation | 45 minutes |
| Spec 4 — Queen harness and allocation | 45 minutes |
| Recovery buffer, demonstration, debrief | 30 minutes |

Rehearse the specs against the provided repo and prepared accounts. The target includes generation, provisioning, tests, and repairs. Suggested supporting materials include recovery checkpoints and explicit acceptance scenarios; these are recommendations, not already-built assets.

## 4. System boundaries

### Local manufacturing simulation

- Runs on each attendee's laptop.
- Receives resources, converts them into parts, and assembles robotic bees.
- Manufacturing is **automatic**. Resources arrive on a set schedule and parts are manufactured as inputs become available.
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
| 1 | Complete automatic manufacturing simulation for one worker-bee type, event integration, and validation | Resources → parts manufacturing → worker assembly, with parts and completed-bee inventory plus event log |
| 2 | Extend manufacturing to multiple robotic bee types | Same screen; additional assembly progress rows and type/count entries in completed-bee inventory |
| 3 | Connect to the broader hive event streams, expose useful operational observations, and allow manual allocation | Separate Colony Operations tab with flat activity cards and a manual bee-assignment panel |
| 4 | Deploy the base Queen harness; allow tuning and automated allocation | Same colony screen with Manual/Queen selection, allocation objective/instructions, latest allocation, and agent activity |

The latest request explicitly allows manual assignment in Spec 3 and automated Queen allocation in Spec 4. One sentence also described Spec 4 as where manual and automated users gain access; the working interpretation used in the latest comps is manual in Spec 3, Queen in Spec 4. Confirm only if timing becomes material to implementation.

## 6. Manufacturing model

Current dashboard resource categories: **resin, silicon, metals, copper, energy**.

| Manufacturing station | Illustrative inputs | Output |
| --- | --- | --- |
| Structural molding | Resin, metals | Chassis/structural components |
| Electronics assembly | Silicon, copper | Electronics modules |
| Actuator fabrication | Metals, copper | Actuators |
| Battery assembly | Energy, copper, metals | Battery packs |

These are abstract simulation recipes, not claims about real electronics or battery manufacturing. Exact quantities, durations, capacities, priorities, and energy semantics remain to be specified.

The four stations can work concurrently subject to inventory and capacity. Parts feed robot assembly. The illustrated worker recipe has been 1 chassis, 3 electronics, 2 batteries, and 8 actuators; this is a provisional mock recipe, not a finalized engineering BOM.

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

### Spec 1 — Manufacturing

- Sidebar: local simulation controls, speed, factory-stream status, scheduled-resource delivery information; manufacturing shown as Automated.
- Remove top aggregate KPI cards for Resources, Parts Ready, and Robots Accepted.
- Remove the production-order section entirely.
- Main layout has three persistent columns: Resources; Parts Manufacturing; Robot Assembly.
- Resources: quantities of the five inputs. Do not imply users can alter supply.
- Parts Manufacturing: four station rows with progress bars. **Parts inventory counts appear below these stations.**
- Robot Assembly: compact worker row with progress bar and status. No large bee illustration and no duplicated parts checklist/counts.
- **Assembled bee inventory appears below robot assembly**, initially worker count only.
- Bottom event log.
- Parts start automatically as resources become available; robot assembly starts when its requirements are met.

### Spec 2 — Manufacturing

- Keep Spec 1's shell, columns, sidebar, resources, stations, parts inventory, and event log.
- Expand assembly into compact progress rows for the additional bee types.
- Expand assembled-bee inventory into type/count entries only.
- No large bee artwork, robot catalog, capability descriptions, detailed recipe cards, production-order forms, or coordinator.
- Small robot thumbnails are acceptable. Different colors/accessories in generated comps are illustrative, not a finalized taxonomy.

### Spec 3 — Colony Operations

- Separate tab; manufacturing remains available and unchanged.
- Simplify the colony visual into flat operational areas/cards.
- Latest comp uses six areas: Resource Collection, Energy Collection, Scouting, Construction, Maintenance, Inspection.
- Each shows assigned-bee count, current activity, recent relevant events with age, and an appropriate operational measure.
- Examples: delayed copper delivery, falling energy reserves, discovered deposit, expansion progress, charger fault, arrival awaiting inspection.
- Give enough evidence for allocation decisions while preserving the hidden-state boundary.
- Manual assignment panel: available bees, bee type, quantity, task, Assign Bees, acknowledgment/status.
- Colony event stream remains visible.
- Allocation is the permitted action; attendees do not directly edit colony state.

### Spec 4 — Colony Operations with Queen

- Keep Spec 3's activity layout and observations.
- Add Manual/Queen mode and manual takeover using the same allocation scope.
- Show objective/instruction tuning, latest allocation, and whether the server accepted it.
- Show the Queen's operational inputs/tools: hive events, MCP data queries, sandbox-script analysis.
- Display tool/action summaries and results, not an invented internal reasoning transcript.
- Queen actions are ONLY bee-to-task allocation. Manufacturing remains independently automatic.
- Avoid unsupported performance improvement claims. Any numbers in comps are illustrative.

## 8. Robot-type vocabulary to finalize

Original proposed roles: Scout drones (discovery), Forager drones (resources), Builder bees (capacity expansion), Nurse bees (assembly/calibration/commissioning), Maintenance bees (repair/recycling/cooling), Guard drones (inspection/anomalies).

Latest comps show Worker, Scout, Forager, Builder, Maintenance, Guard. **Nurse versus base Worker remains unresolved.** Do not treat the generated six-chip catalog as a final data model or silently discard the nurse role. Begin Spec 1 with the generic base worker, then settle the types/recipe/capability matrix for Spec 2.

## 9. Event architecture guidance discussed, not yet finalized contracts

- Use explicit event schemas, unique event/delivery IDs, student/colony isolation, timestamps, job/robot identifiers, and correlation across stages.
- Apply deliveries once; resource delivery events must not accidentally double-count snapshots as increments.
- Inventory deductions/reservations must be atomic so parallel jobs cannot spend the same resources.
- Publish meaningful transitions rather than noisy frame-by-frame progress events.
- Dashboard views should reflect state derived from the simulation and events.
- Test duplicates, shortages, delayed input, reconnect behavior, and traceability from resources to completed robot.
- Bee assignment requests need validation and acceptance/rejection outcomes from the authoritative system.
- A local factory service can own inventory/jobs; separate microservices per station are not required merely to teach EDA.
- Example names in discussions/comps include `resource.received`, `resource.delivered`, `part.produced`, `robot.assembled`, `bee.assignment.accepted`, `charger.fault.reported`, `mcp.query.completed`, and `sandbox.script.completed`. Names are illustrative and inconsistent across drafts; normalize before implementation.
- MCP/sandbox activity may belong in harness telemetry rather than the authoritative hive event topic. Do not conflate all visible log rows into one finalized stream schema.

## 10. Important unresolved implementation questions

1. What provisions/run on GCP before Spec 4, versus local laptop, IBM Cloud, and Confluent?
2. What generates scheduled resources in Specs 1–2 before the broader hive connection in Spec 3? Use an explicit starter feed/fixture or a limited server feed; decide rather than assume.
3. How does local assembled inventory become available for allocation in the primary hive? Define registration, IDs, ownership, acknowledgment, retries, and reconciliation.
4. What automatic policy selects bee types and production priority after Spec 2? Manufacturing is automatic, but the scheduling policy is not specified.
5. How are task eligibility, capacities, reassignment, in-flight work, and unavailable robots represented?
6. What are the exact Queen MCP tools, action limits, sandbox access, trigger cadence, and evaluation measures?
7. What tenant-isolation model, Confluent topics/keys, schema evolution, state persistence, and recovery behavior are required for the workshop?
8. How do local pause/speed/reset controls interact with the cloud hive's time once connected?

## 11. Superseded ideas — do not restore by accident

- Old five stages: connectivity → inventory → parts → assembly → reliability. **Superseded:** Spec 1 delivers all factory capabilities.
- Drastically redesigned dashboard for each spec. **Superseded:** incremental additions to a stable shell.
- Top manufacturing KPI summary cards. **Removed.**
- Manual production orders and Queen-controlled manufacturing. **Removed:** manufacturing is automatic; Queen allocates bees.
- Large biological bee drawings, decorative bee images, rich isometric colony artwork. **Replace with robotic assets, compact progress rows, flat event-rich activity areas.**
- Read-only colony screen with no allowed attendee actions. **Superseded:** observed state plus explicit manual allocation in Spec 3.
- Manual/Queen controls confined to Manufacturing. **Superseded by latest request and comps:** allocation belongs in Colony Operations.
- Queen can alter resources, manufacture robots, or broadly control the colony. **Superseded:** task allocation only, informed by observations, queries, and scripts.
- Harness only in a separate future workshop. **Updated:** basic harness is now Spec 4; advanced work can extend into follow-up workshops.

## 12. Presentation and continuity

The user wants one shared introductory deck initially, addressing the technical sales team building the workshop, attendees, and sales/marketing teams promoting it. A prior plan was five slides at approximately 30 seconds narration each, later expanded into a five-minute video with demonstrations. Those earlier scripts predate the latest four-spec architecture and require revision before reuse.

The latest four screen comps, font archive, and palette will be supplied separately in the new chat. Treat them as design references; this document and subsequent explicit user corrections govern behavior. Generated sample values, dates, robot counts, event names, and status combinations are illustrative and should be made internally consistent during implementation.

**Resume instruction:** Continue from this four-spec, automated-manufacturing, allocation-only-Queen direction. Do not restart discovery or revive rejected layouts. Distinguish agreed requirements from proposals when creating detailed specs, event contracts, workshop materials, or revised screens.
