# Attendee setup

## Needed on the laptop

Python 3.11+ with pip/venv, Node.js 22.12+, npm, git and a browser. Use the Python/FastAPI + React/TypeScript baseline. No Rancher, Docker, local Kafka, database or cloud account login is needed to run this attendee package.

Provide a private workshop token, Simulation Server HTTPS URL, approved connection profile, Confluent consumer bootstrap endpoint and key/secret. Provisioning additionally needs producer credentials to submit to the server. These can be the same attendee-scoped pair for a pilot, but separate keys are preferred. A key alone is insufficient.

Implement specifications/scripts/setup_validation.py for local tools, root configuration, loopback ports and supplied assets. Add distinct checks for server reachability/token validity, Confluent metadata and actual consumer access once a factory is provisioned. Never echo configuration secrets. Do not copy the older container/Kafka broker validator into this package.

## Local project

Generate backend/, frontend/, schemas/, tests/, runtime/ and reports/ alongside specifications/. Put private root .env outside git; .env.example contains placeholders. Keep the projection and event history in memory; no local database is needed. Bind backend/frontend to loopback and restrict origins to the exact local frontend origin. Route every server call through the local backend so workshop tokens do not enter browser storage.

Cloud server and Confluent outages should produce a usable disconnected UI. Closing the laptop or browser does not pause the hosted factory. The attendee must explicitly Pause/Stop, or wait for server TTL expiry.

## Configure root .env

The included .env and .env.example are matching templates. Populate .env privately before connecting. All variables below are read by the local Python backend or its development launcher, never bundled into React.

| Variable | Meaning and source | Required |
| --- | --- | --- |
| SIMULATION_SERVER_URL | HTTPS base URL of the deployed Spec 1 Simulation Server, supplied by the organizer. Do not append /v1; the client adds API paths. Example shape: https://your-simulation-server.example | Yes |
| WORKSHOP_ACCESS_TOKEN | Organizer-issued owner token. The local backend sends it as a Bearer token to the Simulation Server. It is not a Confluent key. | Yes |
| CONNECTION_PROFILE_ID | Organizer-issued profile identifier for the approved Confluent cluster/namespace. Sent during factory registration. | Yes |
| CONFLUENT_BOOTSTRAP_SERVERS | Kafka bootstrap host:port from the assigned Confluent cluster's client configuration. Must match the selected profile; this is not the Simulation Server URL. | Yes |
| CONFLUENT_CONSUMER_API_KEY | Kafka API key for an identity allowed to read the assigned factory topics and use the assigned consumer-group prefix. Maps to the local consumer's SASL username. | Yes |
| CONFLUENT_CONSUMER_API_SECRET | Secret paired with that Kafka API key. Maps to the local consumer's SASL password. Obtain it when the key is created or have the organizer supply it privately. | Yes |
| LOCAL_BACKEND_HOST | Local API bind address; retain 127.0.0.1. | Default supplied |
| LOCAL_BACKEND_PORT | Port for the local Python API, default 8000. | Default supplied |
| LOCAL_FRONTEND_PORT | Port for the local React development server, default 5173. | Default supplied |

Consumer credentials remain in the local backend. Producer credentials are entered separately for factory registration and sent over HTTPS to the Simulation Server. If the pilot uses one pair with both permissions, the attendee may intentionally use that same pair in both places; consumer keys must never be assumed to have write permissions.

The connection screen initializes from backend configuration but returns only presence/masked status for secrets. Session edits override .env for that session; persist only when the attendee explicitly chooses Save, using the private configuration mechanism in nn_connection.md. Keep bootstrap/profile consistent. A process restart reloads saved configuration, not simulation state.

## Validation requirements

The generated setup validator must name missing/placeholder settings without printing values. Validate the server URL, profile presence, loopback host and distinct local ports. Then check the authenticated GET /v1/server, establish a TLS/SASL Kafka metadata connection, and test real read/group permissions after the assigned topics are known. A metadata connection alone is not a successful consumer test.

## No projection database

PROJECTION_DATABASE_PATH is an obsolete setting from the earlier SQLite design. Remove it from older .env files; the implementation must not create or open a projection database. Keep the latest observed snapshot and bounded event history in memory. On local application restart, rediscover the current factory and rebuild the view from Kafka as described in nn_consumer.md.

When updating an older extraction, replace its .env with this template and transfer only the still-supported connection values from your private copy. Do not publish populated credentials.
