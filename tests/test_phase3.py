"""Verify Phase 3 (Session & Memory) modules import cleanly."""

import pytest


class TestSession:
    def test_import(self):
        from agent.session import (
            SessionData, SessionExpiredError, SessionNotFoundError,
            create_session, load_session, refresh_session,
            update_session_workspace, get_or_create_session,
        )
        assert issubclass(SessionExpiredError, Exception)
        assert issubclass(SessionNotFoundError, Exception)
        assert callable(get_or_create_session)

    def test_session_expired_error(self):
        from agent.session import SessionExpiredError
        err = SessionExpiredError("abc-123")
        assert err.session_id == "abc-123"
        assert "abc-123" in str(err)

    def test_session_not_found_error(self):
        from agent.session import SessionNotFoundError
        err = SessionNotFoundError("abc-123")
        assert err.session_id == "abc-123"

    def test_session_key_format(self):
        from agent.session import _session_key
        assert _session_key("x") == "session:x"


class TestMemory:
    def test_import(self):
        from agent.memory import (
            load_conversation_history, build_initial_state_messages,
        )
        assert callable(load_conversation_history)
        assert callable(build_initial_state_messages)

    def test_row_to_langchain_message_user(self):
        from agent.memory import _row_to_langchain_message
        from langchain_core.messages import HumanMessage

        msg = _row_to_langchain_message({"role": "user", "content": "hello"})
        assert isinstance(msg, HumanMessage)
        assert msg.content == "hello"

    def test_row_to_langchain_message_assistant(self):
        from agent.memory import _row_to_langchain_message
        from langchain_core.messages import AIMessage

        msg = _row_to_langchain_message({"role": "assistant", "content": "hi there"})
        assert isinstance(msg, AIMessage)
        assert msg.content == "hi there"

    def test_row_to_langchain_message_unknown_role(self):
        from agent.memory import _row_to_langchain_message

        msg = _row_to_langchain_message({"role": "system", "content": "beep"})
        assert msg is None


class TestConversationsQueries:
    def test_functions_import(self):
        from db.queries.conversations import (
            create_conversation, get_conversation_by_id,
            touch_conversation, append_message, load_message_history,
        )
        assert callable(create_conversation)
        assert callable(append_message)
