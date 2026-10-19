# Welcome to the Hive Robotics Workshop

**HIVE** is an interactive, hands-on workshop for hybrid cloud software developers interested in enterprise event-driven architecture, real-time stream processing, and spec-driven development.

Attendees build, connect, and observe the real-time data pipelines surrounding an autonomous robotic bee factory colony powered by **Confluent Cloud** (Apache Kafka, Apache Flink, Tableflow) and AI assistants (IBM Bob).

---

## Workshop Architecture

```
┌─────────────────────────────────┐
│   Hosted Cloud Simulation       │ (Autonomous Robotic Bee Factory)
└───────────────┬─────────────────┘
                │ Raw Factory Events (*.started, *.completed, factory.state)
                ▼
┌─────────────────────────────────┐
│        Confluent Cloud          │
│  ├─ Apache Kafka Topics         │
│  ├─ Apache Flink Streaming SQL  │ (Job Durations, Material Ledgers, Balances)
│  └─ Confluent Tableflow         │ (Apache Iceberg Data Lakehouse Sync)
└───────────────┬─────────────────┘
                │ Stream Projections & SSE
                ▼
┌─────────────────────────────────┐
│   Unified Hive Dashboard        │ (level-0-hive-dashboard/)
│  └─ Level Selector Dropdown     │ [Level 0] -> [Level 1] -> [Level 2] -> [Level 3]
└─────────────────────────────────┘
```

---

## Workshop Milestones & Level Progression

Attendees use a **single unified dashboard** throughout the entire workshop. As you complete milestones, select your active level from the dashboard dropdown:

| Level | Name | Description |
|---|---|---|
| **Level 0** | **Kickoff & Unified Dashboard** | Configure credentials and launch the local dashboard backend and frontend services. |
| **Level 1** | **Connect Simulation** | Provision Kafka topics, connect real-time event streams, and observe live simulation controls and the sim clock. |
| **Level 2** | **Implement Apache Flink** | Deploy streaming SQL interval joins to correlate paired job durations and production throughput. |
| **Level 3** | **Hive Dashboard & Ledgers** | Construct append-only material ledgers, stateful inventory balances, and Tableflow Iceberg sync. |

Automated validation tests verify that you have completed the required steps for each level before advancing.

---

## Next Steps: Getting Started

To configure your environment and launch the Hive Dashboard, head directly to:

👉 **[`level-0-hive-dashboard/README.md`](level-0-hive-dashboard/README.md)**
