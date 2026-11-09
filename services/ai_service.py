"""PyScribe AI assistant service.

Talks to LLM providers over two wire protocols, both implemented with the Python
standard library only (no extra dependencies, works in the frozen executable):

* **OpenAI-compatible** ``/chat/completions`` (SSE streaming) — DeepSeek,
  OpenAI/ChatGPT API, OpenRouter, Groq, Google Gemini (compatibility endpoint),
  opencode zen, Ollama, LM Studio and any custom server.
* **Anthropic Messages API** ``/messages`` — Claude, with native
  ``content_block_delta`` streaming and the ``tool_use`` / ``tool_result``
  content blocks.

Features
--------
* streaming answers (``stream``) and one-shot answers (``complete``)
* tool calling (MCP tools) with a bounded agent loop (``converse``)
* provider/model presets, including free tiers
* connection test and model discovery
* actionable errors: wrong key shape, 401, quota, rate limits, offline
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from services.ai_providers import KIND_ANTHROPIC, PROVIDERS, get_provider

# Shape of a bare 32-character hexadecimal token (what other services use for
# API keys; DeepSeek keys always start with "sk-").
_HEX32_RE = re.compile(r"[0-9a-fA-F]{32}")
# Canonical UUID v4 form, e.g. "3e0ff2db-f9cb-4888-ba7d-be13b833ffb0".
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# "api_key=..." / "key: ..." pasted together with the field name.
_NAME_VALUE_RE = re.compile(
    r"^\s*(api[_-]?key|apikey|key|secret|token)\s*[=:]\s*\S+", re.IGNORECASE
)

__all__ = [
    "AIError",
    "AIService",
    "AIMessage",
    "ToolCall",
    "PROVIDERS",
    "SYSTEM_PROMPT",
]

DEFAULT_TIMEOUT = 180
# Context is no longer cut: the provider receives the whole file/context block.
MAX_CONTEXT_CHARS = None
# Kept for backwards compatibility with older callers; the agent harness runs
# the tool loop itself and has no practical round limit.
MAX_TOOL_ROUNDS = None

# The old release always sent an output budget of 8192 tokens, which is what
# produced answers cut in half. Anything at or below it is treated as that
# legacy default and replaced by "let the provider decide".
LEGACY_OUTPUT_TOKENS = 8192
# Anthropic's API requires max_tokens; use a generous ceiling there.
ANTHROPIC_MAX_TOKENS = 32000
# Safety valve for the auto-continuation of a truncated answer.
MAX_CONTINUATIONS = 100

REASONING_EFFORTS = ("auto", "none", "low", "medium", "high")
REASONING_LABELS = {
    "auto": "Авто",
    "none": "Без размышлений",
    "low": "Низкий",
    "medium": "Средний",
    "high": "Высокий",
}
REASONING_HINTS = {
    "auto": "Провайдер решает сам (по умолчанию)",
    "none": "Отключить рассуждения, отвечать сразу",
    "low": "Быстрые ответы, минимум рассуждений",
    "medium": "Баланс скорости и глубины",
    "high": "Глубокий анализ, медленнее и дороже",
}
# Compact labels for the header chip (the full ones go into the menu).
REASONING_SHORT = {"auto": "Авто", "none": "Нет", "low": "Низк.",
                   "medium": "Сред.", "high": "Выс."}
ANTHROPIC_THINKING_BUDGET = {"low": 2048, "medium": 8192, "high": 16000}

SYSTEM_PROMPT = (
    "Ты — PyScribe AI, встроенный инженерный ассистент в IDE PyScribe. "
    "Отвечай по-русски, кратко и по делу. "
    "Если тебе доступны инструменты проекта — ИЗМЕНЯЙ ФАЙЛЫ ИМИ (write_file), а не выводи код в чат: "
    "в чате только краткое объяснение того, что сделано и как это проверить. "
    "Держи ответ коротким: обычно 3–6 строк, без повторов кода, который уже записан в файл, "
    "без полного дампа файлов и без длинных рассуждений. "
    "Код в чате показывай только если пользователь прямо просит его увидеть или инструменты недоступны. "
    "Не выдумывай API: если данных не хватает, задай уточняющий вопрос. "
    "Перед изменением файла сначала прочитай его инструментом read_file. "
    "Всегда указывай, как проверить результат (команда запуска, тест)."
)

# Base prompt for teaching mode: same assistant identity, but WITHOUT the
# "give ready-to-run code" instruction, which would fight the Socratic rules.
PROMPT_FOR_TEACHING_BASE = (
    "Ты — PyScribe AI, встроенный инженерный ассистент в IDE PyScribe. "
    "Отвечай по-русски, кратко и по делу. "
    "Не выдумывай API: если данных не хватает, задай уточняющий вопрос. "
    "Если тебе доступны инструменты (MCP) — используй их, когда нужны файлы проекта "
    "или внешние данные."
)

# Added to the system prompt in "teach" mode. The rules are deliberately
# strict: the point of the mode is that the *user* writes the fix.
TEACHING_PROMPT = """ТЫ — НАСТАВНИК, А НЕ РЕШАТЕЛЬ.

Твоя цель — чтобы пользователь САМ пришёл к решению и понял его.
Готовое решение, выданное сразу, считается твоей ошибкой.

ЖЁСТКИЕ ПРАВИЛА:
1. НИКОГДА не выдавай готовый код решения и не переписывай код пользователя целиком.
2. Максимум ОДИН вопрос за сообщение. Вопрос — последняя строка твоего ответа.
   Все промежуточные обращения оформляй утверждениями, а не вопросами
   («проверь случай с пустым списком», а не «а что если список пуст?»).
3. Разрешено: указать на область («посмотри, что вернёт функция при пустом списке»),
   назвать концепцию («это классическая ошибка индексации»), задать наводящий вопрос.
4. Запрещено: блоки кода длиннее лимита твоего уровня строгости (см. ниже);
   готовые формулы ответа; фразы «вот исправленный код».
5. Если пользователь ошибся — не исправляй, а спроси, что произойдёт в его варианте.
6. Если пользователь рассуждает верно — прямо подтверди, что именно верно, и углуби
   вопрос на один шаг.
7. Если пользователь прямо и настойчиво просит «дай готовый ответ» ДВА раза подряд —
   выдай решение, но обязательно добавь разбор: почему это работает и что было не так.
8. Отвечай кратко: 2–5 предложений плюс один вопрос.

ПОСЛЕДОВАТЕЛЬНОСТЬ ПОДСКАЗОК (не перескакивай):
шаг 1 — укажи область кода или условие, где искать;
шаг 2 — назови концепцию/правило языка;
шаг 3 — покажи фрагмент в пределах лимита своего уровня строгости;
шаг 4 — только после двух неудачных попыток пользователя — полное решение с разбором."""

# Strictness of the tutor: how much code an answer may contain.
# Values are the maximum number of lines allowed inside a fenced block
# (0 = no code at all).
TEACH_STRICTNESS_CODE_LINES = {"soft": 5, "normal": 3, "strict": 0}
TEACH_STRICTNESS_LABELS = {
    "soft": "Мягкий",
    "normal": "Обычный",
    "strict": "Строгий",
}
TEACH_STRICTNESS_HINTS = {
    "soft": "Разрешены короткие примеры до 5 строк",
    "normal": "Примеры не длиннее 3 строк",
    "strict": "Код запрещён полностью — только словами",
}
TEACH_STRICTNESS_ADDENDUM = {
    "soft": (
        "УРОВЕНЬ СТРОГОСТИ: МЯГКИЙ.\n"
        "Разрешено показывать короткие примеры до 5 строк, если без них объяснение "
        "буксует. Готовое решение целиком по-прежнему запрещено."
    ),
    "normal": (
        "УРОВЕНЬ СТРОГОСТИ: ОБЫЧНЫЙ.\n"
        "Примеры не длиннее 3 строк и только как иллюстрация мысли, а не как готовое "
        "решение. Предпочтительны объяснения словами."
    ),
    "strict": (
        "УРОВЕНЬ СТРОГОСТИ: СТРОГИЙ.\n"
        "Код запрещён полностью, даже одна строка. Объясняй словами; при необходимости "
        "называй имена функций, методов и параметров, но не пиши их вызовы."
    ),
}

# Nudge used when the model breaks the teaching rules.
TEACHING_RETRY_NUDGE = (
    "Ты нарушил правила наставника: выдал готовый код. Перепиши ответ по правилам."
)

TEACHING_MODE_LABELS = {"solve": "Решение", "teach": "Наставник"}
TEACHING_MODE_HINTS = {
    "solve": "Агент даёт готовые ответы и код",
    "teach": "Агент ведёт вопросами и не выдаёт готовое решение",
}


def _is_uuid_like(key: str) -> bool:
    """True for UUID-shaped values (an *ID*, not an API key)."""
    return bool(_UUID_RE.fullmatch(key))


class AIError(RuntimeError):
    """Raised for any AI request failure with a user-facing message."""

    def __init__(self, message: str, status: Optional[int] = None,
                 retryable: bool = False):
        super().__init__(message)
        self.status = status
        # Transient failures (rate limits, provider hiccups, dropped sockets)
        # are retried by the agent harness; configuration errors are not.
        self.retryable = retryable or status in (408, 409, 425, 429,
                                                 500, 502, 503, 504)


@dataclass
class AIMessage:
    role: str
    content: str

    def as_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIService:
    """Provider-agnostic chat client for PyScribe."""

    config: Dict = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT
    # Set by every streamed request: why the model stopped ("stop", "length", ...).
    last_finish_reason: Optional[str] = None
    # Token accounting of the last request, when the provider reports it.
    last_usage: Dict[str, Any] = field(default_factory=dict)
    # The model's reasoning text for the last request (hidden from the answer).
    last_reasoning: str = ""

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _setting(self, key: str, default=None):
        value = (self.config or {}).get(key)
        return default if value in (None, "") else value

    @property
    def provider_key(self) -> str:
        return str(self._setting("ai_provider", "deepseek")).strip().lower()

    @property
    def provider(self):
        return get_provider(self.provider_key)

    @property
    def kind(self) -> str:
        return self.provider.kind

    @property
    def is_anthropic(self) -> bool:
        return self.kind == KIND_ANTHROPIC

    @property
    def base_url(self) -> str:
        # A *missing* setting falls back to the provider default, but an
        # explicitly cleared value stays empty so validation can report it.
        if not self.config or "ai_base_url" not in self.config:
            value = self.provider.base_url
        else:
            value = self.config.get("ai_base_url") or ""
        return str(value).strip().rstrip("/")

    @property
    def model(self) -> str:
        if not self.config or "ai_model" not in self.config:
            return self.provider.default_model
        return str(self.config.get("ai_model") or "").strip()

    @property
    def api_key(self) -> str:
        """The key as typed, minus whitespace, quotes and a stray ``Bearer``."""
        key = str(self._setting("ai_api_key", "")).strip().strip('"').strip("'")
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        return key

    @property
    def temperature(self) -> float:
        try:
            return max(0.0, min(2.0, float(self._setting("ai_temperature", 3)) / 10.0))
        except (TypeError, ValueError):
            return 0.3

    @property
    def mode(self) -> str:
        """``solve`` (default) or ``teach`` — the Socratic tutor mode."""
        value = str(self._setting("ai_mode", "solve")).strip().lower()
        return value if value in ("solve", "teach") else "solve"

    @property
    def is_teaching(self) -> bool:
        return self.mode == "teach"

    @property
    def teach_strictness(self) -> str:
        """``soft`` | ``normal`` | ``strict`` — how much code the tutor may show."""
        value = str(self._setting("ai_teach_strictness", "normal")).strip().lower()
        return value if value in TEACH_STRICTNESS_CODE_LINES else "normal"

    @property
    def teach_code_limit(self) -> int:
        """Maximum code lines allowed in a teaching answer (0 = none)."""
        return TEACH_STRICTNESS_CODE_LINES[self.teach_strictness]

    @property
    def max_tokens(self) -> Optional[int]:
        """Output budget for one request, or ``None`` for "provider default".

        Appending a hard ``max_tokens`` to every request is what cut answers in
        half: modern models must be allowed to finish. The field is only sent
        when the user explicitly configured a budget larger than the legacy
        default, and always for Anthropic (their API requires it).
        """
        raw = self._setting("ai_max_tokens", None)
        value: Optional[int] = None
        if raw not in (None, "", 0, "0"):
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = None
        if value is None or value <= LEGACY_OUTPUT_TOKENS:
            return ANTHROPIC_MAX_TOKENS if self.is_anthropic else None
        return max(1, value)

    @property
    def reasoning_effort(self) -> str:
        """``auto`` | ``none`` | ``low`` | ``medium`` | ``high``."""
        value = str(self._setting("ai_reasoning_effort", "auto")).strip().lower()
        aliases = {"off": "none", "disabled": "none", "default": "auto",
                   "minimal": "low", "min": "low", "max": "high"}
        value = aliases.get(value, value)
        return value if value in REASONING_EFFORTS else "auto"

    def _apply_reasoning(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add the provider-specific "how hard to think" switch to *payload*.

        The switch is a request for the provider, not a local limit: when a
        server rejects the parameter the request layer retries once without it
        and remembers that for the rest of the session.
        """
        effort = self.reasoning_effort
        if effort in ("auto", "none") or getattr(self, "_reasoning_unsupported", False):
            return payload
        if self.is_anthropic:
            budget = ANTHROPIC_THINKING_BUDGET.get(effort)
            limit = payload.get("max_tokens") or ANTHROPIC_MAX_TOKENS
            if budget and budget < int(limit):
                payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
                # Extended thinking only works with temperature = 1.
                payload["temperature"] = 1.0
        else:
            payload["reasoning_effort"] = effort
        return payload

    def _strip_reasoning(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(payload)
        cleaned.pop("reasoning_effort", None)
        cleaned.pop("thinking", None)
        return cleaned

    @staticmethod
    def _is_reasoning_parameter_error(exc: "AIError") -> bool:
        """True when the server rejected ``reasoning_effort``/``thinking``."""
        if getattr(exc, "status", None) not in (400, 422):
            return False
        text = str(exc).lower()
        return any(word in text for word in (
            "reasoning_effort", "reasoning", "thinking", "unknown field",
            "unsupported", "unrecognized", "invalid request"))

    @property
    def prompt_cache_enabled(self) -> bool:
        """Prompt caching for the stable prefix (Anthropic-style servers)."""
        if getattr(self, "_cache_unsupported", False):
            return False
        value = self._setting("ai_prompt_cache", True)
        return value not in (False, "False", "false", 0, "0")

    @staticmethod
    def _has_cache_control(payload: Dict[str, Any]) -> bool:
        system = payload.get("system")
        if isinstance(system, list) and any(
                isinstance(block, dict) and "cache_control" in block for block in system):
            return True
        tools = payload.get("tools")
        return bool(isinstance(tools, list) and tools
                    and isinstance(tools[-1], dict) and "cache_control" in tools[-1])

    @staticmethod
    def _strip_cache(payload: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(payload)
        system = cleaned.get("system")
        if isinstance(system, list):
            cleaned["system"] = "".join(
                str(block.get("text") or "") for block in system
                if isinstance(block, dict))
        tools = cleaned.get("tools")
        if isinstance(tools, list) and tools and isinstance(tools[-1], dict):
            tools = [dict(tool) for tool in tools]
            tools[-1].pop("cache_control", None)
            cleaned["tools"] = tools
        return cleaned

    def _fallback_payload(self, payload: Dict[str, Any],
                          exc: "AIError") -> Optional[Dict[str, Any]]:
        """Retry payload without optional fields the server refused."""
        if getattr(exc, "status", None) not in (400, 422):
            return None
        text = str(exc).lower()
        if not any(word in text for word in (
                "reasoning", "thinking", "cache", "unknown field",
                "unsupported", "unrecognized", "invalid request", "extra inputs")):
            return None
        cleaned = payload
        for _attempt in range(2):
            if "reasoning_effort" in cleaned or "thinking" in cleaned:
                cleaned = self._strip_reasoning(cleaned)
                self._reasoning_unsupported = True
                continue
            if self._has_cache_control(cleaned):
                cleaned = self._strip_cache(cleaned)
                self._cache_unsupported = True
                continue
            break
        return cleaned if cleaned != payload else None

    @property
    def enabled(self) -> bool:
        return self._setting("ai_enabled", True) not in (False, "False", "false", 0, "0")

    @property
    def context_scope(self) -> str:
        """``project`` | ``file`` | ``none`` — what the agent attaches."""
        return str(self._setting("ai_context_scope", "file")).strip().lower()

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def requires_api_key(self) -> bool:
        url = self.base_url.lower()
        if any(host in url for host in ("localhost", "127.0.0.1", "0.0.0.0")):
            return False
        return True

    def configuration_problem(self) -> Optional[str]:
        if not self.enabled:
            return "ИИ-агент отключён в настройках (Настройки → ИИ-агент)."
        if not self.base_url:
            return "Не задан базовый URL API (Настройки → ИИ-агент)."
        if not self.model:
            return "Не выбрана модель (Настройки → ИИ-агент)."
        if self.requires_api_key() and not self.api_key:
            return ("Не задан API-ключ (Настройки → ИИ-агент). "
                    f"Ключ {self.provider.label} можно получить здесь: {self.provider.key_url}")
        return self.key_format_problem()

    # ------------------------------------------------------------------
    # API key hygiene
    # ------------------------------------------------------------------
    def key_looks_like(self) -> str:
        key = self.api_key
        if key.startswith("sk-or-"):
            return "OpenRouter"
        if key.startswith(("sk-ant-", "sk-ant-api")):
            return "Anthropic (Claude)"
        if key.startswith(("sk-proj-", "sk-svcacct-")):
            return "OpenAI"
        if key.startswith("sk-"):
            return "ключ вида «sk-…»"
        if key.startswith("AIza"):
            return "Google Gemini"
        if key.startswith("gsk_"):
            return "Groq"
        if _is_uuid_like(key):
            return "UUID (идентификатор, а не API-ключ)"
        if _HEX32_RE.fullmatch(key):
            return "hex-строка (это не API-ключ)"
        return ""

    def key_format_problem(self) -> Optional[str]:
        """Detect an obviously wrong key *before* the provider answers 401."""
        key = self.api_key
        if not key:
            return None
        raw = str(self._setting("ai_api_key", "")).strip()
        low_raw = raw.lower()
        if low_raw.startswith("bearer "):
            return None  # api_key strips the prefix
        if low_raw.startswith(("api_key=", "apikey=")) or _NAME_VALUE_RE.match(raw):
            return ("Ключ вставлен вместе с «api_key=» — оставьте только значение "
                    "ключа (Настройки → ИИ-агент).")
        if "://" in key:
            return "В поле ключа вставлен URL, а не API-ключ (Настройки → ИИ-агент)."
        if _is_uuid_like(key):
            expect = "Ключ DeepSeek выглядит как «sk-…»." if self.provider_key == "deepseek" \
                else f"Ключ {self.provider.label} — это другая строка."
            return (f"Это не API-ключ, а идентификатор в формате UUID (ID ключа или аккаунта). "
                    f"{expect} Создайте ключ здесь: {self.provider.key_url}")
        provider = self.provider_key
        if provider == "deepseek" and not key.startswith("sk-"):
            return ("Ключ DeepSeek должен начинаться с «sk-». Проверьте, что скопирован "
                    "весь ключ, а не его фрагмент (Настройки → ИИ-агент).")
        if provider == "anthropic" and not key.startswith("sk-ant-"):
            return ("Ключи Anthropic начинаются с «sk-ant-». Создайте ключ в "
                    "console.anthropic.com/settings/keys (подписка Claude Pro/Max не подходит).")
        if provider == "gemini" and not key.startswith("AIza"):
            return ("Ключи Google AI Studio начинаются с «AIza». Получите бесплатный ключ: "
                    "aistudio.google.com/apikey.")
        if provider == "groq" and not key.startswith("gsk_"):
            return "Ключи Groq начинаются с «gsk_». Получите ключ: console.groq.com/keys."
        if provider == "openrouter" and not key.startswith("sk-or-"):
            return "Ключи OpenRouter начинаются с «sk-or-». Получите ключ: openrouter.ai/keys."
        if provider == "openai" and not key.startswith("sk-"):
            return "Ключи OpenAI начинаются с «sk-». Создайте ключ: platform.openai.com/api-keys."
        return None

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PyScribe/1.0 AI",
        }
        if self.is_anthropic:
            # Claude uses its own auth + version headers.
            if self.api_key:
                headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _endpoint(self, path: str) -> str:
        base = self.base_url
        for suffix in ("/chat/completions", "/messages", "/models"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        if not base:
            return path
        # Providers accept either "https://host" or "https://host/v1". Add the
        # API version segment when the user gave only the host (the DeepSeek
        # docs list both forms) unless the URL already carries one.
        tail = base.rsplit("/", 1)[-1]
        has_version = tail.startswith("v") and tail[1:2].isdigit()
        if not has_version and "/openai" not in base and not base.endswith("/anthropic"):
            if not path.startswith("/v1") and self.kind != KIND_ANTHROPIC:
                return f"{base}/v1{path}"
        return f"{base}{path}"

    @staticmethod
    def _extract_error_detail(body: str) -> str:
        try:
            payload = json.loads(body)
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or "")
            if isinstance(error, str):
                return error
            if payload.get("message"):
                return str(payload["message"])
        except Exception:
            pass
        return (body or "").strip()[:300]

    def _describe_401(self, detail: str) -> str:
        """Turn a provider 401 into an explanation the user can act on."""
        key = self.api_key
        looks = self.key_looks_like()
        unmasked = ""
        if detail:
            match = re.search(r"\*\*\*\*(\w+)", detail)
            if match:
                unmasked = f" Провайдер видит ключ, заканчивающийся на «…{match.group(1)}»."
        hint = f" Сохранённый ключ похож на {looks}." if looks else ""
        expect = ""
        if self.provider_key == "deepseek" and not key.startswith("sk-"):
            expect = " Ключи DeepSeek начинаются с «sk-»."
        return (f"Провайдер {self.provider.label} отклонил API-ключ (401): ключ неверный, "
                f"отозван или от другого сервиса. Проверьте ключ в Настройки → ИИ-агент "
                f"(получить: {self.provider.key_url})." + hint + expect + unmasked)

    def _friendly_http_error(self, code: int, body: str) -> AIError:
        detail = self._extract_error_detail(body)
        message = self._friendly_http_message(code, detail)
        return AIError(message, status=code)

    def _friendly_http_message(self, code: int, detail: str) -> str:
        if code == 401:
            return self._describe_401(detail)
        if code == 402:
            return "Недостаточно средств на счёте провайдера (402). Пополните баланс."
        if code == 403:
            return "Доступ запрещён (403). Проверьте права ключа и доступ к модели."
        if code == 404:
            return ("Модель или адрес API не найдены (404). Проверьте модель и базовый URL."
                    + (f" Детали: {detail}" if detail else ""))
        if code == 429:
            return ("Слишком много запросов (429). Подождите и повторите "
                    "— либо выберите другую бесплатную модель.")
        if code >= 500:
            return (f"Ошибка на стороне провайдера ({code}). Попробуйте позже."
                    + (f": {detail}" if detail else ""))
        return f"Ошибка API ({code})" + (f": {detail}" if detail else "")

    def _open(self, req: urllib.request.Request):
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise self._friendly_http_error(exc.code, body) from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise AIError(
                "Нет соединения с API. Проверьте интернет и базовый URL "
                f"({self.base_url}). Причина: {reason}"
            ) from None
        except TimeoutError:
            raise AIError("Превышено время ожидания ответа API.")
        except ValueError as exc:
            raise AIError(f"Некорректный адрес API: {exc}") from None

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._post_json_once(path, payload)
        except AIError as exc:
            fallback = self._fallback_payload(payload, exc)
            if fallback is None:
                raise
            return self._post_json_once(path, fallback)

    def _post_json_once(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self._endpoint(path), data=data,
                                     headers=self._headers(), method="POST")
        with self._open(req) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise AIError("Провайдер вернул ответ в неизвестном формате.") from None

    def _stream_json(self, path: str, payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        try:
            yield from self._stream_json_once(path, payload)
        except AIError as exc:
            fallback = self._fallback_payload(payload, exc)
            if fallback is None:
                raise
            yield from self._stream_json_once(path, fallback)

    def _stream_json_once(self, path: str,
                          payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Yield SSE ``data:`` payloads as dicts."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self._endpoint(path), data=data,
                                     headers=self._headers(), method="POST")
        with self._open(req) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    parsed = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    yield parsed

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------
    def build_system_prompt(self) -> str:
        extra = str(self._setting("ai_system_prompt", "")).strip()
        prompt = SYSTEM_PROMPT
        if self.is_teaching:
            # Teaching rules override the "give ready code" instruction above.
            level = self.teach_strictness
            prompt = (PROMPT_FOR_TEACHING_BASE + "\n\n" + TEACHING_PROMPT
                      + "\n\n" + TEACH_STRICTNESS_ADDENDUM[level])
        if extra:
            prompt += "\n\n" + extra
        return prompt

    def build_messages(self, user_prompt: str, history: Optional[List[AIMessage]] = None,
                       context: Optional[str] = None) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": self.build_system_prompt()}]
        for item in history or []:
            messages.append(item.as_dict())
        prompt = user_prompt
        if context:
            prompt = f"{user_prompt}\n\n{context}"
        messages.append({"role": "user", "content": prompt})
        return messages

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------
    def _payload(self, messages: List[Dict[str, Any]], stream: bool,
                 tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if self.is_anthropic:
            system = ""
            chat = []
            for message in messages:
                if message.get("role") == "system":
                    system = message.get("content") or ""
                    continue
                chat.append(message)
            payload: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens or ANTHROPIC_MAX_TOKENS,
                "temperature": self.temperature,
                "messages": chat,
                "stream": stream,
            }
            if system:
                if self.prompt_cache_enabled:
                    # Prompt caching: the system block (identity + project rules)
                    # is identical between rounds, so the provider charges a
                    # fraction for it and answers faster.
                    payload["system"] = [{
                        "type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }]
                else:
                    payload["system"] = system
            if tools:
                payload["tools"] = [
                    {"name": t["function"]["name"],
                     "description": t["function"].get("description", ""),
                     "input_schema": t["function"].get("parameters")
                     or {"type": "object", "properties": {}}}
                    for t in tools
                ]
                if self.prompt_cache_enabled:
                    # Cache the whole tool catalogue together with the system
                    # prompt: it is the stable prefix of every request.
                    payload["tools"][-1]["cache_control"] = {"type": "ephemeral"}
            return self._apply_reasoning(payload)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": stream,
        }
        if self.max_tokens is not None:
            # Only an explicit user budget is sent; otherwise the provider's
            # own maximum applies (a hard cap here cut answers in half).
            payload["max_tokens"] = self.max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return self._apply_reasoning(payload)

    def complete(self, user_prompt: str, history: Optional[List[AIMessage]] = None,
                 context: Optional[str] = None) -> str:
        problem = self.configuration_problem()
        if problem:
            raise AIError(problem)
        messages = self.build_messages(user_prompt, history, context)
        path = "/messages" if self.is_anthropic else "/chat/completions"
        parsed = self._post_json(path, self._payload(messages, stream=False))
        if self.is_anthropic:
            return "".join(
                block.get("text", "")
                for block in parsed.get("content") or []
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
        choices = parsed.get("choices") or []
        if not choices:
            error = parsed.get("error")
            raise AIError(str(error) if error else "Пустой ответ от модели.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            content = choices[0].get("text", "")
        return str(content or "").strip()

    def stream(self, user_prompt: str, history: Optional[List[AIMessage]] = None,
               context: Optional[str] = None,
               on_reasoning: Optional[Callable[[str], None]] = None) -> Iterator[str]:
        """Yield answer deltas. Delegates to the shared streaming path so that
        finish reason, token usage and reasoning are tracked identically to
        ``converse`` (this used to be a second, divergent implementation)."""
        problem = self.configuration_problem()
        if problem:
            raise AIError(problem)
        messages = self.build_messages(user_prompt, history, context)
        return self._stream_with(messages, on_reasoning=on_reasoning)

    # ------------------------------------------------------------------
    # Tool calling (MCP)
    # ------------------------------------------------------------------
    def converse(self, user_prompt: str, history: Optional[List[AIMessage]] = None,
                 context: Optional[str] = None,
                 tools: Optional[List[Dict[str, Any]]] = None,
                 tool_runner: Optional[Callable[[str, Dict[str, Any]], str]] = None,
                 on_text: Optional[Callable[[str], None]] = None,
                 on_tool: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                 on_reasoning: Optional[Callable[[str], None]] = None,
                 on_tool_end: Optional[Callable[[Any], None]] = None,
                 should_stop: Optional[Callable[[], bool]] = None,
                 max_rounds: Optional[int] = None) -> str:
        """Run a chat turn through the agent harness.

        The harness owns the tool loop: it keeps calling tools until the model
        produces its final answer (no low round limit), passes full tool
        results back, retries transient provider errors and detects repeated
        identical calls. ``tool_runner(name, args)`` executes one tool.
        """
        problem = self.configuration_problem()
        if problem:
            raise AIError(problem)
        from services.agent_harness import AgentHarness

        messages = self.build_messages(user_prompt, history, context)
        harness = AgentHarness(
            self,
            tools=tools,
            tool_runner=tool_runner,
            max_rounds=max_rounds,
            on_text=on_text,
            on_reasoning=on_reasoning,
            on_tool_start=(lambda name, args: on_tool(name, args)) if on_tool else None,
            on_tool_end=on_tool_end,
            should_stop=should_stop,
        )
        result = harness.run(messages)
        self.last_usage = result.usage
        self.last_stop_reason = result.stop_reason
        self.last_tool_runs = [run.as_dict() for run in result.tool_runs]
        return result.text

    def _stream_with(self, messages: List[Dict[str, Any]],
                     on_reasoning: Optional[Callable[[str], None]] = None) -> Iterator[str]:
        path = "/messages" if self.is_anthropic else "/chat/completions"
        payload = self._payload(messages, stream=True)
        self.last_finish_reason = None
        self.last_usage = {}
        self.last_reasoning = ""
        for event in self._stream_json(path, payload):
            usage = event.get("usage")
            if isinstance(usage, dict):
                self.last_usage = {**self.last_usage, **usage}
            if self.is_anthropic:
                etype = event.get("type")
                if etype == "content_block_delta":
                    delta = event.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
                    elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                        # Claude's extended thinking arrives as its own delta.
                        piece = delta["thinking"]
                        self.last_reasoning += piece
                        if on_reasoning:
                            on_reasoning(piece)
                elif etype == "message_delta":
                    # Claude reports why generation ended here.
                    self.last_finish_reason = (
                        (event.get("delta") or {}).get("stop_reason")
                        or self.last_finish_reason)
            else:
                choices = event.get("choices") or []
                if choices:
                    choice = choices[0]
                    delta = choice.get("delta") or {}
                    # DeepSeek (and some others) stream reasoning separately from
                    # the answer in ``reasoning_content`` / ``reasoning``.
                    thought = delta.get("reasoning_content") or delta.get("reasoning")
                    if thought:
                        self.last_reasoning += thought
                        if on_reasoning:
                            on_reasoning(thought)
                    piece = delta.get("content")
                    if piece:
                        yield piece
                    if choice.get("finish_reason"):
                        self.last_finish_reason = choice["finish_reason"]

    @property
    def truncated(self) -> bool:
        """True when the last streamed answer hit the output-token limit."""
        return str(self.last_finish_reason or "").lower() in (
            "length", "max_tokens", "max_output_tokens")

    def _continue_prompt(self) -> str:
        """Instruction used when an answer was cut off by the token limit."""
        return ("Продолжи ответ ровно с того места, где он оборвался. "
                "Не повторяй уже написанное, не начинай заново и не извиняйся — "
                "просто продолжи текст.")

    def _stream_until_complete(self, messages: List[Dict[str, Any]],
                               on_text: Optional[Callable[[str], None]] = None,
                               on_reasoning: Optional[Callable[[str], None]] = None) -> str:
        """Stream one answer, automatically continuing it if the model truncates.

        Providers stop with ``finish_reason == "length"`` when the output budget
        runs out, which used to leave the user with a sentence cut in half. Here
        the partial answer is fed back and generation resumes, up to
        ``MAX_CONTINUATIONS`` times.
        """
        collected: List[str] = []
        working = list(messages)
        for attempt in range(MAX_CONTINUATIONS + 1):
            for piece in self._stream_with(working, on_reasoning=on_reasoning):
                collected.append(piece)
                if on_text:
                    on_text(piece)
            if not self.truncated:
                break
            if attempt == MAX_CONTINUATIONS:
                break
            partial = "".join(collected)
            working = list(messages) + [
                {"role": "assistant", "content": partial},
                {"role": "user", "content": self._continue_prompt()},
            ]
        return "".join(collected)

    def _openai_tool_round(self, messages, tools, on_text, on_reasoning=None):
        payload = self._payload(messages, stream=True, tools=tools)
        text: List[str] = []
        calls: Dict[int, Dict[str, Any]] = {}
        self.last_usage = {}
        self.last_finish_reason = None
        for chunk in self._stream_json("/chat/completions", payload):
            usage = chunk.get("usage")
            if isinstance(usage, dict):
                self.last_usage = {**self.last_usage, **usage}
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            thought = delta.get("reasoning_content") or delta.get("reasoning")
            if thought:
                self.last_reasoning += thought
                if on_reasoning:
                    on_reasoning(thought)
            if choice.get("finish_reason"):
                self.last_finish_reason = choice["finish_reason"]
            piece = delta.get("content")
            if piece:
                text.append(piece)
                if on_text:
                    on_text(piece)
            for position, item in enumerate(delta.get("tool_calls") or []):
                # The provider streams parallel calls with an explicit index; each
                # chunk usually carries one entry, so ``enumerate`` alone would
                # collapse every call into slot 0 and corrupt the arguments.
                try:
                    index = int(item.get("index", position))
                except (TypeError, ValueError):
                    index = position
                slot = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if item.get("id"):
                    slot["id"] = item["id"]
                function = item.get("function") or {}
                if function.get("name"):
                    slot["name"] = function["name"]
                if function.get("arguments"):
                    slot["arguments"] += function["arguments"]
        parsed: List[ToolCall] = []
        for index in sorted(calls):
            slot = calls[index]
            try:
                args = json.loads(slot["arguments"]) if slot["arguments"].strip() else {}
            except json.JSONDecodeError:
                args = {}
            parsed.append(ToolCall(slot["id"] or f"call_{index}", slot["name"], args))
        return "".join(text), parsed

    def _anthropic_tool_round(self, messages, tools, on_text, on_reasoning=None):
        payload = self._payload(messages, stream=True, tools=tools)
        blocks: List[Dict[str, Any]] = []
        current_text: List[str] = []
        calls: List[ToolCall] = []
        current_call: Optional[Dict[str, Any]] = None
        self.last_usage = {}
        self.last_finish_reason = None
        for event in self._stream_json("/messages", payload):
            etype = event.get("type")
            usage = event.get("usage")
            if isinstance(usage, dict):
                self.last_usage = {**self.last_usage, **usage}
            if etype == "error":
                raise AIError(str((event.get("error") or {}).get("message")))
            if etype == "message_delta":
                self.last_finish_reason = (
                    (event.get("delta") or {}).get("stop_reason")
                    or self.last_finish_reason)
            if etype == "content_block_start":
                block = event.get("content_block") or {}
                if block.get("type") == "tool_use":
                    current_call = {"id": block.get("id", ""), "name": block.get("name", ""),
                                    "json": ""}
            elif etype == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    current_text.append(delta["text"])
                    if on_text:
                        on_text(delta["text"])
                elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                    piece = delta["thinking"]
                    self.last_reasoning += piece
                    if on_reasoning:
                        on_reasoning(piece)
                elif delta.get("type") == "input_json_delta" and current_call is not None:
                    current_call["json"] += delta.get("partial_json") or ""
            elif etype == "content_block_stop":
                if current_call is not None:
                    try:
                        args = json.loads(current_call["json"]) if current_call["json"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    calls.append(ToolCall(current_call["id"], current_call["name"], args))
                    blocks.append({"type": "tool_use", "id": current_call["id"],
                                   "name": current_call["name"], "input": args})
                    current_call = None
        text = "".join(current_text)
        if text:
            blocks.insert(0, {"type": "text", "text": text})
        return blocks, calls

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def test_connection(self):
        problem = self.configuration_problem()
        if problem:
            return False, problem
        try:
            answer = self.complete("Ответь одним словом: OK")
        except AIError as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001
            return False, f"Ошибка: {exc}"
        if not answer:
            return False, "API ответил пустым сообщением."
        return True, f"Подключение работает: {self.provider.label} · {self.model}."

    def list_models(self) -> List[str]:
        if not self.base_url:
            return []
        if self.is_anthropic:
            headers = self._headers()
            req = urllib.request.Request(self._endpoint("/models") + "?limit=100",
                                         headers=headers, method="GET")
        else:
            req = urllib.request.Request(self._endpoint("/models"),
                                         headers=self._headers(), method="GET")
        try:
            with self._open(req) as resp:
                parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"Не удалось получить список моделей: {exc}") from None
        items = parsed.get("data") or parsed.get("models") or []
        models = []
        for item in items:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name")
            else:
                model_id = str(item)
            if model_id:
                models.append(str(model_id))
        return sorted(set(models))

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------
    @staticmethod
    def build_context_block(file_path: Optional[str] = None, code: Optional[str] = None,
                            language: Optional[str] = None, selection: Optional[str] = None,
                            problems: Optional[Iterable[str]] = None,
                            project_files: Optional[Iterable[Tuple[str, str]]] = None,
                            project_root: Optional[str] = None) -> str:
        """Compose the context block appended to the user's prompt."""
        parts: List[str] = []
        header = []
        if project_root:
            header.append(f"Корень проекта: {project_root}")
        if file_path:
            header.append(f"Файл: {file_path}")
        if language:
            header.append(f"Язык: {language}")
        if header:
            parts.append("\n".join(header))
        if problems:
            lines = [str(p) for p in problems if p]
            if lines:
                parts.append("Найденные проблемы:\n" + "\n".join(f"- {line}" for line in lines))
        for rel_path, text in list(project_files or []):
            # No character budget: an @-mentioned file is sent whole. Cutting it
            # here made the agent re-read files and give up half-way.
            parts.append(f"Файл проекта {rel_path}:\n```\n{text or ''}\n```")
        if selection:
            parts.append("Выделенный фрагмент:\n```\n" + selection + "\n```")
        if code:
            parts.append("Содержимое файла:\n```\n" + code + "\n```")
        if not parts:
            return ""
        return "<context>\n" + "\n\n".join(parts) + "\n</context>"


def extract_code_blocks(text: str) -> List[str]:
    """Pull fenced code blocks out of a model answer (used by "применить")."""
    blocks: List[str] = []
    lines = text.splitlines()
    in_block = False
    current: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                blocks.append("\n".join(current))
                current = []
                in_block = False
            else:
                in_block = True
            continue
        if in_block:
            current.append(line)
    if in_block and current:
        blocks.append("\n".join(current))
    return [b for b in blocks if b.strip()]


# ----------------------------------------------------------------------
# Teaching-mode enforcement
# ----------------------------------------------------------------------
TEACHING_HIDDEN_NOTE = "(фрагмент решения скрыт в режиме наставника)"
TEACHING_FOLLOWUP_QUESTION = "Какая часть этого фрагмента тебе непонятна?"


def _code_blocks_with_spans(text: str) -> List[Tuple[int, int, int]]:
    """Return ``(start_line, end_line, body_line_count)`` for fenced blocks.

    Line numbers are 0-based indexes into ``text.splitlines()``; the range is
    inclusive of the fence lines.
    """
    lines = text.splitlines()
    spans: List[Tuple[int, int, int]] = []
    start = None
    body = 0
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            if start is None:
                start = index
                body = 0
            else:
                spans.append((start, index, body))
                start = None
            continue
        if start is not None:
            body += 1
    if start is not None:
        spans.append((start, len(lines) - 1, body))
    return spans


def has_forbidden_solution(answer: str, max_lines: int = 3) -> bool:
    """True when an answer exceeds the allowed code block size.

    ``max_lines`` is the number of lines allowed *inside* a fenced block
    (``0`` means no code at all). A block longer than that is treated as
    handing over the solution.
    """
    allowed = max(0, int(max_lines))
    for _start, _end, body_lines in _code_blocks_with_spans(answer or ""):
        if body_lines > allowed:
            return True
    return False


def _replace_long_code_blocks(text: str, max_lines: int = 3) -> str:
    """Replace forbidden blocks with a note, keeping the surrounding text."""
    lines = text.splitlines()
    spans = _code_blocks_with_spans(text)
    if not spans:
        return text
    allowed = max(0, int(max_lines))
    out: List[str] = []
    cursor = 0
    for start, end, body_lines in spans:
        out.extend(lines[cursor:start])
        if body_lines > allowed:
            out.append(TEACHING_HIDDEN_NOTE)
        else:
            out.extend(lines[start:end + 1])   # short hint fragment is allowed
        cursor = end + 1
    out.extend(lines[cursor:])
    return "\n".join(out)


def enforce_teaching_rules(answer_text: str, service: Optional["AIService"] = None,
                           max_lines: Optional[int] = None) -> str:
    """Guarantee that a teaching-mode answer does not hand over the solution.

    The prompt asks the model to hold back, but models slip. This is the hard
    stop: code blocks above the strictness limit are removed and a question is
    appended so the reply still guides the user instead of ending abruptly.

    ``max_lines`` defaults to the service's strictness level. In ``solve`` mode
    the text is returned unchanged.
    """
    if service is not None and not service.is_teaching:
        return answer_text
    if max_lines is None:
        max_lines = service.teach_code_limit if service is not None else 3
    if not has_forbidden_solution(answer_text, max_lines=max_lines):
        return answer_text
    cleaned = _replace_long_code_blocks(answer_text, max_lines=max_lines)
    if TEACHING_FOLLOWUP_QUESTION not in cleaned:
        cleaned = cleaned.rstrip() + "\n\n" + TEACHING_FOLLOWUP_QUESTION
    return cleaned
