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


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


async def generate_class(prompt: str) -> GenerateClassResponse:
    models_to_try = [settings.llm_model, FALLBACK_MODEL]
    last_error = ""

    for attempt, model in enumerate(models_to_try):
        try:
            return await _try_generate(prompt, model)
        except (ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            logger.warning("Attempt %d with %s failed: %s", attempt + 1, model, last_error[:100])
            continue

    raise ValueError(f"No se pudo generar el plan de clase después de {len(models_to_try)} intentos. {last_error}")


async def _try_generate(prompt: str, model: str) -> GenerateClassResponse:
    llm = ChatOpenAI(
        model=model,
        temperature=0.3,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=180,
        max_retries=1,
    )
    messages = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    json_str = _extract_json(raw)
    data = json.loads(json_str)

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
