# In-memory event consumer

Use ../..//event_contract.md. The Python backend holds the latest snapshot, bounded event history and duplicate-ID cache in memory. No SQLite database, durable checkpoints or persistent quarantine is required.

Expose local GET /api/state, /api/events and /api/stream from that consumed view only. Never query cloud inventory as a fallback. Validate server_epoch and factory_id against the active server registration; apply newer snapshot generations/revisions and ignore old or foreign factory records.

On local app startup call the server to obtain its epoch and the owner's current factory. If it exists, start a fresh consumer-session group within the authorized prefix and replay available records from earliest, building the view from full snapshots. Do not reuse an old group's end offsets after losing the in-memory view. If the server restarted and the factory is missing, require new registration and begin with awaiting_events for the new factory ID.

Keep only a bounded ring of activity and duplicate IDs. Full-state snapshots replace quantities rather than add inventory, so replay does not inflate counts. Old activity outside retention or memory capacity is intentionally unavailable. Ignore connection.test records and report malformed observations with bounded diagnostics.
- **Duplicate ID Cache Eviction**: Cap the in-memory `seen_event_ids` set (e.g. at 1,000 entries) to prevent memory leaks during long-running streaming sessions. Because full snapshots completely replace state, cache eviction cannot cause duplicate additive inventory bugs.

A local process restart loses the local view but does not stop a still-running server factory. A server process restart loses the factory itself. Explain this difference in the UI. Closing the browser never automatically stops a factory. Connection settings/credentials may be kept in private configuration; that is not durable simulation state.
