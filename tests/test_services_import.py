"""Verify all service modules import cleanly. Does not require running services."""

import pytest
from config.settings import Settings


class TestHttpClient:
    def test_init_and_close(self):
        from services.http_client import init_http_clients, close_http_clients, get_workspace_client, get_users_client
        import httpx

        init_http_clients()
        ws = get_workspace_client()
        us = get_users_client()
        assert isinstance(ws, httpx.AsyncClient)
        assert isinstance(us, httpx.AsyncClient)

        import asyncio
        asyncio.run(close_http_clients())

    def test_service_error(self):
        from services.http_client import ServiceError, raise_for_service_error
        import httpx

        err = ServiceError(service="test", status_code=500, detail="boom")
        assert err.service == "test"
        assert err.status_code == 500
        assert "HTTP 500" in str(err)

        success = httpx.Response(200, request=httpx.Request("GET", "http://test"))
        raise_for_service_error(success, "test")  # no raise

        fail = httpx.Response(404, json={"message": "not found"}, request=httpx.Request("GET", "http://test"))
        with pytest.raises(ServiceError) as exc:
            raise_for_service_error(fail, "test")
        assert exc.value.status_code == 404
        assert exc.value.detail == "not found"


class TestWorkspaceService:
    def test_dtos(self):
        from services.workspace_service import (
            WorkspaceDTO, MemberDTO, AssignmentDTO, SubmissionDTO,
            BasicWorkspaceReportDTO, WorkspacePerformanceDataDTO,
        )
        ws = WorkspaceDTO(id=1, name="test")
        assert ws.name == "test"

        report = BasicWorkspaceReportDTO(
            workspaceId=1, totalAssignments=5, gradedSubmissions=3, pendingSubmissions=2
        )
        assert report.totalAssignments == 5

    def test_functions_import(self):
        from services.workspace_service import (
            get_all_workspaces, get_workspace_by_id, get_workspace_members,
            get_user_memberships, get_assignments_for_workspace, get_assignment_by_id,
            get_submissions_for_assignment, get_submissions_for_user, get_submission_by_id,
            get_basic_workspace_report, get_workspace_performance_data,
        )
        assert callable(get_all_workspaces)


class TestUsersService:
    def test_dtos(self):
        from services.users_service import UserDTO, UserExistsDTO
        user = UserDTO(id=1, name="Test User")
        assert user.name == "Test User"

    def test_functions_import(self):
        from services.users_service import get_user_by_id, get_user_by_email, user_exists
        assert callable(get_user_by_id)


class TestGrpcClient:
    def test_stubs_exist(self):
        import importlib
        try:
            importlib.import_module("proto.ai_service_pb2")
            importlib.import_module("proto.ai_service_pb2_grpc")
        except ImportError:
            pytest.fail("gRPC stubs not found. Run `make proto`.")

    def test_import(self):
        from services.grpc_client import init_grpc_client, close_grpc_client, get_stub
        assert callable(init_grpc_client)


class TestOrchestratorService:
    def test_result_types(self):
        from services.orchestrator_service import (
            GradingResult, CriterionResult, SuggestionStats,
            SuggestAssignmentResult, ApproveResult, GradeAssignmentResult,
            AssignmentPerformance, StudentPerformance, PerformanceReportResult,
        )
        r = GradingResult(
            result_id="1", submission_id="1", total_score=85.0, max_score=100.0,
            feedback_summary="good", grading_model="gemini", evaluated_at="now",
        )
        assert r.total_score == 85.0

    def test_functions_import(self):
        from services.orchestrator_service import (
            suggest_assignment, approve_suggestion, grade_assignment, generate_performance_report,
        )
        assert callable(suggest_assignment)


class TestSettings:
    def test_required_fields_must_come_from_env(self):
        fields = Settings.model_fields
        assert fields["google_api_key"].is_required()
        assert fields["database_url"].is_required()
        assert fields["redis_url"].is_required()

    def test_service_urls_use_correct_names_and_ports(self):
        s = Settings.model_construct(
            google_api_key="test", database_url="test", redis_url="test"
        )
        assert "user-service" in s.users_service_url and "8080" in s.users_service_url
        assert "workspace-service" in s.workspace_service_url and "8080" in s.workspace_service_url
