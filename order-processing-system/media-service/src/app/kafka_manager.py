import os
import json
from aiokafka import AIOKafkaProducer
import logging

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BROKERS", "kafka:29092")
        self.producer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka Producer started")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped")

    async def send_event(self, topic: str, message: dict):
        if not self.producer:
            await self.start()
        try:
            await self.producer.send_and_wait(topic, message)
            logger.info(f"Event sent to {topic}: {message}")
        except Exception as e:
            logger.error(f"Error sending Kafka event: {e}")
            raise

kafka_manager = KafkaManager()
