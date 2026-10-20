# HIVE: From Factory Events to Real-Time Insight

## 1. High-level architecture

![HIVE architecture](assets/images/Hive_Architecture.png)

The instructor-hosted simulation operates a robotic bee factory: gathering resources, manufacturing parts, and assembling robots. It publishes lifecycle events and factory-state snapshots to Apache Kafka in Confluent Cloud.

Two consumers put those events to work. The attendee's local FastAPI backend builds an in-memory view and sends updates to the React dashboard using Server-Sent Events (SSE). Apache Flink independently joins started and completed events and writes derived duration records to the `job_durations` table and Kafka topic. Attendees validate that output in the Confluent SQL workspace.

Factory controls follow a separate path: the browser sends HTTP requests to the local backend, which forwards REST commands to the simulation. The dashboard observes Kafka events; it does not query an internal factory database. IBM Bob supports development alongside this architecture rather than running in the event-processing path.

Dashed paths show planned extensions: richer dashboard views, event-derived material ledgers and inventory balances, and Tableflow synchronization to Apache Iceberg tables.

## 2. Introduction for attendees

Welcome to the Hive. Your mission is to turn a busy robotic bee factory's stream of activity into useful, real-time insight.

Resources arrive, parts move through manufacturing, and robots roll off assembly lines. Every step produces events—but an event that says a job started, and another that says it finished, don't tell the whole story on their own. How long did the job take? Which production stage is it part of? How can you build a live operational view from events flowing across independent services?

In this hands-on workshop, you'll connect a live factory simulation to Apache Kafka on Confluent Cloud and watch its activity appear in your dashboard. Then you'll use Apache Flink streaming SQL to match related events, calculate production durations, and create a new stream of derived information. You'll validate the results while the factory keeps running, seeing how continuous processing differs from querying a static dataset.

You'll work with a supplied React and FastAPI dashboard, shared event contracts, and guided SQL exercises. IBM Bob is available as an AI development assistant to help you understand the specifications and work through the code. Your focus is the event-driven system: connecting its components, understanding the data, and proving your pipeline works.

By the end of the core labs, you'll be able to:

- Explain how Kafka separates event producers from independent consumers.
- Connect a live event stream to an operational dashboard.
- Use Flink interval joins to correlate started and completed jobs across gathering, manufacturing, and assembly.
- Distinguish simulated production time from elapsed wall-clock time.
- Validate a continuously running SQL pipeline and its derived output.

The next stage extends these ideas toward inventory reconstruction and lakehouse analytics with Confluent Tableflow—building on the Kafka and Flink foundations you've established first.

## 3. Workshop summary

HIVE is a hands-on workshop for developers and engineers exploring enterprise event-driven architecture. A simulated robotic bee factory provides a visible, practical setting for learning how Apache Kafka moves operational events and how Apache Flink transforms those events into continuous insight.

Attendees configure a local dashboard, provision Kafka topics, connect to an instructor-hosted simulation, and observe live production activity. They then deploy Flink SQL interval joins that correlate job-start and job-completion events, producing an append-only stream of duration records. The exercises connect event contracts, decoupled services, stateful stream processing, and live validation in one working example.

The workshop's broader progression introduces material ledgers, inventory balances, and Tableflow integration with Apache Iceberg. These are documented extensions; the current repository's completed core centers on event connectivity and duration processing.

| Stage | Attendee activity | Learning outcome | Repository status |
|---|---|---|---|
| Level 0 — Set up | Configure credentials and launch the local dashboard | Understand the components and connection points | Setup guide and application supplied |
| Level 1 — Connect | Provision topics, start the factory, observe events | See producer/consumer decoupling in action | Code and guided steps supplied |
| Level 2 — Derive | Deploy and validate Flink interval joins | Turn separate lifecycle events into job-duration facts | Sink, processing, and validation SQL supplied |
| Level 3 — Extend | Reconstruct inventory and connect streams to lakehouse tables | Apply stateful processing and broaden analytical access | Planned/in progress in working notes |

## Review notes and source references

Reviewed repository commit `520bacb27bb43735c0ae5fdf14c8209a2ded7740` on October 19, 2026 (Pacific time). This review examined documentation, dashboard backend and frontend registration, and Flink SQL; it did not run a live cloud deployment.

The opening guide describes the intended four-level experience more broadly than the current code implements. The unified frontend currently registers only Level 1. Its Kafka consumer handles factory event envelopes; the derived `job_durations` stream is not yet wired into that dashboard. Working notes list level validation gates, ledger/balance SQL, and the Tableflow runbook as open work. Some older guides also contain obsolete folder names and example resources. The copy above follows current source behavior where these disagree.

Primary sources:

- [Workshop overview](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/GETTING_STARTED.md)
- [Level 0 setup](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-0-hive-dashboard/README.md)
- [Level 1 connectivity](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-1-connect-simulation/README.md)
- [Level 2 Flink exercises](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-2-implement-flink/README.md)
- [Flink processing SQL](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-2-implement-flink/flink/02_run_jobs.sql)
- [Dashboard backend](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-0-hive-dashboard/backend/app.py)
- [Current level registry](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/level-0-hive-dashboard/frontend/src/levels/registry.ts)
- [Working notes and roadmap](https://github.com/ibm-self-serve-assets/hive/blob/520bacb27bb43735c0ae5fdf14c8209a2ded7740/next_steps.md)
