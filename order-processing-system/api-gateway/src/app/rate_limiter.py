import os
import redis
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Lua script for atomic Token Bucket rate limiting
# KEYS[1] - rate_limit_key
# ARGV[1] - capacity
# ARGV[2] - fill_rate (tokens per second)
# ARGV[3] - request_tokens (usually 1)
# ARGV[4] - now (timestamp in seconds)
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local fill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local state = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(state[1]) or capacity
local last_updated = tonumber(state[2]) or now

-- Fill the bucket based on elapsed time
local elapsed = math.max(0, now - last_updated)
tokens = math.min(capacity, tokens + (elapsed * fill_rate))

local allowed = false
if tokens >= requested then
    tokens = tokens - requested
    allowed = true
end

redis.call('HMSET', key, 'tokens', tokens, 'last_updated', now)
-- Set TTL to 1 hour to clean up unused keys
redis.call('EXPIRE', key, 3600)

return {allowed and 1 or 0, tokens}
"""

class RateLimiter:
    def __init__(self, host='redis', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        self.script = self.redis_client.register_script(TOKEN_BUCKET_SCRIPT)

    def is_allowed(self, key: str, capacity: int, fill_rate: float, requested: int = 1) -> Tuple[bool, int, int]:
        """
        Check if a request is allowed under the rate limit.
        Returns: (allowed, remaining_tokens, retry_after)
        """
        try:
            now = time.time()
            res = self.script(keys=[f"ratelimit:{key}"], args=[capacity, fill_rate, requested, now])
            allowed = bool(res[0])
            remaining = int(res[1])
            
            # Update metrics in Redis
            if allowed:
                self.redis_client.incr("metrics:ratelimit_hits")
            else:
                self.redis_client.incr("metrics:ratelimit_rejects")

            retry_after = 0
            if not allowed:
                # Calculate how long until we have enough tokens
                needed = requested - remaining
                retry_after = int(needed / fill_rate) + 1 if fill_rate > 0 else 60
                
            return allowed, remaining, retry_after
        except Exception as e:
            logger.error(f"Rate limiter error for key {key}: {e}")
            # Fail open to avoid blocking traffic if Redis is down
            return True, capacity, 0

rate_limiter = RateLimiter(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD")
)
