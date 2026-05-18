import asyncpg
from typing import Optional
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None

async def init_pool():
    global _pool
    if _pool is not None:
        return
    
    # asyncpg expects 'postgresql://' instead of 'postgresql+asyncpg://'
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
