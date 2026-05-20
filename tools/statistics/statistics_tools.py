"""
tools/statistics/statistics_tools.py

Statistics and report tools.

Two data sources:
  - basic_workspace_report   -> workspace-service public endpoint (fast, aggregate counts)
  - workspace_performance    -> workspace-service internal endpoint (full per-assignment/student breakdown)

Both use workspace_id from session context.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.workspace_service import (
    get_basic_workspace_report,
    get_workspace_performance_data,
)
from services.http_client import ServiceError
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def make_statistics_tools(ctx: ToolContext) -> list:
    _ = ctx

    @tool
    async def basic_workspace_report() -> dict:
        """
        Returns high-level statistics for the current workspace:
        total assignments, graded submissions, pending submissions, and average score.
        Use this when the teacher asks for a quick overview or summary of their class
        (e.g. 'how is my class doing?', 'give me a summary of this workspace').
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            report = await get_basic_workspace_report(workspace_id)
            return {
                "workspaceId": str(report.workspaceId),
                "totalAssignments": report.totalAssignments,
                "gradedSubmissions": report.gradedSubmissions,
                "pendingSubmissions": report.pendingSubmissions,
                "averageScore": report.averageScore,
            }
        except ServiceError as e:
            logger.error("basic_workspace_report failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("basic_workspace_report unexpected error")
            return {"error": f"Unexpected error fetching workspace report: {e}"}

    @tool
    async def workspace_performance_report() -> dict:
        """
        Returns a detailed performance breakdown for the current workspace:
        per-assignment stats (average score, failure rate, graded/pending counts)
        and per-student stats (average score, submission counts).
        Use this when the teacher wants to identify struggling students, compare
        assignment difficulty, or get a full picture of class performance.
        More detailed than basic_workspace_report.
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            data = await get_workspace_performance_data(workspace_id)

            summary = {}
            if data.summary:
                summary = {
                    "totalAssignments": data.summary.totalAssignments,
                    "totalSubmissions": data.summary.totalSubmissions,
                    "gradedSubmissions": data.summary.gradedSubmissions,
                    "pendingSubmissions": data.summary.pendingSubmissions,
                    "averageScore": data.summary.averageScore,
                }

            assignments = [
                {
                    "assignmentId": str(a.assignmentId),
                    "assignmentName": a.assignmentName,
                    "averageScore": a.averageScore,
                    "maxScore": a.maxScore,
                    "failedSubmissions": a.failedSubmissions,
                    "failureRate": a.failureRate,
                }
                for a in data.assignments
            ]

            students = [
                {
                    "userId": str(s.userId),
                    "totalSubmissions": s.totalSubmissions,
                    "gradedSubmissions": s.gradedSubmissions,
                    "pendingSubmissions": s.pendingSubmissions,
                    "averageScore": s.averageScore,
                }
                for s in data.students
            ]

            return {"summary": summary, "assignments": assignments, "students": students}

        except ServiceError as e:
            logger.error("workspace_performance_report failed: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("workspace_performance_report unexpected error")
            return {"error": f"Unexpected error fetching performance report: {e}"}

    return [basic_workspace_report, workspace_performance_report]
