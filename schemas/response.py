
from typing import Literal, Union
from pydantic import BaseModel

class TextBlock(BaseModel):
    type: Literal["text"]
    content: str

class TableBlock(BaseModel):
    type: Literal["table"]
    title: str
    columns: list[str]
    rows: list[list[str]]

class CardBlock(BaseModel):
    type: Literal["card"]
    title: str
    subtitle: str | None
    fields: dict[str, str]
    actions: list[str] | None   # e.g. ["view_submission", "trigger_grading"]

class ChartBlock(BaseModel):
    type: Literal["chart"]
    chart_type: Literal["bar", "line", "pie", "radar"]
    title: str
    labels: list[str]
    datasets: list[dict]

class StatBlock(BaseModel):
    type: Literal["stat"]
    label: str
    value: str | int | float
    delta: str | None           # e.g. "+12% vs last week"
    color: Literal["default", "success", "warning", "danger"] | None

class AlertBlock(BaseModel):
    type: Literal["alert"]
    level: Literal["info", "warning", "error", "success"]
    message: str

# The envelope — every agent response is this
class AgentResponse(BaseModel):
    session_id: str
    message: str                # short human-readable summary
    blocks: list[Union[
        TextBlock, TableBlock, CardBlock,
        ChartBlock, StatBlock, AlertBlock
    ]]
    actions_triggered: list[str]   # audit trail of what tools fired
    error: str | None
