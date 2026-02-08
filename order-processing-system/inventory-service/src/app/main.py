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

from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Seed initial data
async def seed_data():
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await init_db()
    await seed_data()
    
    # Start gRPC server in the background
    server = grpc.aio.server()
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    listen_addr = "[::]:50052"
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting gRPC server on {listen_addr}")
    await server.start()
    
    yield
    
    # Shutdown logic
    logger.info("Stopping gRPC server...")
    await server.stop(0)

# FastAPI Setup
app = FastAPI(title="Inventory Service API", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/inventory")
async def list_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()
    return items

from . import crud

# gRPC Servicer Implementation
class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    async def CheckStock(self, request, context):
        async with async_session() as session:
            item = await crud.get_inventory_item(session, request.product_id)
            quantity = item.quantity if item else 0
            return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=quantity)

    async def ReserveStock(self, request, context):
        async with async_session() as session:
            try:
                success, message = await crud.reserve_stock_atomic(session, request.order_id, request.items)
                return inventory_pb2.ReserveStockResponse(success=success, message=message)
            except Exception as e:
                logger.error(f"Error during stock reservation: {e}")
                await session.rollback()
                return inventory_pb2.ReserveStockResponse(success=False, message=str(e))

    async def ReleaseStock(self, request, context):
        async with async_session() as session:
            try:
                await crud.release_stock_atomic(session, request.order_id, request.items)
                return inventory_pb2.ReleaseStockResponse(success=True)
            except Exception as e:
                logger.error(f"Error during stock release: {e}")
                await session.rollback()
                return inventory_pb2.ReleaseStockResponse(success=False)

    async def UpdateStock(self, request, context):
        async with async_session() as session:
            try:
                db_item = await crud.update_stock_level(session, request.product_id, request.quantity_change)
                return inventory_pb2.UpdateStockResponse(
                    product_id=db_item.product_id, 
                    new_quantity=db_item.quantity
                )
            except Exception as e:
                await session.rollback()
                context.abort(grpc.StatusCode.INTERNAL, str(e))
