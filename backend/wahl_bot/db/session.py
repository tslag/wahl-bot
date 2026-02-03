"""Async SQLAlchemy engine and session helpers.

Provides a configured async engine, sessionmaker and helper functions for
initializing the database and yielding sessions for dependency injection.
"""

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
    """Create required database extensions and metadata tables.

    This function attempts to create the `vector` extension and then
    create all metadata tables defined on the declarative `Base`.

    Raises:
        Exception: Re-raises any exception encountered while initializing.
    """

    logger.info("Initializing database (extensions + tables)")
    async with engine.begin() as conn:
        try:
            # NOTE: Ensure the Postgres `vector` extension exists for pgvector usage.
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialization complete")
        except Exception:
            logger.exception("Database initialization failed")
            raise


async def get_db():
    """Yield an async database session for FastAPI dependency injection.

    Usage:
        db: AsyncSession = Depends(get_db)

    Yields:
        AsyncSession: an asynchronous SQLAlchemy session.
    """

    async with AsyncSessionLocal() as session:
        yield session
