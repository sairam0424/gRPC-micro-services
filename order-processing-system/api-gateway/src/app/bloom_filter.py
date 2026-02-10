import os
import redis
import logging

logger = logging.getLogger(__name__)

class BloomFilterManager:
    def __init__(self, host='redis', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password,
            decode_responses=True
        )
        self.bloom_key = "bf:catalog"

    def is_present(self, product_id: str) -> bool:
        """
        Check if the product_id is MAYBE present in the bloom filter.
        """
        try:
            # BF.EXISTS returns 1 if present (maybe), 0 if definitely not
            exists = self.redis_client.execute_command("BF.EXISTS", self.bloom_key, product_id) == 1
            
            # Update metrics
            if exists:
                self.redis_client.incr("metrics:bf_tier1_hits")
            else:
                self.redis_client.incr("metrics:bf_tier1_rejects")
                self.redis_client.incr("metrics:db_hits_prevented")
                
            return exists
        except redis.exceptions.ResponseError as e:
            if "ERR unknown command" in str(e):
                logger.error("RedisBloom module not loaded. Check if using redis-stack.")
            else:
                logger.error(f"Bloom Filter error: {e}")
            # Fallback to True to avoid blocking legitimate orders if filter fails
            return True
        except Exception as e:
            logger.error(f"Unexpected error checking bloom filter: {e}")
            return True

    def get_metrics(self):
        """Fetch all filter metrics from Redis."""
        keys = [
            "metrics:bf_tier1_hits", 
            "metrics:bf_tier1_rejects",
            "metrics:cf_tier2_hits",
            "metrics:cf_tier2_rejects",
            "metrics:db_hits_prevented"
        ]
        values = self.redis_client.mget(keys)
        return dict(zip([k.split(':')[-1] for k in keys], [int(v) if v else 0 for v in values]))

bloom_manager = BloomFilterManager(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD")
)
