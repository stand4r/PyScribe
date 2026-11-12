"""Provider registry for the PyScribe AI agent.

Every provider is described declaratively so the UI (settings page, model
picker) and the HTTP client share one source of truth.

Two wire protocols are supported:

``openai``
    ``POST {base}/chat/completions`` with SSE ``data: {...}`` chunks. Covers
    DeepSeek, OpenAI, OpenRouter, Groq, Mistral, Gemini's
    compatibility endpoint, Ollama, LM Studio and any custom server.
``anthropic``
    ``POST {base}/messages`` with the native Claude Messages API
    (``x-api-key`` + ``anthropic-version`` headers, ``content_block_delta`` SSE
    events), used for Claude.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "ProviderSpec",
    "PROVIDERS",
    "KIND_OPENAI",
    "KIND_ANTHROPIC",
    "get_provider",
    "provider_choices",
    "models_for",
]

KIND_OPENAI = "openai"
KIND_ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class ModelSpec:
    """One selectable model."""

    id: str
    label: str
    free: bool = False
    note: str = ""
    version: str = ""   # human-facing model version, e.g. "DeepSeek-V4.1-Flash-1017"


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    kind: str
    base_url: str
    models: List[ModelSpec] = field(default_factory=list)
    key_url: str = ""
    docs_url: str = ""
    local: bool = False
    hint: str = ""
    # Anthropic-format endpoint for providers that proxy Claude models
    # (DeepSeek serves one at https://api.deepseek.com/anthropic).
    anthropic_base_url: str = ""

    @property
    def default_model(self) -> str:
        return self.models[0].id if self.models else ""


def _m(model_id: str, label: str = "", free: bool = False, note: str = "",
       version: str = "") -> ModelSpec:
    return ModelSpec(model_id, label or model_id, free, note, version)


PROVIDERS: Dict[str, ProviderSpec] = {
    # ------------------------------------------------------------------
    "deepseek": ProviderSpec(
        key="deepseek",
        label="DeepSeek",
        kind=KIND_OPENAI,
        base_url="https://api.deepseek.com",
        anthropic_base_url="https://api.deepseek.com/anthropic",
        key_url="https://platform.deepseek.com/api_keys",
        docs_url="https://api-docs.deepseek.com/quick_start/pricing",
        models=[
            _m("deepseek-flash", "DeepSeek Flash", note="1M контекст, thinking по умолчанию",
               version="DeepSeek-V4.1-Flash-1017"),
            _m("deepseek-v4-pro", "DeepSeek V4 Pro", note="Максимальное качество",
               version="DeepSeek-V4-Pro-0813"),
        ],
        hint="Ключ начинается с «sk-». Актуальные модели: deepseek-flash (V4.1-Flash-1017) "
             "и deepseek-v4-pro. Старое имя deepseek-chat тоже принимается, но это тот же Flash.",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI / ChatGPT",
        kind=KIND_OPENAI,
        base_url="https://api.openai.com/v1",
        key_url="https://platform.openai.com/api-keys",
        models=[
            _m("gpt-5.1", "GPT-5.1"),
            _m("gpt-5", "GPT-5"),
            _m("gpt-5-mini", "GPT-5 mini", note="Быстро и дёшево"),
            _m("gpt-4.1", "GPT-4.1"),
            _m("o3", "o3", note="Рассуждения"),
            _m("gpt-4o-mini", "GPT-4o mini", note="Устаревает"),
        ],
        hint="Обычный API-ключ OpenAI (не подписка ChatGPT).",
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Claude (Anthropic)",
        kind=KIND_ANTHROPIC,
        base_url="https://api.anthropic.com/v1",
        key_url="https://console.anthropic.com/settings/keys",
        models=[
            _m("claude-opus-4-6", "Claude Opus 4.6", version="claude-opus-4-6-20260205"),
            _m("claude-sonnet-4-5", "Claude Sonnet 4.5"),
            _m("claude-haiku-4-5", "Claude Haiku 4.5", note="Быстрый и дешёвый"),
            _m("claude-opus-4-1", "Claude Opus 4.1"),
        ],
        hint="Ключ вида «sk-ant-…». Подписка Claude Pro/Max не подходит — нужен API-ключ.",
    ),
    "gemini": ProviderSpec(
        key="gemini",
        label="Google Gemini",
        kind=KIND_OPENAI,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        key_url="https://aistudio.google.com/apikey",
        models=[
            _m("gemini-4-argon", "Gemini 4 Argon", note="Самая новая, 1M контекст"),
            _m("gemini-3.6-flash", "Gemini 3.6 Flash", free=True, note="Бесплатный тариф"),
            _m("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", free=True, note="Бесплатный тариф"),
            _m("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", free=True),
            _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ],
        hint="Ключ бесплатно в Google AI Studio (aistudio.google.com/apikey).",
    ),
    "opencode": ProviderSpec(
        key="opencode",
        label="opencode zen",
        kind=KIND_OPENAI,
        base_url="https://opencode.ai/zen/v1",
        key_url="https://opencode.ai/auth",
        models=[
            _m("gpt-5.1", "GPT-5.1"),
            _m("claude-sonnet-4-5", "Claude Sonnet 4.5"),
            _m("qwen3-coder", "Qwen3 Coder"),
            _m("kimi-k2", "Kimi K2"),
        ],
        hint="Ключ из opencode (/connect → opencode zen).",
    ),
    # ------------------------------------------------------------------
    # Free / no-key-required tier
    # ------------------------------------------------------------------
    "openrouter": ProviderSpec(
        key="openrouter",
        label="OpenRouter",
        kind=KIND_OPENAI,
        base_url="https://openrouter.ai/api/v1",
        key_url="https://openrouter.ai/keys",
        models=[
            _m("deepseek/deepseek-v4.1-flash-1017", "DeepSeek V4.1 Flash 1017", free=True),
            _m("deepseek/deepseek-v4.1-flash", "DeepSeek V4.1 Flash", free=True),
            _m("qwen/qwen3-coder:free", "Qwen3 Coder (free)", free=True),
            _m("google/gemini-3.6-flash:free", "Gemini 3.6 Flash (free)", free=True),
            _m("meta-llama/llama-3.3-70b-instruct:free", "Llama 3.3 70B (free)", free=True),
        ],
        hint="Бесплатные модели помечены «:free» и работают с бесплатным ключом OpenRouter.",
    ),
    "groq": ProviderSpec(
        key="groq",
        label="Groq",
        kind=KIND_OPENAI,
        base_url="https://api.groq.com/openai/v1",
        key_url="https://console.groq.com/keys",
        models=[
            _m("llama-3.3-70b-versatile", "Llama 3.3 70B", free=True, note="Бесплатный тариф"),
            _m("qwen/qwen3-32b", "Qwen3 32B", free=True),
            _m("openai/gpt-oss-120b", "GPT-OSS 120B", free=True),
        ],
        hint="Groq даёт бесплатный тариф для разработки.",
    ),
    "ollama": ProviderSpec(
        key="ollama",
        label="Ollama (локально, бесплатно)",
        kind=KIND_OPENAI,
        base_url="http://localhost:11434/v1",
        key_url="https://ollama.com/download",
        local=True,
        models=[
            _m("qwen3-coder:30b", "Qwen3 Coder 30B", free=True),
            _m("qwen2.5-coder:7b", "Qwen2.5 Coder 7B", free=True),
            _m("llama3.2:3b", "Llama 3.2 3B", free=True),
        ],
        hint="Локальная модель: бесплатно, без ключа, работает без интернета.",
    ),
    "lmstudio": ProviderSpec(
        key="lmstudio",
        label="LM Studio (локально, бесплатно)",
        kind=KIND_OPENAI,
        base_url="http://localhost:1234/v1",
        key_url="https://lmstudio.ai",
        local=True,
        models=[_m("local-model", "Любая загруженная модель", free=True)],
        hint="В LM Studio включите локальный сервер (Developer → Start Server).",
    ),
    "custom": ProviderSpec(
        key="custom",
        label="Свой сервер (OpenAI-совместимый)",
        kind=KIND_OPENAI,
        base_url="",
        models=[],
        hint="Укажите базовый URL вида https://host/v1 и имя модели.",
    ),
}


def get_provider(key: str) -> ProviderSpec:
    return PROVIDERS.get(str(key or "").strip().lower(), PROVIDERS["deepseek"])


def provider_choices() -> List[ProviderSpec]:
    return list(PROVIDERS.values())


def models_for(key: str) -> List[ModelSpec]:
    return list(get_provider(key).models)
