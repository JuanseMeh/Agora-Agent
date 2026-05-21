from typing import Optional, Any
from uuid import UUID
from db.pool import get_pool
import asyncpg
import json

async def create_grading_summary(
    workspace_id: UUID,
    assignment_id: UUID,
    suggestion_id: str,
    status: str,
    summary_blocks: Any,
    conversation_id: Optional[UUID] = None
) -> UUID:
    pool = get_pool()
    query = """
        INSERT INTO grading_summaries 
        (conversation_id, workspace_id, assignment_id, suggestion_id, status, summary_blocks)
        VALUES ($1, $2, $3, $4, $5::grading_status, $6::jsonb)
        RETURNING id;
    """
    blocks_json = json.dumps(summary_blocks)
    async with pool.acquire() as conn:
        summary_id = await conn.fetchval(
            query, 
            conversation_id, 
            workspace_id, 
            assignment_id, 
            suggestion_id, 
            status, 
            blocks_json
        )
        return summary_id

async def update_grading_summary_status(suggestion_id: str, status: str) -> None:
    pool = get_pool()
    query = """
        UPDATE grading_summaries 
        SET status = $1::grading_status 
        WHERE suggestion_id = $2;
    """
    async with pool.acquire() as conn:
        await conn.execute(query, status, suggestion_id)

async def invalidate_grading_summary(suggestion_id: str) -> None:
    pool = get_pool()
    query = """
        UPDATE grading_summaries 
        SET invalidated_at = NOW() 
        WHERE suggestion_id = $1;
    """
    async with pool.acquire() as conn:
        await conn.execute(query, suggestion_id)

async def get_grading_summary_by_suggestion(suggestion_id: str) -> Optional[asyncpg.Record]:
    pool = get_pool()
    query = """
        SELECT * FROM grading_summaries 
        WHERE suggestion_id = $1;
    """
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, suggestion_id)
