import etcd3
import os
import json
import logging
import psutil
import socket
import asyncio
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class RaftConsensusManager:
    def __init__(self):
        self.host = os.getenv("ETCD_HOST", "localhost")
        self.port = int(os.getenv("ETCD_PORT", 2379))
        self.etcd = etcd3.client(host=self.host, port=self.port)
        self.node_id = socket.gethostname()
        self.lease_ttl = 30 # Increased for stability during startup
        self.lease = None
        self.is_leader = False
        self._stop_event = asyncio.Event()

    async def register_node(self):
        """Register node in etcd and start tasks"""
        logger.info(f"Registering node {self.node_id} with etcd at {self.host}:{self.port}")
        # Start heartbeat and election as background tasks
        asyncio.create_task(self.heartbeat_loop())
        asyncio.create_task(self.election_loop())

    async def heartbeat_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.lease is None:
                    try:
                        # Attempt to create lease
                        self.lease = self.etcd.lease(self.lease_ttl)
                        logger.info(f"Etcd lease created for node {self.node_id}")
                    except Exception as e:
                        logger.warning(f"Failed to create etcd lease: {e}")
                        await asyncio.sleep(5)
                        continue

                self.lease.refresh()
                # Update metrics in background
                try:
                    await self.update_metrics()
                except Exception as e:
                    logger.warning(f"Failed to update metrics in etcd: {e}")
                
                await asyncio.sleep(self.lease_ttl / 4) # Refresh more frequently
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                self.lease = None # Reset lease to trigger recreation
                await asyncio.sleep(5)

    async def update_metrics(self):
        """Update CPU and connection count in etcd"""
        metrics = {
            "cpu_usage": psutil.cpu_percent(),
            "connections": len(psutil.net_connections()),
            "status": "healthy",
            "node_id": self.node_id
        }
        self.etcd.put(f"/nodes/{self.node_id}", json.dumps(metrics), lease=self.lease)

    async def election_loop(self):
        """Attempt to become leader (write node)"""
        while not self._stop_event.is_set():
            try:
                # Try to create the leader key
                success = self.etcd.transaction(
                    compare=[
                        self.etcd.transactions.version("/leader") == 0
                    ],
                    success=[
                        self.etcd.transactions.put("/leader", self.node_id, lease=self.lease)
                    ],
                    failure=[]
                )[0]
                
                if success:
                    if not self.is_leader:
                        logger.info(f"Node {self.node_id} elected as LEADER")
                        self.is_leader = True
                else:
                    current_leader = self.etcd.get("/leader")[0]
                    if current_leader == self.node_id.encode():
                        self.is_leader = True
                    else:
                        self.is_leader = False
                
                await asyncio.sleep(self.lease_ttl / 2)
            except Exception as e:
                logger.error(f"Election error: {e}")
                await asyncio.sleep(1)

    def get_all_nodes(self) -> Dict[str, dict]:
        """Get all registered nodes and their metrics"""
        nodes = {}
        for value, metadata in self.etcd.get_prefix("/nodes/"):
            node_id = metadata.key.decode().split("/")[-1]
            nodes[node_id] = json.loads(value.decode())
        return nodes

    def get_leader(self) -> Optional[str]:
        val = self.etcd.get("/leader")[0]
        return val.decode() if val else None

    def get_db_cluster_status(self) -> Dict[str, dict]:
        """Get PostgreSQL HA cluster status from Patroni's etcd namespace"""
        db_nodes = {}
        # Patroni scope is 'pg-cluster'
        prefix = "/service/pg-cluster/members/"
        try:
            for value, metadata in self.etcd.get_prefix(prefix):
                node_name = metadata.key.decode().split("/")[-1]
                data = json.loads(value.decode())
                db_nodes[node_name] = {
                    "role": data.get("role"),
                    "state": data.get("state"),
                    "host": data.get("host"),
                    "port": data.get("port"),
                    "lag": data.get("lag", 0)
                }
        except Exception as e:
            logger.error(f"Failed to fetch DB cluster status: {e}")
        return db_nodes

consensus_manager = RaftConsensusManager()
