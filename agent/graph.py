"""
agent/graph.py

LangGraph agent graph -- linear topology, single tool call per node execution.

Graph structure:
  START -> check_pending -> confirm (if approval intent) -> END
                         -> call_llm -> call_tool -> call_llm (loop) -> respond -> END
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from config.settings import settings
from services.orchestrator_service import approve_suggestion
from tools import get_tools
from tools.context import ToolContext

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    ctx: ToolContext
    iteration: int
    has_error: bool
    unexpected_error: bool
    approval_pending: bool
    confirmed: bool
    actions_triggered: list[str]


_APPROVAL_INTENT_PROMPT = """The teacher has just seen grading suggestions and sent the following message:

"{message}"

Does this message indicate the teacher wants to APPROVE and commit the grading suggestions?
Answer with a single word: YES or NO.
Only answer YES if the teacher clearly wants to apply, confirm, or commit the grades.
Phrases like "yes", "approve", "looks good", "grade them", "apply", "confirm", "go ahead" -> YES.
Phrases like "no", "discard", "redo", "cancel", "show me again" -> NO.
Ambiguous or unrelated messages -> NO."""


def _make_llm(tools: list) -> ChatOpenAI:
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    return llm.bind_tools(tools)


def _make_classifier_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        max_tokens=10,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


async def check_pending_node(state: AgentState) -> dict:
    ctx = state["ctx"]

    if ctx.pending_suggestion_id is None:
        return {"approval_pending": False}

    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if last_human is None:
        return {"approval_pending": False}

    classifier = _make_classifier_llm()
    prompt = _APPROVAL_INTENT_PROMPT.format(message=last_human.content)
    response = await classifier.ainvoke([HumanMessage(content=prompt)])

    is_approval = response.content.strip().upper().startswith("YES")
    logger.info(
        "Approval intent check: pending=%s input=%r -> %s",
        ctx.pending_suggestion_id, last_human.content, "APPROVE" if is_approval else "CONTINUE",
    )
    return {"approval_pending": is_approval}


async def confirm_node(state: AgentState) -> dict:
    ctx = state["ctx"]
    suggestion_id = ctx.pending_suggestion_id

    try:
        result = await approve_suggestion(suggestion_id)

        ctx.pending_suggestion_id = None
        ctx.pending_assignment_id = None

        from agent.session import clear_session_pending
        await clear_session_pending(ctx.session_id)

        logger.info(
            "Suggestion approved: %s results=%d", suggestion_id, len(result.results)
        )

        confirmation_msg = AIMessage(content=json.dumps({
            "suggestion_id": result.suggestion_id,
            "approved_count": len(result.results),
            "results": [
                {
                    "submissionId": r.submission_id,
                    "totalScore": r.total_score,
                    "maxScore": r.max_score,
                    "feedbackSummary": r.feedback_summary,
                }
                for r in result.results
            ],
        }))

        return {
            "messages": [confirmation_msg],
            "confirmed": True,
            "has_error": False,
            "actions_triggered": state.get("actions_triggered", []) + ["approve_suggestion"],
        }

    except Exception as e:
        logger.exception("confirm_node failed: suggestion_id=%s", suggestion_id)
        error_msg = AIMessage(content=json.dumps({
            "error": f"Failed to approve suggestion: {e}"
        }))
        return {
            "messages": [error_msg],
            "confirmed": False,
            "has_error": True,
            "actions_triggered": state.get("actions_triggered", []) + ["approve_suggestion"],
        }


async def call_llm_node(state: AgentState, llm) -> dict:
    response: AIMessage = await llm.ainvoke(state["messages"])

    logger.debug(
        "LLM response: tool_calls=%d content_len=%d",
        len(response.tool_calls) if response.tool_calls else 0,
        len(response.content) if response.content else 0,
    )

    had_prev_error = state.get("has_error", False)
    updates: dict = {"messages": [response]}
    if had_prev_error:
        updates["has_error"] = False
        updates["unexpected_error"] = False
    return updates


async def call_tool_node(state: AgentState, tool_map: dict) -> dict:
    last_message: AIMessage = state["messages"][-1]
    tool_call = last_message.tool_calls[0]

    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_id = tool_call["id"]

    tool = tool_map.get(tool_name)
    unexpected_error = False
    has_error = False

    if tool is None:
        result = {"error": f"Tool '{tool_name}' not found."}
        has_error = True
        unexpected_error = True
    else:
        try:
            raw_result = await tool.ainvoke(tool_args)
            result = raw_result if isinstance(raw_result, dict) else {"result": raw_result}
            has_error = "error" in result
        except Exception as e:
            logger.exception("Tool %s raised unexpectedly", tool_name)
            result = {"error": f"Tool {tool_name} failed: {e}"}
            has_error = True
            unexpected_error = True

    if has_error:
        logger.warning("Tool %s returned error: %s", tool_name, result.get("error"))

    tool_message = ToolMessage(
        content=json.dumps(result),
        tool_call_id=tool_id,
        name=tool_name,
    )

    triggered = state.get("actions_triggered", []) + [tool_name]

    return {
        "messages": [tool_message],
        "has_error": has_error,
        "unexpected_error": unexpected_error,
        "iteration": state["iteration"] + 1,
        "actions_triggered": triggered,
    }


def route_after_check_pending(state: AgentState) -> Literal["confirm", "call_llm"]:
    if state.get("approval_pending", False):
        return "confirm"
    return "call_llm"


def route_after_llm(state: AgentState) -> Literal["call_tool", "respond"]:
    last = state["messages"][-1]

    if not isinstance(last, AIMessage):
        return "respond"

    if state["iteration"] >= settings.agent_max_iterations:
        logger.warning("Max iterations reached (%d), forcing respond", settings.agent_max_iterations)
        return "respond"

    if not last.tool_calls:
        return "respond"

    return "call_tool"


def route_after_tool(state: AgentState) -> Literal["call_llm", "respond"]:
    if state.get("has_error") and state["iteration"] > 1:
        return "respond"

    if state["iteration"] >= settings.agent_max_iterations:
        return "respond"

    return "call_llm"


def compile_graph(ctx: ToolContext):
    tools = get_tools(ctx)
    tool_map = {t.name: t for t in tools}
    llm = _make_llm(tools)

    async def _call_llm(state: AgentState) -> dict:
        return await call_llm_node(state, llm)

    async def _call_tool(state: AgentState) -> dict:
        return await call_tool_node(state, tool_map)

    builder = StateGraph(AgentState)

    builder.add_node("check_pending", check_pending_node)
    builder.add_node("confirm", confirm_node)
    builder.add_node("call_llm", _call_llm)
    builder.add_node("call_tool", _call_tool)

    builder.add_edge(START, "check_pending")

    builder.add_conditional_edges(
        "check_pending",
        route_after_check_pending,
        {"confirm": "confirm", "call_llm": "call_llm"},
    )

    builder.add_edge("confirm", END)

    builder.add_conditional_edges(
        "call_llm",
        route_after_llm,
        {"call_tool": "call_tool", "respond": END},
    )

    builder.add_conditional_edges(
        "call_tool",
        route_after_tool,
        {"call_llm": "call_llm", "respond": END},
    )

    return builder.compile()
