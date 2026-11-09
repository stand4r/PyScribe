"""PyScribe agent harness: the multi-round tool loop.

This is the piece that turns a chat model into a working coding agent:

* the loop keeps going until the model produces a final answer — there is no
  low round limit any more (the old ``MAX_TOOL_ROUNDS = 6`` is exactly why the
  agent "read a few files and stopped mid-way");
* tool results are passed back in full (the old code cut every result at 8000
  characters, so the model never saw the rest of a file and re-read it until
  the round budget ran out);
* repeated identical tool calls are detected: the result is reused and the
  model is told to move on instead of looping forever;
* transient provider errors (429/5xx/network) are retried with backoff;
* token usage is accumulated over all rounds and reported once;
* the user can abort at any moment (``should_stop``) between rounds and calls.

The class deliberately knows nothing about Qt: the panel passes plain callbacks
and receives a plain :class:`AgentResult`, which keeps it testable.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from services.ai_service import AIError, AIService, ToolCall

__all__ = ["AgentHarness", "AgentResult", "AgentUsage", "ToolRun"]

# A pathological model could keep calling tools forever; this is a fuse, not a
# policy. Normal work (dozens of file reads and edits) fits easily.
SAFETY_MAX_ROUNDS = 200

# A single tool result is copied into the transcript as-is. The limit only
# protects the process from a runaway command dumping gigabytes.
MAX_TOOL_RESULT_CHARS = 2_000_000

# How many identical (tool, arguments) calls are allowed before the harness
# answers with the cached result and asks the model to continue.
SAME_CALL_LIMIT = 3

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRY_ATTEMPTS = 4
RETRY_DELAYS = (0.8, 1.8, 4.0)

USAGE_KEYS = (
    "prompt_tokens", "completion_tokens", "total_tokens",
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
    "reasoning_tokens",
)


@dataclass
class AgentUsage:
    """Token usage summed over every request of one answer."""

    values: Dict[str, int] = field(default_factory=dict)

    def add(self, usage: Optional[Dict[str, Any]]) -> None:
        if not isinstance(usage, dict):
            return
        for key in USAGE_KEYS:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                self.values[key] = int(self.values.get(key, 0)) + int(value)
        # OpenAI nests reasoning tokens in completion_tokens_details.
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict) and isinstance(details.get("reasoning_tokens"), int):
            self.values["reasoning_tokens"] = (self.values.get("reasoning_tokens", 0)
                                               + details["reasoning_tokens"])

    def as_dict(self) -> Dict[str, int]:
        return dict(self.values)

    @property
    def empty(self) -> bool:
        return not self.values


@dataclass
class ToolRun:
    """One executed tool call, for the UI and for the transcript."""

    name: str
    arguments: Dict[str, Any]
    output: str
    ok: bool = True
    duration_ms: int = 0
    repeated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "arguments": self.arguments, "ok": self.ok,
                "duration_ms": self.duration_ms, "repeated": self.repeated,
                "output_chars": len(self.output or "")}


@dataclass
class AgentResult:
    text: str
    messages: List[Dict[str, Any]]
    usage: Dict[str, int]
    rounds: int
    tool_runs: List[ToolRun] = field(default_factory=list)
    stop_reason: str = "answer"  # answer | stopped | empty
    truncated: bool = False


class AgentHarness:
    """Run a tool-using conversation turn to completion."""

    def __init__(
        self,
        service: AIService,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_runner: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        *,
        max_rounds: Optional[int] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_end: Optional[Callable[[ToolRun], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        tool_result_limit: int = MAX_TOOL_RESULT_CHARS,
    ):
        self.service = service
        self.tools = list(tools or [])
        self.tool_runner = tool_runner
        self.max_rounds = max_rounds
        self.on_text = on_text
        self.on_reasoning = on_reasoning
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.should_stop = should_stop or (lambda: False)
        self.tool_result_limit = int(tool_result_limit)

    # ------------------------------------------------------------------
    def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        messages = list(messages)
        usage = AgentUsage()
        runs: List[ToolRun] = []
        seen_calls: Dict[str, int] = {}
        rounds = 0
        stop_reason = "answer"
        # Text said *before* a tool call is narration ("читаю файл, проверяю…"),
        # not part of the answer: joining it with the final text produced fused,
        # unreadable paragraphs and looked like reasoning left in the chat.
        narration = ""
        answer = ""

        while True:
            if self.should_stop():
                stop_reason = "stopped"
                break
            rounds += 1
            if rounds > SAFETY_MAX_ROUNDS:
                stop_reason = "limit"
                break
            if self.max_rounds is not None and rounds > self.max_rounds:
                stop_reason = "limit"
                break

            text, calls = self._one_round(messages, usage)
            if self.should_stop():
                narration = text or narration
                stop_reason = "stopped"
                break

            if not calls:
                answer = text or narration
                if self.service.truncated:
                    answer = self._join(answer,
                                        self._extend_truncated(messages, answer))
                stop_reason = "answer"
                break

            if text.strip():
                narration = text
            messages = self._append_assistant_turn(messages, text, calls)
            for call in calls:
                self._handle_call(messages, call, runs, seen_calls)

        if stop_reason == "stopped":
            answer = narration
        if not answer.strip() and stop_reason == "answer":
            stop_reason = "empty"
        return AgentResult(
            text=answer,
            messages=messages,
            usage=usage.as_dict(),
            rounds=rounds,
            tool_runs=runs,
            stop_reason=stop_reason,
            truncated=bool(self.service.truncated),
        )

    @staticmethod
    def _join(first: str, second: str) -> str:
        """Join an auto-continued answer with the text it continues."""
        first = (first or "").rstrip()
        second = (second or "").lstrip()
        if not first:
            return second
        if not second:
            return first
        return first + " " + second

    # ------------------------------------------------------------------
    # One request + transient-error retries
    # ------------------------------------------------------------------
    def _one_round(self, messages: List[Dict[str, Any]],
                   usage: AgentUsage) -> tuple[str, List[ToolCall]]:
        last_error: Optional[Exception] = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                if self.service.is_anthropic:
                    blocks, calls = self.service._anthropic_tool_round(
                        messages, self.tools, self._text_callback, self._reasoning_callback)
                    usage.add(self.service.last_usage)
                    text = "".join(
                        str(block.get("text") or "")
                        for block in blocks
                        if isinstance(block, dict) and block.get("type") == "text")
                    if calls:
                        # Keep the assistant turn (text + tool_use) for the next round.
                        self._pending_blocks = blocks
                    return text, calls
                text, calls = self.service._openai_tool_round(
                    messages, self.tools, self._text_callback, self._reasoning_callback)
                usage.add(self.service.last_usage)
                return text, calls
            except AIError as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt >= RETRY_ATTEMPTS - 1:
                    raise
                self._sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
        raise last_error or AIError("Не удалось выполнить запрос к модели.")

    def _text_callback(self, piece: str) -> None:
        if self.on_text and not self.should_stop():
            self.on_text(piece)

    def _reasoning_callback(self, piece: str) -> None:
        if self.on_reasoning and not self.should_stop():
            self.on_reasoning(piece)

    @staticmethod
    def _is_retryable(exc: AIError) -> bool:
        if getattr(exc, "retryable", False):
            return True
        status = getattr(exc, "status", None)
        if status in RETRYABLE_STATUS:
            return True
        text = str(exc).lower()
        return any(token in text for token in (
            "429", "500", "502", "503", "504", "timed out", "timeout",
            "connection", "соединен", "времен", "overloaded", "rate limit"))

    def _sleep(self, seconds: float) -> None:
        """Sleep in small slices so a stop request is honoured quickly."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.should_stop():
                return
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))

    # ------------------------------------------------------------------
    # Message bookkeeping
    # ------------------------------------------------------------------
    def _append_assistant_turn(self, messages: List[Dict[str, Any]],
                               text: str, calls: List[ToolCall]) -> List[Dict[str, Any]]:
        messages = list(messages)
        if self.service.is_anthropic:
            blocks = getattr(self, "_pending_blocks", None) or []
            if not blocks:
                blocks = []
                if text:
                    blocks.append({"type": "text", "text": text})
                for call in calls:
                    blocks.append({"type": "tool_use", "id": call.id,
                                   "name": call.name, "input": call.arguments})
            messages.append({"role": "assistant", "content": blocks})
        else:
            messages.append({
                "role": "assistant",
                "content": text or "",
                "tool_calls": [
                    {"id": call.id, "type": "function",
                     "function": {"name": call.name,
                                  "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
                    for call in calls],
            })
        return messages

    def _handle_call(self, messages: List[Dict[str, Any]], call: ToolCall,
                     runs: List[ToolRun], seen_calls: Dict[str, int]) -> None:
        signature = call.name + "|" + json.dumps(call.arguments or {},
                                                 sort_keys=True, ensure_ascii=False)
        seen_calls[signature] = seen_calls.get(signature, 0) + 1
        repeated = seen_calls[signature] > SAME_CALL_LIMIT

        if repeated:
            output = self._repeat_notice(call)
            self._append_tool_result(messages, call, output)
            runs.append(ToolRun(call.name, call.arguments, output, ok=False, repeated=True))
            return

        if self.on_tool_start:
            try:
                self.on_tool_start(call.name, call.arguments)
            except Exception:  # noqa: BLE001 - a UI callback must not kill the run
                pass

        started = time.perf_counter()
        ok = True
        if self.tool_runner is None:
            output = f"Инструмент {call.name} недоступен."
            ok = False
        else:
            try:
                output = self.tool_runner(call.name, call.arguments)
            except Exception as exc:  # noqa: BLE001 - report, keep the loop alive
                output = f"Ошибка инструмента {call.name}: {exc}"
                ok = False
        duration_ms = int((time.perf_counter() - started) * 1000)

        text = "" if output is None else str(output)
        if len(text) > self.tool_result_limit:
            text = (text[: self.tool_result_limit]
                    + f"\n… (результат обрезан на {self.tool_result_limit} символах; "
                      "запроси нужный фрагмент отдельно через смещение/лимит)")
        self._append_tool_result(messages, call, text)
        run = ToolRun(call.name, call.arguments, text, ok=ok, duration_ms=duration_ms)
        runs.append(run)
        if self.on_tool_end:
            try:
                self.on_tool_end(run)
            except Exception:  # noqa: BLE001
                pass

    def _append_tool_result(self, messages: List[Dict[str, Any]], call: ToolCall,
                            output: str) -> None:
        if self.service.is_anthropic:
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call.id, "content": output}
            ]})
        else:
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    @staticmethod
    def _repeat_notice(call: ToolCall) -> str:
        return (
            f"Инструмент {call.name} уже вызывался с этими аргументами "
            f"{SAME_CALL_LIMIT} раза; результат выше в истории. Повторный вызов не выполнен. "
            "Используй уже полученные данные и продолжай работу."
        )

    # ------------------------------------------------------------------
    def _extend_truncated(self, messages: List[Dict[str, Any]], partial: str) -> str:
        """Continue a text answer that hit the provider's output ceiling."""
        working = list(messages) + [
            {"role": "assistant", "content": partial},
            {"role": "user", "content": self.service._continue_prompt()},
        ]
        extra = self.service._stream_until_complete(working, self.on_text, self.on_reasoning)
        return extra
