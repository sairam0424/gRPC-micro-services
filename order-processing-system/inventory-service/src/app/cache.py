import os
import redis
import logging
import random
import asyncio
from contextlib import asynccontextmanager
from opentelemetry import metrics

logger = logging.getLogger(__name__)
meter = metrics.get_meter("inventory.cache")

cache_hits_counter = meter.create_counter(
    "inventory.cache.hits",
    description="Number of cache hits",
    unit="1"
)
cache_misses_counter = meter.create_counter(
    "inventory.cache.misses",
    description="Number of cache misses",
    unit="1"
)

class CacheManager:
    def __init__(self, host='redis', port=6379, db=1, password=None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password,
            decode_responses=True
        )
        self.stock_prefix = "inventory:stock:"
        self.lock_prefix = "lock:stock:"
        self.default_ttl = 3600  # 1 hour
        
        # Request Coalescing (Singleflight)
        self._inflight = {}

    def _get_ttl(self):
        """TTL + Jitter to prevent Thundering Herd"""
        jitter = random.randint(0, 300)  # up to 5 mins jitter
        return self.default_ttl + jitter

    def get_stock(self, product_id: str):
        try:
            val = self.redis_client.get(f"{self.stock_prefix}{product_id}")
            if val is not None:
                logger.info(f"Cache Hit: {product_id} = {val}")
                cache_hits_counter.add(1, {"product_id": product_id})
                return int(val)
            logger.info(f"Cache Miss: {product_id}")
            cache_misses_counter.add(1, {"product_id": product_id})
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set_stock(self, product_id: str, quantity: int):
        try:
            ttl = self._get_ttl()
            self.redis_client.set(f"{self.stock_prefix}{product_id}", quantity, ex=ttl)
            logger.info(f"Cache Set: {product_id} = {quantity} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def invalidate_stock(self, product_id: str):
        try:
            self.redis_client.delete(f"{self.stock_prefix}{product_id}")
            logger.info(f"Cache Invalidate: {product_id}")
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")

    @asynccontextmanager
    async def single_flight(self, key: str):
        """
        Request Coalescing (Single-flight pattern) to prevent Cache Stampede.
        Ensures only one request goes to the database for a given key.
        """
        if key in self._inflight:
            # Wait for the existing request to finish
            logger.info(f"Request coalescing for key: {key}")
            yield await self._inflight[key]
            return

        # Mark this key as inflight
        fut = asyncio.get_running_loop().create_future()
        self._inflight[key] = fut
        
        try:
            # First caller gets to proceed to DB
            yield None
            # After result is fetched and cache is set, result can be provided (not used here, caller handles DB)
        finally:
            # Resolve the future if it wasn't already (simplified)
            if not fut.done():
                fut.set_result(True)
            self._inflight.pop(key, None)

cache_manager = CacheManager(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD")
)
