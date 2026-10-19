import asyncio
import json
import logging
import uuid
from typing import Optional, Callable

from backend.models import EventEnvelope
from backend.store import DashboardStore

logger = logging.getLogger("hive.consumer")

try:
    from confluent_kafka import Consumer as ConfluentConsumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    ConfluentConsumer = None
    KafkaError = None
    KAFKA_AVAILABLE = False


class EventConsumerManager:
    """
    Consumes factory events from Confluent Cloud and feeds the dashboard store.
    Identical transport to spec-3; only the store differs.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topics: Optional[list] = None,
        on_event_callback: Optional[Callable] = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topics = topics or []
        self.on_event_callback = on_event_callback

        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._kafka_consumer = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._run())
        logger.info("Event consumer started.")

    def stop(self):
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
        if self._kafka_consumer:
            try:
                self._kafka_consumer.close()
            except Exception:
                pass
            self._kafka_consumer = None
        logger.info("Event consumer stopped.")

    async def _run(self):
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret and self.topics):
            logger.info("Kafka consumer not started: missing credentials or topics.")
            return

        group_id = uuid.uuid4().hex[:8]
        logger.info(f"Kafka consumer group: {group_id}, topics: {self.topics}")

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
        self._kafka_consumer = ConfluentConsumer(conf)
        self._kafka_consumer.subscribe(self.topics)

        while self._running:
            try:
                msg = await asyncio.to_thread(self._kafka_consumer.poll, 0.5)
                if msg is None:
                    continue
                if msg.error():
                    logger.warning(f"Kafka error: {msg.error()}")
                    continue

                try:
                    raw_val = msg.value().decode("utf-8")
                    data = json.loads(raw_val)
                    env = EventEnvelope(**data)
                    if not env.event_type and msg.topic():
                        env.event_type = msg.topic().replace("-", ".")
                except Exception as parse_err:
                    logger.debug(f"Skipping malformed or unparseable record on {msg.topic()}: {parse_err}")
                    continue

                if env.event_type == "connection.test":
                    continue

                updated = self.store.ingest(env)
                if updated and self.on_event_callback:
                    await self.on_event_callback(self.store.snapshot())


            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kafka consumer error: {e}")
                await asyncio.sleep(0.5)
