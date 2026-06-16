"""
services/workspace_service.py

Typed async client for workspace-service (Java/Spring, port 8080).
Covers: Workspaces, Members, Assignments, Submissions, and Reports.

All IDs are treated as strings at this layer (workspace_id, assignment_id, user_id).
The workspace-service uses numeric IDs internally -- this client handles that transparently.

Endpoints verified from Postman collection + Java source controllers:

  Workspaces:
    GET /workspaces/getAllWorkspaces
    GET /workspaces/getWorkspaceById/{id}

  Members:
    GET /workspaces/member/workspace/{workspaceId}/details
    GET /workspaces/member/user                              (header: X-User-Id)

  Assignments:
    GET /workspaces/assignments/workspace/{workspaceId}
    GET /workspaces/assignments/{id}

  Submissions:
    GET /workspaces/submission/assignment/{assignmentId}
    GET /workspaces/submission/user/{userId}
    GET /workspaces/submission/{id}

  Reports (public):
    GET /workspaces/{workspaceId}/reports/basic

  Reports (internal):
    GET /internal/reports/workspaces/{workspaceId}/performance-data
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from services.http_client import get_workspace_client, raise_for_service_error

logger = logging.getLogger(__name__)

_SVC = "workspace-service"


class WorkspaceDTO(BaseModel):
    id: Any
    name: str
    description: str | None = None
    ownerId: Any | None = None
    createdAt: str | None = None


class MemberDTO(BaseModel):
    id: Any | None = None
    userId: Any
    workspaceId: Any
    role: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    fullName: str | None = None
    avatarUrl: str | None = None


class AssignmentDTO(BaseModel):
    id: Any
    workspaceId: Any
    name: str
    description: str | None = None
    dueDate: str | None = None
    maxScore: float | None = None
    status: str | None = None


class SubmissionDTO(BaseModel):
    id: Any
    assignmentId: Any
    userId: Any
    status: str | None = None
    score: float | None = None
    feedback: str | None = None
    submittedAt: str | None = None
    gradedAt: str | None = None
    result: dict | None = None


class BasicWorkspaceReportDTO(BaseModel):
    workspaceId: Any
    totalAssignments: int
    gradedSubmissions: int
    pendingSubmissions: int
    averageScore: float | None = None


class AssignmentPerformanceDTO(BaseModel):
    assignmentId: Any
    assignmentName: str
    averageScore: float | None = None
    maxScore: float | None = None
    failedSubmissions: int | None = None
    failureRate: float | None = None


class StudentPerformanceDTO(BaseModel):
    userId: Any
    totalSubmissions: int
    gradedSubmissions: int
    pendingSubmissions: int
    averageScore: float | None = None


class PerformanceSummaryDTO(BaseModel):
    totalAssignments: int | None = None
    totalSubmissions: int | None = None
    gradedSubmissions: int | None = None
    pendingSubmissions: int | None = None
    averageScore: float | None = None


class WorkspacePerformanceDataDTO(BaseModel):
    summary: PerformanceSummaryDTO | None = None
    assignments: list[AssignmentPerformanceDTO] = []
    students: list[StudentPerformanceDTO] = []


async def get_all_workspaces(user_id: str | None = None) -> list[WorkspaceDTO]:
    client = get_workspace_client()
    headers = {}
    if user_id:
        headers["X-User-Id"] = user_id
    response = await client.get("/workspaces/getAllWorkspaces", headers=headers)
    raise_for_service_error(response, _SVC)
    return [WorkspaceDTO(**item) for item in response.json()]


async def get_workspace_by_id(workspace_id: str | int) -> WorkspaceDTO:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/getWorkspaceById/{workspace_id}")
    raise_for_service_error(response, _SVC)
    return WorkspaceDTO(**response.json())


async def get_workspace_members(workspace_id: str | int) -> list[MemberDTO]:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/member/workspace/{workspace_id}/details")
    raise_for_service_error(response, _SVC)
    return [MemberDTO(**item) for item in response.json()]


async def get_user_memberships(user_id: str | int) -> list[MemberDTO]:
    client = get_workspace_client()
    response = await client.get(
        "/workspaces/member/user",
        headers={"X-User-Id": str(user_id)},
    )
    raise_for_service_error(response, _SVC)
    data = response.json()
    if isinstance(data, list):
        return [MemberDTO(**item) for item in data]
    return [MemberDTO(**data)]


async def get_assignments_for_workspace(workspace_id: str | int) -> list[AssignmentDTO]:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/assignments/workspace/{workspace_id}")
    raise_for_service_error(response, _SVC)
    return [AssignmentDTO(**item) for item in response.json()]


async def get_assignment_by_id(assignment_id: str | int) -> AssignmentDTO:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/assignments/{assignment_id}")
    raise_for_service_error(response, _SVC)
    return AssignmentDTO(**response.json())


async def get_submissions_for_assignment(assignment_id: str | int) -> list[SubmissionDTO]:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/submission/assignment/{assignment_id}")
    raise_for_service_error(response, _SVC)
    return [SubmissionDTO(**item) for item in response.json()]


async def get_submissions_for_user(user_id: str | int) -> list[SubmissionDTO]:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/submission/user/{user_id}")
    raise_for_service_error(response, _SVC)
    return [SubmissionDTO(**item) for item in response.json()]


async def get_submission_by_id(submission_id: str | int) -> SubmissionDTO:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/submission/{submission_id}")
    raise_for_service_error(response, _SVC)
    return SubmissionDTO(**response.json())


async def get_basic_workspace_report(workspace_id: str | int) -> BasicWorkspaceReportDTO:
    client = get_workspace_client()
    response = await client.get(f"/workspaces/{workspace_id}/reports/basic")
    raise_for_service_error(response, _SVC)
    return BasicWorkspaceReportDTO(**response.json())


async def get_workspace_performance_data(workspace_id: str | int) -> WorkspacePerformanceDataDTO:
    client = get_workspace_client()
    response = await client.get(
        f"/internal/reports/workspaces/{workspace_id}/performance-data"
    )
    raise_for_service_error(response, _SVC)
    return WorkspacePerformanceDataDTO(**response.json())


if __name__ == "__main__":
    import asyncio
    from services.http_client import init_http_clients, close_http_clients

    async def smoke_test() -> None:
        init_http_clients()
        try:
            workspaces = await get_all_workspaces()
            print(f"get_all_workspaces -> {len(workspaces)} workspace(s)")
            if workspaces:
                ws_id = workspaces[0].id
                ws = await get_workspace_by_id(ws_id)
                print(f"get_workspace_by_id({ws_id}) -> {ws.name}")

                assignments = await get_assignments_for_workspace(ws_id)
                print(f"get_assignments_for_workspace({ws_id}) -> {len(assignments)} assignment(s)")

                members = await get_workspace_members(ws_id)
                print(f"get_workspace_members({ws_id}) -> {len(members)} member(s)")

                report = await get_basic_workspace_report(ws_id)
                print(f"get_basic_workspace_report({ws_id}) -> {report}")
        finally:
            await close_http_clients()

    asyncio.run(smoke_test())
