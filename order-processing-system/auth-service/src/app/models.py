from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Session
from sqlalchemy.pool import NullPool
import os

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@auth-db:5432/auth_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "sslmode": "require",
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
