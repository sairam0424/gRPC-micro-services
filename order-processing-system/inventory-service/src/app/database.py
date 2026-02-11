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
# Replica/Reader
REPLICA_DATABASE_URL = clean_url(os.getenv("REPLICA_DATABASE_URL", DATABASE_URL))

# Writer Engine
writer_engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    poolclass=NullPool,
    connect_args={"ssl": "require"} if "neon.tech" in DATABASE_URL else {},
)
writer_session = async_sessionmaker(writer_engine, expire_on_commit=False, class_=AsyncSession)

# Reader Engine
reader_engine = create_async_engine(
    REPLICA_DATABASE_URL,
    echo=True,
    poolclass=NullPool,
    connect_args={"ssl": "require"} if "neon.tech" in REPLICA_DATABASE_URL else {},
)
reader_session = async_sessionmaker(reader_engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

async def get_writer_db():
    async with writer_session() as session:
        yield session

async def get_reader_db():
    async with reader_session() as session:
        yield session

# Alias for backwards compatibility or default behavior
get_db = get_reader_db

async def init_db():
    async with writer_engine.begin() as conn:
        from . import models
        await conn.run_sync(Base.metadata.create_all)
