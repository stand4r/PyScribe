"""Tests for the agent harness: the tool loop, retries and limits.

The old agent gave up after ``MAX_TOOL_ROUNDS = 6`` rounds and cut every tool
result at 8000 characters — reading a few files exhausted the budget and the
answer stopped half-way. These tests pin the new behaviour.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_service import AIError, AIService, ToolCall  # noqa: E402
from services.agent_harness import (SAME_CALL_LIMIT, AgentHarness,  # noqa: E402
                                    AgentResult)


class ScriptedService:
    """Minimal stand-in for AIService used by the harness."""

    is_anthropic = False
    truncated = False

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.last_usage = {}
        self.requests = 0
        self.seen = []

    def _openai_tool_round(self, messages, tools, on_text, on_reasoning=None):
        self.requests += 1
        self.seen.append([dict(message) for message in messages])
        if not self.rounds:
            return "конец", []
        text, calls = self.rounds.pop(0)
        self.last_usage = {"prompt_tokens": 10, "completion_tokens": 5}
        if text and on_text:
            on_text(text)
        return text, calls

    def _continue_prompt(self):
        return "продолжи"

    def _stream_until_complete(self, messages, on_text=None, on_reasoning=None):
        return ""


def _user_messages():
    return [{"role": "user", "content": "сделай задачу"}]


def test_harness_runs_far_beyond_the_old_round_limit():
    rounds = [("", [ToolCall(f"call_{i}", "read_file", {"path": f"f{i}.py"})])
              for i in range(10)]
    rounds.append(("Готово", []))
    service = ScriptedService(rounds)
    executed = []

    def runner(name, args):
        executed.append(args["path"])
        return "x = 1\n"

    result = AgentHarness(service, tools=[{"type": "function"}], tool_runner=runner).run(
        _user_messages())
    assert result.text.endswith("Готово")
    assert result.rounds == 11, result.rounds
    assert len(executed) == 10, executed
    assert result.stop_reason == "answer"


def test_tool_results_are_passed_back_whole():
    payload = "A" * 25_000
    service = ScriptedService([
        ("", [ToolCall("c1", "read_file", {"path": "big.py"})]),
        ("Готово", []),
    ])
    harness = AgentHarness(service, tools=[{}], tool_runner=lambda name, args: payload)
    result = harness.run(_user_messages())
    tool_messages = [message for message in result.messages if message.get("role") == "tool"]
    assert tool_messages, "tool result must be appended to the conversation"
    assert len(tool_messages[0]["content"]) == len(payload), len(tool_messages[0]["content"])


def test_repeated_identical_calls_do_not_loop_forever():
    rounds = [("", [ToolCall("c", "read_file", {"path": "same.py"})]) for _ in range(6)]
    rounds.append(("Хватит", []))
    service = ScriptedService(rounds)
    executed = []

    def runner(name, args):
        executed.append(name)
        return "файл прочитан"

    result = AgentHarness(service, tools=[{}], tool_runner=runner).run(_user_messages())
    assert len(executed) == SAME_CALL_LIMIT, executed
    joined = "\n".join(str(message.get("content")) for message in result.messages)
    assert "повторно" in joined.lower() or "повтор" in joined.lower()
    assert result.text.endswith("Хватит")


def test_narration_before_tools_is_not_part_of_the_answer():
    """«Читаю файл…» before a tool call must not leak into the final answer."""
    service = ScriptedService([
        ("Читаю файл и проверяю.", [ToolCall("c1", "read_file", {"path": "a.py"})]),
        ("Файл исправлен. Проверка: pytest.", []),
    ])
    result = AgentHarness(service, tools=[{}], tool_runner=lambda n, a: "x").run(
        _user_messages())
    assert result.text == "Файл исправлен. Проверка: pytest.", result.text
    assert "Читаю файл" not in result.text


def test_usage_is_summed_across_rounds():
    rounds = [("", [ToolCall("c", "read_file", {"path": f"{i}.py"})]) for i in range(4)]
    rounds.append(("ok", []))
    result = AgentHarness(ScriptedService(rounds), tools=[{}],
                          tool_runner=lambda name, args: "y").run(_user_messages())
    # 4 tool rounds + the final answer round: every request reports 10/5.
    assert result.usage.get("prompt_tokens") == 50, result.usage
    assert result.usage.get("completion_tokens") == 25, result.usage


def test_stop_request_ends_the_run_before_new_tools():
    service = ScriptedService([
        ("", [ToolCall("c1", "read_file", {"path": "a.py"})]),
        ("не должно случиться", []),
    ])
    executed = []
    harness = AgentHarness(service, tools=[{}],
                           tool_runner=lambda name, args: executed.append(name) or "x",
                           should_stop=lambda: True)
    result = harness.run(_user_messages())
    assert result.stop_reason == "stopped"
    assert executed == []


def test_transient_error_is_retried():
    class FlakyService(ScriptedService):
        def _openai_tool_round(self, messages, tools, on_text, on_reasoning=None):
            self.requests += 1
            if self.requests == 1:
                raise AIError("Слишком много запросов (429)", status=429)
            return "после повтора", []

    class FastHarness(AgentHarness):
        def _sleep(self, seconds):
            return None

    service = FlakyService([])
    result = FastHarness(service).run(_user_messages())
    assert result.text == "после повтора"
    assert service.requests == 2


def test_non_retryable_error_propagates():
    class Broken(ScriptedService):
        def _openai_tool_round(self, messages, tools, on_text, on_reasoning=None):
            raise AIError("Неверный ключ (401)", status=401)

    try:
        AgentHarness(Broken([])).run(_user_messages())
    except AIError as exc:
        assert getattr(exc, "status", None) == 401
    else:
        raise AssertionError("AIError was expected")


# ----------------------------------------------------------------------
# Request payload: no hard token cap, reasoning switch
# ----------------------------------------------------------------------
def _service(**extra):
    config = {"ai_enabled": True, "ai_provider": "deepseek",
              "ai_base_url": "https://api.deepseek.com",
              "ai_model": "deepseek-flash",
              "ai_api_key": "sk-" + "a" * 32}
    config.update(extra)
    return AIService(config=config)


def test_no_max_tokens_by_default():
    payload = _service()._payload([{"role": "user", "content": "hi"}], stream=True)
    assert "max_tokens" not in payload
    assert "reasoning_effort" not in payload


def test_explicit_budget_is_sent_only_when_larger_than_legacy_default():
    assert "max_tokens" not in _service(ai_max_tokens=8192)._payload(
        [{"role": "user", "content": "hi"}], stream=True)
    assert _service(ai_max_tokens=20000)._payload(
        [{"role": "user", "content": "hi"}], stream=True)["max_tokens"] == 20000


def test_reasoning_effort_mapping():
    payload = _service(ai_reasoning_effort="high")._payload(
        [{"role": "user", "content": "hi"}], stream=True)
    assert payload["reasoning_effort"] == "high"
    assert "reasoning_effort" not in _service(ai_reasoning_effort="none")._payload(
        [{"role": "user", "content": "hi"}], stream=True)


def test_anthropic_reasoning_and_prompt_cache():
    service = AIService(config={"ai_enabled": True, "ai_provider": "anthropic",
                                "ai_base_url": "https://api.anthropic.com/v1",
                                "ai_model": "claude-sonnet-4-5",
                                "ai_api_key": "sk-ant-" + "b" * 32,
                                "ai_reasoning_effort": "medium"})
    payload = service._payload([{"role": "system", "content": "sys"},
                                {"role": "user", "content": "hi"}], stream=True)
    assert payload["max_tokens"] >= 16000
    assert payload["thinking"]["type"] == "enabled"
    assert payload["thinking"]["budget_tokens"] == 8192
    assert isinstance(payload["system"], list)
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_rejected_reasoning_parameter_is_stripped_and_retried():
    service = _service(ai_reasoning_effort="high")
    payloads = []

    def fake_post(path, payload):
        payloads.append(payload)
        if len(payloads) == 1:
            raise AIError("unknown field: reasoning_effort", status=400)
        return {"choices": [{"message": {"content": "OK"}}]}

    service._post_json_once = fake_post
    answer = service.complete("привет")
    assert answer == "OK"
    assert "reasoning_effort" in payloads[0]
    assert "reasoning_effort" not in payloads[1]
    assert service._reasoning_unsupported is True


# ----------------------------------------------------------------------
# Context: no truncation, caching
# ----------------------------------------------------------------------
def test_context_block_is_not_truncated():
    code = "x = 1\n" * 40_000          # ~240k characters
    block = AIService.build_context_block(file_path="a.py", code=code)
    assert len(block) > 200_000
    assert "файл обрезан" not in block


def test_context_cache_reuses_unchanged_files():
    from services.ai_context import ContextCache
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "app.py"
        path.write_text("print(1)\n", encoding="utf-8")
        cache = ContextCache()
        first = cache.read(path)
        second = cache.read(path)
        assert first == second == "print(1)\n"
        assert cache.stats()["hits"] == 1
        assert cache.stats()["misses"] == 1
        time.sleep(0.01)
        path.write_text("print(2)\n", encoding="utf-8")
        assert cache.read(path) == "print(2)\n"
        assert cache.stats()["misses"] == 2


# ----------------------------------------------------------------------
# Project tools: no budget on reads, pagination
# ----------------------------------------------------------------------
def test_read_file_has_no_character_budget_and_supports_paging():
    from services.agent_tools import LocalToolbox
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        body = "\n".join(f"line {i}" for i in range(1, 501))
        (root / "big.py").write_text(body, encoding="utf-8")
        box = LocalToolbox(str(root))
        whole = box.read_file("big.py")
        assert whole == body, "read_file must not cut the file"
        page = box.read_file("big.py", offset=10, limit=5)
        assert "строки 10–14" in page
        assert page.splitlines()[1] == "line 10"


TESTS = [
    test_harness_runs_far_beyond_the_old_round_limit,
    test_tool_results_are_passed_back_whole,
    test_narration_before_tools_is_not_part_of_the_answer,
    test_repeated_identical_calls_do_not_loop_forever,
    test_usage_is_summed_across_rounds,
    test_stop_request_ends_the_run_before_new_tools,
    test_transient_error_is_retried,
    test_non_retryable_error_propagates,
    test_no_max_tokens_by_default,
    test_explicit_budget_is_sent_only_when_larger_than_legacy_default,
    test_reasoning_effort_mapping,
    test_anthropic_reasoning_and_prompt_cache,
    test_rejected_reasoning_parameter_is_stripped_and_retried,
    test_context_block_is_not_truncated,
    test_context_cache_reuses_unchanged_files,
    test_read_file_has_no_character_budget_and_supports_paging,
]


def main():
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {test.__name__}: {exc!r}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
