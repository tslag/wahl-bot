from config.config import settings
from core.logging import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

engine = create_async_engine(
    settings.DATABASE_URL_ASYNC, echo=True, pool_size=5, max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


async def initialize_database():
    logger.info("Initializing database (extensions + tables)")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialization complete")
        except Exception:
            logger.exception("Database initialization failed")
            raise


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
