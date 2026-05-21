"""
schemas/response.py

Typed block models and the AgentResponse envelope.
Every agent response returns one of these -- never plain text.

Block types: stat . table . card . chart . alert . text
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel


class StatBlock(BaseModel):
    type: Literal["stat"] = "stat"
    label: str
    value: Any
    delta: float | None = None


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    title: str = ""
    columns: list[str] = []
    rows: list[list[Any]] = []


class CardField(BaseModel):
    label: str
    value: str


class CardBlock(BaseModel):
    type: Literal["card"] = "card"
    title: str = ""
    fields: list[CardField] = []


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"] = "bar"
    title: str = ""
    labels: list[str] = []
    values: list[float] = []


class AlertBlock(BaseModel):
    type: Literal["alert"] = "alert"
    severity: Literal["info", "warning", "error"] = "info"
    message: str = ""


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str = ""


AnyBlock = Union[StatBlock, TableBlock, CardBlock, ChartBlock, AlertBlock, TextBlock]


class AgentResponse(BaseModel):
    session_id: str
    message: str
    blocks: list[AnyBlock] = []
    actions_triggered: list[str] = []
    error: str | None = None

    model_config = {"populate_by_name": True}
