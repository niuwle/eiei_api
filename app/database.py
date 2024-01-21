from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import SQLALCHEMY_DATABASE_URL
from contextlib import asynccontextmanager

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("No SQLALCHEMY_DATABASE_URL set in environment")

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)



@asynccontextmanager
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session