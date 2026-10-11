import asyncio
import json
import logging
import uuid
from typing import Optional, Callable

from backend.models import EventEnvelope
from backend.store import InMemProjectionStore

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
    Consumes factory events from Confluent Cloud Kafka topics and feeds them
    into the in-memory projection store.

    Events flow exclusively via Kafka: sim server → Confluent → local consumer → UI.
    The consumer will not start until Confluent credentials and topic assignments are
    provided (after the attendee submits the connect dialog).
    """

    def __init__(
        self,
        store: InMemProjectionStore,
        sim_server_url: str,
        token: Optional[str] = None,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topics: Optional[list] = None,
        consumer_group: Optional[str] = None,
        on_event_callback: Optional[Callable] = None,
    ):
        self.store = store
        self.sim_server_url = sim_server_url.rstrip("/")
        self.token = token
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topics = topics or []
        self.consumer_group = consumer_group
        self.on_event_callback = on_event_callback

        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._kafka_consumer = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._run_consumer())
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

    async def _run_consumer(self):
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret and self.topics and self.consumer_group):
            logger.info("Kafka consumer not started: missing credentials or topic assignments. Submit the connect dialog to begin.")
            return
        await self._run_kafka_consumer()

    async def _run_kafka_consumer(self):
        # Unique group ID per local session so we always replay from earliest
        # without reusing committed offsets from a previous session.
        session_suffix = uuid.uuid4().hex[:8]
        group_id = f"{self.consumer_group}-{session_suffix}"
        logger.info(f"Starting Kafka consumer group: {group_id}")

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
                    logger.warning(f"Kafka consumer error: {msg.error()}")
                    continue

                raw_val = msg.value().decode("utf-8")
                data = json.loads(raw_val)
                env = EventEnvelope(**data)

                # Skip onboarding connection probes — never create log rows
                if env.event_type == "connection.test":
                    continue

                # Validate factory identity; mismatches are quarantined, not displayed
                if self.store.active_factory_id and env.factory_id != self.store.active_factory_id:
                    logger.debug(
                        f"Quarantined: factory_id mismatch "
                        f"(expected {self.store.active_factory_id[:8]}, "
                        f"got {env.factory_id[:8]})"
                    )
                    continue
                if self.store.server_epoch and env.server_epoch != self.store.server_epoch:
                    logger.debug(
                        f"Quarantined: server_epoch mismatch "
                        f"(expected {self.store.server_epoch[:8]}, "
                        f"got {env.server_epoch[:8]})"
                    )
                    continue

                updated = self.store.ingest_envelope(env)
                if updated and self.on_event_callback:
                    await self.on_event_callback(env.model_dump())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kafka consumption error: {e}")
                await asyncio.sleep(1.0)
