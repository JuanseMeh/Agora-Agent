"""
tools/context.py

ToolContext is the session-scoped object injected into every tool at graph
compilation time. It carries the IDs the tools need without the LLM ever
having to supply or know about them.

Usage (in agent/core.py when compiling the graph):

    ctx = ToolContext(
        user_id=session["user_id"],
        workspace_id=session["workspace_id"],
        conversation_id=session["conversation_id"],
    )
    tools = get_tools(ctx)

Tools receive workspace_id from ctx, never as an LLM argument.
The LLM resolves natural language to concrete IDs by calling
read tools first (list_assignments, list_submissions), then using those
concrete IDs in action tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolContext:
    user_id: str
    conversation_id: str
    workspace_id: str | None = None

    pending_suggestion_id: str | None = field(default=None, repr=False)
    pending_assignment_id: str | None = field(default=None, repr=False)

    def has_workspace(self) -> bool:
        return self.workspace_id is not None

    def workspace_id_required(self) -> str:
        if self.workspace_id is None:
            raise ValueError(
                "No workspace context. The teacher must specify a workspace before this action."
            )
        return self.workspace_id
