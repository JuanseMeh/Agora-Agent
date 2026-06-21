from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from agent.core import run
from agent.session import SessionExpiredError, get_or_create_session, load_session, restore_session
from api.dependencies import get_session_id, get_user_id
from db.queries.conversations import append_message, delete_conversation, get_conversation_by_session_id, list_conversations_by_user, load_message_history
from db.queries.class_plans import create_class_plan, list_class_plans_by_user
from schemas.response import AgentResponse
from schemas.class_plan import (
    ClassPlanListItem,
    GenerateClassRequest,
    GenerateClassResponse,
    SaveClassPlanRequest,
)

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


class SuggestGradesRequest(BaseModel):
    workspace_id: str
    assignment_id: str
    submission_ids: list[str] | None = None
    user_ids: list[str] | None = None
    include_already_graded: bool = False


class OverrideItem(BaseModel):
    submission_id: int
    criterion_id: str
    original_score: float
    teacher_score: float
    teacher_feedback: str


class ApproveSuggestionRequest(BaseModel):
    suggestion_id: str
    overrides: list[OverrideItem] = []


@router.post("/suggest-grades")
async def suggest_grades(
    body: SuggestGradesRequest,
    user_id: str = Depends(get_user_id),
) -> dict:
    from services.orchestrator_service import suggest_assignment

    logger.info(
        "suggest_grades: workspace=%s assignment=%s user=%s",
        body.workspace_id, body.assignment_id, user_id,
    )

    result = await suggest_assignment(
        workspace_id=body.workspace_id,
        assignment_id=body.assignment_id,
        requester_user_id=user_id,
        submission_ids=body.submission_ids,
        user_ids=body.user_ids,
        include_already_graded=body.include_already_graded,
    )

    return {
        "suggestion_id": result.suggestion_id,
        "results": [
            {
                "submission_id": r.submission_id,
                "total_score": r.total_score,
                "max_score": r.max_score,
                "feedback_summary": r.feedback_summary,
                "grading_model": r.grading_model,
                "evaluated_at": r.evaluated_at,
                "criteria_results": [
                    {
                        "criterion_id": c.criterion_id,
                        "criterion_name": c.criterion_name,
                        "score": c.score,
                        "max_score": c.max_score,
                        "feedback": c.feedback,
                        "matched_level": c.matched_level,
                    }
                    for c in r.criteria_results
                ],
            }
            for r in result.results
        ],
        "stats": {
            "average_score": result.stats.average_score,
            "max_score": result.stats.max_score,
            "graded_submissions": result.stats.graded_submissions,
        },
    }


@router.post("/approve-suggestion")
async def approve_suggestion(
    body: ApproveSuggestionRequest,
) -> dict:
    from services.orchestrator_service import approve_suggestion

    logger.info(
        "approve_suggestion: suggestion_id=%s",
        body.suggestion_id,
    )

    overrides = [
        {
            "submission_id": o.submission_id,
            "criterion_id": o.criterion_id,
            "original_score": o.original_score,
            "teacher_score": o.teacher_score,
            "teacher_feedback": o.teacher_feedback,
        }
        for o in body.overrides
    ]
    result = await approve_suggestion(body.suggestion_id, overrides)

    return {
        "suggestion_id": result.suggestion_id,
        "results": [
            {
                "submission_id": r.submission_id,
                "total_score": r.total_score,
                "max_score": r.max_score,
                "feedback_summary": r.feedback_summary,
                "grading_model": r.grading_model,
                "evaluated_at": r.evaluated_at,
            }
            for r in result.results
        ],
    }


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


@router.get("/chat/conversations")
async def get_conversations(user_id: str = Depends(get_user_id)) -> dict:
    conversations = await list_conversations_by_user(user_id)
    return {
        "conversations": [
            {
                "id": c["id"],
                "session_id": c["session_id"],
                "first_message": (c["first_message"] or "")[:100],
                "last_message": (c["last_message"] or "")[:100],
                "started_at": c["started_at"].isoformat() if hasattr(c["started_at"], "isoformat") else str(c["started_at"]),
                "last_active_at": c["last_active_at"].isoformat() if hasattr(c["last_active_at"], "isoformat") else str(c["last_active_at"]),
            }
            for c in conversations
        ],
    }


@router.delete("/chat/conversations")
async def delete_chat_conversation(
    session_id: str = Query(...),
    user_id: str = Depends(get_user_id),
) -> dict:
    from db.pool import get_redis

    deleted = await delete_conversation(session_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    redis = get_redis()
    await redis.delete(f"session:{session_id}")

    return {"status": "deleted"}


@router.post("/generate-class", response_model=GenerateClassResponse)
async def generate_class(
    body: GenerateClassRequest,
    user_id: str = Depends(get_user_id),
) -> GenerateClassResponse:
    from services.class_generator import generate_class as run_generator

    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    logger.info("generate_class: user=%s prompt_len=%d", user_id, len(body.prompt))

    try:
        result = await run_generator(body.prompt)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("generate_class failed: user=%s", user_id)
        raise HTTPException(status_code=500, detail="Error generating class plan.")


@router.post("/generate-class/save")
async def save_class_plan(
    body: SaveClassPlanRequest,
    user_id: str = Depends(get_user_id),
) -> dict:
    plan = await create_class_plan(
        user_id=user_id,
        title=body.title,
        prompt=body.prompt,
        plan_data=body.plan_data,
    )
    return {"plan": plan}


@router.get("/generate-class/history")
async def get_class_plan_history(
    user_id: str = Depends(get_user_id),
    limit: int = 50,
) -> dict:
    plans = await list_class_plans_by_user(user_id, limit=limit)
    return {"plans": [ClassPlanListItem(**p).model_dump() for p in plans]}


@router.get("/chat/history")
async def get_chat_messages(session_id: str = Query(...)) -> dict:
    conversation_id: str | None = None

    try:
        session = await load_session(session_id)
        conversation_id = session["conversation_id"]
    except SessionExpiredError:
        conv = await get_conversation_by_session_id(session_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Session not found or expired.")
        conversation_id = conv["id"]
        await restore_session(
            session_id=session_id,
            user_id=conv["user_id"],
            conversation_id=conv["id"],
            workspace_id=conv.get("workspace_id"),
        )

    messages = await load_message_history(
        conversation_id=conversation_id,
        limit=50,
    )

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "blocks": m.get("blocks"),
                "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
            }
            for m in messages
        ],
    }
