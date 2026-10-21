# Level 1: Connect Simulation & Foundation UI

Level 1 establishes connectivity between the hosted Hive Simulation server, Confluent Cloud, and the single unified Hive Dashboard application.

---

## Architecture & Workflow

In Level 1, attendees connect their local dashboard to Confluent Cloud to monitor factory activity streams in real time:

1. **Kafka Topics Provisioning**: Provision all required factory event topics on Confluent Cloud.
2. **Dashboard Backend**: Connects to Confluent Cloud via `confluent-kafka` and streams raw events (`*.started`, `*.completed`, `factory.state`) to the frontend over Server-Sent Events (SSE).
3. **Dashboard Frontend**: Displays the real-time simulation floor, active/completed counters, sim clock (`Day X, HH:MM`), and factory lifecycle controls (Run, Pause, Stop, Restart).

---

## Quickstart

### Step 1: Provision Topics on Confluent Cloud

Before you start, finish [Level 0](../level-0-hive-dashboard/README.md). It covers creating your Confluent Cloud environment, cluster and API key, and filling in `spec-shared/.env` with your Confluent credentials and workshop access token.

The script creates the 10 topics listed in [`spec-shared/schemas/event_payloads.json`](../spec-shared/schemas/event_payloads.json) and is safe to run more than once:

```bash
cd level-1-connect-simulation
./provision_topics.sh
```

To preview the topic names without calling Confluent, run `./provision_topics.sh --dry-run`.

---

### Step 2: Ensure Dashboard is Running

If not already running from [Level 0](../level-0-hive-dashboard/README.md):

**Start Backend**:
```bash
cd level-0-hive-dashboard/backend
./start_backend.sh
```

**Start Frontend**:
```bash
cd level-0-hive-dashboard/frontend
npm install
npm run dev
```

The dashboard will open at `http://localhost:5174` (or the port shown in your terminal).

---

## Validation & Acceptance Criteria

- The dashboard shows **Connected** in the status pill.
- Clicking **Run** boots the factory simulation on the cloud server.
- The simulation clock advances (`0d 00h 00m` upwards at 1 real sec = 1 sim min).
- Resource gathering counters increment as resources arrive.
- Stations trigger and animated dot flows pulse from Resources $\rightarrow$ Parts $\rightarrow$ Robots.
- Factory controls (Run, Pause, Stop, Restart) respond seamlessly.

---

## Next Step

Proceed to **[Level 2 — Intro to Flink](../level-2-intro-to-flink/README.md)** to turn the `started` and `completed` events into job durations.
