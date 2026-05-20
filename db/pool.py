import asyncpg
from typing import Optional
from redis.asyncio import Redis
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_redis: Optional[Redis] = None


async def init_pool():
    global _pool
    if _pool is not None:
        return

    db_url = settings.database_url.replace("+asyncpg", "")
    logger.info("Initializing asyncpg connection pool...")
    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=1,
        max_size=10,
    )
    logger.info("Database connection pool initialized.")


async def close_pool():
    global _pool
    if _pool is not None:
        logger.info("Closing asyncpg connection pool...")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed.")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_pool() first.")
    return _pool


async def init_redis():
    global _redis
    if _redis is not None:
        return

    logger.info("Connecting to Redis at %s", settings.redis_url)
    _redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    await _redis.ping()
    logger.info("Redis connection established.")


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed.")


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() on startup.")
    return _redis
