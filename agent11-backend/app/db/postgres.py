"""PostgreSQL connection pool using asyncpg"""
import asyncpg
from typing import Optional
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


class Database:
    """PostgreSQL Database wrapper with connection pool"""

    @classmethod
    async def connect(cls) -> "Database":
        """Connect to PostgreSQL and create connection pool"""
        global _pool

        settings = get_settings()

        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_database,
            min_size=5,
            max_size=20,
            command_timeout=60,
        )

        logger.info(
            "postgres_connected",
            host=settings.postgres_host,
            database=settings.postgres_database
        )

        return cls()

    @classmethod
    async def disconnect(cls):
        """Close connection pool"""
        global _pool
        if _pool:
            await _pool.close()
            _pool = None
            logger.info("postgres_disconnected")

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """Get the connection pool"""
        if _pool is None:
            raise RuntimeError("Database not connected")
        return _pool

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        """Execute a query"""
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args) -> list[asyncpg.Record]:
        """Fetch all rows"""
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row"""
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetchval(cls, query: str, *args):
        """Fetch a single value"""
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @classmethod
    async def health_check(cls) -> bool:
        """Check database health"""
        try:
            pool = cls.get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error("postgres_health_check_failed", error=str(e))
            return False
