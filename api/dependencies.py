from __future__ import annotations

from fastapi import Header, HTTPException


async def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required.")
    return x_user_id


async def get_session_id(x_session_id: str | None = Header(default=None)) -> str | None:
    return x_session_id
