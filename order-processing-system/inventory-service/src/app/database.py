import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

# Neon requires SSL. asyncpg uses sslmode in the URL, but for SQLAlchemy with asyncpg, 
# we need to ensure the URL is properly formatted.
# The user provided: postgresql://.../?sslmode=require
# SQLAlchemy asyncpg usually handles this via connect_args or query params.

engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    connect_args={"ssl": "require"} if "sslmode=require" in DATABASE_URL else {}
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
