import asyncio
import logging
import os
import sys
from concurrent import futures
import grpc
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Ensure generated code is in the path
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
sys.path.append(GENERATED_DIR)

from inventory.v1 import inventory_pb2, inventory_pb2_grpc
from .database import init_db, get_db, async_session
from .models import InventoryItem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI Setup
app = FastAPI(title="Inventory Service API", version="0.1.0")

@app.on_event("startup")
async def startup():
    await init_db()
    # Seed initial data if empty
    async with async_session() as session:
        result = await session.execute(select(InventoryItem).limit(1))
        if not result.scalar():
            logger.info("Seeding initial inventory data...")
            items = [
                InventoryItem(product_id="PROD-001", name="Laptop", quantity=10),
                InventoryItem(product_id="PROD-002", name="Mouse", quantity=50),
                InventoryItem(product_id="PROD-003", name="Keyboard", quantity=25),
            ]
            session.add_all(items)
            await session.commit()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/inventory")
async def list_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()
    return items

# gRPC Servicer Implementation
class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    async def CheckStock(self, request, context):
        async with async_session() as session:
            result = await session.execute(
                select(InventoryItem).where(InventoryItem.product_id == request.product_id)
            )
            item = result.scalar()
            if not item:
                return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=0)
            return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=item.quantity)

    async def ReserveStock(self, request, context):
        logger.info(f"Reserving stock for order {request.order_id}")
        async with async_session() as session:
            try:
                # Check all items first (locking them for consistency)
                items_to_reserve = []
                for item_req in request.items:
                    result = await session.execute(
                        select(InventoryItem).where(InventoryItem.product_id == item_req.product_id).with_for_update()
                    )
                    db_item = result.scalar()
                    if not db_item or db_item.quantity < item_req.quantity:
                        return inventory_pb2.ReserveStockResponse(
                            success=False, 
                            message=f"Insufficient stock for {item_req.product_id}"
                        )
                    items_to_reserve.append((db_item, item_req.quantity))
                
                # Execute updates
                for db_item, qty in items_to_reserve:
                    db_item.quantity -= qty
                
                await session.commit()
                return inventory_pb2.ReserveStockResponse(success=True, message="Stock reserved successfully")
            except Exception as e:
                logger.error(f"Error during stock reservation: {e}")
                await session.rollback()
                return inventory_pb2.ReserveStockResponse(success=False, message=str(e))

    async def ReleaseStock(self, request, context):
        logger.info(f"Releasing stock for order {request.order_id}")
        async with async_session() as session:
            try:
                for item_req in request.items:
                    await session.execute(
                        update(InventoryItem)
                        .where(InventoryItem.product_id == item_req.product_id)
                        .values(quantity=InventoryItem.quantity + item_req.quantity)
                    )
                await session.commit()
                return inventory_pb2.ReleaseStockResponse(success=True)
            except Exception as e:
                logger.error(f"Error during stock release: {e}")
                await session.rollback()
                return inventory_pb2.ReleaseStockResponse(success=False)

    async def UpdateStock(self, request, context):
        async with async_session() as session:
            try:
                result = await session.execute(
                    select(InventoryItem).where(InventoryItem.product_id == request.product_id).with_for_update()
                )
                db_item = result.scalar()
                if not db_item:
                    db_item = InventoryItem(
                        product_id=request.product_id, 
                        name=f"Product {request.product_id}", 
                        quantity=request.quantity_change
                    )
                    session.add(db_item)
                else:
                    db_item.quantity += request.quantity_change
                
                await session.commit()
                return inventory_pb2.UpdateStockResponse(
                    product_id=db_item.product_id, 
                    new_quantity=db_item.quantity
                )
            except Exception as e:
                await session.rollback()
                context.abort(grpc.StatusCode.INTERNAL, str(e))

async def serve_grpc():
    server = grpc.aio.server()
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    listen_addr = "[::]:50052"
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting gRPC server on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

async def serve_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    logger.info("Starting FastAPI server on 0.0.0.0:8001")
    await server.serve()

async def main():
    await asyncio.gather(
        serve_grpc(),
        serve_fastapi()
    )

if __name__ == "__main__":
    asyncio.run(main())
