import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def clean_url(url: str):
    if not url:
        return url
    if "sslmode=" in url:
        u = urlparse(url)
        q = parse_qs(u.query)
        q.pop("sslmode", None)
        return urlunparse(u._replace(query=urlencode(q, doseq=True)))
    return url

# Leader/Writer
DATABASE_URL = clean_url(os.getenv("DATABASE_URL"))
# Replica 1
REPLICA_DATABASE_URL = clean_url(os.getenv("REPLICA_DATABASE_URL", DATABASE_URL))
# Replica 2
REPLICA2_DATABASE_URL = clean_url(os.getenv("REPLICA2_DATABASE_URL", REPLICA_DATABASE_URL))

# Writer Engine
writer_engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    poolclass=NullPool,
    connect_args={"ssl": "require"} if "neon.tech" in DATABASE_URL else {},
)
writer_session = async_sessionmaker(writer_engine, expire_on_commit=False, class_=AsyncSession)

# Reader Engines
reader_engines = {
    "replica1": create_async_engine(
        REPLICA_DATABASE_URL,
        echo=True,
        poolclass=NullPool,
        connect_args={"ssl": "require"} if "neon.tech" in REPLICA_DATABASE_URL else {},
    ),
    "replica2": create_async_engine(
        REPLICA2_DATABASE_URL,
        echo=True,
        poolclass=NullPool,
        connect_args={"ssl": "require"} if "neon.tech" in REPLICA2_DATABASE_URL else {},
    )
}

reader_sessions = {
    "replica1": async_sessionmaker(reader_engines["replica1"], expire_on_commit=False, class_=AsyncSession),
    "replica2": async_sessionmaker(reader_engines["replica2"], expire_on_commit=False, class_=AsyncSession)
}

Base = declarative_base()

async def get_writer_db():
    async with writer_session() as session:
        yield session

async def get_reader_db():
    from .consensus import consensus_manager
    nodes = consensus_manager.get_all_nodes()
    
    # Simple routing logic: pick the node with lowest CPU usage among replicas
    # In a real setup, we'd map node_id to replica_id. For now, we'll round-robin or pick healthiest.
    selected_replica = "replica1"
    
    try:
        if nodes:
            # Filter for healthy nodes and pick one with lowest CPU
            healthy_nodes = [n for n in nodes.values() if n.get("status") == "healthy"]
            if healthy_nodes:
                best_node = min(healthy_nodes, key=lambda x: x.get("cpu_usage", 100))
                # For demo purposes, we'll map even/odd node indices to replicas
                # Replace with actual mapping in production
                selected_replica = "replica1" if hash(best_node['node_id']) % 2 == 0 else "replica2"
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
