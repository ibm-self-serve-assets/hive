# Attendee Get Started

Fill in your `.env` file first (copy from `.env.example`), then follow these steps.

---

## Step 1 — Provision your topics

Run the shell wrapper from the `spec_2_hive_controls/` directory. It creates a `.venv/`, installs all dependencies (including `certifi` for SSL), and runs `provision_topics.py`:

```bash
cd spec_2_hive_controls
./provision_topics.sh
```

When it completes, confirm in Confluent Cloud UI: **Cluster → Topics** — you should see **8 topics** prefixed with your `WORKSHOP_ID` (e.g. `hive-1`):

| Topic suffix | Retention |
| --- | --- |
| `.resource-delivered` | 24 h delete |
| `.manufacturing-started` | 24 h delete |
| `.manufacturing-completed` | 24 h delete |
| `.manufacturing-blocked` | 24 h delete |
| `.assembly-started` | 24 h delete |
| `.assembly-completed` | 24 h delete |
| `.assembly-blocked` | 24 h delete |
| `.factory-state` | compact |

---

## Step 2 — Start the sim server

The sim server must be running before the backend can register your factory.

```bash
cd spec_1_simulation
./start_server.sh
```

It starts on `http://localhost:8080` by default.

---

## Step 3 — Start the spec_2 backend

```bash
cd spec_2_hive_controls
./start_backend.sh
```

The script creates (or reuses) `.venv/`, installs all dependencies, and starts the backend on `http://127.0.0.1:8000`. All credentials are read from `.env` on startup — no dialog or manual input required.

---

## Step 4 — Start the frontend

```bash
cd spec_2_hive_controls/frontend
npm run dev
```

Open `http://localhost:5173`. The UI auto-connects on load. If any `.env` values are missing it will show an error banner instead.

---

## Step 5 — Watch provisioning complete

On startup the UI posts to `/api/connect`. Behind the scenes:

1. The backend hits `GET /v1/server` on the sim server to get the current epoch.
2. The backend hits `POST /v1/factories` — the sim server creates your factory and runs probe writes against all 8 Confluent topics.
3. The UI shows a **provisioning** banner while the probe runs (~3–8 s). Controls are disabled until the first `factory.state` event arrives confirming success.

If the sim server logs show `provisioning_probe_failed`, the topics either don't exist yet or the credentials were wrong. Re-check that `provision_topics.sh` ran cleanly and that `CONFLUENT_API_KEY`/`CONFLUENT_API_SECRET` in `.env` are correct.

---

## Step 6 — Start your factory

Click **Start** in the UI. The sim server begins publishing events to your Confluent topics. The backend Kafka consumer receives them and pushes state updates to the UI via SSE.

You should see the dashboard come alive — resource deliveries, manufacturing jobs starting and completing, robots assembling.

---

## Step 7 — Confirm Kafka is the path

Check the backend logs. You should see a line like:

```
Starting Kafka consumer group: hive-1.queen-XXX-<8hex>
```

If you do not see that line after the UI loads, the consumer credentials or bootstrap server in `.env` are wrong.
