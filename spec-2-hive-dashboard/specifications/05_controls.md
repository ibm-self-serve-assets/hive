# Factory controls

Implement ../../spec-shared/factory_api.md through the local backend. The browser does not call the cloud API with a bearer token directly. Local command endpoints validate a per-session anti-CSRF token and exact allowed origin; do not accept arbitrary cross-origin control or credential-setting requests on localhost.

| Button | Server action | UI behavior |
| --- | --- | --- |
| Start | POST start | Start/resume paused run; no duplicate action while pending |
| Pause | POST pause | Freeze same run; allow Start later |
| Stop | POST stop | Confirm current run ends; Start no longer resumes it |
| Restart at zero | POST restart | Confirm inventory/work reset; default start=true, offer start=false |
| 1x / 5x | POST speed | Change future rate only |

Send Idempotency-Key and expected_generation from the latest known server metadata. If an old command conflicts after restart, fetch control metadata and ask the engineer to retry deliberately; do not silently retarget it to the new run. Network retry of an unchanged request retains its idempotency key. A new deliberate click gets a new key.

Keep displayed inventory from Kafka until the matching/newer-generation snapshot arrives. Server metadata may establish that Stop or Restart succeeded even while Kafka is disconnected, but must not populate the observed factory view. Later commands can supersede a pending observation; reconcile using command receipts, generations and last_applied_command_id rather than waiting forever for an exact old snapshot that may be compacted.

Handle 401 with reauthentication, 404 as unavailable/not owned, 409 as stale generation or invalid lifecycle, 410 as expired, 429 with Retry-After/backoff where supplied, and 503 as temporarily unable to commit. Do not retry a destructive restart with a new idempotency key after an ambiguous timeout.

## Server replacement

Read GET /v1/server and include X-Server-Epoch on mutations. On server_restarted or missing factory, discard pending commands and require deliberate re-registration. Idempotency caches do not survive a server process restart. Never silently retry an ambiguous old Restart or registration against the new epoch.
