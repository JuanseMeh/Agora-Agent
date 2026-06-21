from __future__ import annotations

import json
import logging
import re

from config.settings import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from schemas.class_plan import GenerateClassResponse, PlanData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un asistente docente experto en planificación de clases.
Genera un plan de clase estructurado en JSON con el siguiente schema:
{
  "title": "string (título de la clase)",
  "plan_data": {
    "objective": "string (objetivo general de la clase)",
    "topics": ["string (lista de temas a cubrir)"],
    "activities": [
      {
        "name": "string (nombre de la actividad)",
        "duration": "string (duración estimada, ej: '15 min')",
        "description": "string (descripción detallada de la actividad)"
      }
    ],
    "rubric": [
      {
        "criterion": "string (criterio de evaluación)",
        "excellent": "string (descripción nivel excelente)",
        "good": "string (descripción nivel bueno)",
        "fair": "string (descripción nivel suficiente)",
        "poor": "string (descripción nivel insuficiente)"
      }
    ],
    "evaluation": {
      "method": "string (método de evaluación, ej: 'Sumativa' o 'Formativa')",
      "criteria": "string (criterios generales de evaluación)"
    }
  }
}
Responde ÚNICAMENTE con el JSON, sin texto adicional ni markdown."""


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
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
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON: %s", raw[:500])
        raise ValueError("No se pudo generar el plan de clase. Intenta de nuevo con más detalles.")

    if "title" not in data or "plan_data" not in data:
        if "objective" in data and "title" not in data:
            data = {"title": prompt[:80], "plan_data": data}

    plan_data = data.get("plan_data", data)
    title = data.get("title") or prompt[:80]

    validated = PlanData(**plan_data)

    return GenerateClassResponse(
        title=title,
        plan_data=validated,
    )
