"""SQLAlchemy async session management"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import Optional

from app.config import get_settings

Base = declarative_base()

_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db():
    """Initialize database engine and session factory"""
    global _engine, _session_factory

    settings = get_settings()
    database_url = (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_database}"
    )

    _engine = create_async_engine(
        database_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncSession:
    """Get a database session"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    async with _session_factory() as session:
        yield session


async def close_db():
    """Close database engine"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def get_engine():
    """Get the database engine"""
    if _engine is None:
        raise RuntimeError("Database not initialized")
    return _engine
