import json
import logging
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from . import crud
from .database import writer_session
from .bloom_filter import filter_manager
from .cache import cache_manager

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self, brokers, topic_in, topic_out):
        self.brokers = brokers
        self.topic_in = topic_in
        self.topic_out = topic_out
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
        await self.consumer.start()
        await self.producer.start()
        asyncio.create_task(self.consume_loop())
        logger.info(f"Kafka Manager started on {self.brokers}")

    async def stop(self):
        self._stop_event.set()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def consume_loop(self):
        try:
            async for msg in self.consumer:
                if self._stop_event.is_set():
                    break
                
                event = msg.value
                logger.info(f"Received event: {event.get('event_type')} for order {event.get('order_id')}")
                
                if event.get("event_type") == "order.created":
                    await self.handle_order_created(event)
                elif event.get("event_type") == "inventory.updated":
                    await self.handle_inventory_updated(event)
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
            try:
                success, message = await crud.reserve_stock_atomic(session, order_id, req_items)
                
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
        product_id = event.get("product_id")
        quantity = event.get("quantity")
        if product_id is not None and quantity is not None:
            logger.info(f"Event-driven Cache Refresh: {product_id} = {quantity}")
            # This is the event-driven warming/invalidation
            cache_manager.set_stock(product_id, quantity)
            # Also update Tier-2 Bloom Filter
            filter_manager.update_stock_status(product_id, quantity > 0)

    async def publish_inventory_update(self, product_id: str, quantity: int):
        """Helper to broadcast inventory changes"""
        event = {
            "event_type": "inventory.updated",
            "product_id": product_id,
            "quantity": quantity
        }
        await self.producer.send_and_wait(self.topic_out, event)
        logger.info(f"Published inventory update: {product_id} = {quantity}")
