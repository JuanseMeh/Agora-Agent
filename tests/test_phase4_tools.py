"""Verify Phase 4 (Tools) modules import and wire correctly."""

from tools.context import ToolContext


def test_tool_context_defaults():
    ctx = ToolContext(user_id="u1", conversation_id="c1")
    assert ctx.user_id == "u1"
    assert ctx.conversation_id == "c1"
    assert ctx.workspace_id is None
    assert ctx.pending_suggestion_id is None
    assert ctx.pending_assignment_id is None


def test_tool_context_has_workspace():
    ctx = ToolContext(user_id="u1", conversation_id="c1", workspace_id="w1")
    assert ctx.has_workspace() is True


def test_tool_context_no_workspace():
    ctx = ToolContext(user_id="u1", conversation_id="c1")
    assert ctx.has_workspace() is False


def test_workspace_id_required_raises():
    ctx = ToolContext(user_id="u1", conversation_id="c1")
    try:
        ctx.workspace_id_required()
        assert False, "expected ValueError"
    except ValueError as e:
        assert "No workspace context" in str(e)


def test_workspace_id_required_returns():
    ctx = ToolContext(user_id="u1", conversation_id="c1", workspace_id="w1")
    assert ctx.workspace_id_required() == "w1"


def test_get_tools_returns_15_tools():
    from tools import get_tools

    ctx = ToolContext(user_id="u", conversation_id="c", workspace_id="w")
    tools = get_tools(ctx)
    assert len(tools) == 15


def test_tool_names():
    from tools import get_tools

    ctx = ToolContext(user_id="u", conversation_id="c", workspace_id="w")
    names = [t.name for t in get_tools(ctx)]
    assert "suggest_grades" in names
    assert "grade_assignment_directly" in names
    assert "get_performance_report" in names
    assert "list_workspaces" in names
    assert "get_workspace" in names
    assert "list_assignments" in names
    assert "get_assignment" in names
    assert "list_submissions_for_assignment" in names
    assert "list_submissions_for_user" in names
    assert "get_submission" in names
    assert "get_user" in names
    assert "get_user_by_email_address" in names
    assert "list_workspace_members" in names
    assert "basic_workspace_report" in names
    assert "workspace_performance_report" in names
    assert len(names) == len(set(names)), "duplicate tool names!"


def test_approve_suggestion_not_a_tool():
    from tools import get_tools

    ctx = ToolContext(user_id="u", conversation_id="c", workspace_id="w")
    names = [t.name for t in get_tools(ctx)]
    assert "approve_suggestion" not in names



