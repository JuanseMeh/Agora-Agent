"""Verify Phase 5 (Agent Core) modules import and wire correctly."""

import json


class TestPrompt:
    def test_system_prompt_exists(self):
        from agent.prompt import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 500
        assert "Agora" in SYSTEM_PROMPT
        assert "suggest -> approve" in SYSTEM_PROMPT


class TestResponseSchemas:
    def test_stat_block(self):
        from schemas.response import StatBlock
        s = StatBlock(label="Test", value=42)
        assert s.type == "stat"
        assert s.value == 42

    def test_table_block(self):
        from schemas.response import TableBlock
        t = TableBlock(title="Scores", columns=["Name", "Score"], rows=[["Alice", "95"]])
        assert t.type == "table"

    def test_card_block_with_fields(self):
        from schemas.response import CardBlock, CardField
        c = CardBlock(title="Student", fields=[CardField(label="Name", value="Alice")])
        assert c.type == "card"
        assert c.fields[0].value == "Alice"

    def test_chart_block(self):
        from schemas.response import ChartBlock
        c = ChartBlock(chart_type="bar", title="Distribution", labels=["A", "B"], values=[10, 20])
        assert c.type == "chart"
        assert c.values == [10.0, 20.0]

    def test_alert_block(self):
        from schemas.response import AlertBlock
        a = AlertBlock(severity="error", message="boom")
        assert a.type == "alert"

    def test_text_block(self):
        from schemas.response import TextBlock
        t = TextBlock(content="hello")
        assert t.content == "hello"

    def test_agent_response(self):
        from schemas.response import AgentResponse, TextBlock
        resp = AgentResponse(
            session_id="s1",
            message="hi",
            blocks=[TextBlock(content="hello")],
            actions_triggered=["tool_a"],
            error=None,
        )
        assert resp.session_id == "s1"
        assert len(resp.blocks) == 1


class TestResponseBuilder:
    def test_parse_llm_json_output(self):
        from agent.response_builder import _parse_llm_output

        content = json.dumps({
            "message": "Found 3 submissions",
            "blocks": [
                {"type": "stat", "label": "Total", "value": 3},
                {"type": "table", "title": "Submissions", "columns": ["ID"], "rows": [["1"]]},
            ],
            "actions_triggered": ["list_submissions_for_assignment"],
        })
        msg, blocks, actions = _parse_llm_output(content)
        assert msg == "Found 3 submissions"
        assert len(blocks) == 2
        assert blocks[0].type == "stat"
        assert blocks[1].type == "table"
        assert "list_submissions_for_assignment" in actions

    def test_parse_llm_plain_text(self):
        from agent.response_builder import _parse_llm_output

        msg, blocks, actions = _parse_llm_output("Hello, this is plain text")
        assert msg == "Hello, this is plain text"
        assert len(blocks) == 1
        assert blocks[0].type == "text"

    def test_parse_llm_strips_markdown_fence(self):
        from agent.response_builder import _parse_llm_output

        content = "```\n{\"message\": \"hi\", \"blocks\": [], \"actions_triggered\": []}\n```"
        msg, blocks, actions = _parse_llm_output(content)
        assert msg == "hi"

    def test_parse_block_unknown_type(self):
        from agent.response_builder import _parse_block
        assert _parse_block({"type": "unknown"}) is None

    def test_parse_block_malformed(self):
        from agent.response_builder import _parse_block
        assert _parse_block({"type": "stat"}) is None  # missing required fields

    def test_build_approval_response(self):
        from agent.response_builder import _build_approval_response

        content = json.dumps({
            "suggestion_id": "sid-1",
            "approved_count": 2,
            "results": [
                {"submissionId": "s1", "totalScore": 85, "maxScore": 100, "feedbackSummary": "good"},
                {"submissionId": "s2", "totalScore": 90, "maxScore": 100, "feedbackSummary": "great"},
            ],
        })
        resp = _build_approval_response("session-1", content, ["approve_suggestion"])
        assert resp.session_id == "session-1"
        assert "2" in resp.message
        assert len(resp.blocks) == 2

    def test_build_approval_response_error(self):
        from agent.response_builder import _build_approval_response

        content = json.dumps({"error": "orchestrator unreachable"})
        resp = _build_approval_response("session-1", content, ["approve_suggestion"])
        assert resp.error == "orchestrator unreachable"


class TestAgentCore:
    def test_run_function_signature(self):
        from agent.core import run
        import inspect
        sig = inspect.signature(run)
        params = list(sig.parameters.keys())
        assert params == ["user_input", "session"]
