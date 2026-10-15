# Publish observations

Use ../../spec_1_2_shared_contract/event_contract.md and generate matching JSON Schema/fixtures. Include server_epoch and factory_id in every record. The server publishes; the attendee application consumes.

Use one bounded memory queue per factory. Under its lock, check capacity, apply the transition and enqueue event objects. Producer network operations happen outside locks. Retry the same objects/IDs until acknowledged or the process ends. This is not a transactional outbox and offers no crash-safe pending-event recovery.

Enforce fair sending across factories and separate credential/client objects. Stop only the affected factory on buffer exhaustion. No server inventory endpoint or server-hosted dashboard should bypass Kafka observations.
