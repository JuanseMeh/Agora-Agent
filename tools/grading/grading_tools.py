"""
tools/grading/grading_tools.py

Grading tools -- all trigger the ai-orchestrator over gRPC.

ApproveSuggestion is NOT here.
It is a confirmation handler, not an LLM-selectable tool.
The graph gates it behind explicit teacher confirmation and calls
orchestrator_service.approve_suggestion() directly from the confirm node.

Tools here:
  suggest_assignment          -- generate suggestions, store suggestion_id in ctx
  grade_assignment_directly   -- grade and persist immediately (no approval step)
  get_performance_report      -- surface results from a previous suggest or grade call
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from services.orchestrator_service import (
    suggest_assignment,
    grade_assignment,
    GradingResult,
)
from tools.context import ToolContext

logger = logging.getLogger(__name__)


def _serialize_grading_result(r: GradingResult) -> dict:
    return {
        "resultId": r.result_id,
        "submissionId": r.submission_id,
        "totalScore": r.total_score,
        "maxScore": r.max_score,
        "feedbackSummary": r.feedback_summary,
        "gradingModel": r.grading_model,
        "evaluatedAt": r.evaluated_at,
        "criteriaResults": [
            {
                "criterionId": c.criterion_id,
                "criterionName": c.criterion_name,
                "score": c.score,
                "maxScore": c.max_score,
                "feedback": c.feedback,
                "matchedLevel": c.matched_level,
            }
            for c in r.criteria_results
        ],
    }


def make_grading_tools(ctx: ToolContext) -> list:
    _ = ctx

    @tool
    async def suggest_grades(
        assignment_id: str,
        include_already_graded: bool = False,
    ) -> dict:
        """
        Generates AI grading suggestions for an assignment without saving them.
        The teacher must review and confirm before grades are committed.
        Use this when the teacher asks to grade, review, or suggest grades for an assignment
        (e.g. 'grade homework 3', 'suggest grades for the midterm').
        After calling this, present the suggestions and ask the teacher to confirm or discard.
        Args:
            assignment_id: The assignment UUID to generate suggestions for.
            include_already_graded: If True, re-grades already graded submissions. Default False.
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            result = await suggest_assignment(
                workspace_id=workspace_id,
                assignment_id=assignment_id,
                requester_user_id=ctx.user_id,
                include_already_graded=include_already_graded,
            )

            ctx.pending_suggestion_id = result.suggestion_id
            ctx.pending_assignment_id = assignment_id

            from agent.session import update_session_pending
            await update_session_pending(
                session_id=ctx.session_id,
                pending_suggestion_id=result.suggestion_id,
                pending_assignment_id=assignment_id,
            )

            logger.info(
                "Suggestion generated: suggestion_id=%s assignment=%s count=%d",
                result.suggestion_id, assignment_id, len(result.results),
            )

            return {
                "suggestion_id": result.suggestion_id,
                "assignment_id": assignment_id,
                "stats": {
                    "averageScore": result.stats.average_score,
                    "maxScore": result.stats.max_score,
                    "gradedSubmissions": result.stats.graded_submissions,
                },
                "results": [_serialize_grading_result(r) for r in result.results],
                "pending_approval": True,
            }

        except Exception as e:
            logger.exception("suggest_grades failed for assignment %s", assignment_id)
            return {"error": f"Failed to generate grading suggestions: {e}"}

    @tool
    async def grade_assignment_directly(
        assignment_id: str,
        include_already_graded: bool = False,
    ) -> dict:
        """
        Grades an assignment and saves the results immediately -- no suggestion or approval step.
        Use this only when the teacher explicitly asks to grade directly and skip review
        (e.g. 'just grade it', 'grade without showing me suggestions').
        For the standard two-phase workflow, use suggest_grades instead.
        Args:
            assignment_id: The assignment UUID to grade.
            include_already_graded: If True, re-grades already graded submissions. Default False.
        """
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            result = await grade_assignment(
                workspace_id=workspace_id,
                assignment_id=assignment_id,
                include_already_graded=include_already_graded,
            )

            logger.info(
                "Direct grading complete: assignment=%s count=%d",
                assignment_id, len(result.results),
            )

            return {
                "assignment_id": assignment_id,
                "graded_count": len(result.results),
                "results": [_serialize_grading_result(r) for r in result.results],
                "pending_approval": False,
            }

        except Exception as e:
            logger.exception("grade_assignment_directly failed for assignment %s", assignment_id)
            return {"error": f"Failed to grade assignment: {e}"}

    @tool
    async def get_performance_report(assignment_id: str | None = None) -> dict:
        """
        Returns a detailed performance report with AI-written analysis.
        Covers per-assignment stats, per-student stats, and an AI summary paragraph.
        Use this when the teacher asks for a performance report, class analysis,
        or wants to understand trends (e.g. 'how did the class do?',
        'give me a performance report for assignment 3', 'who is struggling?').
        Args:
            assignment_id: Optional. Scope the report to one assignment. Omit for workspace-wide.
        """
        from services.orchestrator_service import generate_performance_report
        try:
            workspace_id = ctx.workspace_id_required()
        except ValueError as e:
            return {"error": str(e)}

        try:
            report = await generate_performance_report(
                workspace_id=workspace_id,
                assignment_id=assignment_id,
            )

            return {
                "workspaceId": report.workspace_id,
                "assignmentId": report.assignment_id,
                "totalAssignments": report.total_assignments,
                "totalSubmissions": report.total_submissions,
                "gradedSubmissions": report.graded_submissions,
                "pendingSubmissions": report.pending_submissions,
                "averageScore": report.average_score,
                "aiAnalysis": report.ai_analysis,
                "assignments": [
                    {
                        "assignmentId": a.assignment_id,
                        "assignmentName": a.assignment_name,
                        "totalSubmissions": a.total_submissions,
                        "gradedSubmissions": a.graded_submissions,
                        "pendingSubmissions": a.pending_submissions,
                        "averageScore": a.average_score,
                        "maxScore": a.max_score,
                        "failedSubmissions": a.failed_submissions,
                        "failureRate": a.failure_rate,
                    }
                    for a in report.assignments
                ],
                "students": [
                    {
                        "userId": s.user_id,
                        "totalSubmissions": s.total_submissions,
                        "gradedSubmissions": s.graded_submissions,
                        "pendingSubmissions": s.pending_submissions,
                        "averageScore": s.average_score,
                    }
                    for s in report.students
                ],
            }

        except Exception as e:
            logger.exception("get_performance_report failed")
            return {"error": f"Failed to generate performance report: {e}"}

    return [suggest_grades, grade_assignment_directly, get_performance_report]
