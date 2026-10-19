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

Ensure your `spec-shared/.env` file is configured with your Confluent credentials and workshop access token:

```bash
cd level-1-connect-simulation
./provision_topics.sh
```

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

The dashboard will open at `http://localhost:5173` (or `http://localhost:5174`).

---

## Validation & Acceptance Criteria

- The dashboard shows **`connected`** in the status pill.
- Clicking **Run** boots the factory simulation on the cloud server.
- The simulation clock advances (`0d 00h 00m` upwards at 1 real sec = 1 sim min).
- Resource gathering counters increment as resources arrive.
- Stations trigger and animated dot flows pulse from Resources $\rightarrow$ Parts $\rightarrow$ Robots.
- Factory controls (Run, Pause, Stop, Restart) respond seamlessly.
