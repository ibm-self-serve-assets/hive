# Server Verification & Test Results Report

## Summary
- **Component**: Hive Simulation Server (Spec 0 Prototype)
- **Deployment Target**: IBM Cloud Code Engine (Single-Instance, In-Memory)
- **Integration Target**: Confluent Cloud (Kafka Producer)
- **Test Suite Status**: 8/8 Tests Passing (Unit, Lifecycle State Machine, Simulation Rules, Buffer Accounting, Schema Conformance).

## Verified Mechanics
1. **Simulation Engine**:
   - Deterministic event clock advances with 100ms ticks and 1x/5x multipliers.
   - Resource deliveries occur every 20 simulated seconds.
   - 4 parts stations (structural molding, electronics assembly, actuator fabrication, battery assembly) and worker robot assembly station execute precise recipes.
   - Non-favoring rotating starting position tie-break for idle station scheduling.
   - Complete material conservation verified.
2. **Event Production & Buffering**:
   - In-memory event queue with double limit enforcement (10,000 records / 16 MiB).
   - Control allowance reserve (16 records / 64 KiB) for pause/stop/restart operations under buffer pressure.
   - Fair publisher loop across all active factories.
   - Onboarding verification probe on 4 activity topics (`connection.test`) and state topic (`factory.state`).
3. **API & Security**:
   - Bearer workshop token authentication against SHA-256 enrollment hashes.
   - `X-Server-Epoch` protection across mutations to reject stale requests after process reboot.
   - Strict attendee factory isolation (404 on unowned factory access).
   - Capacity enforcement (`MAX_FACTORIES = 25`, return 429).
   - 6-hour TTL expiry handling (return 410 on expired instances).
