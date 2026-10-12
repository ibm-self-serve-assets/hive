import asyncio
import json
import uuid
import logging
from typing import Dict, Optional, Tuple, Any
from server.models import EventEnvelope, ConnectionTestPayload

logger = logging.getLogger("hive.producer")

# Try importing confluent_kafka, fallback to stub if not installed in current environment
try:
    from confluent_kafka import Producer as ConfluentProducer, KafkaException
    KAFKA_AVAILABLE = True
except ImportError:
    ConfluentProducer = None
    KafkaException = Exception
    KAFKA_AVAILABLE = False


class FactoryKafkaProducer:
    def __init__(
        self,
        bootstrap_servers: str,
        security_protocol: str,
        sasl_mechanism: str,
        api_key: str,
        api_secret: str,
        topic_prefix: str,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.security_protocol = security_protocol
        self.sasl_mechanism = sasl_mechanism
        self.api_key = api_key
        self.api_secret = api_secret
        self.topic_prefix = topic_prefix

        self.topics = {
            ".resource-delivered": f"{topic_prefix}.resource-delivered",
            ".manufacturing-started": f"{topic_prefix}.manufacturing-started",
            ".manufacturing-completed": f"{topic_prefix}.manufacturing-completed",
            ".manufacturing-blocked": f"{topic_prefix}.manufacturing-blocked",
            ".assembly-started": f"{topic_prefix}.assembly-started",
            ".assembly-completed": f"{topic_prefix}.assembly-completed",
            ".assembly-blocked": f"{topic_prefix}.assembly-blocked",
            ".factory-state": f"{topic_prefix}.factory-state",
        }

        self._producer = None
        self._init_client()

    def _init_client(self):
        if not KAFKA_AVAILABLE:
            logger.warning("confluent_kafka not available; running with in-memory mock producer")
            return

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": self.security_protocol,
            "client.id": f"hive-sim-{self.topic_prefix}",
            "acks": "all",
            "retries": 3,
            "request.timeout.ms": 10000,
        }
        if self.security_protocol in ("SASL_SSL", "SASL_PLAINTEXT"):
            conf["sasl.mechanisms"] = self.sasl_mechanism
            conf["sasl.username"] = self.api_key
            conf["sasl.password"] = self.api_secret

        try:
            self._producer = ConfluentProducer(conf)
        except Exception as e:
            logger.error(f"Failed to initialize ConfluentProducer: {e}")
            self._producer = None

    def verify_topics_exist(self) -> Tuple[bool, Optional[str]]:
        """
        Calls list_topics() to confirm all five expected topics are present in
        cluster metadata. Returns (True, None) on success or (False, message) if
        any topic is missing or the metadata fetch fails.
        Only runs when confluent_kafka is available and the producer is initialised.
        """
        if self._producer is None:
            # Mock / test mode — skip check
            return True, None

        try:
            metadata = self._producer.list_topics(timeout=5.0)
        except Exception as e:
            return False, f"Failed to fetch cluster metadata: {e}"

        missing = [
            full_topic
            for full_topic in self.topics.values()
            if full_topic not in metadata.topics
        ]
        if missing:
            return False, f"Topics not found in cluster metadata: {', '.join(missing)}"
        return True, None

    def publish_sync(self, topic_suffix: str, key_bytes: bytes, value_bytes: bytes) -> bool:
        """
        Synchronously publish and flush record with delivery confirmation.
        Returns True only on broker acknowledgment; False on any error.
        In mock mode (KAFKA_AVAILABLE=False / no producer) returns True immediately.
        """
        full_topic = self.topics.get(topic_suffix)
        if not full_topic:
            raise ValueError(f"Unknown topic suffix: {topic_suffix}")

        if self._producer is None:
            # Mock mode (confluent_kafka not installed in test environment)
            return True

        delivery_result = {"delivered": False, "error": None}

        def delivery_callback(err, msg):
            if err is not None:
                delivery_result["error"] = err
            else:
                delivery_result["delivered"] = True

        try:
            self._producer.produce(
                topic=full_topic,
                key=key_bytes,
                value=value_bytes,
                callback=delivery_callback,
            )
            self._producer.flush(timeout=3.0)
            if delivery_result["error"] is not None:
                logger.warning(f"Kafka produce delivery failed: {delivery_result['error']}")
                return False
            return delivery_result["delivered"]
        except Exception as e:
            logger.warning(f"Kafka publish exception: {e}")
            return False

    async def verify_permissions_and_topics(
        self,
        factory_id: str,
        server_epoch: str,
        run_id: str,
        run_generation: int,
        operation_id: str,
        empty_snapshot_event: EventEnvelope,
        next_event_seq_fn,
    ) -> Tuple[bool, Optional[str]]:
        """
        Runs onboarding probe verification:
        1. Sends connection.test probe to the four activity topics.
        2. Sends empty paused factory.state snapshot to .factory-state topic.
        All require broker acknowledgment.
        """
        if self._producer is None and not KAFKA_AVAILABLE:
            # Mock / development pass (confluent_kafka not installed)
            return True, None

        # Step 1: confirm topics exist in cluster metadata before attempting writes
        ok, err = self.verify_topics_exist()
        if not ok:
            return False, err

        activity_topics = [
            ".resource-delivered",
            ".manufacturing-started",
            ".manufacturing-completed",
            ".manufacturing-blocked",
            ".assembly-started",
            ".assembly-completed",
            ".assembly-blocked",
        ]

        # 1. Probes on 4 activity topics
        for suffix in activity_topics:
            probe_payload = ConnectionTestPayload(operation_id=operation_id, probe=True)
            seq = next_event_seq_fn()
            probe_event = EventEnvelope(
                event_id=str(uuid.uuid4()) if 'uuid' in globals() else "probe-id",
                event_type="connection.test",
                schema_version=1,
                factory_id=factory_id,
                server_epoch=server_epoch,
                run_id=run_id,
                run_generation=run_generation,
                event_sequence=seq,
                state_revision=0,
                occurred_at=empty_snapshot_event.occurred_at,
                sim_time_ms=0,
                causation_id=None,
                payload=probe_payload.model_dump(),
            )
            k = probe_event.factory_id.encode("utf-8")
            v = json.dumps(probe_event.model_dump()).encode("utf-8")

            success = await asyncio.to_thread(self.publish_sync, suffix, k, v)
            if not success:
                return False, f"Failed write probe verification on topic '{self.topics[suffix]}'"

        # 2. factory-state snapshot probe
        k = empty_snapshot_event.factory_id.encode("utf-8")
        v = json.dumps(empty_snapshot_event.model_dump()).encode("utf-8")
        success = await asyncio.to_thread(self.publish_sync, ".factory-state", k, v)
        if not success:
            return False, f"Failed state probe verification on topic '{self.topics['.factory-state']}'"

        return True, None

    def close(self):
        if self._producer:
            try:
                self._producer.flush(timeout=2.0)
            except Exception:
                pass
            self._producer = None
