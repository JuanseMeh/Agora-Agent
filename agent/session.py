"""
agent/session.py

Session lifecycle management.

Redis owns the session (ephemeral, TTL-managed).
Postgres owns the conversation record (persistent, auditable).

Session shape in Redis:
  key:   session:{session_id}
  value: {
    user_id:         str,
    workspace_id:    str | null,
    conversation_id: str,
    started_at:      ISO str
  }
  ttl:   settings.session_ttl_seconds (default 3600)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from redis.asyncio import Redis

from config.settings import settings
from db.pool import get_redis
from db.queries.conversations import create_conversation

logger = logging.getLogger(__name__)


class SessionExpiredError(Exception):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session expired: {session_id}")


class SessionNotFoundError(Exception):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionData(TypedDict):
    session_id: str
    user_id: str
    workspace_id: str | None
    conversation_id: str
    started_at: str
    pending_suggestion_id: str | None
    pending_assignment_id: str | None


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


async def create_session(
    user_id: str,
    workspace_id: str | None,
) -> SessionData:
    redis: Redis = get_redis()

    session_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    conversation_id = await create_conversation(
        session_id=session_id,
        user_id=user_id,
    )

    data: SessionData = {
        "session_id": session_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "conversation_id": conversation_id,
        "started_at": started_at,
        "pending_suggestion_id": None,
        "pending_assignment_id": None,
    }

    await redis.set(
        _session_key(session_id),
        json.dumps(data),
        ex=settings.session_ttl_seconds,
    )

    logger.info(
        "Session created: session_id=%s user_id=%s workspace_id=%s conversation_id=%s",
        session_id, user_id, workspace_id, conversation_id,
    )
    return data


async def load_session(session_id: str) -> SessionData:
    redis: Redis = get_redis()
    raw = await redis.get(_session_key(session_id))

    if raw is None:
        logger.warning("Session not found in Redis: %s", session_id)
        raise SessionExpiredError(session_id)

    data: SessionData = json.loads(raw)
    return data


async def refresh_session(session_id: str) -> None:
    redis: Redis = get_redis()
    existed = await redis.expire(_session_key(session_id), settings.session_ttl_seconds)
    if not existed:
        logger.warning("refresh_session called on missing key: %s", session_id)


async def update_session_workspace(session_id: str, workspace_id: str) -> None:
    redis: Redis = get_redis()
    raw = await redis.get(_session_key(session_id))
    if raw is None:
        raise SessionExpiredError(session_id)

    data: SessionData = json.loads(raw)
    data["workspace_id"] = workspace_id

    await redis.set(
        _session_key(session_id),
        json.dumps(data),
        ex=settings.session_ttl_seconds,
    )
    logger.info(
        "Session workspace updated: session_id=%s workspace_id=%s",
        session_id, workspace_id,
    )


async def update_session_pending(
    session_id: str,
    pending_suggestion_id: str | None,
    pending_assignment_id: str | None,
) -> None:
    redis: Redis = get_redis()
    raw = await redis.get(_session_key(session_id))
    if raw is None:
        raise SessionExpiredError(session_id)

    data: SessionData = json.loads(raw)
    data["pending_suggestion_id"] = pending_suggestion_id
    data["pending_assignment_id"] = pending_assignment_id

    await redis.set(
        _session_key(session_id),
        json.dumps(data),
        ex=settings.session_ttl_seconds,
    )
    logger.debug(
        "Session pending state updated: session=%s suggestion=%s assignment=%s",
        session_id, pending_suggestion_id, pending_assignment_id,
    )


async def restore_session(session_id: str, user_id: str, conversation_id: str, workspace_id: str | None = None) -> SessionData:
    redis: Redis = get_redis()
    data: SessionData = {
        "session_id": session_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "conversation_id": conversation_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "pending_suggestion_id": None,
        "pending_assignment_id": None,
    }
    await redis.set(
        _session_key(session_id),
        json.dumps(data),
        ex=settings.session_ttl_seconds,
    )
    logger.info("Session restored from Postgres: session_id=%s", session_id)
    return data


async def clear_session_pending(session_id: str) -> None:
    await update_session_pending(session_id, None, None)


async def get_or_create_session(
    session_id: str | None,
    user_id: str,
    workspace_id: str | None,
) -> SessionData:
    if session_id is None:
        return await create_session(user_id=user_id, workspace_id=workspace_id)

    session = await load_session(session_id)
    await refresh_session(session_id)

    if session["workspace_id"] is None and workspace_id is not None:
        await update_session_workspace(session_id, workspace_id)
        session["workspace_id"] = workspace_id

    return session
