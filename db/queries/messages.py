from typing import Optional, Any
from uuid import UUID
from db.pool import get_pool
import asyncpg
import json

async def create_message(
    conversation_id: UUID,
    role: str,
    content: str,
    blocks: Optional[Any] = None,
    tokens_used: Optional[int] = None
) -> UUID:
    pool = get_pool()
    query = """
        INSERT INTO messages (conversation_id, role, content, blocks, tokens_used)
        VALUES ($1, $2::message_role, $3, $4::jsonb, $5)
        RETURNING id;
    """
    blocks_json = json.dumps(blocks) if blocks is not None else None
    async with pool.acquire() as conn:
        message_id = await conn.fetchval(
            query, 
            conversation_id, 
            role, 
            content, 
            blocks_json, 
            tokens_used
        )
        return message_id

async def get_messages(conversation_id: UUID, limit: int = 50) -> list[asyncpg.Record]:
    pool = get_pool()
    query = """
        SELECT * FROM messages 
        WHERE conversation_id = $1 
        ORDER BY created_at ASC 
        LIMIT $2;
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, conversation_id, limit)
