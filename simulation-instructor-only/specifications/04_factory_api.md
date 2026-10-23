# Owned simulations and controls

Implement ../../spec-shared/simulation_api.md. Keep the endpoint and lifecycle semantics, but store simulation objects, owner mappings, operation results and idempotency caches in memory only.

Use an in-process registration lock to enforce one simulation per enrolled owner and a per-simulation lock for controls/simulation changes. Validate producer credentials asynchronously without holding locks during network calls. A failed provisioning attempt remains available for retry during this process lifetime.

Workshop token hashes and approved cluster profiles are loaded from organizer deployment configuration. Submitted producer secrets exist only in the process and are discarded on expiry/shutdown. No secret store for simulation credentials, database or custom encryption layer is needed. Continue to redact secrets from all logs/responses.

Generate a new server_epoch at boot. Expose it through GET /v1/server; validate X-Server-Epoch on mutations. In-memory idempotency prevents repeat effects only during this epoch. Old requests cannot be replayed automatically after deployment to recreate/reset a simulation.

Test ownership, concurrent registration, command retries, generation conflicts and loss of simulations across server restart. Document that the attendee must re-register after that loss.
