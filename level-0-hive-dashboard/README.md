# Level 0: Kickoff & Unified Dashboard Setup

Welcome to **Level 0** of the Hive Robotics Workshop!

In this kickoff step, you will set up your local development environment, configure your Confluent Cloud and simulation credentials in `spec-shared/.env`, and launch the unified **Hive Dashboard**.

> **Important**: You must configure `spec-shared/.env` **before** starting the backend or frontend servers. The backend relies on these credentials at startup to connect to Confluent Cloud and authenticate with the simulation server.

---

## Architecture Overview

Throughout the entire workshop, you will use this **single unified dashboard** install:

- **Backend** (`backend/`): FastAPI service that connects to Confluent Cloud via `confluent-kafka` and streams live factory projections to the UI over Server-Sent Events (SSE).
- **Frontend** (`frontend/`): React + TypeScript + Vite UI displaying the robotic manufacturing floor, factory controls, and the level progression selector.

As you advance through the workshop, you will select your active level from the top dropdown, and automated validation tests will verify that your stream processing jobs and data pipelines are running.

---

## Step 1: Prerequisites

Make sure you have installed:
- **Python 3.12+**
- **Node.js 18+** & npm
- A Confluent Cloud account and cluster access

---

## Step 2: Configure Environment Credentials (`spec-shared/.env`)

The backend and topic provisioning scripts read configuration from `spec-shared/.env`.

1. Copy the example environment template from the repository root or `spec-shared/`:

   ```bash
   cp spec-shared/.env.example spec-shared/.env
   ```

2. Open `spec-shared/.env` in your editor and configure the following required values:

   ```ini
   # Organizer-issued bearer token for authenticating with the simulation server
   WORKSHOP_ACCESS_TOKEN=your-issued-access-token
   
   # Your attendee identifier (e.g. queen-042)
   ATTENDEE_ID=your-attendee-id

   # ── 2. Confluent Cloud Cluster Credentials ────────────────────────────────
   # Confluent Cloud -> Cluster Settings -> Bootstrap server (e.g. pkc-xxxxx.us-west-2.aws.confluent.cloud:9092)
   CONFLUENT_BOOTSTRAP_SERVER=pkc-xxxxx.us-west-2.aws.confluent.cloud:9092

   # API Key & Secret with cluster access (Confluent Cloud -> API Keys)
   CONFLUENT_API_KEY=your-api-key
   CONFLUENT_API_SECRET=your-api-secret

   # ── 3. Topic Provisioning Settings (Confluent REST API) ───────────────────
   # Confluent Cloud -> Cluster Settings -> Endpoints -> REST endpoint
   CONFLUENT_REST_ENDPOINT=https://pkc-xxxxx.us-west-2.aws.confluent.cloud
   
   # Confluent Cloud -> Cluster Settings -> General -> Cluster ID (e.g. lkc-xxxxxx)
   CONFLUENT_CLUSTER_ID=lkc-xxxxxx
   ```

3. Save `spec-shared/.env`.

---

## Step 3: Start the Backend Service

Once `spec-shared/.env` is configured, start the backend service:

```bash
cd level-0-hive-dashboard/backend
./start_backend.sh
```

*(Alternatively, create a virtual environment, run `pip install -r requirements.txt`, and start uvicorn on port 8001).*

The backend will start at **`http://localhost:8001`**.

---

## Step 4: Start the Frontend UI

Open a second terminal and start the frontend development server:

```bash
cd level-0-hive-dashboard/frontend
npm install
npm run dev
```

Open your browser at **`http://localhost:5173`** (or the port displayed in your terminal).

---

## Step 5: Verification & Next Steps

When the dashboard loads:
1. You will see the **Hive Robotics** floor interface.
2. The connection status indicator and level selector dropdown will be visible.

Now proceed to **Level 1** to provision your Kafka topics and connect the live simulation stream:

👉 **[`level-1-connect-simulation/README.md`](../level-1-connect-simulation/README.md)**
