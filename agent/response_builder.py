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
    GradingBlock,
    GradingResultItem,
    CriterionResult,
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
    # Strip tab-delimited raw data only when blocks are also present (redundant)
    if raw_blocks:
        message = "\n".join(
            line for line in message.split("\n") if "\t" not in line
        ).strip()
    actions = parsed.get("actions_triggered", [])

    blocks: list[AnyBlock] = []
    for raw in raw_blocks:
        block = _parse_block(raw)
        if block is not None:
            blocks.append(block)

    if not message.strip():
        for b in blocks:
            if isinstance(b, TextBlock) and b.content.strip():
                message = b.content
                break

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


_COLUMN_LABELS = {
    "id": "ID", "name": "Nombre", "title": "Nombre",
    "description": "Descripción", "role": "Rol", "email": "Correo",
    "dueDate": "Fecha límite", "maxScore": "Puntaje máx",
    "status": "Estado",
}

_HIDDEN_KEYS = {"id", "avatarUrl", "accentColor"}


def _auto_blocks_from_tool_result(result: dict, tool_name: str) -> list[AnyBlock]:
    if "workspaces" in result:
        items = result["workspaces"]
        if isinstance(items, list) and items:
            keys = [k for k in list(items[0].keys()) if k not in _HIDDEN_KEYS]
            columns = [_COLUMN_LABELS.get(k, k) for k in keys]
            rows = [[str(item.get(k, "")) for k in keys] for item in items]
            return [TableBlock(title="Espacios de trabajo", columns=columns, rows=rows)]

    if "assignments" in result:
        items = result["assignments"]
        if isinstance(items, list) and items:
            keys = [k for k in list(items[0].keys()) if k not in _HIDDEN_KEYS]
            columns = [_COLUMN_LABELS.get(k, k) for k in keys]
            rows = [[str(item.get(k, "")) for k in keys] for item in items]
            return [TableBlock(title="Tareas", columns=columns, rows=rows)]

    if "members" in result:
        items = result["members"]
        if isinstance(items, list) and items:
            keys = [k for k in list(items[0].keys()) if k not in _HIDDEN_KEYS]
            columns = [_COLUMN_LABELS.get(k, k) for k in keys]
            rows = [[str(item.get(k, "")) for k in keys] for item in items]
            return [TableBlock(title="Miembros", columns=columns, rows=rows)]

    return []


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

    # Validate that LLM-claimed tool calls actually happened
    # The LLM may fabricate actions_triggered and data blocks without calling any tool.
    actual_tool_names = {
        msg.name for msg in messages
        if msg.type == "tool" and hasattr(msg, "name")
    }
    for claimed_tool in (llm_actions or []):
        if claimed_tool not in actual_tool_names:
            logger.warning(
                "LLM claimed tool %r was called but no ToolMessage found. "
                "Clearing fabricated blocks and message.",
                claimed_tool,
            )
            message = "Ocurrió un error al obtener los datos. Por favor, intentá de nuevo."
            blocks = [AlertBlock(severity="error", message="No se pudieron obtener los datos reales. Intentá de nuevo.")]
            merged_actions = [a for a in merged_actions if a != claimed_tool]
            break

    # Auto-generate data blocks from tool results when LLM didn't include them
    if not any(not isinstance(b, TextBlock) for b in blocks):
        for tool_msg in reversed(messages):
            if tool_msg.type == "tool" and tool_msg.content:
                try:
                    result = json.loads(tool_msg.content)
                    if "error" in result:
                        continue
                    data_blocks = _auto_blocks_from_tool_result(result, tool_msg.name or "")
                    if data_blocks:
                        blocks = data_blocks
                        break
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

    # Correct stat blocks with actual tool result data
    # The LLM sometimes hallucinates stat values (e.g. "Tareas: 0" when there is 1).
    # Scan tool results for basic_workspace_report and list_workspace_members,
    # then fix any matching stat blocks with real values.
    stat_corrections: dict[str, int | str] = {}
    for tool_msg in messages:
        if tool_msg.type == "tool" and tool_msg.content:
            try:
                result = json.loads(tool_msg.content)
                if "totalAssignments" in result:
                    stat_corrections["Tareas"] = result["totalAssignments"]
                if "gradedSubmissions" in result:
                    stat_corrections["Calificadas"] = result["gradedSubmissions"]
                if "pendingSubmissions" in result:
                    stat_corrections["Por calificar"] = result["pendingSubmissions"]
                if "averageScore" in result and result["averageScore"] is not None:
                    stat_corrections["Promedio"] = result["averageScore"]
                if "members" in result and isinstance(result["members"], list):
                    student_count = sum(
                        1 for m in result["members"]
                        if m.get("role", "").upper() in ("STUDENT", "ALUMNO")
                    )
                    stat_corrections["Estudiantes"] = student_count
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    if stat_corrections:
        for block in blocks:
            if isinstance(block, StatBlock):
                label_key = block.label
                if label_key in stat_corrections and block.value != stat_corrections[label_key]:
                    logger.info(
                        "Correcting stat block %r from %r to %r",
                        label_key, block.value, stat_corrections[label_key],
                    )
                    block.value = stat_corrections[label_key]

    # Inject GradingBlock when suggest_grades was triggered
    if "suggest_grades" in merged_actions:
        for tool_msg in reversed(messages):
            if tool_msg.type == "tool" and tool_msg.name == "suggest_grades" and tool_msg.content:
                try:
                    tool_result = json.loads(tool_msg.content)
                    if "suggestion_id" in tool_result and "results" in tool_result:
                        blocks.append(
                            GradingBlock(
                                suggestion_id=tool_result["suggestion_id"],
                                assignment_id=tool_result.get("assignment_id", ""),
                                results=[
                                    GradingResultItem(
                                        submission_id=r.get("submissionId", r.get("submission_id", "")),
                                        total_score=r.get("totalScore", r.get("total_score", 0)),
                                        max_score=r.get("maxScore", r.get("max_score", 0)),
                                        feedback_summary=r.get("feedbackSummary", r.get("feedback_summary", "")),
                                        grading_model=r.get("gradingModel", r.get("grading_model", "")),
                                        evaluated_at=r.get("evaluatedAt", r.get("evaluated_at", "")),
                                        criteria_results=[
                                            CriterionResult(
                                                criterion_id=c.get("criterionId", c.get("criterion_id", "")),
                                                criterion_name=c.get("criterionName", c.get("criterion_name", "")),
                                                score=c.get("score", 0),
                                                max_score=c.get("maxScore", c.get("max_score", 0)),
                                                feedback=c.get("feedback", ""),
                                                matched_level=c.get("matchedLevel", c.get("matched_level", "")),
                                            )
                                            for c in r.get("criteriaResults", r.get("criteria_results", []))
                                        ],
                                    )
                                    for r in tool_result["results"]
                                ],
                            )
                        )
                except (json.JSONDecodeError, TypeError, ValueError):
                    logger.warning("Failed to parse suggest_grades tool result for GradingBlock")
                break

    unexpected_error = final_state.get("unexpected_error", False)
    error_val: str | None = None
    if unexpected_error and not any(
        isinstance(b, AlertBlock) and b.severity == "error" for b in blocks
    ):
        error_val = "One or more tool calls returned an error."
        blocks.append(
            AlertBlock(
                severity="error",
                message=error_val,
            )
        )

    if not message.strip() and not any(
        isinstance(b, AlertBlock) and b.severity == "error" for b in blocks
    ):
        logger.warning("Empty response after parsing LLM output — session=%s", session_id)
        message = "No pude generar una respuesta. ¿Podrías reformular tu consulta?"
        blocks = [
            AlertBlock(
                severity="info",
                message="Intenta ser más específico o reformula tu pregunta.",
            )
        ]
        if not error_val:
            error_val = "Empty LLM response content"

    return AgentResponse(
        session_id=session_id,
        message=message,
        blocks=blocks,
        actions_triggered=merged_actions,
        error=error_val,
    )
