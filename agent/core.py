"""
agent/core.py

Agent entrypoint -- the single function the API route calls.

run(user_input, session) does the following:
  1. Builds ToolContext from session data
  2. Loads conversation history from Postgres (last N messages)
  3. Appends current user message
  4. Compiles the LangGraph graph bound to this session's context
  5. Invokes the graph
  6. Builds and returns AgentResponse from final state
"""

from __future__ import annotations

import logging

from agent.graph import AgentState, compile_graph
from agent.memory import build_initial_state_messages
from agent.prompt import SYSTEM_PROMPT
from agent.response_builder import build_response
from agent.session import SessionData
from langchain_core.messages import SystemMessage
from schemas.response import AgentResponse, AlertBlock
from tools.context import ToolContext

logger = logging.getLogger(__name__)


async def run(
    user_input: str,
    session: SessionData,
) -> AgentResponse:
    session_id = session["session_id"]
    conversation_id = session["conversation_id"]

    logger.info(
        "Agent run: session=%s conversation=%s workspace=%s",
        session_id, conversation_id, session.get("workspace_id"),
    )

    ctx = ToolContext(
        user_id=session["user_id"],
        workspace_id=session.get("workspace_id"),
        conversation_id=conversation_id,
    )

    messages = await build_initial_state_messages(
        conversation_id=conversation_id,
        user_input=user_input,
    )

    initial_state: AgentState = {
        "messages": [SystemMessage(content=SYSTEM_PROMPT)] + messages,
        "ctx": ctx,
        "iteration": 0,
        "has_error": False,
        "approval_pending": False,
        "confirmed": False,
        "actions_triggered": [],
    }

    graph = compile_graph(ctx)

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.exception("Graph invocation failed: session=%s", session_id)
        return AgentResponse(
            session_id=session_id,
            message="Something went wrong while processing your request. Please try again.",
            blocks=[AlertBlock(severity="error", message=str(e))],
            actions_triggered=[],
            error=str(e),
        )

    if ctx.workspace_id and not session.get("workspace_id"):
        from agent.session import update_session_workspace
        await update_session_workspace(session_id, ctx.workspace_id)
        logger.info(
            "Workspace resolved during run: session=%s workspace=%s",
            session_id, ctx.workspace_id,
        )

    response = build_response(session_id=session_id, final_state=final_state)

    logger.info(
        "Agent run complete: session=%s blocks=%d actions=%s error=%s",
        session_id,
        len(response.blocks),
        response.actions_triggered,
        response.error,
    )

    return response
