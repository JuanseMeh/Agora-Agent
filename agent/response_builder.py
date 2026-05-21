"""
agent/response_builder.py

Maps the final LangGraph state to a structured AgentResponse.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from schemas.response import (
    AgentResponse,
    AlertBlock,
    CardBlock,
    ChartBlock,
    StatBlock,
    TableBlock,
    TextBlock,
)

logger = logging.getLogger(__name__)

AnyBlock = StatBlock | TableBlock | CardBlock | ChartBlock | AlertBlock | TextBlock


def _parse_block(raw: dict[str, Any]) -> AnyBlock | None:
    block_type = raw.get("type")

    try:
        if block_type == "stat":
            return StatBlock(
                label=raw["label"],
                value=raw["value"],
                delta=raw.get("delta"),
            )
        elif block_type == "table":
            return TableBlock(
                title=raw.get("title", ""),
                columns=raw.get("columns", []),
                rows=raw.get("rows", []),
            )
        elif block_type == "card":
            return CardBlock(
                title=raw.get("title", ""),
                fields=raw.get("fields", []),
            )
        elif block_type == "chart":
            return ChartBlock(
                chart_type=raw.get("chart_type", "bar"),
                title=raw.get("title", ""),
                labels=raw.get("labels", []),
                values=raw.get("values", []),
            )
        elif block_type == "alert":
            return AlertBlock(
                severity=raw.get("severity", "info"),
                message=raw.get("message", ""),
            )
        elif block_type == "text":
            return TextBlock(
                content=raw.get("content", ""),
            )
        else:
            logger.warning("Unknown block type: %r -- skipping", block_type)
            return None
    except (KeyError, TypeError) as e:
        logger.warning("Malformed block %r: %s -- skipping", raw, e)
        return None


def _parse_llm_output(content: str) -> tuple[str, list[AnyBlock], list[str]]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.debug("LLM output was not JSON, wrapping in text block")
        return (
            content[:500],
            [TextBlock(content=content)],
            [],
        )

    message = parsed.get("message", "")
    raw_blocks = parsed.get("blocks", [])
    actions = parsed.get("actions_triggered", [])

    blocks: list[AnyBlock] = []
    for raw in raw_blocks:
        block = _parse_block(raw)
        if block is not None:
            blocks.append(block)

    return message, blocks, actions


def _build_approval_response(
    session_id: str,
    content: str,
    actions_triggered: list[str],
) -> AgentResponse:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return AgentResponse(
            session_id=session_id,
            message="Grades have been approved and committed.",
            blocks=[AlertBlock(severity="info", message="Approval complete.")],
            actions_triggered=actions_triggered,
            error=None,
        )

    if "error" in data:
        return AgentResponse(
            session_id=session_id,
            message="There was a problem approving the grades.",
            blocks=[AlertBlock(severity="error", message=data["error"])],
            actions_triggered=actions_triggered,
            error=data["error"],
        )

    approved_count = data.get("approved_count", 0)
    results = data.get("results", [])

    blocks: list[AnyBlock] = [
        StatBlock(label="Grades committed", value=approved_count, delta=None),
        TableBlock(
            title="Committed grades",
            columns=["Submission ID", "Score", "Max Score", "Feedback"],
            rows=[
                [
                    r.get("submissionId", ""),
                    str(r.get("totalScore", "")),
                    str(r.get("maxScore", "")),
                    r.get("feedbackSummary", ""),
                ]
                for r in results
            ],
        ),
    ]

    return AgentResponse(
        session_id=session_id,
        message=f"Done -- {approved_count} grade(s) have been committed to the platform.",
        blocks=blocks,
        actions_triggered=actions_triggered,
        error=None,
    )


def build_response(
    session_id: str,
    final_state: dict[str, Any],
) -> AgentResponse:
    messages = final_state.get("messages", [])
    actions_triggered = final_state.get("actions_triggered", [])
    confirmed = final_state.get("confirmed", False)

    last_ai: AIMessage | None = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)),
        None,
    )

    if last_ai is None:
        return AgentResponse(
            session_id=session_id,
            message="I wasn't able to generate a response. Please try again.",
            blocks=[AlertBlock(severity="error", message="No response generated.")],
            actions_triggered=actions_triggered,
            error="No AI message in final state",
        )

    content = last_ai.content or ""

    if confirmed:
        return _build_approval_response(session_id, content, actions_triggered)

    message, blocks, llm_actions = _parse_llm_output(content)

    merged_actions = actions_triggered or llm_actions

    has_error = final_state.get("has_error", False)
    error_val: str | None = None
    if has_error and not any(
        isinstance(b, AlertBlock) and b.severity == "error" for b in blocks
    ):
        error_val = "One or more tool calls returned an error."
        blocks.append(
            AlertBlock(
                severity="error",
                message=error_val,
            )
        )

    return AgentResponse(
        session_id=session_id,
        message=message,
        blocks=blocks,
        actions_triggered=merged_actions,
        error=error_val,
    )
