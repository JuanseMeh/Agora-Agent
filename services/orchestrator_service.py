"""
services/orchestrator_service.py

Typed async wrappers for all four ai-orchestrator gRPC RPCs.

ID type mismatch -- proto uses int32 for workspace_id, assignment_id, submission_ids.
    The rest of the agent treats all IDs as strings/UUIDs.
    Conversion is handled here at the boundary: str -> int going IN, int -> str coming OUT.
    Nothing outside this file should ever see raw proto types.

RPCs:
  SuggestAssignment       -- generate grading suggestions (not persisted until approved)
  ApproveSuggestion       -- commit a cached suggestion set as final grades
  GradeAssignment         -- grade and persist immediately, no approval step
  GeneratePerformanceReport -- per-assignment/student metrics + AI-written analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from proto import ai_service_pb2  # type: ignore[import]
from services.grpc_client import get_stub

logger = logging.getLogger(__name__)


@dataclass
class CriterionResult:
    criterion_id: str
    criterion_name: str
    score: float
    max_score: float
    feedback: str
    matched_level: str


@dataclass
class GradingResult:
    result_id: str
    submission_id: str
    total_score: float
    max_score: float
    feedback_summary: str
    grading_model: str
    evaluated_at: str
    criteria_results: list[CriterionResult] = field(default_factory=list)


@dataclass
class SuggestionStats:
    average_score: float
    max_score: float
    graded_submissions: int


@dataclass
class SuggestAssignmentResult:
    suggestion_id: str
    results: list[GradingResult]
    stats: SuggestionStats


@dataclass
class ApproveResult:
    suggestion_id: str
    results: list[GradingResult]


@dataclass
class GradeAssignmentResult:
    results: list[GradingResult]


@dataclass
class AssignmentPerformance:
    assignment_id: str
    assignment_name: str
    total_submissions: int
    graded_submissions: int
    pending_submissions: int
    average_score: float
    max_score: float
    failed_submissions: int
    failure_rate: float


@dataclass
class StudentPerformance:
    user_id: str
    total_submissions: int
    graded_submissions: int
    pending_submissions: int
    average_score: float


@dataclass
class PerformanceReportResult:
    workspace_id: str
    assignment_id: str | None
    total_assignments: int
    total_submissions: int
    graded_submissions: int
    pending_submissions: int
    average_score: float
    ai_analysis: str
    assignments: list[AssignmentPerformance]
    students: list[StudentPerformance]


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Cannot convert ID to int32 for gRPC: {value!r}") from exc


def _parse_criterion(c: ai_service_pb2.CriterionResult) -> CriterionResult:
    return CriterionResult(
        criterion_id=c.criterion_id,
        criterion_name=c.criterion_name,
        score=c.score,
        max_score=c.max_score,
        feedback=c.feedback,
        matched_level=c.matched_level,
    )


def _parse_grading_result(r: ai_service_pb2.GradingResult) -> GradingResult:
    return GradingResult(
        result_id=r.result_id,
        submission_id=str(r.submission_id),
        total_score=r.total_score,
        max_score=r.max_score,
        feedback_summary=r.feedback_summary,
        grading_model=r.grading_model,
        evaluated_at=r.evaluated_at,
        criteria_results=[_parse_criterion(c) for c in r.criteria_results],
    )


async def suggest_assignment(
    workspace_id: str | int,
    assignment_id: str | int,
    requester_user_id: str,
    submission_ids: list[str | int] | None = None,
    user_ids: list[str] | None = None,
    include_already_graded: bool = False,
) -> SuggestAssignmentResult:
    stub = get_stub()

    request = ai_service_pb2.SuggestAssignmentRequest(
        workspace_id=_to_int(workspace_id),
        assignment_id=_to_int(assignment_id),
        requester_user_id=requester_user_id,
        submission_ids=[_to_int(sid) for sid in (submission_ids or [])],
        user_ids=list(user_ids or []),
        include_already_graded=include_already_graded,
    )

    logger.info(
        "SuggestAssignment: workspace=%s assignment=%s submissions=%s users=%s",
        workspace_id, assignment_id, submission_ids, user_ids,
    )

    response: ai_service_pb2.SuggestAssignmentResponse = await stub.SuggestAssignment(request)

    return SuggestAssignmentResult(
        suggestion_id=response.suggestion_id,
        results=[_parse_grading_result(r) for r in response.results],
        stats=SuggestionStats(
            average_score=response.stats.average_score,
            max_score=response.stats.max_score,
            graded_submissions=response.stats.graded_submissions,
        ),
    )


async def approve_suggestion(
    suggestion_id: str,
    overrides: list[dict] | None = None,
) -> ApproveResult:
    stub = get_stub()

    request = ai_service_pb2.ApproveSuggestionRequest(suggestion_id=suggestion_id)
    if overrides:
        for o in overrides:
            override = request.overrides.add()
            override.submission_id = o["submission_id"]
            override.criterion_id = o["criterion_id"]
            override.original_score = o["original_score"]
            override.teacher_score = o["teacher_score"]
            override.teacher_feedback = o["teacher_feedback"]

    logger.info(
        "ApproveSuggestion: suggestion_id=%s overrides=%s",
        suggestion_id, len(overrides or []),
    )

    response: ai_service_pb2.ApproveSuggestionResponse = await stub.ApproveSuggestion(request)

    return ApproveResult(
        suggestion_id=response.suggestion_id,
        results=[_parse_grading_result(r) for r in response.results],
    )


async def grade_assignment(
    workspace_id: str | int,
    assignment_id: str | int,
    submission_ids: list[str | int] | None = None,
    user_ids: list[str] | None = None,
    include_already_graded: bool = False,
) -> GradeAssignmentResult:
    stub = get_stub()

    request = ai_service_pb2.GradeAssignmentRequest(
        workspace_id=_to_int(workspace_id),
        assignment_id=_to_int(assignment_id),
        submission_ids=[_to_int(sid) for sid in (submission_ids or [])],
        user_ids=list(user_ids or []),
        include_already_graded=include_already_graded,
    )

    logger.info(
        "GradeAssignment: workspace=%s assignment=%s submissions=%s users=%s",
        workspace_id, assignment_id, submission_ids, user_ids,
    )

    response: ai_service_pb2.GradeAssignmentResponse = await stub.GradeAssignment(request)

    return GradeAssignmentResult(
        results=[_parse_grading_result(r) for r in response.results],
    )


async def generate_performance_report(
    workspace_id: str | int,
    assignment_id: str | int | None = None,
) -> PerformanceReportResult:
    stub = get_stub()

    request = ai_service_pb2.GeneratePerformanceReportRequest(
        workspace_id=_to_int(workspace_id),
    )
    if assignment_id is not None:
        request.assignment_id = _to_int(assignment_id)

    logger.info(
        "GeneratePerformanceReport: workspace=%s assignment=%s",
        workspace_id, assignment_id,
    )

    response: ai_service_pb2.GeneratePerformanceReportResponse = (
        await stub.GeneratePerformanceReport(request)
    )

    assignments = [
        AssignmentPerformance(
            assignment_id=str(a.assignment_id),
            assignment_name=a.assignment_name,
            total_submissions=a.total_submissions,
            graded_submissions=a.graded_submissions,
            pending_submissions=a.pending_submissions,
            average_score=a.average_score,
            max_score=a.max_score,
            failed_submissions=a.failed_submissions,
            failure_rate=a.failure_rate,
        )
        for a in response.assignments
    ]

    students = [
        StudentPerformance(
            user_id=s.user_id,
            total_submissions=s.total_submissions,
            graded_submissions=s.graded_submissions,
            pending_submissions=s.pending_submissions,
            average_score=s.average_score,
        )
        for s in response.students
    ]

    return PerformanceReportResult(
        workspace_id=str(response.workspace_id),
        assignment_id=str(response.assignment_id) if response.HasField("assignment_id") else None,
        total_assignments=response.total_assignments,
        total_submissions=response.total_submissions,
        graded_submissions=response.graded_submissions,
        pending_submissions=response.pending_submissions,
        average_score=response.average_score,
        ai_analysis=response.ai_analysis,
        assignments=assignments,
        students=students,
    )


if __name__ == "__main__":
    import asyncio
    import sys
    from services.grpc_client import init_grpc_client, close_grpc_client

    async def smoke_test(workspace_id: str, assignment_id: str) -> None:
        await init_grpc_client()
        try:
            report = await generate_performance_report(workspace_id, assignment_id)
            print(f"GeneratePerformanceReport -> workspace={report.workspace_id}")
            print(f"   total_assignments={report.total_assignments}")
            print(f"   total_submissions={report.total_submissions}")
            print(f"   average_score={report.average_score}")
            print(f"   ai_analysis={report.ai_analysis[:120]}...")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await close_grpc_client()

    ws = sys.argv[1] if len(sys.argv) > 1 else "1"
    asgn = sys.argv[2] if len(sys.argv) > 2 else "1"
    asyncio.run(smoke_test(ws, asgn))
