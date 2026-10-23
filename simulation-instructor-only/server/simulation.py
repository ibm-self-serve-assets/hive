import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from server.models import (
    ResourceQuantities,
    PartQuantities,
    StationState,
    StationJobState,
    CompletedWorkersState,
    ResourceDeliveryState,
    FactoryStatePayload,
    OperationalError,
    EventEnvelope,
    ResourceStartedPayload,
    ResourceCompletedPayload,
    ResourceBlockedPayload,
    JobStartedPayload,
    AssemblyStartedPayload,
    PartProducedPayload,
    RobotAssembledPayload,
    ResourcesAcquiredPayload,
    PartsAcquiredPayload,
    ManufacturingBlockedPayload,
)
from server.rules import get_simulation_rules, SimulationRules


class ActiveJob:
    def __init__(
        self,
        job_id: str,
        station_id: str,
        output_type: str,
        output_kind: str,
        started_at_sim_ms: int,
        completes_at_sim_ms: int,
        duration_ms: int,
        consumed_inputs: Dict[str, int],
        started_event_id: str,
    ):
        self.job_id = job_id
        self.station_id = station_id
        self.output_type = output_type
        self.output_kind = output_kind
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
        lifecycle_status: str = "paused",
    ):
        self.factory_id = factory_id
        self.server_epoch = server_epoch
        self.run_id = run_id or str(uuid.uuid4())
        self.run_generation = run_generation
        self.lifecycle_status = lifecycle_status  # paused, running, stopped, expired
        self.operational_error: Optional[OperationalError] = None

        self.sim_time_ms: int = 0
        self.state_revision: int = 0

        self.rules: SimulationRules = get_simulation_rules()

        # Resources — initialised from rules so the dict always contains every resource name
        self.resources: Dict[str, int] = {r.name: 0 for r in self.rules.resources}

        self.parts: Dict[str, int] = {p: 0 for p in self.rules.parts}
        self.completed_parts_count: Dict[str, int] = {
            m.station_id: 0 for m in self.rules.manufacturing
        }

        # Open delivery cycle per resource: resource_name -> (job_id, started_event_id).
        # A cycle starts (gathering.started) and completes at its delivery time
        # (gathering.completed), the same lifecycle as a manufacturing job.
        self._resource_cycles: Dict[str, Tuple[str, str]] = {}

        # Per-resource delivery timers: resource_name → next sim-ms when that resource fires
        # All start at 0 so the first delivery lands at sim-time zero when the run starts.
        self.next_delivery_sim_time_ms: Dict[str, int] = {
            r.name: 0 for r in self.rules.resources
        }

        # Staging cart per station: station_id -> {input_name: quantity}. An idle station
        # moves whatever it can from factory stock into its cart on every scheduling pass,
        # and starts its job (consuming the cart) once the cart holds the whole recipe.
        self.carts: Dict[str, Dict[str, int]] = {}

        self.active_jobs: Dict[str, ActiveJob] = {}  # station_id -> ActiveJob
        self.completed_robots_count: int = 0
        self.completed_robots_by_station: Dict[str, int] = {
            a.station_id: 0 for a in self.rules.assembly
        }
        self.last_robot_id: Optional[str] = None
        self.last_applied_command_id: Optional[str] = None

        # Tracks which stations are currently in a blocked state so manufacturing.blocked /
        # assembly.blocked events are only emitted on entry (transition into blocked), not every pass.
        self._blocked_stations: set = set()

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
            # Find next deadline — earliest across all per-resource timers and job completions
            next_deadline = target_sim_time_ms

            # 1. Per-resource delivery deadlines
            for res_cfg in self.rules.resources:
                t = self.next_delivery_sim_time_ms[res_cfg.name]
                if self.sim_time_ms <= t <= target_sim_time_ms:
                    next_deadline = min(next_deadline, t)

            # 2. Job completion deadlines
            for job in self.active_jobs.values():
                if self.sim_time_ms <= job.completes_at_sim_ms <= target_sim_time_ms:
                    next_deadline = min(next_deadline, job.completes_at_sim_ms)

            instant = next_deadline
            self.sim_time_ms = instant

            # Process instant steps:
            # 1. Apply all resource deliveries due at this instant
            delivery_applied = False
            for res_cfg in self.rules.resources:
                if self.next_delivery_sim_time_ms[res_cfg.name] == instant:
                    events = self._apply_single_resource_delivery(
                        res_cfg.name,
                        res_cfg.quantity,
                        instant,
                        occurred_iso,
                        event_seq_generator,
                    )
                    emitted_events.extend(events)
                    delivery_applied = True
                    self.next_delivery_sim_time_ms[res_cfg.name] = (
                        instant + res_cfg.duration_ms
                    )

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

            # 3. Schedule pass if delivery or job completed
            if delivery_applied or jobs_completed:
                start_events = self._run_scheduling_pass(instant, occurred_iso, event_seq_generator)
                emitted_events.extend(start_events)

            if instant == target_sim_time_ms:
                break

        return emitted_events

    def initial_scheduling(
        self,
        event_seq_generator,
        occurred_at: Optional[str] = None,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Run initial scheduling pass at current sim time (e.g., on start/resume).
        Resources start at zero — the first delivery fires after one full interval,
        not at time zero. Advance timers past zero so advance_to doesn't fire them
        immediately on the first tick.
        """
        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        emitted: List[Tuple[str, EventEnvelope]] = []

        if self.sim_time_ms == 0:
            for res_cfg in self.rules.resources:
                if self.next_delivery_sim_time_ms[res_cfg.name] == 0:
                    # Push first delivery to the end of the first interval
                    interval_ms = res_cfg.duration_ms
                    self.next_delivery_sim_time_ms[res_cfg.name] = interval_ms
                    # The first delivery cycle begins now
                    emitted.append(self._start_resource_cycle(
                        res_cfg.name, res_cfg.quantity,
                        0, occurred_iso, event_seq_generator,
                    ))

        # No scheduling pass at time zero — stations have no resources yet
        return emitted

    def _make_event(
        self,
        event_type: str,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
        payload: Dict[str, Any],
        causation_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> EventEnvelope:
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_type=event_type,
            schema_version=1,
            factory_id=self.factory_id,
            server_epoch=self.server_epoch,
            run_id=self.run_id,
            run_generation=self.run_generation,
            event_sequence=event_seq_generator(),
            state_revision=self.state_revision,
            occurred_at=occurred_iso,
            sim_time_minutes=instant_ms // 60_000,
            causation_id=causation_id,
            payload=payload,
        )

    def _start_resource_cycle(
        self,
        resource_name: str,
        quantity: int,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> Tuple[str, EventEnvelope]:
        """Begin a delivery cycle for one resource and emit gathering.started."""
        job_id = str(uuid.uuid4())
        started_event_id = str(uuid.uuid4())
        self._resource_cycles[resource_name] = (job_id, started_event_id)
        self.state_revision += 1
        event = self._make_event(
            "gathering.started", instant_ms, occurred_iso, event_seq_generator,
            ResourceStartedPayload(
                job_id=job_id,
                resource_id=resource_name,
                quantity=quantity,
            ).model_dump(),
            event_id=started_event_id,
        )
        return (".gathering-started", event)

    def _apply_single_resource_delivery(
        self,
        resource_name: str,
        quantity: int,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Complete the open delivery cycle for one resource (gathering.completed),
        then immediately begin the next cycle (gathering.started).
        """
        self.state_revision += 1
        self.resources[resource_name] = self.resources.get(resource_name, 0) + quantity

        job_id, started_event_id = self._resource_cycles.get(resource_name, (str(uuid.uuid4()), None))
        completed = self._make_event(
            "gathering.completed", instant_ms, occurred_iso, event_seq_generator,
            ResourceCompletedPayload(
                job_id=job_id,
                resource_id=resource_name,
                quantity=quantity,
            ).model_dump(),
            causation_id=started_event_id,
        )
        next_started = self._start_resource_cycle(
            resource_name, quantity, instant_ms, occurred_iso, event_seq_generator,
        )
        return [(".gathering-completed", completed), next_started]

    def emit_resource_blocked(
        self,
        resource_id: str,
        reason: str,
        event_seq_generator,
        occurred_at: Optional[str] = None,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        PLACEHOLDER: not called by the simulation yet.

        A future event (e.g. broken equipment) will call this to report that a
        resource supplier cannot deliver. That change will also need to hold the
        resource's delivery timer while blocked; for now this only builds the
        gathering.blocked event so the topic, schema and UI are ready.
        """
        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        event = self._make_event(
            "gathering.blocked", self.sim_time_ms, occurred_iso, event_seq_generator,  # noqa: keep ms arg to _make_event
            ResourceBlockedPayload(resource_id=resource_id, reason=reason).model_dump(),
        )
        return [(".gathering-blocked", event)]

    def _complete_job(
        self,
        job: ActiveJob,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        self.state_revision += 1
        events: List[Tuple[str, EventEnvelope]] = []

        if job.output_kind == "part":
            self.parts[job.output_type] = self.parts.get(job.output_type, 0) + 1
            self.completed_parts_count[job.station_id] = (
                self.completed_parts_count.get(job.station_id, 0) + 1
            )
            payload = PartProducedPayload(
                job_id=job.job_id,
                station_id=job.station_id,
                part_id=job.output_type,
                quantity=1,
            )
            event = EventEnvelope(
                event_id=str(uuid.uuid4()),
                event_type="manufacturing.completed",
                schema_version=1,
                factory_id=self.factory_id,
                server_epoch=self.server_epoch,
                run_id=self.run_id,
                run_generation=self.run_generation,
                event_sequence=event_seq_generator(),
                state_revision=self.state_revision,
                occurred_at=occurred_iso,
                sim_time_minutes=instant_ms // 60_000,
                causation_id=job.started_event_id,
                payload=payload.model_dump(),
            )
            events.append((".manufacturing-completed", event))
        elif job.output_kind == "robot":
            self.completed_robots_count += 1
            self.completed_robots_by_station[job.station_id] = (
                self.completed_robots_by_station.get(job.station_id, 0) + 1
            )
            self.last_robot_id = job.output_type
            payload = RobotAssembledPayload(
                job_id=job.job_id,
                station_id=job.station_id,
                output_type=job.output_type,
                quantity=1,
            )
            event = EventEnvelope(
                event_id=str(uuid.uuid4()),
                event_type="assembly.completed",
                schema_version=1,
                factory_id=self.factory_id,
                server_epoch=self.server_epoch,
                run_id=self.run_id,
                run_generation=self.run_generation,
                event_sequence=event_seq_generator(),
                state_revision=self.state_revision,
                occurred_at=occurred_iso,
                sim_time_minutes=instant_ms // 60_000,
                causation_id=job.started_event_id,
                payload=payload.model_dump(),
            )
            events.append((".assembly-completed", event))

        return events

    def _run_scheduling_pass(
        self,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Executes independent scheduling passes for parts manufacturing (resource-driven)
        and robot assembly (parts-driven).
        """
        emitted_events: List[Tuple[str, EventEnvelope]] = []
        emitted_events.extend(self._schedule_parts_manufacturing(instant_ms, occurred_iso, event_seq_generator))
        emitted_events.extend(self._schedule_robot_assembly(instant_ms, occurred_iso, event_seq_generator))
        return emitted_events

    def _stage_inputs(
        self,
        station_id: str,
        required: Dict[str, int],
        stock: Dict[str, int],
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Move min(still needed, available) of each required input from `stock` into the
        station's cart.

        Returns:
            missing  — inputs still needed to fill the cart (empty when cart is complete)
            grabbed  — what was actually removed from stock this call (empty if nothing moved)
        """
        cart = self.carts.setdefault(station_id, {})
        missing: Dict[str, int] = {}
        grabbed: Dict[str, int] = {}
        for name, qty in required.items():
            held = cart.get(name, 0)
            grab = min(qty - held, stock.get(name, 0))
            if grab > 0:
                stock[name] -= grab
                held += grab
                cart[name] = held
                grabbed[name] = grab
            if held < qty:
                missing[name] = qty - held
        return missing, grabbed

    def _schedule_parts_manufacturing(
        self,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Schedules parts manufacturing stations consuming raw resources.
        Prioritizes stations with the fewest completed parts first. Each idle station
        stages whatever part of its recipe is in stock into its cart, and starts once the
        cart is complete.
        """
        emitted_events: List[Tuple[str, EventEnvelope]] = []
        mfg_stations = [m.station_id for m in self.rules.manufacturing]

        while True:
            started_any = False
            # Prioritize parts manufacturing by least completed parts count first
            sorted_mfg = sorted(
                mfg_stations,
                key=lambda st_id: self.completed_parts_count.get(st_id, 0),
            )

            for st_id in sorted_mfg:
                if st_id in self.active_jobs:
                    self._blocked_stations.discard(st_id)
                    continue

                mfg = self.rules.get_manufacturing(st_id)
                if not mfg:
                    continue

                inputs = mfg.inputs
                duration_ms = mfg.duration_ms
                output_type = mfg.output_type
                missing, grabbed = self._stage_inputs(st_id, inputs, self.resources)

                # Emit resources.acquired for every item moved from stock into cart
                if grabbed:
                    self.state_revision += 1
                    emitted_events.append((".manufacturing-resources-acquired", EventEnvelope(
                        event_id=str(uuid.uuid4()),
                        event_type="manufacturing.resources.acquired",
                        schema_version=1,
                        factory_id=self.factory_id,
                        server_epoch=self.server_epoch,
                        run_id=self.run_id,
                        run_generation=self.run_generation,
                        event_sequence=event_seq_generator(),
                        state_revision=self.state_revision,
                        occurred_at=occurred_iso,
                        sim_time_minutes=instant_ms // 60_000,
                        causation_id=None,
                        payload=ResourcesAcquiredPayload(
                            station_id=st_id,
                            inputs_grabbed=grabbed,
                        ).model_dump(),
                    )))

                if missing:
                    if st_id not in self._blocked_stations:
                        self._blocked_stations.add(st_id)
                        emitted_events.append((".manufacturing-blocked", EventEnvelope(
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
                            sim_time_minutes=instant_ms // 60_000,
                            causation_id=None,
                            payload=ManufacturingBlockedPayload(
                                station_id=st_id, missing_inputs=missing,
                            ).model_dump(),
                        )))
                else:
                    self._blocked_stations.discard(st_id)
                    job_id = str(uuid.uuid4())
                    started_event_id = str(uuid.uuid4())
                    self.carts[st_id] = {}  # cart is consumed by the job
                    self.active_jobs[st_id] = ActiveJob(
                        job_id=job_id,
                        station_id=st_id,
                        output_type=output_type,
                        output_kind="part",
                        started_at_sim_ms=instant_ms,
                        completes_at_sim_ms=instant_ms + duration_ms,
                        duration_ms=duration_ms,
                        consumed_inputs=dict(inputs),
                        started_event_id=started_event_id,
                    )
                    self.state_revision += 1
                    emitted_events.append((".manufacturing-started", EventEnvelope(
                        event_id=started_event_id,
                        event_type="manufacturing.started",
                        schema_version=1,
                        factory_id=self.factory_id,
                        server_epoch=self.server_epoch,
                        run_id=self.run_id,
                        run_generation=self.run_generation,
                        event_sequence=event_seq_generator(),
                        state_revision=self.state_revision,
                        occurred_at=occurred_iso,
                        sim_time_minutes=instant_ms // 60_000,
                        causation_id=None,
                        payload=JobStartedPayload(
                            job_id=job_id,
                            station_id=st_id,
                            output_type=output_type,
                            inputs=dict(inputs),
                        ).model_dump(),
                    )))
                    started_any = True

            if not started_any:
                break

        return emitted_events

    def _schedule_robot_assembly(
        self,
        instant_ms: int,
        occurred_iso: str,
        event_seq_generator,
    ) -> List[Tuple[str, EventEnvelope]]:
        """
        Schedules robot assembly stations independently using completed parts inventory.
        Prioritizes stations with the fewest completed robots first. Each idle station
        stages whatever part of its recipe is in stock into its cart, and starts once the
        cart holds the whole robot recipe.
        """
        emitted_events: List[Tuple[str, EventEnvelope]] = []
        asm_stations = [a.station_id for a in self.rules.assembly]
        sorted_asm = sorted(
            asm_stations,
            key=lambda st_id: self.completed_robots_by_station.get(st_id, 0),
        )

        for st_id in sorted_asm:
            if st_id in self.active_jobs:
                self._blocked_stations.discard(st_id)
                continue

            asm = self.rules.get_assembly(st_id)
            if not asm:
                continue

            inputs_a = asm.inputs
            duration_ms_a = asm.duration_ms
            robot_id = asm.output_type
            missing_parts, grabbed_parts = self._stage_inputs(st_id, inputs_a, self.parts)

            # Emit parts.acquired for every item moved from parts stock into cart
            if grabbed_parts:
                self.state_revision += 1
                emitted_events.append((".assembly-parts-acquired", EventEnvelope(
                    event_id=str(uuid.uuid4()),
                    event_type="assembly.parts.acquired",
                    schema_version=1,
                    factory_id=self.factory_id,
                    server_epoch=self.server_epoch,
                    run_id=self.run_id,
                    run_generation=self.run_generation,
                    event_sequence=event_seq_generator(),
                    state_revision=self.state_revision,
                    occurred_at=occurred_iso,
                    sim_time_minutes=instant_ms // 60_000,
                    causation_id=None,
                    payload=PartsAcquiredPayload(
                        station_id=st_id,
                        inputs_grabbed=grabbed_parts,
                    ).model_dump(),
                )))

            if missing_parts:
                if st_id not in self._blocked_stations:
                    self._blocked_stations.add(st_id)
                    emitted_events.append((".assembly-blocked", EventEnvelope(
                        event_id=str(uuid.uuid4()),
                        event_type="assembly.blocked",
                        schema_version=1,
                        factory_id=self.factory_id,
                        server_epoch=self.server_epoch,
                        run_id=self.run_id,
                        run_generation=self.run_generation,
                        event_sequence=event_seq_generator(),
                        state_revision=self.state_revision,
                        occurred_at=occurred_iso,
                        sim_time_minutes=instant_ms // 60_000,
                        causation_id=None,
                        payload=ManufacturingBlockedPayload(
                            station_id=st_id, missing_inputs=missing_parts,
                        ).model_dump(),
                    )))
            else:
                self._blocked_stations.discard(st_id)
                job_id = str(uuid.uuid4())
                started_event_id = str(uuid.uuid4())
                self.carts[st_id] = {}  # cart is consumed by the job
                self.active_jobs[st_id] = ActiveJob(
                    job_id=job_id,
                    station_id=st_id,
                    output_type=robot_id,
                    output_kind="robot",
                    started_at_sim_ms=instant_ms,
                    completes_at_sim_ms=instant_ms + duration_ms_a,
                    duration_ms=duration_ms_a,
                    consumed_inputs=dict(inputs_a),
                    started_event_id=started_event_id,
                )
                self.state_revision += 1
                emitted_events.append((".assembly-started", EventEnvelope(
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
                    sim_time_minutes=instant_ms // 60_000,
                    causation_id=None,
                    payload=AssemblyStartedPayload(
                        job_id=job_id,
                        station_id=st_id,
                        output_type=robot_id,
                        inputs=dict(inputs_a),
                    ).model_dump(),
                )))

        return emitted_events

    def build_snapshot_payload(self, include_debug_inventory: bool = False) -> FactoryStatePayload:
        station_states: List[StationState] = []

        for st_id in self.rules.station_order:
            # Determine output_type and inputs for idle-state missing-input calculation
            mfg = self.rules.get_manufacturing(st_id)
            asm = self.rules.get_assembly(st_id)
            if st_id in self.active_jobs:
                job = self.active_jobs[st_id]
                elapsed = max(0, self.sim_time_ms - job.started_at_sim_ms)
                progress = min(100.0, max(0.0, (elapsed / job.duration_ms) * 100.0))
                job_state = StationJobState(
                    job_id=job.job_id,
                    output_type=job.output_type,
                    started_at_sim_ms=job.started_at_sim_ms,
                    completes_at_sim_ms=job.completes_at_sim_ms,
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
                cart = {k: v for k, v in self.carts.get(st_id, {}).items() if v > 0}
                if mfg is not None:
                    for res, req_qty in mfg.inputs.items():
                        held = cart.get(res, 0)
                        if held < req_qty:
                            missing[res] = req_qty - held
                    st_status = "waiting_for_resources" if missing else "idle"
                elif asm is not None:
                    for part, req_qty in asm.inputs.items():
                        held = cart.get(part, 0)
                        if held < req_qty:
                            missing[part] = req_qty - held
                    st_status = "waiting_for_parts" if missing else "idle"
                else:
                    st_status = "idle"

                station_states.append(
                    StationState(
                        station_id=st_id,
                        status=st_status,
                        missing_inputs=missing,
                        job=None,
                    )
                )

        # Build per-resource delivery states
        resource_deliveries: List[ResourceDeliveryState] = []
        is_running = self.lifecycle_status == "running" and self.operational_error is None
        for res_cfg in self.rules.resources:
            next_t = self.next_delivery_sim_time_ms[res_cfg.name]
            remaining_sim_ms = max(0, next_t - self.sim_time_ms)
            resource_deliveries.append(
                ResourceDeliveryState(
                    name=res_cfg.name,
                    interval_sim_ms=res_cfg.duration_ms,
                    next_delivery_sim_time_ms=next_t,
                    next_delivery_in_ms=remaining_sim_ms,
                    quantity=res_cfg.quantity,
                )
            )

        payload = FactoryStatePayload(
            lifecycle_status=self.lifecycle_status,
            running=is_running,
            operational_error=self.operational_error,
            resource_deliveries=resource_deliveries,
            resources=dict(self.resources),
            parts=dict(self.parts),
            stations=station_states,
            completed_robots=CompletedWorkersState(
                count=self.completed_robots_count,
                last_robot_id=self.last_robot_id,
            ),
            last_applied_command_id=self.last_applied_command_id,
        )

        if include_debug_inventory:
            # Aggregate robots by output_type across all assembly stations
            robots: Dict[str, int] = {}
            for st_id, count in self.completed_robots_by_station.items():
                asm = self.rules.get_assembly(st_id)
                if asm:
                    robots[asm.output_type] = robots.get(asm.output_type, 0) + count

            payload.debug_mode_instructor_only = {
                "resource": dict(self.resources),
                "part": dict(self.parts),
                "robot": robots,
            }

        return payload

    def create_snapshot_event(
        self,
        event_seq_generator,
        occurred_at: Optional[str] = None,
        causation_id: Optional[str] = None,
        include_debug_inventory: bool = False,
    ) -> Tuple[str, EventEnvelope]:
        occurred_iso = occurred_at or datetime.now(timezone.utc).isoformat()
        payload = self.build_snapshot_payload(include_debug_inventory=include_debug_inventory)
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
            sim_time_minutes=self.sim_time_ms // 60_000,
            causation_id=causation_id,
            payload=payload.model_dump(),
        )
        return (".factory-state", event)
