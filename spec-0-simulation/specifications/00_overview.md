# Simulation Server: memory-only prototype

Build one containerized Python/FastAPI server that creates an owned logical Hive Factory when an enrolled attendee submits Confluent producer credentials. The local consumer/UI is a separate package.

Observation path: hosted simulation → Kafka producer → Confluent → local consumer → UI. Commands use the server API independently.

Each factory is an in-memory object containing clock, resources, jobs, robots, lifecycle, owner, credentials and a bounded pending-event queue. Use one process and one Code Engine instance. No PostgreSQL, SQLite, durable outbox, migrations, leases or recovery store is required.

Start/Pause/Stop/Restart at zero continue to work during the server process lifetime. A server crash or deployment loses all factories and unsent events. Attendees register again and start from zero. Already-published Kafka records remain observations, not backups from which the server restores factories.

Use a server_epoch on each boot and new factory IDs on re-registration to prevent stale clients/events from targeting replacement factories. Preserve separate workshop-owner tokens and Confluent credentials. Enrollment hashes and approved cluster profiles are organizer deployment configuration, loaded into memory on startup.

This simplification is intentional for the first build. State durability and horizontal scaling can be added later without changing the factory mechanics. Read 02_simulation.md and the shared contracts in ../../spec_1_2_shared_contract/ before implementation.
