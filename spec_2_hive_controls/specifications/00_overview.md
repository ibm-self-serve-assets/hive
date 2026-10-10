# Local Hive Controls: scope

Build the attendee's local application: a React/TypeScript dashboard plus a local Python/FastAPI backend that consumes Confluent events and sends lifecycle commands to the hosted Simulation Server.

The attendee does not run the factory or Kafka broker. They run the UI and local consumer. The local consumer owns a in-memory projection/cache, not authoritative factory state. This replaces the earlier single-laptop simulator architecture.

Observation path: Simulation Server → Kafka producer → Confluent → local Python consumer → local API/SSE → React UI.

Command path: React UI → local Python backend → authenticated Simulation Server endpoints. Commands may be acknowledged before the corresponding observed state arrives. Show those as separate facts.

Use the provided comp/fonts/palette for the base manufacturing view. Extend the sidebar for Stop and Restart at zero, and add a small connection/registration screen. Preserve the three-column factory layout. Schema Registry, colony operations and Queen control remain outside these two packages.

The shared files in contracts/ are identical to the server package. Read them before implementing. Start this package after a server deployment and prepared attendee enrollment are available; fixtures can support early frontend work but are not the integration acceptance test.
