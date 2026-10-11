import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from server.models import (
    ResourceQuantities,
    PartQuantities,
    StationState,
    StationJobState,
    CompletedWorkersState,
    FactoryStatePayload,
    OperationalError,
    EventEnvelope,
    ResourceDeliveredPayload,
    JobStartedPayload,
    AssemblyStartedPayload,
    PartProducedPayload,
    RobotAssembledPayload,
    ManufacturingBlockedPayload,
)
from server.rules import get_simulation_rules, SimulationRules


class ActiveJob:
    def __init__(
        self,
        job_id: str,
        station_id: str,
        output_id: str,
        output_type: str,
        started_at_sim_ms: int,
        completes_at_sim_ms: int,
        duration_ms: int,
        consumed_inputs: Dict[str, int],
        started_event_id: str,
    ):
        self.job_id = job_id
        self.station_id = station_id
        self.output_id = output_id
        self.output_type = output_type
        self.started_at_sim_ms = started_at_sim_ms
        self.completes_at_sim_ms = completes_at_sim_ms
        self.duration_ms = duration_ms
        self.consumed_inputs = consumed_inputs
        self.started_event_id = started_event_id


class SimulationRun:
    def __init__(
        self,
        factory_id: str,
        server_epoch: str,
        run_id: Optional[str] = None,
        run_generation: int = 1,
        speed: int = 1,
        lifecycle_status: str = "paused",
    ):
        self.factory_id = factory_id
        self.server_epoch = server_epoch
        self.run_id = run_id or str(uuid.uuid4())
        self.run_generation = run_generation
        self.speed = speed
        self.lifecycle_status = lifecycle_status  # paused, running, stopped, expired
        self.operational_error: Optional[OperationalError] = None

        self.sim_time_ms: int = 0
        self.state_revision: int = 0
        self.station_cursor: int = 0

        self.resources: Dict[str, int] = {
            "resin": 0,
            "silicon": 0,
            "metals": 0,
            "copper": 0,
            "energy": 0,
        }
        self.parts: Dict[str, int] = {
            "chassis": 0,
            "electronics": 0,
            "actuator": 0,
            "battery": 0,
        }

        self.delivery_sequence: int = 0
        self.next_delivery_sim_time_ms: int = 0  # Due at time zero once started

        self.active_jobs: Dict[str, ActiveJob] = {}  # station_id -> ActiveJob
        self.completed_workers_count: int = 0
        self.last_robot_id: Optional[str] = None
        self.last_applied_command_id: Optional[str] = None

        # Tracks which stations are currently in a blocked state so manufacturing.blocked
        # events are only emitted on entry (transition into blocked), not on every scheduling pass.
        self._blocked_stations: set = set()

        self.rules: SimulationRules = get_simulation_rules()

    def advance_to(
        self,
        target_sim_time_ms: int,
        event_seq_generator,
        occurred_at: Optional[str] = None,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Advance simulation clock from self.sim_time_ms to target_sim_time_ms.
        Processes all delivery and completion deadlines in chronological order.
        Returns list of (topic_suffix, EventEnvelope).
        """
        if self.lifecycle_status != "running" or self.operational_error is not None:
            return []

        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        emitted_events: List[Tuple[str, EventEnvelope]] = []

        while self.sim_time_ms < target_sim_time_ms:
            # Find next deadline
            next_deadline = target_sim_time_ms

            # 1. Delivery deadline
            if self.next_delivery_sim_time_ms <= target_sim_time_ms:
                if self.next_delivery_sim_time_ms >= self.sim_time_ms:
                    next_deadline = min(next_deadline, self.next_delivery_sim_time_ms)

            # 2. Job completion deadlines
            for job in self.active_jobs.values():
                if job.completes_at_sim_ms <= target_sim_time_ms:
                    if job.completes_at_sim_ms >= self.sim_time_ms:
                        next_deadline = min(next_deadline, job.completes_at_sim_ms)

            # If next_deadline is greater than target_sim_time_ms, we can jump to target
            instant = next_deadline
            self.sim_time_ms = instant

            # Process instant steps:
            # 1. Apply any due delivery
            delivery_applied = False
            if self.next_delivery_sim_time_ms == instant:
                events = self._apply_delivery(instant, occurred_iso, event_seq_generator)
                emitted_events.extend(events)
                delivery_applied = True
                self.next_delivery_sim_time_ms += self.rules.delivery.interval_sim_seconds * 1000

            # 2. Finish all jobs due at this instant
            finished_jobs = [
                j for j in self.active_jobs.values() if j.completes_at_sim_ms == instant
            ]
            jobs_completed = False
            for job in finished_jobs:
                del self.active_jobs[job.station_id]
                events = self._complete_job(job, instant, occurred_iso, event_seq_generator)
                emitted_events.extend(events)
                jobs_completed = True

            # 3. Schedule pass if delivery or job completed or on init
            if delivery_applied or jobs_completed:
                start_events = self._run_scheduling_pass(instant, occurred_iso, event_seq_generator)
                emitted_events.extend(start_events)

            # If no deadlines matched between sim_time_ms and target, break
            if instant == target_sim_time_ms:
                break

        return emitted_events

    def initial_scheduling(
        self,
        event_seq_generator,
        occurred_at: Optional[str] = None,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Run initial scheduling pass at current sim time (e.g., on start).
        """
        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        emitted_events: List[Tuple[str, EventEnvelope]] = []
        
        # If at time 0 and next delivery is at 0, apply first delivery
        if self.sim_time_ms == 0 and self.next_delivery_sim_time_ms == 0:
            events = self._apply_delivery(0, occurred_iso, event_seq_generator)
            emitted_events.extend(events)
            self.next_delivery_sim_time_ms = self.rules.delivery.interval_sim_seconds * 1000

        start_events = self._run_scheduling_pass(self.sim_time_ms, occurred_iso, event_seq_generator)
        emitted_events.extend(start_events)
        return emitted_events

    def _apply_delivery(
        self,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        self.delivery_sequence += 1
        self.state_revision += 1
        delivery_id = str(uuid.uuid4())
        
        # Add resources
        bundle = dict(self.rules.delivery.resources)
        for r, qty in bundle.items():
            self.resources[r] = self.resources.get(r, 0) + qty

        payload = ResourceDeliveredPayload(
            delivery_id=delivery_id,
            delivery_sequence=self.delivery_sequence,
            resources=bundle,
        )

        event = EventEnvelope(
            event_id=str(uuid.uuid4()),
            event_type="resource.delivered",
            schema_version=1,
            factory_id=self.factory_id,
            server_epoch=self.server_epoch,
            run_id=self.run_id,
            run_generation=self.run_generation,
            event_sequence=event_seq_generator(),
            state_revision=self.state_revision,
            occurred_at=occurred_iso,
            sim_time_ms=instant_ms,
            causation_id=None,
            payload=payload.model_dump(),
        )
        return [(".resource-delivered", event)]

    def _complete_job(
        self,
        job: ActiveJob,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        self.state_revision += 1
        events: List[Tuple[str, EventEnvelope]] = []

        if job.output_type == "part":
            self.parts[job.output_id] = self.parts.get(job.output_id, 0) + 1
            payload = PartProducedPayload(
                job_id=job.job_id,
                station_id=job.station_id,
                part_id=job.output_id,
                quantity=1,
            )
            event = EventEnvelope(
                event_id=str(uuid.uuid4()),
                event_type="part.produced",
                schema_version=1,
                factory_id=self.factory_id,
                server_epoch=self.server_epoch,
                run_id=self.run_id,
                run_generation=self.run_generation,
                event_sequence=event_seq_generator(),
                state_revision=self.state_revision,
                occurred_at=occurred_iso,
                sim_time_ms=instant_ms,
                causation_id=job.started_event_id,
                payload=payload.model_dump(),
            )
            events.append((".part-produced", event))
        elif job.output_type == "robot":
            self.completed_workers_count += 1
            robot_id = str(uuid.uuid4())
            self.last_robot_id = robot_id
            payload = RobotAssembledPayload(
                job_id=job.job_id,
                robot_id=robot_id,
                robot_type="worker",
                display_number=self.completed_workers_count,
                quantity=1,
            )
            event = EventEnvelope(
                event_id=str(uuid.uuid4()),
                event_type="robot.assembled",
                schema_version=1,
                factory_id=self.factory_id,
                server_epoch=self.server_epoch,
                run_id=self.run_id,
                run_generation=self.run_generation,
                event_sequence=event_seq_generator(),
                state_revision=self.state_revision,
                occurred_at=occurred_iso,
                sim_time_ms=instant_ms,
                causation_id=job.started_event_id,
                payload=payload.model_dump(),
            )
            events.append((".robot-assembled", event))

        return events

    def _run_scheduling_pass(
        self,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Deterministic rotating starting position through the 5 stations.
        While any station can start, we loop until no more stations can start at this instant.
        Each pass rotates cursor by 1.
        """
        emitted_events: List[Tuple[str, EventEnvelope]] = []
        station_order = self.rules.station_order
        n = len(station_order)

        # We may be able to start multiple jobs consecutively (e.g. if one finished or resources allow multiple)
        while True:
            started_any = False
            start_cursor = self.station_cursor
            
            for i in range(n):
                idx = (start_cursor + i) % n
                st_id = station_order[idx]
                
                # Check if station is idle
                if st_id in self.active_jobs:
                    # Station is running — clear any blocked state for it
                    self._blocked_stations.discard(st_id)
                    continue
                
                recipe = self.rules.stations[st_id]
                can_start = True
                
                if recipe.output_type == "part":
                    missing: Dict[str, int] = {}
                    for res, qty in recipe.inputs.items():
                        if self.resources.get(res, 0) < qty:
                            can_start = False
                            missing[res] = qty - self.resources.get(res, 0)
                    if not can_start:
                        # Only emit manufacturing.blocked on transition into blocked state
                        if st_id not in self._blocked_stations:
                            self._blocked_stations.add(st_id)
                            blocked_payload = ManufacturingBlockedPayload(
                                station_id=st_id,
                                missing_inputs=missing,
                            )
                            blocked_event = EventEnvelope(
                                event_id=str(uuid.uuid4()),
                                event_type="manufacturing.blocked",
                                schema_version=1,
                                factory_id=self.factory_id,
                                server_epoch=self.server_epoch,
                                run_id=self.run_id,
                                run_generation=self.run_generation,
                                event_sequence=event_seq_generator(),
                                state_revision=self.state_revision,
                                occurred_at=occurred_iso,
                                sim_time_ms=instant_ms,
                                causation_id=None,
                                payload=blocked_payload.model_dump(),
                            )
                            emitted_events.append((".manufacturing-blocked", blocked_event))
                    if can_start:
                        # Station unblocked — clear blocked state and start job
                        self._blocked_stations.discard(st_id)
                        # Deduct inputs atomically
                        for res, qty in recipe.inputs.items():
                            self.resources[res] -= qty
                        
                        job_id = str(uuid.uuid4())
                        started_event_id = str(uuid.uuid4())
                        job = ActiveJob(
                            job_id=job_id,
                            station_id=st_id,
                            output_id=recipe.output_id,
                            output_type=recipe.output_type,
                            started_at_sim_ms=instant_ms,
                            completes_at_sim_ms=instant_ms + recipe.duration_ms,
                            duration_ms=recipe.duration_ms,
                            consumed_inputs=dict(recipe.inputs),
                            started_event_id=started_event_id,
                        )
                        self.active_jobs[st_id] = job
                        self.state_revision += 1

                        payload = JobStartedPayload(
                            job_id=job_id,
                            station_id=st_id,
                            output_id=recipe.output_id,
                            inputs=dict(recipe.inputs),
                            duration_ms=recipe.duration_ms,
                        )
                        event = EventEnvelope(
                            event_id=started_event_id,
                            event_type="job.started",
                            schema_version=1,
                            factory_id=self.factory_id,
                            server_epoch=self.server_epoch,
                            run_id=self.run_id,
                            run_generation=self.run_generation,
                            event_sequence=event_seq_generator(),
                            state_revision=self.state_revision,
                            occurred_at=occurred_iso,
                            sim_time_ms=instant_ms,
                            causation_id=None,
                            payload=payload.model_dump(),
                        )
                        emitted_events.append((".job-started", event))
                        started_any = True
                
                elif recipe.output_type == "robot":
                    missing_parts: Dict[str, int] = {}
                    for part, qty in recipe.inputs.items():
                        if self.parts.get(part, 0) < qty:
                            can_start = False
                            missing_parts[part] = qty - self.parts.get(part, 0)
                    if not can_start:
                        # Only emit manufacturing.blocked on transition into blocked state
                        if st_id not in self._blocked_stations:
                            self._blocked_stations.add(st_id)
                            blocked_payload = ManufacturingBlockedPayload(
                                station_id=st_id,
                                missing_inputs=missing_parts,
                            )
                            blocked_event = EventEnvelope(
                                event_id=str(uuid.uuid4()),
                                event_type="manufacturing.blocked",
                                schema_version=1,
                                factory_id=self.factory_id,
                                server_epoch=self.server_epoch,
                                run_id=self.run_id,
                                run_generation=self.run_generation,
                                event_sequence=event_seq_generator(),
                                state_revision=self.state_revision,
                                occurred_at=occurred_iso,
                                sim_time_ms=instant_ms,
                                causation_id=None,
                                payload=blocked_payload.model_dump(),
                            )
                            emitted_events.append((".manufacturing-blocked", blocked_event))
                    if can_start:
                        # Station unblocked — clear blocked state and deduct parts atomically
                        self._blocked_stations.discard(st_id)
                        for part, qty in recipe.inputs.items():
                            self.parts[part] -= qty

                        job_id = str(uuid.uuid4())
                        started_event_id = str(uuid.uuid4())
                        job = ActiveJob(
                            job_id=job_id,
                            station_id=st_id,
                            output_id=recipe.output_id,
                            output_type=recipe.output_type,
                            started_at_sim_ms=instant_ms,
                            completes_at_sim_ms=instant_ms + recipe.duration_ms,
                            duration_ms=recipe.duration_ms,
                            consumed_inputs=dict(recipe.inputs),
                            started_event_id=started_event_id,
                        )
                        self.active_jobs[st_id] = job
                        self.state_revision += 1

                        payload = AssemblyStartedPayload(
                            job_id=job_id,
                            station_id=st_id,
                            robot_type=recipe.output_id,
                            inputs=dict(recipe.inputs),
                            duration_ms=recipe.duration_ms,
                        )
                        event = EventEnvelope(
                            event_id=started_event_id,
                            event_type="assembly.started",
                            schema_version=1,
                            factory_id=self.factory_id,
                            server_epoch=self.server_epoch,
                            run_id=self.run_id,
                            run_generation=self.run_generation,
                            event_sequence=event_seq_generator(),
                            state_revision=self.state_revision,
                            occurred_at=occurred_iso,
                            sim_time_ms=instant_ms,
                            causation_id=None,
                            payload=payload.model_dump(),
                        )
                        emitted_events.append((".assembly-started", event))
                        started_any = True

            # Advance cursor by 1 for this scheduling pass
            self.station_cursor = (self.station_cursor + 1) % n

            if not started_any:
                break

        return emitted_events

    def build_snapshot_payload(self) -> FactoryStatePayload:
        station_states: List[StationState] = []

        for st_id in self.rules.station_order:
            recipe = self.rules.stations[st_id]
            if st_id in self.active_jobs:
                job = self.active_jobs[st_id]
                elapsed = max(0, self.sim_time_ms - job.started_at_sim_ms)
                progress = min(100.0, max(0.0, (elapsed / job.duration_ms) * 100.0))
                job_state = StationJobState(
                    job_id=job.job_id,
                    output_id=job.output_id,
                    started_at_sim_ms=job.started_at_sim_ms,
                    completes_at_sim_ms=job.completes_at_sim_ms,
                    duration_ms=job.duration_ms,
                    consumed_inputs=job.consumed_inputs,
                    progress_percent=round(progress, 2),
                )
                station_states.append(
                    StationState(
                        station_id=st_id,
                        status="working",
                        missing_inputs={},
                        job=job_state,
                    )
                )
            else:
                missing: Dict[str, int] = {}
                if recipe.output_type == "part":
                    for res, req_qty in recipe.inputs.items():
                        avail = self.resources.get(res, 0)
                        if avail < req_qty:
                            missing[res] = req_qty - avail
                    st_status = "waiting_for_resources" if missing else "idle"
                else:
                    for part, req_qty in recipe.inputs.items():
                        avail = self.parts.get(part, 0)
                        if avail < req_qty:
                            missing[part] = req_qty - avail
                    st_status = "waiting_for_parts" if missing else "idle"

                station_states.append(
                    StationState(
                        station_id=st_id,
                        status=st_status,
                        missing_inputs=missing,
                        job=None,
                    )
                )

        next_in = max(0, self.next_delivery_sim_time_ms - self.sim_time_ms)
        is_running = self.lifecycle_status == "running" and self.operational_error is None

        return FactoryStatePayload(
            lifecycle_status=self.lifecycle_status,
            running=is_running,
            operational_error=self.operational_error,
            speed=self.speed,
            next_delivery_sim_time_ms=self.next_delivery_sim_time_ms,
            next_delivery_in_ms=next_in,
            resources=dict(self.resources),
            parts=dict(self.parts),
            stations=station_states,
            completed_workers=CompletedWorkersState(
                count=self.completed_workers_count,
                last_robot_id=self.last_robot_id,
            ),
            last_applied_command_id=self.last_applied_command_id,
        )

    def create_snapshot_event(
        self,
        event_seq_generator,
        occurred_at: Optional[str] = None,
        causation_id: Optional[str] = None,
    ) -> Tuple[str, EventEnvelope]:
        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        payload = self.build_snapshot_payload()
        event = EventEnvelope(
            event_id=str(uuid.uuid4()),
            event_type="factory.state",
            schema_version=1,
            factory_id=self.factory_id,
            server_epoch=self.server_epoch,
            run_id=self.run_id,
            run_generation=self.run_generation,
            event_sequence=event_seq_generator(),
            state_revision=self.state_revision,
            occurred_at=occurred_iso,
            sim_time_ms=self.sim_time_ms,
            causation_id=causation_id,
            payload=payload.model_dump(),
        )
        return (".factory-state", event)
