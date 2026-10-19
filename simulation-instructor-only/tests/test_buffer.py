import pytest
import uuid
import hashlib
from server.models import EventEnvelope
from server.buffer import FactoryEventBuffer


def make_test_event(factory_id: str, seq: int) -> EventEnvelope:
    return EventEnvelope(
        event_id=str(uuid.uuid4()),
        event_type="test.event",
        schema_version=1,
        factory_id=factory_id,
        server_epoch=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        run_generation=1,
        event_sequence=seq,
        state_revision=1,
        occurred_at="2026-01-01T00:00:00Z",
        sim_time_minutes=0,
        causation_id=None,
        payload={"sample": "data"},
    )


def test_buffer_accounting_and_limits():
    fid = str(uuid.uuid4())
    buf = FactoryEventBuffer(max_events=3, max_bytes=100000)

    e1 = make_test_event(fid, 1)
    e2 = make_test_event(fid, 2)
    e3 = make_test_event(fid, 3)
    e4 = make_test_event(fid, 4)

    assert buf.can_fit([(".test", e1), (".test", e2), (".test", e3)]) is True
    assert buf.can_fit([(".test", e1), (".test", e2), (".test", e3), (".test", e4)]) is False

    buf.enqueue(".test", e1)
    buf.enqueue(".test", e2)
    buf.enqueue(".test", e3)
    assert buf.total_events == 3

    # Enqueue 4th fails
    assert buf.enqueue(".test", e4) is False
    assert buf.total_events == 3

    # Acknowledge 1 event
    batch = buf.get_batch(max_batch_size=1)
    assert len(batch) == 1
    buf.acknowledge(batch[0])
    assert buf.total_events == 2

    # Now e4 can fit
    assert buf.enqueue(".test", e4) is True
    assert buf.total_events == 3
