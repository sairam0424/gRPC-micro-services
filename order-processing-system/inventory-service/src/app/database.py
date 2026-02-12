import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager

from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def get_connect_args(url: str):
    args = {}
    if "neon.tech" in url:
        args["ssl"] = True
    return args

def clean_full_url(url: str):
    if not url:
        return url
    u = urlparse(url)
    q = parse_qs(u.query)
    # Strip options and sslmode as they are handled via connect_args to avoid TypeErrors in asyncpg
    q.pop("sslmode", None)
    q.pop("options", None)
    return urlunparse(u._replace(query=urlencode(q, doseq=True)))

# Leader/Writer
DATABASE_URL_RAW = os.getenv("DATABASE_URL")
DATABASE_URL = clean_full_url(DATABASE_URL_RAW)
# Replica 1
REPLICA_DATABASE_URL_RAW = os.getenv("REPLICA_DATABASE_URL", DATABASE_URL_RAW)
REPLICA_DATABASE_URL = clean_full_url(REPLICA_DATABASE_URL_RAW)
# Replica 2
REPLICA2_DATABASE_URL_RAW = os.getenv("REPLICA2_DATABASE_URL", REPLICA_DATABASE_URL_RAW)
REPLICA2_DATABASE_URL = clean_full_url(REPLICA2_DATABASE_URL_RAW)

# Writer Engine
writer_engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    connect_args=get_connect_args(DATABASE_URL_RAW),
)
writer_session = async_sessionmaker(writer_engine, expire_on_commit=False, class_=AsyncSession)

# Reader Engines
reader_engines = {
    "replica1": create_async_engine(
        REPLICA_DATABASE_URL,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        connect_args=get_connect_args(REPLICA_DATABASE_URL_RAW),
    ),
    "replica2": create_async_engine(
        REPLICA2_DATABASE_URL,
        echo=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        connect_args=get_connect_args(REPLICA2_DATABASE_URL_RAW),
    )
}

reader_sessions = {
    "replica1": async_sessionmaker(reader_engines["replica1"], expire_on_commit=False, class_=AsyncSession),
    "replica2": async_sessionmaker(reader_engines["replica2"], expire_on_commit=False, class_=AsyncSession)
}

Base = declarative_base()

@asynccontextmanager
async def get_writer_db():
    async with writer_session() as session:

        yield session

@asynccontextmanager
async def get_reader_db():

    from .consensus import consensus_manager
    nodes = consensus_manager.get_all_nodes()
    
    # Simple routing logic: pick the node with lowest CPU usage among replicas
    # In a real setup, we'd map node_id to replica_id. For now, we'll round-robin or pick healthiest.
    # If same as primary/replica1, we effectively have fewer replicas.
    # Handle routing gracefully.
    replica_pool = ["replica1"]
    if os.getenv("REPLICA2_DATABASE_URL") and os.getenv("REPLICA2_DATABASE_URL") != os.getenv("REPLICA_DATABASE_URL"):
        replica_pool.append("replica2")

    try:
        if nodes:
            # Filter for healthy nodes and pick one with lowest CPU
            healthy_nodes = [n for n in nodes.values() if n.get("status") == "healthy"]
            if healthy_nodes and len(replica_pool) > 1:
                best_node = min(healthy_nodes, key=lambda x: x.get("cpu_usage", 100))
                selected_replica = "replica1" if hash(best_node['node_id']) % 2 == 0 else "replica2"
            else:
                selected_replica = replica_pool[0]
        else:
            selected_replica = replica_pool[0]
    except Exception:
        selected_replica = "replica1"

    async with reader_sessions[selected_replica]() as session:
        yield session

# Alias for backwards compatibility
get_db = get_reader_db

async def init_db():
    async with writer_engine.begin() as conn:
        from . import models
        await conn.run_sync(Base.metadata.create_all)
