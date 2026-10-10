# spec_2_hive_controls

This is an engineering specification package, not an implemented application. Read the ordered documents in specifications/. References such as nn_setup.md refer to the current document with that suffix; numeric prefixes can change. Keep the supplied directory structure and put implementation code alongside specifications/ at package root.

Start with nn_overview.md, then read all specifications before implementation. Shared API/event contracts in contracts/ are identical in both packages. Proposed deployment and security defaults are explained explicitly so they can be refined before implementation.

No cloud resources, accounts or credentials were created by this package. No real API keys are included.

Current scope: memory-only simulation and UI projection. No application database or crash recovery. Kafka retains already-published events under its own topic policy. Server restart loses factories; local app restart only loses its displayed cache.

## Implementation Lessons Learned (Spec 2)

Key non-obvious architecture and frontend/consumer insights discovered during implementation:
- **Font Asset Location in React/Vite**: Fonts located in `specifications/assets/fonts/` must be placed in `frontend/public/fonts/` so `@font-face` URL paths (`/fonts/IBMPlexSans-*.ttf`) can be fetched by the browser dev server and bundled during production builds without bundler path resolution errors.
- **Vite Proxy & Anti-CSRF Boundary**: When proxying `/api` requests from Vite (`:5173`) to FastAPI (`:8000`), issue an initial `GET /api/csrf` on app load and attach `X-CSRF-Token` headers to all mutating control calls (`/api/controls`, `/api/connect`) to satisfy strict localhost origin validation.
- **Separate Accepted vs Observed Status**: Command execution returns HTTP 200 immediately with a command receipt (`command_id`, `accepted=true`), but the UI state must not update factory inventory until the corresponding `factory.state` snapshot arrives via the consumer SSE stream. Maintain a separate `latest_command_receipt` in the projection store.
- **Consumer Group Ephemeral Sessioning**: Because in-memory state is discarded on local app restart, Kafka consumers must append a unique session suffix to their assigned `consumer_group_prefix` (e.g. `{prefix}-session-{uuid}`) and configure `auto.offset.reset: earliest` to replay the compacted `.factory-state` snapshot from the beginning.
