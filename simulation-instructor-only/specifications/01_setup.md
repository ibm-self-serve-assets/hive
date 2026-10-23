# Prepare the prototype

Provide a Code Engine project/region, image registry, approved Confluent cluster profiles, precreated attendee topics/permissions and organizer-issued workshop tokens. Load enrollment/token hashes and connection profiles from a mounted deployment configuration/secret. They are setup inputs, not a simulation-state database.

Use Python 3.11+, FastAPI, a Kafka client, JSON Schema validation and container tooling. Rancher with Moby/dockerd or Docker is suitable for development. No database installation, migration or encryption-key service is required.

Generate server/, schemas/, tests/, deployment/, reports/ and Dockerfile at package root. Implement specifications/scripts/setup_validation.py to check tools, configuration and selected integration/deployment prerequisites without printing secrets. Keep root .env private and use .env.example as the template.

Run one server process. Use process locks for registration and per-simulation transitions. Build deterministic tests using in-memory state and a controllable clock. Integration tests additionally need real Confluent access. No application code or cloud resources are supplied merely by this specification.

## Server configuration: root .env

The .env and .env.example files use the same configuration names. For local development, load root .env. In Code Engine, supply the same values as deployment environment variables and mount the enrollment configuration through the deployment's configuration/secret mechanism. Explicit process environment values override .env values. Do not embed configuration secrets in the image.

| Variable | Default | Purpose and behavior |
| --- | --- | --- |
| PORT | 8080 | HTTP port inside the container. Bind the service to 0.0.0.0 inside the container so the platform can reach it. |
| MAX_FACTORIES | 25 | Maximum resident, non-expired simulation instances across the server, including provisioning, paused, running, stopped and failed-provisioning instances. Reject additional creation with 429 capacity_reached. The one-simulation-per-attendee rule still applies. Expiry removes the simulation from this count; its small expired marker remains until process exit. |
| FACTORY_TTL_SECONDS | 21600 | Six-hour lifetime measured in wall time from successful provisioning. Pause, Stop and Restart at zero do not extend it. At expiry halt the simulation, release credentials/workers and return 410 for controls, as defined by the API contract. |
| FACTORY_BUFFER_LIMIT_EVENTS | 10000 | Maximum pending, unacknowledged production/snapshot events per simulation in memory. This replaces the older FACTORY_BACKLOG_LIMIT_EVENTS setting. Check capacity before applying a transition. |
| FACTORY_BUFFER_LIMIT_BYTES | 16777216 | 16 MiB maximum serialized UTF-8 payload plus key bytes for pending records per simulation. Either this limit or the event-count limit can trigger buffer_full. Actual Python/client memory overhead is additional. |
| SIM_TICK_MILLISECONDS | 100 | Scheduler wake-up interval in wall-clock milliseconds. It is not a job duration or fixed amount of simulated time. Advance by actual elapsed monotonic time multiplied by 1x/5x and process intervening deadlines. |
| SNAPSHOT_INTERVAL_MILLISECONDS | 200 | Minimum interval between routine running snapshots in wall time: default five snapshots per second. Immediate lifecycle snapshots may occur between routine snapshots. Paused/stopped heartbeat snapshots remain once per second. This interval does not change manufacturing speed. |

These are starting defaults for rehearsal, not a measured capacity guarantee. At 25 simulations, the per-simulation byte limit alone allows up to 400 MiB of serialized queued data, plus interpreter, simulation and Kafka-client overhead. Size the container and test the intended cohort; MAX_FACTORIES is admission control, not a Code Engine scaling setting.

## Buffer accounting and behavior

Count queued and in-flight unacknowledged events once. Retrying the same record does not add another queue entry or byte charge. Release its charge after broker acknowledgment. Keep a small fixed control allowance of at most 16 records / 64 KiB per simulation in addition to the configured limits, for Pause/Stop/error notifications; this allowance is included in memory planning.

If a simulation transition would exceed either production limit, leave it unapplied and flag buffer_full. A running simulation stops advancing time until the buffer drains and the attendee explicitly resumes. Start may clear this operational error only when capacity exists; otherwise return 409 buffer_full. Stop/Pause remain usable. Restart at zero must not silently discard earlier pending events: reject it with 409 buffer_full if its initial snapshot cannot fit. Never silently evict accepted records to make room. A process restart still loses every pending record.

## Enrollment configuration and credentials

The attendee list is loaded from `schemas/workshop_attendees.json` at startup. The implementation must document and validate its JSON shape, uniqueness of attendee IDs, token-hash format. Load it into memory on startup; runtime editing and hot reload are outside this prototype.

Do not place attendees' producer API secrets in that enrollment file. They are submitted at simulation registration and kept only in server process memory. Simulation objects and idempotency history are not written back to the configuration file.

## Validation and old settings

Validate all numeric settings as positive integers and PORT as a valid port. Configuration errors must name the setting without revealing tokens or secrets.

FACTORY_BACKLOG_LIMIT_EVENTS=100000 belongs to the earlier durable-outbox proposal. The current memory-only configuration uses FACTORY_BUFFER_LIMIT_EVENTS=10000 and an explicit byte limit. Do not accept the old variable silently: report it as obsolete and direct the engineer to the new name. Remove DATABASE_URL and CREDENTIAL_ENCRYPTION_KEY if present in an older .env. Reject those obsolete settings when loaded from the project's .env or explicitly supplied to the application; no database or credential-encryption service is configured here.
