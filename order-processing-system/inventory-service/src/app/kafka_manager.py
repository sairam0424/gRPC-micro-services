import json
import logging
import struct
import requests
from typing import Optional
from confluent_kafka import Consumer, Producer, KafkaError
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.protobuf import ProtobufDeserializer, ProtobufSerializer
from . import crud, schemas
from .database import writer_session, reader_sessions
from .bloom_filter import filter_manager
from .cache import cache_manager
from .schemas import ItemReq
from generated.events.v1 import events_pb2

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self, brokers, topic_in, topic_out, schema_registry_url, topic_dlq=None):
        self.brokers = brokers
        self.topic_in = topic_in
        self.topic_out = topic_out
        self.topic_dlq = topic_dlq or f"{topic_in}.dlq"
        self.schema_registry_url = schema_registry_url
        
        # Initialize Schema Registry client
        self.schema_registry_client = SchemaRegistryClient({'url': schema_registry_url})
        
        # Initialize Protobuf deserializers for incoming events
        self.order_created_deserializer = ProtobufDeserializer(
            events_pb2.OrderCreatedEvent,
            {'use.deprecated.format': False}
        )
        
        self.inventory_updated_deserializer = ProtobufDeserializer(
            events_pb2.InventoryUpdatedEvent,
            {'use.deprecated.format': False}
        )
        
        # Initialize Protobuf serializer for outgoing events
        self.inventory_reserved_serializer = ProtobufSerializer(
            events_pb2.InventoryReservedEvent,
            self.schema_registry_client,
            {'use.deprecated.format': False}
        )
        
        self.inventory_failed_serializer = ProtobufSerializer(
            events_pb2.InventoryFailedEvent,
            self.schema_registry_client,
            {'use.deprecated.format': False}
        )
        
        self.inventory_updated_serializer = ProtobufSerializer(
            events_pb2.InventoryUpdatedEvent,
            self.schema_registry_client,
            {'use.deprecated.format': False}
        )
        
        # Initialize Consumer
        self.consumer = Consumer({
            'bootstrap.servers': brokers,
            'group.id': 'inventory-service-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        })
        
        # Initialize Producer
        self.producer = Producer({
            'bootstrap.servers': brokers,
            'client.id': 'inventory-service-producer'
        })
        
        self.running = False

    def start(self):
        """Start consuming messages"""
        self.running = True
        self.consumer.subscribe([self.topic_in])
        logger.info(f"Kafka Manager started, subscribed to {self.topic_in}")
        
        try:
            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        continue
                
                try:
                    # Deserialize Protobuf message
                    event = self._deserialize_event(msg)
                    
                    if event:
                        logger.info(f"Received event: {event.event_type} for order {event.order_id}")
                        
                        if event.event_type == "order.created":
                            self._handle_order_created_sync(event)
                        elif event.event_type == "inventory.updated":
                            self._handle_inventory_updated_sync(event)
                        
                        # Manual Commit after successful sync handling
                        self.consumer.commit(asynchronous=False)
                            
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self._publish_to_dlq_sync(msg.value(), str(e))
                    # Commit even if sent to DLQ to avoid re-processing
                    self.consumer.commit(asynchronous=False)
                    
        except Exception as e:
            logger.error(f"Fatal error in consume loop: {e}")
        finally:
            self.consumer.close()

    def stop(self):
        """Stop the consumer"""
        self.running = False
        logger.info("Kafka Manager stopping...")

    def is_healthy(self) -> bool:
        """Check if Kafka is healthy"""
        return self.running

    def _deserialize_event(self, msg):
        """Deserialize Confluent wire format Protobuf message using official deserializer"""
        if msg is None or msg.value() is None:
            return None
            
        try:
            # Try to deserialize as OrderCreatedEvent first
            try:
                event = self.order_created_deserializer(
                    msg.value(), 
                    SerializationContext(msg.topic(), MessageField.VALUE)
                )
                return event
            except Exception:
                # If that fails, try InventoryUpdatedEvent
                event = self.inventory_updated_deserializer(
                    msg.value(),
                    SerializationContext(msg.topic(), MessageField.VALUE)
                )
                return event
            
        except Exception as e:
            logger.error(f"Failed to deserialize event: {e}")
            return None

    def _handle_order_created_sync(self, event):
        """Handle order.created event synchronously"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_order_created(event))
        finally:
            loop.close()

    def _handle_inventory_updated_sync(self, event):
        """Handle inventory.updated event synchronously"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_inventory_updated(event))
        finally:
            loop.close()

    def _publish_to_dlq_sync(self, original_msg, error):
        """Publish to DLQ synchronously"""
        dlq_event = {
            "original_event": original_msg.hex(),
            "error": error,
            "service": "inventory-service",
            "retry_exhausted": True
        }
        try:
            self.producer.produce(
                self.topic_dlq,
                value=json.dumps(dlq_event).encode('utf-8')
            )
            self.producer.flush()
            logger.warning(f"Message sent to DLQ {self.topic_dlq}")
        except Exception as e:
            logger.error(f"Failed to publish to DLQ: {e}")

    async def handle_order_created(self, event):
        """Handle order.created event"""
        order_id = event.order_id
        customer_id = event.customer_id
        items = event.items
        
        req_items = [ItemReq(item.product_id, item.quantity) for item in items]
        
        # Tier-2 Bloom Filter Check
        for item in req_items:
            if not filter_manager.is_in_stock(item.product_id):
                logger.info(f"Bloom Filter Reject: Product {item.product_id} likely out of stock")
                await self._publish_inventory_failed(event, f"Product {item.product_id} is likely out of stock")
                return

            # Fast Cache Check
            cached_qty = cache_manager.get_stock(item.product_id)
            if cached_qty is not None and cached_qty < item.quantity:
                logger.info(f"Cache Reject: Insufficient stock for {item.product_id}")
                await self._publish_inventory_failed(event, f"Insufficient stock for {item.product_id}")
                return

        async with writer_session() as session:
            # Idempotency Check
            event_id = event.event_id or f"order_{order_id}"
            if not await crud.check_and_record_event(session, event_id, "inventory-service"):
                logger.info(f"Duplicate event ignored: {event_id}")
                return

            try:
                success, message, response_items = await crud.reserve_stock_atomic(session, order_id, req_items)
                
                if success:
                    await self._publish_inventory_reserved(event, message)
                else:
                    await self._publish_inventory_failed(event, message)
                    
            except Exception as e:
                logger.error(f"Error handling order.created: {e}")
                await self._publish_inventory_failed(event, str(e))

    async def _publish_inventory_reserved(self, original_event, message):
        """Publish inventory.reserved event"""
        event = events_pb2.InventoryReservedEvent(
            event_id=f"inv_reserved_{original_event.order_id}",
            event_type="inventory.reserved",
            order_id=original_event.order_id,
            customer_id=original_event.customer_id,
            status="PROCESSING",
            message=message,
            items=original_event.items,
            timestamp=int(time.time() * 1000)
        )
        
        serialized = self.inventory_reserved_serializer(
            event,
            SerializationContext(self.topic_out, MessageField.VALUE)
        )
        
        self.producer.produce(self.topic_out, value=serialized, key=original_event.order_id.encode('utf-8'))
        self.producer.flush()
        logger.info(f"Published inventory.reserved for order {original_event.order_id}")

    async def _publish_inventory_failed(self, original_event, message):
        """Publish inventory.failed event"""
        import time
        event = events_pb2.InventoryFailedEvent(
            event_id=f"inv_failed_{original_event.order_id}",
            event_type="inventory.failed",
            order_id=original_event.order_id,
            customer_id=original_event.customer_id,
            status="FAILED",
            message=message,
            items=original_event.items,
            timestamp=int(time.time() * 1000)
        )
        
        serialized = self.inventory_failed_serializer(
            event,
            SerializationContext(self.topic_out, MessageField.VALUE)
        )
        
        self.producer.produce(self.topic_out, value=serialized, key=original_event.order_id.encode('utf-8'))
        self.producer.flush()
        logger.info(f"Published inventory.failed for order {original_event.order_id}")

    async def handle_inventory_updated(self, event):
        """Handle inventory.updated event"""
        event_id = event.event_id or f"inv_upd_{event.product_id}_{event.quantity}"
        
        async with writer_session() as session:
            if not await crud.check_and_record_event(session, event_id, "inventory-service"):
                logger.info(f"Duplicate inventory update ignored: {event_id}")
                return
            await session.commit()

        product_id = event.product_id
        quantity = event.quantity
        
        if product_id and quantity is not None:
            logger.info(f"Event-driven Cache Refresh: {product_id} = {quantity}")
            cache_manager.set_stock(product_id, quantity)
            filter_manager.update_stock_status(product_id, quantity > 0)
            
            # Async Replication to Replica 2
            async with reader_sessions["replica2"]() as session:
                try:
                    await crud.update_stock_level(session, product_id, 0, override_quantity=quantity)
                    await session.commit()
                    logger.info(f"Async Replication to Replica 2 complete for {product_id}")
                except Exception as e:
                    logger.error(f"Async Replication failed for {product_id}: {e}")
                    await session.rollback()
