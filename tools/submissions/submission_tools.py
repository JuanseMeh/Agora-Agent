"""
tools/submissions/submission_tools.py

Submission read tools.

Three access patterns covered:
  - by assignment  (most common: 'show me all submissions for homework 3')
  - by user        ('show me all submissions from student X')
  - by ID          (direct lookup after the LLM has a submission_id)
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.workspace_service import (
    get_submission_by_id,
    get_submissions_for_assignment,
    get_submissions_for_user,
)
from services.http_client import ServiceError
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def _serialize_submission(s) -> dict:
    return {
        "id": str(s.id),
        "assignmentId": str(s.assignmentId),
        "userId": str(s.userId),
        "status": s.status,
        "score": s.score,
        "feedback": s.feedback,
        "submittedAt": s.submittedAt,
        "gradedAt": s.gradedAt,
    }


def make_submission_tools(ctx: ToolContext) -> list:
    _ = ctx

    @tool
    async def list_submissions_for_assignment(assignment_id: str) -> dict:
        """
        Lists all submissions for a specific assignment.
        Use this when the teacher asks to see submissions, grades, or grading status
        for an assignment (e.g. 'show me all submissions for homework 3').
        Returns submission IDs, student IDs, status, scores, and feedback.
        Args:
            assignment_id: The assignment UUID to fetch submissions for.
        """
        try:
            submissions = await get_submissions_for_assignment(assignment_id)
            return {
                "assignment_id": assignment_id,
                "count": len(submissions),
                "submissions": [_serialize_submission(s) for s in submissions],
            }
        except ServiceError as e:
            logger.error("list_submissions_for_assignment(%s) failed: %s", assignment_id, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("list_submissions_for_assignment unexpected error")
            return {"error": f"Unexpected error listing submissions: {e}"}

    @tool
    async def list_submissions_for_user(user_id: str) -> dict:
        """
        Lists all submissions by a specific student.
        Use this when the teacher asks about a particular student's work
        (e.g. 'what has student Maria submitted?', 'show me John's submissions').
        Args:
            user_id: The student's user UUID.
        """
        try:
            submissions = await get_submissions_for_user(user_id)
            return {
                "user_id": user_id,
                "count": len(submissions),
                "submissions": [_serialize_submission(s) for s in submissions],
            }
        except ServiceError as e:
            logger.error("list_submissions_for_user(%s) failed: %s", user_id, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("list_submissions_for_user unexpected error")
            return {"error": f"Unexpected error listing user submissions: {e}"}

    @tool
    async def get_submission(submission_id: str) -> dict:
        """
        Returns full details for a single submission by its ID.
        Use this for a deep look at one specific submission -- score, feedback, grading status.
        Args:
            submission_id: The submission UUID to fetch.
        """
        try:
            s = await get_submission_by_id(submission_id)
            return _serialize_submission(s)
        except ServiceError as e:
            logger.error("get_submission(%s) failed: %s", submission_id, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("get_submission unexpected error")
            return {"error": f"Unexpected error fetching submission {submission_id}: {e}"}

    return [list_submissions_for_assignment, list_submissions_for_user, get_submission]
