import json
import logging
import asyncio
import backoff
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from . import crud
from .database import writer_session, reader_sessions
from .bloom_filter import filter_manager
from .cache import cache_manager

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self, brokers, topic_in, topic_out, topic_dlq=None):
        self.brokers = brokers
        self.topic_in = topic_in
        self.topic_out = topic_out
        self.topic_dlq = topic_dlq or f"{topic_in}.dlq"
        self.consumer = None
        self.producer = None
        self._stop_event = asyncio.Event()

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic_in,
            bootstrap_servers=self.brokers,
            group_id="inventory-service-group",
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Start connection in background to avoid blocking lifespan
        asyncio.create_task(self._connect_and_run())
        logger.info(f"Kafka Manager initialization started (background) for {self.brokers}")

    async def _connect_and_run(self):
        """Internal method to handle connection and the consume loop"""
        try:
            logger.info("Connecting to Kafka...")
            await self.consumer.start()
            await self.producer.start()
            logger.info("Kafka consumer and producer started successfully")
            await self.consume_loop()
        except Exception as e:
            logger.error(f"Failed to start Kafka: {e}")
            # We don't crash the app, but health check will reflect disconnected state

    async def stop(self):
        self._stop_event.set()
        if self.consumer:
            try:
                await self.consumer.stop()
            except Exception:
                pass
        if self.producer:
            try:
                await self.producer.stop()
            except Exception:
                pass

    def is_healthy(self) -> bool:
        """Check if Kafka producer and consumer are running and connected"""
        # A simple check: if we have the objects and the producer sender task is running
        return (self.producer is not None and 
                self.consumer is not None and 
                getattr(self.producer, '_sender', None) is not None and 
                getattr(self.producer._sender, 'sender_task', None) is not None)

    async def publish_to_dlq(self, event, error):
        """Publish failed events to the Dead Letter Queue"""
        dlq_event = {
            "original_event": event,
            "error": str(error),
            "service": "inventory-service",
            "retry_exhausted": True
        }
        try:
            await self.producer.send_and_wait(self.topic_dlq, dlq_event)
            logger.warning(f"Message sent to DLQ {self.topic_dlq}: {event.get('order_id')}")
        except Exception as e:
            logger.error(f"Failed to publish to DLQ: {e}")

    async def consume_loop(self):
        try:
            async for msg in self.consumer:
                if self._stop_event.is_set():
                    break
                
                event = msg.value
                logger.info(f"Received event: {event.get('event_type')} for order {event.get('order_id')}")
                
                # Use backoff to retry message processing
                @backoff.on_exception(
                    backoff.expo,
                    (Exception),
                    max_tries=3,
                    on_giveup=lambda details: asyncio.create_task(self.publish_to_dlq(event, details['exception']))
                )
                async def process_with_retry():
                    if event.get("event_type") == "order.created":
                        await self.handle_order_created(event)
                    elif event.get("event_type") == "inventory.updated":
                        await self.handle_inventory_updated(event)

                try:
                    await process_with_retry()
                except Exception as e:
                    logger.error(f"Processing failed after retries: {e}")

        except Exception as e:
            logger.error(f"Error in Kafka consume loop: {e}")

    async def handle_order_created(self, event):
        order_id = event["order_id"]
        customer_id = event["customer_id"]
        items = event["items"]
        
        # We need to adapt the items list to what our crud expects (objects with product_id and quantity)
        class ItemReq:
            def __init__(self, product_id, quantity):
                self.product_id = product_id
                self.quantity = quantity

        req_items = [ItemReq(i["product_id"], i["quantity"]) for i in items]
        
        # Tier-2 Bloom Filter Check: Is the product likely in stock?
        for item in req_items:
            if not filter_manager.is_in_stock(item.product_id):
                logger.info(f"Bloom Filter Reject (Tier-2): Product {item.product_id} likely out of stock for order {order_id}")
                response_event = {
                    "event_type": "inventory.failed",
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "status": "FAILED",
                    "message": f"Product {item.product_id} is likely out of stock (Tier-2 check)",
                    "items": items
                }
                await self.producer.send_and_wait(self.topic_out, response_event)
                return

            # 2. Fast Cache Check
            cached_qty = cache_manager.get_stock(item.product_id)
            if cached_qty is not None and cached_qty < item.quantity:
                logger.info(f"Cache Reject: Product {item.product_id} has insufficient stock for order {order_id} ({cached_qty} < {item.quantity})")
                response_event = {
                    "event_type": "inventory.failed",
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "status": "FAILED",
                    "message": f"Insufficient stock for {item.product_id} (cached check)",
                    "items": items
                }
                await self.producer.send_and_wait(self.topic_out, response_event)
                return

        async with writer_session() as session:
            # Idempotency Check
            event_id = event.get("event_id") or f"order_{order_id}"
            if not await crud.check_and_record_event(session, event_id, "inventory-service"):
                logger.info(f"Duplicate event ignored: {event_id}")
                return

            try:
                success, message, response_items = await crud.reserve_stock_atomic(session, order_id, req_items)
                
                response_event = {
                    "event_type": "inventory.reserved" if success else "inventory.failed",
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "status": "PROCESSING" if success else "FAILED",
                    "message": message,
                    "items": items
                }
                
                await self.producer.send_and_wait(self.topic_out, response_event)
                logger.info(f"Published outcome for order {order_id}: {response_event['event_type']}")
                
            except Exception as e:
                logger.error(f"Error handling order.created: {e}")
                # Optional: publish a generic failure event

    async def handle_inventory_updated(self, event):
        """
        Golden Rule: Refresh cache via events.
        Ensures consistency across all instances.
        """
        event_id = event.get("event_id") or f"inv_upd_{event.get('product_id')}_{event.get('quantity')}"
        
        async with writer_session() as session:
            if not await crud.check_and_record_event(session, event_id, "inventory-service"):
                logger.info(f"Duplicate inventory update ignored: {event_id}")
                return
            await session.commit() # Commit the idempotency record early for cache/bloom sync if needed, 
                                   # although typically we'd do it as part of a larger transaction.

        product_id = event.get("product_id")
        quantity = event.get("quantity")
        if product_id is not None and quantity is not None:
            logger.info(f"Event-driven Cache Refresh & Async Rep: {product_id} = {quantity}")
            # 1. Update Cache
            cache_manager.set_stock(product_id, quantity)
            # 2. Update Tier-2 Bloom Filter
            filter_manager.update_stock_status(product_id, quantity > 0)
            
            # 3. Async Replication to Replica 2
            async with reader_sessions["replica2"]() as session:
                try:
                    await crud.update_stock_level(session, product_id, 0, override_quantity=quantity)
                    await session.commit()
                    logger.info(f"Async Replication to Replica 2 complete for {product_id}")
                except Exception as e:
                    logger.error(f"Async Replication failed for {product_id}: {e}")
                    await session.rollback()

    async def publish_inventory_update(self, product_id: str, quantity: int):
        """Helper to broadcast inventory changes"""
        event = {
            "event_type": "inventory.updated",
            "product_id": product_id,
            "quantity": quantity
        }
        await self.producer.send_and_wait(self.topic_out, event)
        logger.info(f"Published inventory update: {product_id} = {quantity}")
