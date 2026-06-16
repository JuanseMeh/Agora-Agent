"""
agent/memory.py

LangGraph-compatible memory loader.

Reads the last N messages from Postgres for a given conversation and converts
them into LangChain message objects (HumanMessage / AIMessage) that can be
injected directly into LangGraph graph state as conversation history.

N is controlled by settings.agent_memory_window.

IMPORTANT — format consistency:
The system prompt instructs the LLM that EVERY response must be a JSON object
with {message, blocks, actions_triggered}.  When loading history we reconstruct
assistant messages as JSON so the LLM sees a consistent format across turns.
Without this, the LLM sees its own previous plain-text response, which
contradicts the system prompt and can cause empty or malformed output.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config.settings import settings
from db.queries.conversations import load_message_history

logger = logging.getLogger(__name__)


def _row_to_langchain_message(row: dict[str, Any]) -> BaseMessage | None:
    role = row.get("role")
    content = row.get("content", "")
    blocks = row.get("blocks")

    if role == "user":
        return HumanMessage(content=content)
    elif role == "assistant":
        reconstructed = json.dumps(
            {
                "message": content,
                "blocks": blocks if blocks else [],
                "actions_triggered": [],
            },
            ensure_ascii=False,
        )
        return AIMessage(content=reconstructed)
    else:
        logger.warning("Unexpected role in message history: %s -- skipping", role)
        return None


async def load_conversation_history(conversation_id: str) -> list[BaseMessage]:
    rows = await load_message_history(
        conversation_id=conversation_id,
        limit=settings.agent_memory_window,
    )

    messages: list[BaseMessage] = []
    for row in rows:
        msg = _row_to_langchain_message(row)
        if msg is not None:
            messages.append(msg)

    logger.debug(
        "Loaded %d messages for conversation %s (window=%d)",
        len(messages), conversation_id, settings.agent_memory_window,
    )
    return messages


async def build_initial_state_messages(
    conversation_id: str,
    user_input: str,
) -> list[BaseMessage]:
    history = await load_conversation_history(conversation_id)
    history.append(HumanMessage(content=user_input))
    return history
