"""Chat slash-commands and @-mentions for the PyScribe AI agent.

Command syntax:

``/``    run a built-in command (``/model``, ``/clear``, ``/context``, …)
``@``    attach a file or folder from the project as context (``@src/app.py``)

This module contains only *parsing* and *descriptions*; execution lives in
``widgets/AIAgentPanel.py`` so commands can touch the UI and the editor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ChatCommand",
    "COMMANDS",
    "find_command",
    "parse_input",
    "mention_candidates",
    "ParsedInput",
]


@dataclass(frozen=True)
class ChatCommand:
    name: str
    usage: str
    description: str


COMMANDS: Tuple[ChatCommand, ...] = (
    ChatCommand("help", "/help", "Показать список команд"),
    ChatCommand("model", "/model [имя]", "Показать или сменить модель"),
    ChatCommand("models", "/models", "Список моделей провайдера (в т.ч. бесплатных)"),
    ChatCommand("provider", "/provider [ключ]", "Сменить провайдера (deepseek, gemini, …)"),
    ChatCommand("context", "/context project|file|none", "Что прикреплять к запросу"),
    ChatCommand("mode", "/mode solve|teach", "Режим агента: решение или наставник"),
    ChatCommand("reasoning", "/reasoning auto|none|low|medium|high",
                "Уровень размышлений модели (сколько «думать» перед ответом)"),
    ChatCommand("strictness", "/strictness soft|normal|strict",
                "Строгость наставника: сколько кода он может показать"),
    ChatCommand("clear", "/clear", "Начать новый диалог"),
    ChatCommand("mcp", "/mcp", "Список подключённых MCP-серверов и инструментов"),
    ChatCommand("free", "/free", "Показать бесплатные модели и переключиться на одну"),
    ChatCommand("explain", "/explain", "Объяснить текущий файл"),
    ChatCommand("tests", "/tests", "Сгенерировать тесты для файла"),
    ChatCommand("fix", "/fix", "Найти и исправить проблемы в файле"),
    ChatCommand("review", "/review", "Код-ревью текущего файла"),
    ChatCommand("stop", "/stop", "Остановить текущий ответ"),
)

_BY_NAME: Dict[str, ChatCommand] = {c.name: c for c in COMMANDS}


def find_command(token: str) -> Optional[ChatCommand]:
    """Resolve ``/name`` (with or without the slash) to a command.

    Typing just "/" must not crash: the stripped token becomes empty, so the
    name is resolved defensively instead of indexing ``split()[0]``.
    """
    parts = token.strip().lstrip("/").split()
    name = parts[0].lower() if parts else ""
    return _BY_NAME.get(name) if name else None


@dataclass
class ParsedInput:
    """Result of parsing one chat message."""

    text: str                       # the message with commands/mentions removed
    command: Optional[ChatCommand]  # leading slash command, if any
    command_arg: str                # everything after the command
    mentions: List[str]             # @-paths, without the '@'

    @property
    def is_command(self) -> bool:
        return self.command is not None


def parse_input(raw: str) -> ParsedInput:
    """Split a chat message into command + mentions + plain text."""
    text = (raw or "").strip()
    command: Optional[ChatCommand] = None
    command_arg = ""

    if text.startswith("/"):
        head, _, rest = text.partition(" ")
        command = find_command(head)
        if command is not None:
            command_arg = rest.strip()
            text = rest.strip()

    mentions: List[str] = []
    words = []
    for word in text.split():
        if word.startswith("@") and len(word) > 1:
            mentions.append(word[1:].strip().strip('"'))
        else:
            words.append(word)
    if mentions:
        text = " ".join(words).strip()
    return ParsedInput(text, command, command_arg, mentions)


def mention_candidates(entries: Sequence[Tuple[str, str]], prefix: str,
                       limit: int = 12) -> List[Tuple[str, str]]:
    """Filter ``(relative_path, kind)`` entries for an ``@``-mention prefix."""
    needle = (prefix or "").lstrip("@").lower()
    scored: List[Tuple[int, Tuple[str, str]]] = []
    for rel_path, kind in entries:
        lowered = rel_path.lower()
        name = lowered.rsplit("/", 1)[-1]
        if not needle:
            score = 0 if kind == "dir" else 1
        elif name.startswith(needle):
            score = 0
        elif lowered.startswith(needle):
            score = 1
        elif needle in lowered:
            score = 2
        else:
            continue
        scored.append((score, (rel_path, kind)))
    scored.sort(key=lambda item: (item[0], len(item[1][0]), item[1][0]))
    return [entry for _score, entry in scored[:limit]]
