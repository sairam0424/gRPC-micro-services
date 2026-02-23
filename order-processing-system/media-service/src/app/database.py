import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

connect_args = {}
if DATABASE_URL and "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "")
    connect_args["ssl"] = True

engine = create_async_engine(DATABASE_URL, echo=True, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        # Import models here to ensure they are registered
        from . import models
        await conn.run_sync(Base.metadata.create_all)
