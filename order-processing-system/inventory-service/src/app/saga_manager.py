import json
import logging
import asyncio
import threading
import time
from confluent_kafka import Consumer, Producer, KafkaError
from . import crud, schemas
from .database import writer_session
from .schemas import ItemReq

logger = logging.getLogger(__name__)

class SagaManager:
    def __init__(self, brokers, topic_in, topic_out):
        self.brokers = brokers
        self.topic_in = topic_in
        self.topic_out = topic_out
        
        # Initialize Consumer
        self.consumer = Consumer({
            'bootstrap.servers': brokers,
            'group.id': 'inventory-service-saga',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        })
        
        # Initialize Producer
        self.producer = Producer({
            'bootstrap.servers': brokers,
            'client.id': 'inventory-service-saga-producer'
        })
        
        self.running = False

    def start(self):
        """Start consuming saga commands"""
        self.running = True
        self.consumer.subscribe([self.topic_in])
        logger.info(f"Saga Manager (Inventory) started, subscribed to {self.topic_in}")
        
        try:
            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Saga Consumer error: {msg.error()}")
                        continue
                
                try:
                    command = json.loads(msg.value().decode('utf-8'))
                    self._handle_command_sync(command)
                    
                    # Manual Commit after successful processing
                    self.consumer.commit(asynchronous=False)
                except Exception as e:
                    logger.error(f"Error processing saga command: {e}")
                    
        except Exception as e:
            logger.error(f"Fatal error in Saga Manager: {e}")
        finally:
            logger.info("Saga Manager: Closing consumer...")
            self.consumer.close()

    def stop(self):
        self.running = False

    def _handle_command_sync(self, command):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_command(command))
        finally:
            loop.close()

    async def handle_command(self, command):
        saga_id = command.get('sagaId')
        order_id = command.get('orderId')
        cmd_type = command.get('command')
        data = command.get('data', {})
        
        logger.info(f"Inventory Service: Handling Saga command {cmd_type} for Saga {saga_id}")
        
        result = {}
        error = None
        
        if not all([saga_id, order_id, cmd_type]):
            logger.error(f"Invalid saga command: missing required fields. id: {saga_id}, order: {order_id}, cmd: {cmd_type}")
            self._publish_event_sync(saga_id, order_id, cmd_type, {}, "Invalid command: missing required fields")
            return

        try:
            if cmd_type == 'reserve_stock':
                items_raw = data.get('items', [])
                if not items_raw:
                    raise ValueError("No items provided for stock reservation")
                req_items = [ItemReq(i.get('product_id'), i.get('quantity')) for i in items_raw]
                
                async with writer_session() as session:
                    # Idempotency Check
                    command_id = f"saga:{saga_id}:{cmd_type}"
                    if not await crud.check_and_record_event(session, command_id, "inventory-service"):
                        logger.info(f"Duplicate saga command ignored: {command_id}")
                        # Still notify orchestrator of success to avoid stuck saga
                        result = {'status': 'RESERVED', 'message': 'Duplicate command handled (already reserved)'}
                        self._publish_event_sync(saga_id, order_id, cmd_type, result, None)
                        return

                    success, message, _ = await crud.reserve_stock_atomic(session, order_id, req_items)
                    if success:
                        result = {'status': 'RESERVED', 'message': message}
                    else:
                        error = message
            
            elif cmd_type == 'release_stock':
                items_raw = data.get('items', [])
                if not items_raw:
                    raise ValueError("No items provided for stock release")
                req_items = [ItemReq(i.get('product_id'), i.get('quantity')) for i in items_raw]
                
                async with writer_session() as session:
                    # Idempotency Check
                    command_id = f"saga:{saga_id}:{cmd_type}"
                    if not await crud.check_and_record_event(session, command_id, "inventory-service"):
                        logger.info(f"Duplicate saga command ignored: {command_id}")
                        result = {'status': 'RELEASED'}
                        self._publish_event_sync(saga_id, order_id, cmd_type, result, None)
                        return

                    await crud.release_stock_atomic(session, order_id, req_items)
                    result = {'status': 'RELEASED'}
            
            else:
                logger.warning(f"Unknown saga command: {cmd_type}")
                return

        except Exception as e:
            logger.error(f"Error executing saga command {cmd_type}: {e}")
            error = str(e)

        self._publish_event_sync(saga_id, order_id, cmd_type, result, error)

    def _publish_event_sync(self, saga_id, order_id, command, result, error):
        status = "SUCCESS" if error is None else "FAILURE"
        payload = {
            "sagaId": saga_id,
            "orderId": order_id,
            "command": command,
            "status": status,
            "data": result,
            "timestamp": int(time.time() * 1000)
        }
        if error:
            payload["error"] = error

        self.producer.produce(
            self.topic_out,
            value=json.dumps(payload).encode('utf-8'),
            key=saga_id.encode('utf-8')
        )
        self.producer.flush()
        logger.info(f"Published Saga event for {saga_id}: {status}")
