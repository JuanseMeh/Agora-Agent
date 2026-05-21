"""
agent/memory.py

LangGraph-compatible memory loader.

Reads the last N messages from Postgres for a given conversation and converts
them into LangChain message objects (HumanMessage / AIMessage) that can be
injected directly into LangGraph graph state as conversation history.

N is controlled by settings.agent_memory_window.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config.settings import settings
from db.queries.conversations import load_message_history

logger = logging.getLogger(__name__)


def _row_to_langchain_message(row: dict[str, Any]) -> BaseMessage | None:
    role = row.get("role")
    content = row.get("content", "")

    if role == "user":
        return HumanMessage(content=content)
    elif role == "assistant":
        return AIMessage(content=content)
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
