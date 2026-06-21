from __future__ import annotations

import json
import logging
from typing import Any

from db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_class_plan(
    user_id: str,
    title: str,
    prompt: str,
    plan_data: dict[str, Any],
) -> dict[str, Any]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO class_plans (user_id, title, prompt, plan_data, created_at)
        VALUES ($1::uuid, $2, $3, $4::jsonb, NOW())
        RETURNING id::text, created_at
        """,
        user_id,
        title,
        prompt,
        json.dumps(plan_data),
    )
    plan_id: str = row["id"]
    logger.info("Created class plan: %s user=%s", plan_id, user_id)
    return _format_plan(row, plan_data)


async def list_class_plans_by_user(
    user_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id::text, user_id::text, title, prompt, plan_data, created_at
        FROM class_plans
        WHERE user_id = $1::uuid
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [_format_plan(r, r["plan_data"]) for r in rows]


async def get_class_plan(
    plan_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id::text, user_id::text, title, prompt, plan_data, created_at
        FROM class_plans
        WHERE id = $1::uuid AND user_id = $2::uuid
        """,
        plan_id,
        user_id,
    )
    if row is None:
        return None
    return _format_plan(row, row["plan_data"])


def _format_plan(row: Any, raw_plan_data: Any) -> dict[str, Any]:
    plan_data = raw_plan_data
    if isinstance(plan_data, str):
        plan_data = json.loads(plan_data)
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "prompt": row["prompt"],
        "plan_data": plan_data,
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
    }
