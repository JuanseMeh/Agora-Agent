from typing import Optional, Any
from uuid import UUID
from db.pool import get_pool
import asyncpg

async def create_conversation(
    session_id: UUID,
    user_id: UUID,
    workspace_id: Optional[UUID] = None
) -> UUID:
    pool = get_pool()
    query = """
        INSERT INTO conversations (session_id, user_id, workspace_id)
        VALUES ($1, $2, $3)
        RETURNING id;
    """
    async with pool.acquire() as conn:
        conversation_id = await conn.fetchval(query, session_id, user_id, workspace_id)
        return conversation_id

async def get_conversation(conversation_id: UUID) -> Optional[asyncpg.Record]:
    pool = get_pool()
    query = """
        SELECT * FROM conversations WHERE id = $1;
    """
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, conversation_id)

async def get_conversation_by_session(session_id: UUID) -> Optional[asyncpg.Record]:
    pool = get_pool()
    query = """
        SELECT * FROM conversations WHERE session_id = $1;
    """
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, session_id)

async def update_last_active(conversation_id: UUID) -> None:
    pool = get_pool()
    query = """
        UPDATE conversations 
        SET last_active_at = NOW() 
        WHERE id = $1;
    """
    async with pool.acquire() as conn:
        await conn.execute(query, conversation_id)
