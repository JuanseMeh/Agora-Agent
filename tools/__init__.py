"""
tools/__init__.py

Tool registry -- single entry point for the agent graph.

Usage in agent/core.py:

    from tools import get_tools
    from tools.context import ToolContext

    ctx = ToolContext(
        user_id=session["user_id"],
        workspace_id=session["workspace_id"],
        conversation_id=session["conversation_id"],
    )
    tools = get_tools(ctx)

All tools are @tool-decorated async functions bound to the ToolContext at call time.
ApproveSuggestion is intentionally absent -- it is a graph confirmation node, not a tool.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from tools.context import ToolContext
from tools.workspace.workspace_tools import make_workspace_tools
from tools.assignments.assignment_tools import make_assignment_tools
from tools.submissions.submission_tools import make_submission_tools
from tools.users.user_tools import make_user_tools
from tools.statistics.statistics_tools import make_statistics_tools
from tools.grading.grading_tools import make_grading_tools


def get_tools(ctx: ToolContext) -> list[BaseTool]:
    """
    Returns the full list of agent tools bound to the given session context.
    Call once per agent invocation with the session's ToolContext.

    15 tools across 6 categories.

    Read-only (safe, no side effects):
      list_workspaces, get_workspace
      list_assignments, get_assignment
      list_submissions_for_assignment, list_submissions_for_user, get_submission
      get_user, get_user_by_email_address, list_workspace_members
      basic_workspace_report, workspace_performance_report

    Write/trigger (side effects -- orchestrator calls):
      suggest_grades               -> stores suggestion_id in ctx, requires teacher approval
      grade_assignment_directly    -> grades and persists immediately
      get_performance_report       -> read-only but calls orchestrator gRPC

    NOT included (handled by graph nodes, not LLM tool selection):
      approve_suggestion           -> confirmation handler in agent/graph.py confirm node
    """
    return [
        *make_workspace_tools(ctx),
        *make_assignment_tools(ctx),
        *make_submission_tools(ctx),
        *make_user_tools(ctx),
        *make_statistics_tools(ctx),
        *make_grading_tools(ctx),
    ]


__all__ = ["get_tools", "ToolContext"]
