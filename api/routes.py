from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.core import run
from agent.session import SessionExpiredError, get_or_create_session
from api.dependencies import get_session_id, get_user_id
from db.queries.conversations import append_message
from schemas.response import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    workspace_id: str | None = None


class GradingCompletedEvent(BaseModel):
    suggestion_id: str
    workspace_id: str
    assignment_id: str
    teacher_id: str


@router.post("/chat", response_model=AgentResponse)
async def chat(
    body: ChatRequest,
    user_id: str = Depends(get_user_id),
    session_id: str | None = Depends(get_session_id),
) -> AgentResponse:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        session = await get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            workspace_id=body.workspace_id,
        )
    except SessionExpiredError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Your session has expired. Please log in again.",
                "session_id": e.session_id,
            },
        )

    try:
        await append_message(
            conversation_id=session["conversation_id"],
            role="user",
            content=body.message,
        )
    except Exception:
        logger.exception(
            "Failed to persist user message: conversation=%s",
            session["conversation_id"],
        )

    try:
        response = await run(user_input=body.message, session=session)
    except Exception:
        logger.exception("Agent run failed: session=%s", session["session_id"])
        raise HTTPException(status_code=500, detail="Agent failed to process your request.")

    try:
        await append_message(
            conversation_id=session["conversation_id"],
            role="assistant",
            content=response.message,
            blocks=[b.model_dump() for b in response.blocks],
        )
    except Exception:
        logger.exception(
            "Failed to persist assistant message: conversation=%s",
            session["conversation_id"],
        )

    return response


@router.post("/internal/events/grading-completed")
async def grading_completed(event: GradingCompletedEvent) -> dict:
    logger.info(
        "Grading completed event received: suggestion_id=%s workspace=%s assignment=%s teacher=%s",
        event.suggestion_id,
        event.workspace_id,
        event.assignment_id,
        event.teacher_id,
    )
    return {"status": "accepted"}
