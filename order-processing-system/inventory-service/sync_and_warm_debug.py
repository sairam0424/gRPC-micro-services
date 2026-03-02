import asyncio
import os
import sys
import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from app.models import InventoryItem
from app.bloom_filter import filter_manager
from app.cache import cache_manager

async def sync_and_warm():
    # Database configuration from .env
    # Since we are running on host, we use NEON_MASTER_HOST directly
    master_host = "ep-holy-block-a15z3e4p.ap-southeast-1.aws.neon.tech"
    db_url = f"postgresql+asyncpg://neondb_owner:npg_Fj6bG0DcStVr@{master_host}:5432/neondb"
    
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    print("--- Checking Database Inventory ---")
    async with async_session() as session:
        result = await session.execute(select(InventoryItem))
        items = result.scalars().all()
        
        if not items:
            print("Database is EMPTY!")
        else:
            for item in items:
                print(f"ID: {item.product_id}, Name: {item.name}, Qty: {item.quantity}")

    print("\n--- Syncing Bloom/Cuckoo Filters ---")
    # Point filter_manager and cache_manager to 'redis' for Docker
    # Use environment variables or hardcoded values matching Docker environment
    redis_password = os.getenv("REDIS_PASSWORD", "bloompass")
    filter_manager.redis_client = redis.Redis(host='redis', port=6379, password=redis_password, decode_responses=True)
    cache_manager.redis_client = redis.Redis(host='redis', port=6379, db=1, password=redis_password, decode_responses=True)

    try:
        filter_manager.init_filters()
        filter_manager.sync_from_db(items)
        print("Bloom/Cuckoo filters synced successfully.")
        
        print("\n--- Warming Redis Cache ---")
        for item in items:
            cache_manager.set_stock(item.product_id, item.quantity)
            print(f"Cached {item.product_id} with qty {item.quantity}")
        print("Redis cache warming complete.")

    except Exception as e:
        print(f"Sync/Warming failed: {e}")

if __name__ == "__main__":
    asyncio.run(sync_and_warm())
