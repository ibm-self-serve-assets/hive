# Local Hive Controls & Manufacturing Dashboard: Architecture & Scope

## Overview

This package defines the attendee's local workstation application: a **React / TypeScript web dashboard** and a **Python / FastAPI local backend service**. The application connects to a remote or local **Simulation Server** and an assigned **Confluent Cloud** Kafka cluster.

The attendee runs the local UI and event consumer. The local consumer maintains an **in-memory projection cache** reconstructed solely from Kafka streams, rather than querying an authoritative database.

---

## Architecture & Data Flow

```
                      ┌─────────────────────────────────┐
                      │    Hosted Simulation Server     │
                      └───────┬─────────────────▲───────┘
         Kafka Events         │                 │ HTTP REST Commands
         (10 topics)          ▼                 │ (Start / Pause / Speed)
                       ┌──────────────┐         │
                       │  Confluent   │         │
                       │    Cloud     │         │
                       └──────┬───────┘         │
                              │ SSE / Stream    │
                              ▼                 │
                       ┌────────────────────────┴───────┐
                       │  Local Python / FastAPI Backend│
                       │  (In-Memory Projection Cache)  │
                       └──────────────┬─────────────────┘
                                      │ SSE / Local API
                                      ▼
                       ┌────────────────────────────────┐
                       │     React / TypeScript UI      │
                       │   (Manufacturing Dashboard)    │
                       └────────────────────────────────┘
```

### 1. The Observation Path (Unidirectional Stream)
`Simulation Server → Kafka Producer → Confluent Cloud → Local Python Consumer → SSE/REST → React UI`
- The simulation engine executes all factory logic (resource harvesting, station manufacturing, robot assembly) and produces point-in-time events to 10 Kafka topics.
- The attendee's local consumer reads these events and projects them into memory.
- The UI renders only what has been observed from Kafka.

### 2. The Command Path (Decoupled REST)
`React UI → Local Python Backend → Simulation Server REST API`
- Commands (Start, Pause, Stop, Restart at zero, Speed change) are dispatched through the local backend to the Simulation Server over authenticated REST calls.
- Command acknowledgments and observed state changes are separate facts: a command receipt acknowledges that the engine accepted the directive, while the UI only updates manufacturing counters when matching Kafka events arrive.

---

## Scope & UI Requirements

- **Three-Column Manufacturing Floor**:
  1. **Resources**: Live stockpiles of resin, silicon, metals, copper, and energy.
  2. **Parts Manufacturing**: Four manufacturing stations (structural molding, electronics assembly, actuator fabrication, battery assembly) with active job progress and parts inventory.
  3. **Robot Assembly**: Final assembly station (`worker_assembly`) producing engineer robots.
- **Controls & Sidebar**: Start, Pause, Stop, Restart at zero, Speed (1x / 5x), and live Kafka connectivity / stream freshness indicators.
- **Event Log**: Real-time chronological audit trail of observed stream events.
- **No Direct Cloud State Coupling**: The browser must never communicate directly with cloud credentials or query factory state over HTTP.
