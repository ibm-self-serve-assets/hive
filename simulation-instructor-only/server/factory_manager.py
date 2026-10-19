import asyncio
import collections
import hashlib
import json
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any

from server.config import ServerConfig, EnrollmentConfig, EnrollmentRecord
from server.models import (
    EventEnvelope,
    FactoryStatePayload,
    FactoryInitializedPayload,
    OperationalError,
)
from server.rules import get_simulation_rules
from topics import TOPICS
from server.simulation import SimulationRun
from server.buffer import FactoryEventBuffer, QueuedEvent
from server.producer import FactoryKafkaProducer

logger = logging.getLogger("hive.factory")


class FactoryInstance:
    def __init__(
        self,
        factory_id: str,
        owner_attendee_id: str,
        server_epoch: str,
        enrollment_record: EnrollmentRecord,
        config: ServerConfig,
    ):
        self.factory_id = factory_id
        self.owner_attendee_id = owner_attendee_id
        self.server_epoch = server_epoch
        self.enrollment_record = enrollment_record
        self.config = config

        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at + timedelta(seconds=config.factory_ttl_seconds)

        self.lock = asyncio.Lock()
        self.event_sequence: int = 0
        self.run_generation: int = 1

        self.current_run = SimulationRun(
            factory_id=self.factory_id,
            server_epoch=self.server_epoch,
            run_id=str(uuid.uuid4()),
            run_generation=self.run_generation,
            lifecycle_status="provisioning",
        )

        self.buffer = FactoryEventBuffer(
            max_events=config.factory_buffer_limit_events,
            max_bytes=config.factory_buffer_limit_bytes,
        )

        # Read-only ring buffer for the /events API — never drained by the producer.
        # Holds the last 200 activity events so direct-poll consumers never miss events
        # that have already been acknowledged out of the main buffer.
        self.event_log: collections.deque = collections.deque(maxlen=200)

        self.producer: Optional[FactoryKafkaProducer] = None
        self.producer_key: Optional[str] = None
        self.producer_secret: Optional[str] = None

        self.last_tick_wall_time: float = time.monotonic()
        self.last_snapshot_wall_time: float = 0.0

        # Per-factory publish back-off state (exponential, capped at 5 s)
        self.publish_failure_count: int = 0
        self.publish_next_retry_after: float = 0.0  # monotonic time

        # Command receipts and idempotency cache: idempotency_key -> response_dict
        self.idempotency_cache: Dict[str, Tuple[str, Dict[str, Any]]] = {}

        self.is_expired: bool = False
        # Set when expiry is first detected; the simulation loop publishes the
        # final expired snapshot and releases the producer while it is still open.
        self.final_publish_pending: bool = False

    def next_event_sequence(self) -> int:
        self.event_sequence += 1
        return self.event_sequence

    def check_expiry(self) -> bool:
        if self.is_expired:
            return True
        max_sim_ms = 14 * 24 * 60 * 60_000  # 14 days = 20,160 sim minutes
        if datetime.now(timezone.utc) >= self.expires_at or self.current_run.sim_time_ms >= max_sim_ms:
            self.is_expired = True
            self.current_run.lifecycle_status = "expired"
            self.current_run.operational_error = None
            self.final_publish_pending = True
            return True
        return False

    def get_topics(self) -> Dict[str, str]:
        return {k.lstrip(".").replace("-", "_"): v for k, v in TOPICS.items()}


class OperationRecord:
    def __init__(self, operation_id: str, owner_attendee_id: str, factory_id: str, op_type: str):
        self.operation_id = operation_id
        self.owner_attendee_id = owner_attendee_id
        self.factory_id = factory_id
        self.op_type = op_type
        self.status = "pending"  # pending, succeeded, failed
        self.error_code: Optional[str] = None
        self.error_message: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)


class FactoryManager:
    def __init__(self, config: ServerConfig, enrollment_config: EnrollmentConfig):
        self.config = config
        self.enrollment_config = enrollment_config
        self.server_epoch = str(uuid.uuid4())

        self.registration_lock = asyncio.Lock()
        
        # attendee_id -> factory_id
        self.owner_factories: Dict[str, str] = {}
        # factory_id -> FactoryInstance
        self.factories: Dict[str, FactoryInstance] = {}
        # operation_id -> OperationRecord
        self.operations: Dict[str, OperationRecord] = {}

        # Global registration idempotency: idempotency_key -> (request_hash, response_dict)
        self.registration_idempotency: Dict[str, Tuple[str, Dict[str, Any]]] = {}

        self._running = False
        self._tick_task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._tick_task = asyncio.create_task(self._simulation_loop())
        self._flush_task = asyncio.create_task(self._publisher_loop())
        logger.info(f"FactoryManager started with server_epoch={self.server_epoch}")

    async def stop(self):
        self._running = False
        if self._tick_task:
            self._tick_task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        for f in self.factories.values():
            if f.producer:
                f.producer.close()
        logger.info("FactoryManager stopped")

    def get_server_epoch(self) -> str:
        return self.server_epoch

    def validate_epoch(self, epoch_header: Optional[str]):
        if not epoch_header or epoch_header != self.server_epoch:
            raise ValueError("server_restarted")

    async def register_factory(
        self,
        attendee_id: str,
        bootstrap_server: str,
        producer_key: str,
        producer_secret: str,
        idempotency_key: str,
    ) -> Tuple[int, Dict[str, Any]]:
        # Check global registration idempotency
        req_body_str = f"{bootstrap_server}:{producer_key}"
        req_hash = hashlib.sha256(req_body_str.encode("utf-8")).hexdigest()

        async with self.registration_lock:
            if idempotency_key in self.registration_idempotency:
                stored_hash, stored_resp = self.registration_idempotency[idempotency_key]
                if stored_hash == req_hash:
                    return 202, stored_resp
                else:
                    return 409, {
                        "error_code": "idempotency_conflict",
                        "message": "Idempotency key reused with different request payload",
                    }

            # Check if attendee already has an active factory
            existing_fid = self.owner_factories.get(attendee_id)
            if existing_fid:
                existing_f = self.factories.get(existing_fid)
                if existing_f and not existing_f.is_expired and not existing_f.check_expiry():
                    return 409, {
                        "error_code": "factory_already_exists",
                        "message": "Attendee already owns an active factory instance",
                        "factory_id": existing_fid,
                    }

            # Find enrollment record
            enrollment_rec = self.enrollment_config.find_by_attendee_id(attendee_id)
            if not enrollment_rec:
                return 401, {"error_code": "unauthorized", "message": "Attendee not enrolled"}

            if not bootstrap_server:
                return 400, {
                    "error_code": "missing_bootstrap_server",
                    "message": "bootstrap_server is required",
                }

            factory_id = str(uuid.uuid4())
            operation_id = str(uuid.uuid4())

            factory = FactoryInstance(
                factory_id=factory_id,
                owner_attendee_id=attendee_id,
                server_epoch=self.server_epoch,
                enrollment_record=enrollment_rec,
                config=self.config,
            )
            factory.producer_key = producer_key
            factory.producer_secret = producer_secret

            factory.producer = FactoryKafkaProducer(
                bootstrap_servers=bootstrap_server,
                security_protocol="SASL_SSL",
                sasl_mechanism="PLAIN",
                api_key=producer_key,
                api_secret=producer_secret,
            )

            op = OperationRecord(
                operation_id=operation_id,
                owner_attendee_id=attendee_id,
                factory_id=factory_id,
                op_type="provision_factory",
            )

            self.factories[factory_id] = factory
            self.owner_factories[attendee_id] = factory_id
            self.operations[operation_id] = op

            resp = {
                "factory_id": factory_id,
                "operation_id": operation_id,
                "status_url": f"/v1/operations/{operation_id}",
                "server_epoch": self.server_epoch,
            }
            self.registration_idempotency[idempotency_key] = (req_hash, resp)

        # Trigger background verification asynchronously outside lock
        asyncio.create_task(
            self._verify_provisioning_task(factory_id, operation_id)
        )

        return 202, resp

    async def _verify_provisioning_task(self, factory_id: str, operation_id: str):
        factory = self.factories.get(factory_id)
        op = self.operations.get(operation_id)
        if not factory or not op:
            return

        # Prepare empty paused snapshot event for probe
        async with factory.lock:
            factory.current_run.lifecycle_status = "paused"
            _, snapshot_event = factory.current_run.create_snapshot_event(
                event_seq_generator=factory.next_event_sequence,
            )
            # Temporarily revert lifecycle to provisioning until verification passes
            factory.current_run.lifecycle_status = "provisioning"

        producer = factory.producer
        if not producer:
            op.status = "failed"
            op.error_code = "no_producer"
            op.error_message = "Producer initialization failed"
            async with factory.lock:
                factory.current_run.lifecycle_status = "provisioning_failed"
            return

        ok, err_msg = await producer.verify_permissions_and_topics(
            factory_id=factory.factory_id,
            server_epoch=factory.server_epoch,
            run_id=factory.current_run.run_id,
            run_generation=factory.current_run.run_generation,
            operation_id=operation_id,
            empty_snapshot_event=snapshot_event,
            next_event_seq_fn=factory.next_event_sequence,
        )

        async with factory.lock:
            if ok:
                op.status = "succeeded"
                factory.current_run.lifecycle_status = "paused"

                # Publish factory.initialized — marks the moment this factory
                # became ready. Published to .factory-state (compact topic) so
                # consumers replaying from earliest always see it.
                rules = get_simulation_rules()
                station_recipes = {m.station_id: dict(m.inputs) for m in rules.manufacturing}
                station_recipes[rules.worker_assembly.station_id] = dict(rules.worker_assembly.inputs)
                init_payload = FactoryInitializedPayload(
                    operation_id=operation_id,
                    attendee_id=factory.owner_attendee_id,
                    expires_at=factory.expires_at.isoformat(),
                    station_recipes=station_recipes,
                )
                init_event = EventEnvelope(
                    event_id=str(uuid.uuid4()),
                    event_type="factory.initialized",
                    schema_version=1,
                    factory_id=factory.factory_id,
                    server_epoch=factory.server_epoch,
                    run_id=factory.current_run.run_id,
                    run_generation=factory.current_run.run_generation,
                    event_sequence=factory.next_event_sequence(),
                    state_revision=factory.current_run.state_revision,
                    occurred_at=datetime.now(timezone.utc).isoformat(),
                    sim_time_minutes=0,
                    causation_id=operation_id,
                    payload=init_payload.model_dump(),
                )
                factory.buffer.enqueue(".factory-state", init_event, is_control=True)

                # Queue initial empty paused snapshot into buffer
                factory.buffer.enqueue(".factory-state", snapshot_event, is_control=True)
            else:
                op.status = "failed"
                op.error_code = "provisioning_probe_failed"
                op.error_message = err_msg or "Verification probe failed"
                factory.current_run.lifecycle_status = "provisioning_failed"

    async def rotate_connection(
        self,
        factory_id: str,
        attendee_id: str,
        bootstrap_server: str,
        producer_key: str,
        producer_secret: str,
        idempotency_key: str,
    ) -> Tuple[int, Dict[str, Any]]:
        factory = self.factories.get(factory_id)
        if not factory or factory.owner_attendee_id != attendee_id:
            return 404, {"error_code": "not_found", "message": "Factory not found"}

        if factory.check_expiry():
            return 410, {"error_code": "expired", "message": "Simulation expired"}

        req_body_str = f"{bootstrap_server}:{producer_key}"
        req_hash = hashlib.sha256(req_body_str.encode("utf-8")).hexdigest()

        async with factory.lock:
            if idempotency_key in factory.idempotency_cache:
                stored_hash, stored_resp = factory.idempotency_cache[idempotency_key]
                if stored_hash == req_hash:
                    return 202, stored_resp
                else:
                    return 409, {
                        "error_code": "idempotency_conflict",
                        "message": "Idempotency key reused with different request payload",
                    }

            operation_id = str(uuid.uuid4())
            op = OperationRecord(
                operation_id=operation_id,
                owner_attendee_id=attendee_id,
                factory_id=factory_id,
                op_type="rotate_connection",
            )
            self.operations[operation_id] = op

            resp = {
                "operation_id": operation_id,
                "status_url": f"/v1/operations/{operation_id}",
                "server_epoch": self.server_epoch,
            }
            factory.idempotency_cache[idempotency_key] = (req_hash, resp)

        # Asynchronously verify replacement credentials
        asyncio.create_task(
            self._verify_rotation_task(
                factory_id, operation_id, bootstrap_server, producer_key, producer_secret
            )
        )

        return 202, resp

    async def _verify_rotation_task(
        self,
        factory_id: str,
        operation_id: str,
        bootstrap_server: str,
        producer_key: str,
        producer_secret: str,
    ):
        factory = self.factories.get(factory_id)
        op = self.operations.get(operation_id)
        if not factory or not op:
            return

        test_producer = FactoryKafkaProducer(
            bootstrap_servers=bootstrap_server,
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            api_key=producer_key,
            api_secret=producer_secret
        )

        async with factory.lock:
            _, snapshot_event = factory.current_run.create_snapshot_event(
                event_seq_generator=factory.next_event_sequence,
            )

        ok, err_msg = await test_producer.verify_permissions_and_topics(
            factory_id=factory.factory_id,
            server_epoch=factory.server_epoch,
            run_id=factory.current_run.run_id,
            run_generation=factory.current_run.run_generation,
            operation_id=operation_id,
            empty_snapshot_event=snapshot_event,
            next_event_seq_fn=factory.next_event_sequence,
        )

        async with factory.lock:
            if ok:
                op.status = "succeeded"
                old_producer = factory.producer
                factory.producer = test_producer
                factory.producer_key = producer_key
                factory.producer_secret = producer_secret
                if old_producer:
                    old_producer.close()
            else:
                op.status = "failed"
                op.error_code = "rotation_verification_failed"
                op.error_message = err_msg or "Replacement credentials probe failed"
                test_producer.close()

    async def execute_command(
        self,
        factory_id: str,
        attendee_id: str,
        command: str,  # start, pause, stop, restart
        body: Dict[str, Any],
        idempotency_key: str,
    ) -> Tuple[int, Dict[str, Any]]:
        factory = self.factories.get(factory_id)
        if not factory or factory.owner_attendee_id != attendee_id:
            return 404, {"error_code": "not_found", "message": "Factory not found"}

        if factory.check_expiry():
            return 410, {"error_code": "expired", "message": "Simulation expired"}

        req_body_str = f"{command}:{sorted(body.items())}"
        req_hash = hashlib.sha256(req_body_str.encode("utf-8")).hexdigest()

        async with factory.lock:
            # Check idempotency cache
            if idempotency_key in factory.idempotency_cache:
                stored_hash, stored_resp = factory.idempotency_cache[idempotency_key]
                if stored_hash == req_hash:
                    return 200, stored_resp
                else:
                    return 409, {
                        "error_code": "idempotency_conflict",
                        "message": "Idempotency key reused with different request payload",
                    }

            # Check expected_generation if provided
            expected_gen = body.get("expected_generation")
            if expected_gen is not None and expected_gen != factory.current_run.run_generation:
                return 409, {
                    "error_code": "generation_conflict",
                    "message": f"Expected generation {expected_gen} does not match current {factory.current_run.run_generation}",
                }

            curr_status = factory.current_run.lifecycle_status

            if curr_status in ("provisioning", "provisioning_failed"):
                return 409, {
                    "error_code": "invalid_lifecycle_state",
                    "message": f"Cannot execute command while factory is {curr_status}",
                }

            command_id = str(uuid.uuid4())
            applied_at = datetime.now(timezone.utc).isoformat()
            new_events: List[Tuple[str, EventEnvelope]] = []

            if command == "start":
                if curr_status == "stopped":
                    return 409, {
                        "error_code": "stopped_run",
                        "message": "Stopped run cannot be resumed; use restart at zero",
                    }
                if curr_status == "running":
                    # No-op
                    pass
                elif curr_status == "paused":
                    # Check if operational error was buffer_full
                    if factory.current_run.operational_error and factory.current_run.operational_error.code == "buffer_full":
                        # Check capacity
                        if not factory.buffer.can_fit([], is_control=False):
                            return 409, {
                                "error_code": "buffer_full",
                                "message": "Buffer is still full; cannot resume",
                            }
                        factory.current_run.operational_error = None

                    factory.current_run.lifecycle_status = "running"
                    factory.last_tick_wall_time = time.monotonic()
                    # Trigger initial scheduling if at time 0
                    if factory.current_run.sim_time_ms == 0:
                        sched_events = factory.current_run.initial_scheduling(
                            event_seq_generator=factory.next_event_sequence,
                            occurred_at=applied_at,
                        )
                        new_events.extend(sched_events)

            elif command == "pause":
                if curr_status == "stopped":
                    return 409, {
                        "error_code": "stopped_run",
                        "message": "Stopped run cannot be paused",
                    }
                if curr_status == "running":
                    factory.current_run.lifecycle_status = "paused"
                elif curr_status == "paused":
                    # No-op
                    pass

            elif command == "stop":
                if curr_status in ("running", "paused"):
                    factory.current_run.lifecycle_status = "stopped"
                elif curr_status == "stopped":
                    # No-op
                    pass

            elif command == "restart":
                # Restart at zero creates a new generation
                start_immediately = body.get("start", True)
                new_gen = factory.run_generation + 1
                factory.run_generation = new_gen
                factory.event_log.clear()

                # Check buffer capacity for empty snapshot
                factory.current_run = SimulationRun(
                    factory_id=factory.factory_id,
                    server_epoch=factory.server_epoch,
                    run_id=str(uuid.uuid4()),
                    run_generation=new_gen,
                    lifecycle_status="running" if start_immediately else "paused",
                )
                factory.last_tick_wall_time = time.monotonic()

                # Generate initial empty time-zero snapshot
                snap = factory.current_run.create_snapshot_event(
                    event_seq_generator=factory.next_event_sequence,
                    occurred_at=applied_at,
                )
                if not factory.buffer.can_fit([snap], is_control=True):
                    return 409, {
                        "error_code": "buffer_full",
                        "message": "Buffer full; cannot fit initial restart snapshot",
                    }
                new_events.append(snap)

                if start_immediately:
                    sched_events = factory.current_run.initial_scheduling(
                        event_seq_generator=factory.next_event_sequence,
                        occurred_at=applied_at,
                    )
                    new_events.extend(sched_events)

            factory.current_run.last_applied_command_id = command_id

            # Create immediate lifecycle snapshot
            snap = factory.current_run.create_snapshot_event(
                event_seq_generator=factory.next_event_sequence,
                occurred_at=applied_at,
                causation_id=command_id,
            )
            new_events.append(snap)

            # Check buffer fit for all generated events
            if not factory.buffer.can_fit(new_events, is_control=True):
                return 409, {
                    "error_code": "buffer_full",
                    "message": "Event buffer capacity exceeded",
                }

            factory.buffer.enqueue_many(new_events, is_control=True)

            resp = {
                "command_id": command_id,
                "accepted": True,
                "lifecycle_status": factory.current_run.lifecycle_status,
                "run_id": factory.current_run.run_id,
                "run_generation": factory.current_run.run_generation,
                "applied_at": applied_at,
                "server_epoch": self.server_epoch,
            }
            factory.idempotency_cache[idempotency_key] = (req_hash, resp)
            return 200, resp

    async def _finalize_expired(self, factory: "FactoryInstance"):
        """
        Best-effort final publish of an expired factory.state snapshot (so the UI
        leaves 'running'), then release the producer and credentials.
        """
        producer = factory.producer
        try:
            if producer:
                async with factory.lock:
                    topic_suffix, ev = factory.current_run.create_snapshot_event(
                        event_seq_generator=factory.next_event_sequence,
                    )
                await asyncio.to_thread(
                    producer.publish_sync,
                    topic_suffix,
                    ev.factory_id.encode("utf-8"),
                    json.dumps(ev.model_dump()).encode("utf-8"),
                )
        except Exception as e:
            logger.warning(f"Final expired snapshot failed for {factory.factory_id[:8]}: {e}")
        finally:
            if producer:
                await asyncio.to_thread(producer.close)
            factory.producer = None
            factory.producer_key = None
            factory.producer_secret = None

    async def _simulation_loop(self):
        """
        Background scheduler waking every SIM_TICK_MILLISECONDS wall time.
        Advances logical clocks and enqueues simulation events and snapshots.
        """
        tick_interval = self.config.sim_tick_milliseconds / 1000.0
        snapshot_interval = self.config.snapshot_interval_milliseconds / 1000.0

        while self._running:
            try:
                await asyncio.sleep(tick_interval)
                now_monotonic = time.monotonic()
                now_utc_iso = datetime.now(timezone.utc).isoformat()

                for factory in list(self.factories.values()):
                    if factory.check_expiry():
                        if factory.final_publish_pending:
                            factory.final_publish_pending = False
                            await self._finalize_expired(factory)
                        continue

                    async with factory.lock:
                        if factory.current_run.lifecycle_status != "running":
                            # If paused or stopped, check 1-second heartbeat snapshot
                            if now_monotonic - factory.last_snapshot_wall_time >= 1.0:
                                snap = factory.current_run.create_snapshot_event(
                                    event_seq_generator=factory.next_event_sequence,
                                    occurred_at=now_utc_iso,
                                )
                                if factory.buffer.can_fit([snap], is_control=False):
                                    factory.buffer.enqueue(*snap)
                                    factory.last_snapshot_wall_time = now_monotonic
                            continue

                        # Calculate elapsed wall time
                        elapsed_wall = now_monotonic - factory.last_tick_wall_time
                        factory.last_tick_wall_time = now_monotonic

                        # 1 real second = 1 sim minute = 60,000 sim ms
                        elapsed_sim_ms = int(elapsed_wall * 60_000.0)
                        if elapsed_sim_ms <= 0:
                            continue

                        max_sim_ms = 14 * 24 * 60 * 60_000  # 14 days = 20,160 sim minutes
                        target_sim_time = min(factory.current_run.sim_time_ms + elapsed_sim_ms, max_sim_ms)

                        # Advance simulation
                        events = factory.current_run.advance_to(
                            target_sim_time_ms=target_sim_time,
                            event_seq_generator=factory.next_event_sequence,
                            occurred_at=now_utc_iso,
                        )

                        # Check snapshot cadence
                        need_snapshot = (now_monotonic - factory.last_snapshot_wall_time) >= snapshot_interval
                        if need_snapshot:
                            snap = factory.current_run.create_snapshot_event(
                                event_seq_generator=factory.next_event_sequence,
                                occurred_at=now_utc_iso,
                            )
                            events.append(snap)

                        # Check buffer capacity
                        if not factory.buffer.can_fit(events, is_control=False):
                            # Buffer full: flag operational error and halt time advance
                            factory.current_run.operational_error = OperationalError(
                                code="buffer_full",
                                message="In-memory event buffer is full; halting simulation advance",
                            )
                        else:
                            factory.buffer.enqueue_many(events, is_control=False)
                            if need_snapshot:
                                factory.last_snapshot_wall_time = now_monotonic
                            # Mirror all activity (non-snapshot) events into the read-only event_log
                            for topic_suffix, ev in events:
                                if ev.event_type != "factory.state":
                                    factory.event_log.append(ev.model_dump())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}", exc_info=True)

    async def _publisher_loop(self):
        """
        Background publisher sending oldest-first queued events to Confluent Kafka.
        Fair sending across all factories. Uses per-factory exponential back-off on
        consecutive publish failures (100 ms → 200 ms → ... → 5 s cap) to prevent
        tight retry storms against a degraded broker without blocking other factories.
        """
        while self._running:
            try:
                await asyncio.sleep(0.02)  # 20 ms base flush loop
                now = time.monotonic()

                for factory in list(self.factories.values()):
                    if factory.is_expired or not factory.producer:
                        continue

                    # Respect per-factory back-off window
                    if now < factory.publish_next_retry_after:
                        continue

                    # Grab batch from buffer under lock
                    async with factory.lock:
                        batch = factory.buffer.get_batch(max_batch_size=20)

                    if not batch:
                        continue

                    # Publish batch asynchronously in one roundtrip
                    records = [
                        (qe.topic_suffix, qe.serialized_key, qe.serialized_value)
                        for qe in batch
                    ]
                    delivery_results = await asyncio.to_thread(
                        factory.producer.publish_batch_sync,
                        records,
                    )

                    factory_ok = True
                    async with factory.lock:
                        for qe, success in zip(batch, delivery_results):
                            if success:
                                factory.buffer.acknowledge(qe)
                            else:
                                qe.in_flight = False
                                factory_ok = False

                    if factory_ok:
                        # Reset back-off on successful flush
                        factory.publish_failure_count = 0
                        factory.publish_next_retry_after = 0.0
                    else:
                        # Exponential back-off: 0.1s * 2^failures, capped at 5 s
                        factory.publish_failure_count += 1
                        delay = min(0.1 * (2 ** factory.publish_failure_count), 5.0)
                        factory.publish_next_retry_after = time.monotonic() + delay
                        logger.debug(
                            f"Factory {factory.factory_id[:8]} publish failed "
                            f"(attempt {factory.publish_failure_count}); "
                            f"retry in {delay:.1f}s"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publisher loop: {e}", exc_info=True)
