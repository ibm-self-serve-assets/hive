# spec-1-simulation

This is an engineering specification package, not an implemented application. Read the ordered documents in specifications/. Documents are referenced by their numbered file names (for example 01_setup.md). Keep the supplied directory structure and put implementation code alongside specifications/ at package root.

Start with specifications/00_overview.md, then read all specifications before implementation. The shared API/event contracts live in ../spec_1_2_shared_contract/ and are used by both packages. Proposed deployment and security defaults are explained explicitly so they can be refined before implementation.

No cloud resources, accounts or credentials were created by this package. No real API keys are included.

Current scope: memory-only simulation and UI projection. No application database or crash recovery. Kafka retains already-published events under its own topic policy. Server restart loses factories; local app restart only loses its displayed cache.

When replacing an older extraction, overwrite its root .env with the included clean .env (or copy .env.example). Old DATABASE_URL or credential-encryption settings are not used by this memory-only prototype. Supply only the enrollment configuration path needed by this version.

## Implementation Lessons Learned (Spec 1)

Key non-obvious architecture and testing insights discovered during implementation:
- **Module & Working Directory Resolution**: Scripts under `specifications/scripts/` and test suites under `tests/` must resolve `schemas/` and `.env` relative to the package root (`spec-1-simulation/`), using `parent.parent.parent` or `PYTHONPATH=.` when invoking tools like `uv` or `pytest`.
- **Scheduling Pass Cascades**: Scheduling does not simply run once per tick. When a job completes at simulated time $t$, its released slot and newly produced parts can satisfy recipes for downstream stations (e.g. `worker_assembly`) at that exact same simulated instant. Loop the rotating tie-break pass until no further idle stations can start.
- **Kafka Availability Fallbacks**: When running unit tests or local rehearsals without a live Confluent broker, `confluent-kafka` C-bindings may be absent or unreachable. The producer layer should gracefully detect missing C-bindings or broker unavailability, providing synchronous mock acknowledgment for unit/schema validation without hanging network threads.
- **Idempotency Key Digesting**: Mutating endpoints require `Idempotency-Key` headers. When hashing request payloads to detect idempotency collisions, do not hash raw credential objects or variable-order dictionaries. Sort dictionary keys and use SHA-256 digests in memory.
