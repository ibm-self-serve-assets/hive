import asyncio
import logging
from typing import Awaitable, Callable, Optional

from backend.store import DashboardStore

logger = logging.getLogger("hive.topic_watch")

try:
    from confluent_kafka.admin import AdminClient
    KAFKA_AVAILABLE = True
except ImportError:
    AdminClient = None
    KAFKA_AVAILABLE = False

POLL_SECONDS = 3.0


class CalculatedValuesWatcher:
    """
    Polls Confluent Cloud until the `calculated_values` topic exists (Flink creates it when the
    attendee runs 01_create_sink.sql), then sets `store.calculated_values_ready` (and keeps it set).
    Only checks that the topic exists; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        topic: str = "calculated_values",
    ):
        self.store = store
        self.topic = topic
        self.on_change = on_change
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret)
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if not self._enabled or self._task:
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _topic_exists(self) -> bool:
        # List all topics rather than asking for this one by name, so a missing topic
        # is never auto-created by the metadata request.
        meta = AdminClient(self._conf).list_topics(timeout=5)
        topic_meta = meta.topics.get(self.topic)
        return topic_meta is not None and topic_meta.error is None

    async def _run(self) -> None:
        while not self.store.calculated_values_ready:
            try:
                if await asyncio.to_thread(self._topic_exists):
                    self.store.calculated_values_ready = True
                    logger.info(f"Topic {self.topic} exists; Level 2 unlocked.")
                    await self.on_change()
                    return
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Topic check failed: {e}")
            await asyncio.sleep(POLL_SECONDS)
