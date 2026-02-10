import os
import redis
import logging

logger = logging.getLogger(__name__)

class InventoryFilterManager:
    def __init__(self, host='redis', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password,
            decode_responses=True
        )
        self.catalog_key = "bf:catalog"
        self.stock_key = "cf:in_stock"

    def init_filters(self, capacity=1000, error_rate=0.01):
        """Initialize filters if they don't exist."""
        try:
            # Initialize Bloom Filter for catalog
            try:
                self.redis_client.execute_command("BF.RESERVE", self.catalog_key, error_rate, capacity)
                logger.info(f"Bloom filter {self.catalog_key} initialized.")
            except redis.exceptions.ResponseError as e:
                if "item already exists" not in str(e).lower():
                    logger.error(f"Error initializing bloom filter: {e}")

            # Initialize Cuckoo Filter for in-stock items
            try:
                self.redis_client.execute_command("CF.RESERVE", self.stock_key, capacity)
                logger.info(f"Cuckoo filter {self.stock_key} initialized.")
            except redis.exceptions.ResponseError as e:
                if "item already exists" not in str(e).lower():
                    logger.error(f"Error initializing cuckoo filter: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize filters: {e}")

    def sync_from_db(self, items):
        """
        Industry-standard seeding: Uses pipelines and batching.
        Assumes locking is handled by the caller.
        """
        try:
            pipe = self.redis_client.pipeline()
            # Clear or re-init? For seeding, we just ADDNX/ADD
            for item in items:
                # Add to catalog (Bloom)
                pipe.execute_command("BF.ADD", self.catalog_key, item.product_id)
                # Update stock status (Cuckoo)
                if item.quantity > 0:
                    pipe.execute_command("CF.ADDNX", self.stock_key, item.product_id)
                else:
                    pipe.execute_command("CF.DEL", self.stock_key, item.product_id)
            
            pipe.execute()
            # Mark as synced
            self.redis_client.set("metrics:filters_synced", "true", ex=3600) 
            logger.info(f"Filters synced for {len(items)} items using pipeline.")
        except Exception as e:
            logger.error(f"Failed to sync filters from DB: {e}")
            raise

    def add_to_catalog(self, product_id: str):
        try:
            self.redis_client.execute_command("BF.ADD", self.catalog_key, product_id)
        except Exception as e:
            logger.error(f"Error adding to catalog filter: {e}")

    def update_stock_status(self, product_id: str, in_stock: bool):
        try:
            if in_stock:
                self.redis_client.execute_command("CF.ADDNX", self.stock_key, product_id)
            else:
                try:
                    self.redis_client.execute_command("CF.DEL", self.stock_key, product_id)
                except redis.exceptions.ResponseError as e:
                    if "not found" not in str(e).lower():
                        logger.error(f"Error deleting from stock filter: {e}")
        except Exception as e:
            logger.error(f"Error updating stock status filter: {e}")

    def is_in_stock(self, product_id: str) -> bool:
        """Tier-2 Check: Is the product likely in stock?"""
        try:
            exists = self.redis_client.execute_command("CF.EXISTS", self.stock_key, product_id) == 1
            
            # Update metrics
            if exists:
                self.redis_client.incr("metrics:cf_tier2_hits")
            else:
                self.redis_client.incr("metrics:cf_tier2_rejects")
                self.redis_client.incr("metrics:db_hits_prevented")
                
            return exists
        except Exception as e:
            logger.error(f"Error checking stock filter: {e}")
            return True # Fallback to True

filter_manager = InventoryFilterManager(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD")
)
