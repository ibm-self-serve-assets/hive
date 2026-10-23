# Single-process container deployment

Create a locked, non-root Python image with PORT default 8080, /health/live and /health/ready, and graceful termination. Supply organizer enrollment/token hashes and cluster profiles through deployment configuration/secrets; no simulation data goes to disk. No database or persistent volume is required.

Initial deployment: Code Engine min instances=1, max instances=1; exactly one application worker process; disable automatic code reload. Request concurrency can exceed one, with in-process locks protecting shared state. Do not horizontally scale this memory-only implementation.

Treat every redeploy/replacement as a destructive simulation reset. Min/max settings do not guarantee preservation or prevent revision overlap. For planned updates, close admissions, stop the old service completely, then start/route to the new one (a maintenance interruption). Do not use a rolling overlap or split traffic between old/new processes. If the platform configuration cannot enforce that operating procedure, do not claim this prototype is safe for live rolling updates. Process epochs distinguish stale clients but are not distributed locks.

Unplanned process loss also loses all simulations. On reconnection, clients detect a changed epoch or missing simulation and ask attendees to register again. Old Kafka snapshots cannot recreate simulations. No high-availability or disaster recovery guarantee is made.

On shutdown stop admission/ticks, try a bounded producer flush, then exit. Warn that unacknowledged queued events may be lost. Readiness checks server configuration, not individual attendees' Kafka credentials. Test background progress with no HTTP traffic and the intended attendee count before class.

Configure maximum simulations, per-simulation queue byte/record limits, six-hour TTL and cleanup. This request creates specs, not deployment resources.

Reference for configurable scaling: https://cloud.ibm.com/docs/codeengine?topic=codeengine-app-scale
