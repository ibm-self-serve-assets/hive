import json
from typing import List, Tuple, Optional
from server.models import EventEnvelope


class QueuedEvent:
    def __init__(self, topic_suffix: str, event: EventEnvelope, is_control: bool = False):
        self.topic_suffix = topic_suffix
        self.event = event
        self.is_control = is_control
        self.serialized_key = event.simulation_id.encode("utf-8")
        self.serialized_value = json.dumps(event.model_dump()).encode("utf-8")
        self.byte_size = len(self.serialized_key) + len(self.serialized_value)
        self.in_flight = False


class SimulationEventBuffer:
    def __init__(
        self,
        max_events: int = 10000,
        max_bytes: int = 16777216,
        control_allowance_records: int = 16,
        control_allowance_bytes: int = 65536,
    ):
        self.max_events = max_events
        self.max_bytes = max_bytes
        self.control_allowance_records = control_allowance_records
        self.control_allowance_bytes = control_allowance_bytes

        self.queue: List[QueuedEvent] = []
        self.total_bytes: int = 0
        self.total_events: int = 0
        self.control_records: int = 0
        self.control_bytes: int = 0

    def can_fit(self, events: List[Tuple[str, EventEnvelope]], is_control: bool = False) -> bool:
        added_events = len(events)
        added_bytes = 0
        for _, ev in events:
            k = ev.simulation_id.encode("utf-8")
            v = json.dumps(ev.model_dump()).encode("utf-8")
            added_bytes += len(k) + len(v)

        if is_control:
            # Control allowance
            if (
                self.control_records + added_events <= self.control_allowance_records
                and self.control_bytes + added_bytes <= self.control_allowance_bytes
            ):
                return True

        if (self.total_events + added_events) > self.max_events:
            return False
        if (self.total_bytes + added_bytes) > self.max_bytes:
            return False

        return True

    def enqueue(self, topic_suffix: str, event: EventEnvelope, is_control: bool = False) -> bool:
        queued = QueuedEvent(topic_suffix, event, is_control=is_control)
        
        # Check capacity
        if not self.can_fit([(topic_suffix, event)], is_control=is_control):
            return False

        self.queue.append(queued)
        self.total_events += 1
        self.total_bytes += queued.byte_size
        if is_control:
            self.control_records += 1
            self.control_bytes += queued.byte_size
        return True

    def enqueue_many(
        self, events: List[Tuple[str, EventEnvelope]], is_control: bool = False
    ) -> bool:
        if not self.can_fit(events, is_control=is_control):
            return False

        for topic_suffix, ev in events:
            self.enqueue(topic_suffix, ev, is_control=is_control)
        return True

    def peek_unacked(self) -> Optional[QueuedEvent]:
        for qe in self.queue:
            if not qe.in_flight:
                return qe
        return None

    def get_batch(self, max_batch_size: int = 50) -> List[QueuedEvent]:
        batch = []
        for qe in self.queue:
            if not qe.in_flight:
                qe.in_flight = True
                batch.append(qe)
                if len(batch) >= max_batch_size:
                    break
        return batch

    def acknowledge(self, queued_event: QueuedEvent):
        if queued_event in self.queue:
            self.queue.remove(queued_event)
            self.total_events -= 1
            self.total_bytes -= queued_event.byte_size
            if queued_event.is_control:
                self.control_records -= 1
                self.control_bytes -= queued_event.byte_size

    def unflight(self, queued_event: QueuedEvent):
        if queued_event in self.queue:
            queued_event.in_flight = False

    def clear(self):
        self.queue.clear()
        self.total_bytes = 0
        self.total_events = 0
        self.control_records = 0
        self.control_bytes = 0
