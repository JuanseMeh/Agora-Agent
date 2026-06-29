from __future__ import annotations

import json
import logging
import re

from config.settings import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError
from schemas.class_plan import GenerateClassResponse, PlanData

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """Respondé SOLO JSON válido, sin markdown, sin comillas simples, sin trailing commas.

Reglas ESTRICTAS:
- Usá SIEMPRE comillas dobles para keys y strings.
- NO dejes comas después del último elemento (antes de } o ]).
- NO uses comentarios.
- Respondé ÚNICAMENTE el JSON, sin explicaciones.

Si saluda o pregunta algo casual:
{"type":"chat","title":"...","message":"..."}

Si pide planificar una clase:
{"type":"plan","title":"...","plan_data":{
  "objective":"...",
  "topics":["t1","t2"],
  "topic_details":[{"name":"...","explanation":"...","key_points":["..."],"examples":["..."]}],
  "activities":[{"name":"...","duration":"...","description":"..."}],
  "rubric":[{"criterion":"...","excellent":"...","good":"...","fair":"...","poor":"..."}],
  "evaluation":{"method":"...","criteria":"..."}
}}

OBLIGATORIO: CADA topic debe tener SU topic_detail en el mismo orden."""


def _clean_json(raw: str) -> str:
    raw = raw.strip()

    # Sacar markdown code blocks
    if raw.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            raw = match.group(1).strip()

    # Extraer solo el primer objeto JSON {...} o array [...]
    first_brace = raw.find("{")
    first_bracket = raw.find("[")
    start = 0
    if first_brace >= 0 and (first_bracket < 0 or first_brace < first_bracket):
        start = first_brace
    elif first_bracket >= 0:
        start = first_bracket

    last_brace = raw.rfind("}")
    last_bracket = raw.rfind("]")
    end = len(raw)
    if last_brace >= 0 and (last_bracket < 0 or last_brace > last_bracket):
        end = last_brace + 1
    elif last_bracket >= 0:
        end = last_bracket + 1

    if start > 0 or end < len(raw):
        raw = raw[start:end]

    # Sacar comentarios (// y #)
    lines = raw.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        cleaned_lines.append(line)
    raw = "\n".join(cleaned_lines)

    # Sacar trailing commas antes de } o ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    # Agregar comas faltantes entre elementos de array en líneas adyacentes
    # }\n{ → },\n{   (objetos en array)
    raw = re.sub(r"\}(\s*\n\s*)\{", r"},\1{", raw)
    # ]\n[ → ],\n[   (arrays en array)
    raw = re.sub(r"\](\s*\n\s*)\[", r"],\1[", raw)

    # Comillas simples → dobles (solo en contextos de JSON, no dentro de strings)
    # 'key': → "key":
    raw = re.sub(r"'([^']+)'\s*:", r'"\1":', raw)
    # : 'value' → : "value"  (junto a , } ])
    raw = re.sub(r":\s*'([^']*)'(\s*[,}\]])", r':"\1"\2', raw)
    # {' → {"
    raw = re.sub(r"\{\s*'", '{"', raw)
    # '} → "}
    raw = re.sub(r"'\}", '"}', raw)

    # Python literals → JSON
    raw = raw.replace("None", "null").replace("True", "true").replace("False", "false")

    return raw


FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


async def generate_class(prompt: str) -> GenerateClassResponse:
    models_to_try = [settings.llm_model, FALLBACK_MODEL]
    last_error = ""

    for attempt, model in enumerate(models_to_try):
        try:
            return await _try_generate(prompt, model)
        except (ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            logger.warning("Attempt %d with %s failed: %s", attempt + 1, model, last_error[:200])
            continue

    raise ValueError(
        f"No se pudo generar el plan de clase después de {len(models_to_try)} intentos. "
        f"Último error: {last_error}"
    )


async def _try_generate(prompt: str, model: str) -> GenerateClassResponse:
    llm = ChatOpenAI(
        model=model,
        temperature=0.3,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=180,
    )
    messages = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    json_str = _clean_json(raw)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("Raw LLM output from %s:\n---\n%s\n---", model, raw)
        raise

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
    try:
        validated = PlanData(**plan_raw)
    except ValidationError as e:
        logger.error("PlanData validation failed with model %s:\n---\n%s\n---\nErrors: %s", model, raw, e.errors())
        raise ValueError(f"PlanData validation error: {e.errors()}") from e

    return GenerateClassResponse(
        type="plan",
        title=title,
        message=None,
        plan_data=validated,
    )


async def generate_class_stream(prompt: str):
    """Async generator that yields NDJSON events: token, result, error."""
    models_to_try = [settings.llm_model, FALLBACK_MODEL]
    last_error = ""

    for attempt, model in enumerate(models_to_try):
        try:
            async for item in _stream_generate(prompt, model):
                yield item
            return
        except (ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            logger.warning("Stream attempt %d with %s failed: %s", attempt + 1, model, last_error[:200])
            continue

    yield {"type": "error", "detail": f"Todos los modelos fallaron. Último error: {last_error}"}


async def _stream_generate(prompt: str, model: str):
    llm = ChatOpenAI(
        model=model,
        temperature=0.3,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=180,
    )
    messages = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    full_text = ""
    async for chunk in llm.astream(messages):
        content = chunk.content
        if content:
            full_text += content
            yield {"type": "token", "content": content}

    json_str = _clean_json(full_text)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("Raw LLM streaming output from %s:\n---\n%s\n---", model, full_text)
        raise

    response_type = data.get("type", "plan")
    title = data.get("title") or prompt[:80]

    if response_type == "chat":
        result = GenerateClassResponse(
            type="chat",
            title=title,
            message=data.get("message", title),
            plan_data=None,
        )
    else:
        plan_raw = data.get("plan_data", data)
        try:
            validated = PlanData(**plan_raw)
        except ValidationError as e:
            logger.error("PlanData validation failed in stream with model %s:\n---\n%s\n---\nErrors: %s", model, full_text, e.errors())
            raise ValueError(f"PlanData validation error: {e.errors()}") from e

        result = GenerateClassResponse(
            type="plan",
            title=title,
            message=None,
            plan_data=validated,
        )

    yield {"type": "result", "data": result.model_dump(mode="json")}
