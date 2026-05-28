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


class SuggestGradesRequest(BaseModel):
    workspace_id: str
    assignment_id: str
    submission_ids: list[str] | None = None
    user_ids: list[str] | None = None
    include_already_graded: bool = False


class ApproveSuggestionRequest(BaseModel):
    suggestion_id: str


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

    result = await approve_suggestion(body.suggestion_id)

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
