import logging
import os
import redis
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)

class LoadShedder:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        # Stress level 0 (normal) to 1.0 (max stress)
        self.stress_level = 0.0
        self.redis_client = redis_client
        
        # Priority mapping for endpoints
        self.critical_endpoints: Set[str] = {
            "/orders",  # POST /orders is critical
            "/health",
            "/"
        }
        
    def set_stress_level(self, level: float):
        """Update system stress level (e.g., based on CPU, memory, or thread pool usage)"""
        self.stress_level = max(0.0, min(1.0, level))
        if self.stress_level > 0.7:
            logger.warning(f"System stress high: {self.stress_level:.2f}. Load shedding active.")

    def should_shed(self, path: str, method: str) -> bool:
        """
        Determine if a request should be shed based on stress level and priority.
        """
        # Clean up path by removing trailing slashes
        clean_path = path.rstrip("/")
        if not clean_path:
            clean_path = "/"

        # Health and Root are always allowed
        if clean_path in ["/health", "/"]:
            return False

        # POST /orders is critical
        if clean_path == "/orders" and method == "POST":
            return False

        # Apply shedding logic
        shed = False
        if self.stress_level > 0.8:
            # High stress: Reject everything except critical
            shed = clean_path not in self.critical_endpoints
            
        elif self.stress_level > 0.5:
            # Medium stress: Reject non-critical read operations
            if clean_path in ["/inventory", "/orders"] and method == "GET":
                shed = True
        
        if shed:
            logger.info(f"Load Shedder REJECT: {method} {path} (Stress: {self.stress_level})")
            if self.redis_client:
                try:
                    self.redis_client.incr("metrics:loadshed_rejects")
                except Exception:
                    pass
            return True
                
        return False

# Global load shedder instance
load_shedder = LoadShedder()

