import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

# asyncpg doesn't support the 'sslmode' query parameter. 
# If it's present (e.g. from a legacy .env or Neon default), we strip it.
if DATABASE_URL and "sslmode=" in DATABASE_URL:
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    u = urlparse(DATABASE_URL)
    q = parse_qs(u.query)
    q.pop("sslmode", None)
    DATABASE_URL = urlunparse(u._replace(query=urlencode(q, doseq=True)))

# Neon requires SSL. asyncpg uses sslmode in the URL, but for SQLAlchemy with asyncpg, 
# we need to ensure the URL is properly formatted.
# SQLAlchemy asyncpg usually handles this via connect_args or query params.

engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    # Neon requires SSL. We explicitly set it for neon.tech hosts.
    connect_args={"ssl": "require"} if "neon.tech" in DATABASE_URL else {},
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        # Import models here to ensure they are registered
        from . import models
        await conn.run_sync(Base.metadata.create_all)
