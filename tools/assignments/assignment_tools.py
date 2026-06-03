"""
tools/assignments/assignment_tools.py

Assignment read tools.

workspace_id always comes from ctx (session context).
assignment_id is supplied by the LLM after it has resolved the name
via list_assignments.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.workspace_service import (
    get_assignment_by_id,
    get_assignments_for_workspace,
)
from services.http_client import ServiceError
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def make_assignment_tools(ctx: ToolContext) -> list:
    _ = ctx

    @tool
    async def list_assignments() -> dict:
        """
        Lists all assignments in the current workspace.
        Use this when the teacher refers to an assignment by name or description
        (e.g. 'the midterm', 'homework 3') and you need to resolve it to an assignment ID.
        Returns assignment IDs, titles, due dates, and max scores.
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            assignments = await get_assignments_for_workspace(workspace_id)
            return {
                "assignments": [
                    {
                        "id": str(a.id),
                        "title": a.name,
                        "description": a.description,
                        "dueDate": a.dueDate,
                        "maxScore": a.maxScore,
                    }
                    for a in assignments
                ]
            }
        except ServiceError as e:
            logger.error("list_assignments failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("list_assignments unexpected error")
            return {"error": f"Unexpected error listing assignments: {e}"}

    @tool
    async def get_assignment(assignment_id: str) -> dict:
        """
        Returns full details for a specific assignment by its ID.
        Use this after resolving the assignment name via list_assignments.
        Args:
            assignment_id: The assignment UUID to fetch.
        """
        try:
            a = await get_assignment_by_id(assignment_id)
            return {
                "id": str(a.id),
                "workspaceId": str(a.workspaceId),
                "title": a.title,
                "description": a.description,
                "dueDate": a.dueDate,
                "maxScore": a.maxScore,
                "createdAt": a.createdAt,
            }
        except ServiceError as e:
            logger.error("get_assignment(%s) failed: %s", assignment_id, e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("get_assignment unexpected error")
            return {"error": f"Unexpected error fetching assignment {assignment_id}: {e}"}

    return [list_assignments, get_assignment]
