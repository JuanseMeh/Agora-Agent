from __future__ import annotations

import json
import logging
import re

from config.settings import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.class_plan import GenerateClassResponse, PlanData, TopicDetail

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """Respondé SOLO JSON, sin markdown.
- Si saluda o pregunta algo casual: {"type":"chat","title":"...","message":"..."}
- Si pide planificar una clase: {"type":"plan","title":"...","plan_data":{
  "objective":"...",
  "topics":["t1","t2"],
  "topic_details":[{"name":"...","explanation":"...","key_points":["..."],"examples":["..."]}],
  "activities":[{"name":"...","duration":"...","description":"..."}],
  "rubric":[{"criterion":"...","excellent":"...","good":"...","fair":"...","poor":"..."}],
  "evaluation":{"method":"...","criteria":"..."}
}}
OBLIGATORIO: CADA topic debe tener SU topic_detail. Sin markdown."""


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=120,
        max_retries=2,
    )


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


async def generate_class(prompt: str) -> GenerateClassResponse:
    llm = _make_llm()
    messages = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON (len=%d): %s", len(raw), raw[:300])
        raise ValueError("No se pudo generar el plan de clase. Intenta de nuevo con más detalles.")

    response_type = data.get("type", "plan")
    title = data.get("title") or prompt[:80]

    if response_type == "chat":
        return GenerateClassResponse(
            type="chat",
            title=title,
            message=data.get("message", title),
            plan_data=None,
        )

    plan_raw = data.get("plan_data", data)
    validated = PlanData(**plan_raw)

    return GenerateClassResponse(
        type="plan",
        title=title,
        message=None,
        plan_data=validated,
    )
