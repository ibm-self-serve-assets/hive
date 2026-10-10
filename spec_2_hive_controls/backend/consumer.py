import asyncio
import json
import logging
from typing import Optional, Callable
import httpx
from backend.models import EventEnvelope
from backend.store import InMemProjectionStore

logger = logging.getLogger("hive.consumer")

# Optional confluent_kafka
try:
    from confluent_kafka import Consumer as ConfluentConsumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    ConfluentConsumer = None
    KafkaError = None
    KAFKA_AVAILABLE = False


class EventConsumerManager:
    """
    Manages event consumption either via direct polling against local Simulation Server
    or via Confluent Cloud Kafka consumer.
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
        # If real Confluent credentials and topics are supplied and KAFKA_AVAILABLE, use Kafka
        if (
            KAFKA_AVAILABLE
            and self.bootstrap_servers
            and self.api_key
            and self.api_secret
            and self.topics
            and self.consumer_group
        ):
            await self._run_kafka_consumer()
        else:
            # Fallback direct loop: fetches local simulation server state regularly
            await self._run_direct_polling_consumer()

    async def _run_direct_polling_consumer(self):
        """
        Polls the simulation server's /snapshot and /events endpoints to get full
        factory.state and activity EventEnvelopes and feeds them into the store.

        This is the local development path. In production, spec_1 publishes the same
        EventEnvelope payloads to Confluent Kafka topics; the Kafka consumer path
        (_run_kafka_consumer) handles that case. No business logic differs — both paths
        ingest identical EventEnvelope structures via store.ingest_envelope().
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            while self._running:
                try:
                    headers = {}
                    if self.token:
                        headers["Authorization"] = f"Bearer {self.token}"

                    # 1. Check server epoch — detect restarts
                    srv_resp = await client.get(f"{self.sim_server_url}/v1/server", headers=headers)
                    if srv_resp.status_code == 200:
                        epoch = srv_resp.json().get("server_epoch")
                        if self.store.server_epoch and self.store.server_epoch != epoch:
                            self.store.reset_view(None, epoch)
                        else:
                            self.store.server_epoch = epoch

                    if self.store.active_factory_id:
                        base = f"{self.sim_server_url}/v1/factories/{self.store.active_factory_id}"

                        # 2. Pull full factory.state snapshot
                        snap_resp = await client.get(f"{base}/snapshot", headers=headers)
                        if snap_resp.status_code == 200:
                            env = EventEnvelope(**snap_resp.json())
                            updated = self.store.ingest_envelope(env)
                            if updated and self.on_event_callback:
                                await self.on_event_callback(env.model_dump())
                        elif snap_resp.status_code == 404:
                            self.store.reset_view(None, self.store.server_epoch)

                        # 3. Pull recent activity events
                        ev_resp = await client.get(f"{base}/events", headers=headers)
                        if ev_resp.status_code == 200:
                            for raw in ev_resp.json().get("events", []):
                                try:
                                    act_env = EventEnvelope(**raw)
                                    ingested = self.store.ingest_envelope(act_env)
                                    if ingested and self.on_event_callback:
                                        await self.on_event_callback(act_env.model_dump())
                                except Exception:
                                    pass

                    await asyncio.sleep(0.2)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Direct consumer poll error: {e}")
                    await asyncio.sleep(1.0)

    async def _run_kafka_consumer(self):
        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "group.id": f"{self.consumer_group}-session",
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
                updated = self.store.ingest_envelope(env)
                if updated and self.on_event_callback:
                    await self.on_event_callback(env)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kafka consumption error: {e}")
                await asyncio.sleep(1.0)
