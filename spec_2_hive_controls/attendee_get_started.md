# Attendee Get Started

Once `provision_topics.sh` completes, here are the exact steps:

---

## Step 1 — Provision your topics

Run the shell wrapper from the `spec_2_hive_controls/` directory. It creates a `.venv/`, installs all dependencies (including `certifi` for SSL), and runs `provision_topics.py`:

```bash
cd spec_2_hive_controls
./provision_topics.sh
```

When it completes, confirm in Confluent Cloud UI: **Cluster → Topics** — you should see 6 topics prefixed with your `WORKSHOP_ID.ATTENDEE_ID` (e.g. `hive-01.queen-001`).

---

## Step 2 — Start the spec_2 backend

```bash
cd spec_2_hive_controls
./start_backend.sh
```

The script creates (or reuses) `.venv/`, installs all dependencies, and starts the backend on `http://127.0.0.1:8000`. All credentials are read from `.env` on startup — no dialog or manual input required.

---

## Step 3 — Start the frontend

```bash
cd spec_2_hive_controls/frontend
npm run dev
```

Open `http://localhost:5173`. The UI will auto-connect and provision your factory immediately. If any `.env` values are missing it will show an error banner instead.

---

## Step 4 — Watch provisioning complete

The UI posts to `/api/connect`. Behind the scenes:

1. spec_2 hits `GET /v1/server` on your sim server — gets the epoch
2. spec_2 hits `POST /v1/factories` — sim server creates your factory and runs the probe writes against your 6 Confluent topics
3. You can poll the operation status at `GET /v1/operations/{id}` or just wait — the UI should show **connected / paused**

If the sim server logs show `provisioning_probe_failed`, the topics either don't exist yet or the producer credentials were wrong. Re-check that `provision_topics.py` ran cleanly.

---

## Step 5 — Start your factory

Click **Start** in the UI. The sim server begins publishing events to your Confluent topics. The spec_2 Kafka consumer (started when you connected in Step 4) receives them and pushes state updates to the UI via SSE.

You should see the dashboard come alive — resource deliveries, jobs starting, parts being produced, robots assembling.

---

## Step 6 — Confirm Kafka is the path

Check the spec_2 backend logs. You should see:

```
Starting Kafka consumer group: hive-01.queen-XXX-<8hex>
```

If you do not see that line after clicking Connect, the consumer credentials or bootstrap server were wrong. Re-submit the connect dialog with corrected values.
