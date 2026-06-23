from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Activity(BaseModel):
    name: str
    duration: str
    description: str


class RubricItem(BaseModel):
    criterion: str
    excellent: str
    good: str
    fair: str
    poor: str


class Evaluation(BaseModel):
    method: str
    criteria: str


class TopicDetail(BaseModel):
    name: str
    explanation: str
    key_points: list[str]
    examples: list[str]


class PlanData(BaseModel):
    objective: str
    topics: list[str]
    activities: list[Activity] = []
    rubric: list[RubricItem] = []
    evaluation: Evaluation | None = None
    topic_details: list[TopicDetail] = []


class GenerateClassRequest(BaseModel):
    prompt: str
    workspace_id: str | None = None


class GenerateClassResponse(BaseModel):
    id: str | None = None
    type: str = "plan"  # "plan" | "chat"
    session_id: str | None = None
    title: str
    message: str | None = None
    plan_data: PlanData | None = None


class SaveClassPlanRequest(BaseModel):
    title: str
    prompt: str
    plan_data: dict[str, Any]


class ClassPlanListItem(BaseModel):
    id: str
    title: str
    prompt: str
    created_at: str
