"""Local tools the AI agent can call: files, terminal, running applications.

The agent runs model-requested actions through this module instead of touching
the disk directly. Everything is confined to the open project and every
mutating action goes through a confirmation callback, so the user stays in
control (same model as DeepSeek Harness).

Plain Python on purpose — no Qt imports, fully unit-testable.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.subprocess_utils import CREATE_NO_WINDOW, popen_hidden, run_hidden

__all__ = ["ToolError", "LocalToolbox", "TOOL_DEFINITIONS"]

MAX_READ_CHARS = None            # no artificial cut: the model sees the whole file
MAX_READ_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_CHARS = 2_000_000     # safety valve against a runaway command only
MAX_SEARCH_RESULTS = 500
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 900
MAX_WRITE_BYTES = 8 * 1024 * 1024

ACCESS_MODES = {
    "read_only": "Только чтение",
    "write_only": "Только запись (с подтверждением)",
    "full": "Полный доступ (без подтверждений)",
}
# Compact labels for the header chip; the full text stays in the menu/tooltip.
ACCESS_SHORT = {
    "read_only": "Чтение",
    "write_only": "Запись",
    "full": "Полный",
}


def normalize_access_mode(value):
    return value if value in ACCESS_MODES else "read_only"

# How a tool is confirmed before it runs: read-only tools never ask.
_CONFIRM_POLICY = {
    "read_file": False,
    "list_directory": False,
    "search_in_project": False,
    "write_file": True,
    "run_terminal_command": True,
    "open_application": True,
}


def _tool(name: str, description: str, properties: Dict[str, Any],
          required: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    _tool(
        "read_file",
        "Прочитать текстовый файл проекта. Путь указывается относительно корня проекта. "
        "Большой файл можно читать частями: offset (первая строка, с 1) и limit (сколько строк).",
        {"path": {"type": "string", "description": "Путь к файлу относительно корня проекта"},
         "offset": {"type": "integer",
                    "description": "С какой строки начинать (1 — начало файла)"},
         "limit": {"type": "integer",
                   "description": "Сколько строк вернуть (0 — до конца файла)"}},
        ["path"],
    ),
    _tool(
        "list_directory",
        "Показать содержимое каталога проекта (файлы и подкаталоги).",
        {"path": {"type": "string",
                  "description": "Каталог относительно корня; '.' — корень проекта"}},
        ["path"],
    ),
    _tool(
        "search_in_project",
        "Найти строку или регулярное выражение в файлах проекта и вернуть совпадения с путями и строками.",
        {"query": {"type": "string", "description": "Искомый текст"},
         "glob": {"type": "string",
                  "description": "Необязательная маска файлов, например '*.py'"}},
        ["query"],
    ),
    _tool(
        "write_file",
        "Создать или полностью перезаписать файл проекта. Требует подтверждения пользователя.",
        {"path": {"type": "string", "description": "Путь относительно корня проекта"},
         "content": {"type": "string", "description": "Новое содержимое файла"}},
        ["path", "content"],
    ),
    _tool(
        "run_terminal_command",
        "Выполнить команду в терминале проекта и вернуть вывод и код возврата. "
        "Требует подтверждения пользователя.",
        {"command": {"type": "string", "description": "Команда оболочки"},
         "timeout_sec": {"type": "integer",
                         "description": "Таймаут в секундах (по умолчанию 30)"}},
        ["command"],
    ),
    _tool(
        "open_application",
        "Запустить приложение или утилиту (например, тестовый сервер или GUI-клиент). "
        "Требует подтверждения пользователя.",
        {"program": {"type": "string", "description": "Исполняемый файл или команда"},
         "args": {"type": "string", "description": "Аргументы через пробел"}},
        ["program"],
    ),
]


class ToolError(RuntimeError):
    """Raised for a rejected or failed tool call (message is user-facing)."""


class LocalToolbox:
    """Executes agent tool calls inside one project root."""

    def __init__(self, project_root: Optional[str],
                 confirm: Optional[Callable[[str, str, str], bool]] = None,
                 allow_write: bool = True,
                 allow_commands: bool = True,
                 access_mode: str = "full"):
        self.root = Path(project_root).resolve() if project_root else None
        self.confirm = confirm
        self.allow_write = allow_write
        self.allow_commands = allow_commands
        self.access_mode = normalize_access_mode(access_mode)

    def _allowed(self, name):
        if name in ("read_file", "list_directory", "search_in_project"):
            return self.access_mode != "write_only"
        if name == "write_file":
            return self.allow_write and self.access_mode != "read_only"
        if name in ("run_terminal_command", "open_application"):
            return self.allow_commands and self.access_mode == "full"
        return False

    # -- helpers -------------------------------------------------------
    def definitions(self) -> List[Dict[str, Any]]:
        """Tool definitions filtered by the user's permission settings."""
        allowed = []
        for definition in TOOL_DEFINITIONS:
            name = definition["function"]["name"]
            if not self._allowed(name):
                continue
            allowed.append(definition)
        return allowed

    def _resolve(self, raw: str) -> Path:
        if self.root is None:
            raise ToolError("Проект не открыт — работа с файлами недоступна.")
        text = str(raw or ".").strip().strip('"').strip("'")
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise ToolError(f"Не удалось разрешить путь: {exc}") from exc
        if resolved != self.root and self.root not in resolved.parents:
            raise ToolError("Путь вне проекта: доступ разрешён только внутри проекта.")
        return resolved

    def _ask(self, name: str, details: str, title: str = "") -> None:
        """Ask the user to confirm a mutating action.

        "Полный доступ" means exactly that: the agent works without per-action
        prompts. Only the restricted modes ask (and there is a settings switch
        to disable edits/commands entirely).
        """
        if not _CONFIRM_POLICY.get(name, True):
            return
        if self.access_mode == "full":
            return
        if self.confirm is None:
            raise ToolError("Действие отклонено: подтверждение недоступно.")
        if not self.confirm(name, title or name, details):
            raise ToolError("Пользователь отклонил действие.")

    # -- tools ---------------------------------------------------------
    def read_file(self, path: str, offset: int = 0, limit: int = 0) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError(f"Файл не найден: {path}")
        try:
            if target.stat().st_size > MAX_READ_BYTES:
                raise ToolError(
                    f"Файл больше {MAX_READ_BYTES // (1024 * 1024)} МБ; читай его частями "
                    "через offset/limit.")
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ToolError(f"Не удалось прочитать файл: {exc}") from exc
        if not offset and not limit:
            return text
        lines = text.splitlines()
        start = max(1, int(offset or 1))
        count = int(limit or 0)
        end = len(lines) if count <= 0 else min(len(lines), start - 1 + count)
        chunk = "\n".join(lines[start - 1:end])
        header = f"[строки {start}–{end} из {len(lines)}]\n"
        return header + chunk

    def list_directory(self, path: str = ".") -> str:
        target = self._resolve(path)
        if not target.is_dir():
            raise ToolError(f"Каталог не найден: {path}")
        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            raise ToolError(f"Не удалось прочитать каталог: {exc}") from exc
        lines = []
        for entry in entries[:2000]:
            if entry.name.startswith(".") and entry.name not in (".pyscribe",):
                continue
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        if len(entries) > 2000:
            lines.append(f"… (показаны первые 2000 из {len(entries)})")
        if not lines:
            return "(пусто)"
        return "\n".join(lines)

    def search_in_project(self, query: str, glob: str = "") -> str:
        if not query:
            raise ToolError("Пустой запрос поиска.")
        if self.root is None:
            raise ToolError("Проект не открыт.")
        from core.ignore_rules import MAX_FILES_DEFAULT, walk_files
        pattern = glob or None
        scan = walk_files(self.root, extensions={pattern} if pattern and pattern.startswith(".") else None,
                          max_files=MAX_FILES_DEFAULT)
        results: List[str] = []
        needle = query.lower()
        for path in scan.files:
            if pattern and not path.match(pattern):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if needle in line.lower():
                    relative = path.relative_to(self.root)
                    results.append(f"{relative}:{number}: {line.strip()[:400]}")
                    if len(results) >= MAX_SEARCH_RESULTS:
                        results.append(f"… (показаны первые {MAX_SEARCH_RESULTS} совпадений, "
                                       "уточни запрос или маску файлов)")
                        return "\n".join(results)
        return "\n".join(results) if results else "Совпадений не найдено."

    def write_file(self, path: str, content: str) -> str:
        if not self.allow_write:
            raise ToolError("Редактирование файлов отключено в настройках агента.")
        target = self._resolve(path)
        payload = str(content)
        if len(payload.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ToolError("Содержимое слишком большое для записи.")
        existed = target.exists()
        preview = payload if len(payload) <= 1200 else payload[:1200] + "\n… (обрезано)"
        self._ask("write_file",
                  f"Файл: {target}\nРежим: {'перезапись' if existed else 'создание'}\n\n{preview}",
                  "Изменить файл проекта")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        except OSError as exc:
            raise ToolError(f"Не удалось записать файл: {exc}") from exc
        return f"{'Обновлён' if existed else 'Создан'} файл {path} ({len(payload)} символов)."

    def run_terminal_command(self, command: str, timeout_sec: int = DEFAULT_TIMEOUT) -> str:
        if not self.allow_commands:
            raise ToolError("Выполнение команд отключено в настройках агента.")
        if self.root is None:
            raise ToolError("Проект не открыт.")
        command = str(command or "").strip()
        if not command:
            raise ToolError("Пустая команда.")
        self._ask("run_terminal_command", f"$ {command}", "Выполнить команду в проекте")
        timeout = max(1, min(int(timeout_sec or DEFAULT_TIMEOUT), MAX_TIMEOUT))
        try:
            completed = run_hidden(
                command, shell=True, cwd=str(self.root),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"Команда не завершилась за {timeout} с и была остановлена."
        except OSError as exc:
            raise ToolError(f"Не удалось запустить команду: {exc}") from exc
        output = (completed.stdout or "") + (completed.stderr or "")
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n… (вывод обрезан)"
        return f"Код возврата: {completed.returncode}\n{output.strip() or '(нет вывода)'}"

    def open_application(self, program: str, args: str = "") -> str:
        if not self.allow_commands:
            raise ToolError("Запуск приложений отключён в настройках агента.")
        program = str(program or "").strip()
        if not program:
            raise ToolError("Не указано приложение.")
        self._ask("open_application", f"{program} {args}".strip(),
                  "Запустить приложение")
        command = program if not args else f'{program} {args}'
        try:
            # Console children of a windowed app need CREATE_NO_WINDOW anyway;
            # the extra process group makes GUI launchers detachable on Windows.
            extra = {}
            if os.name == "nt":
                extra["creationflags"] = CREATE_NO_WINDOW | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            popen_hidden(command, cwd=str(self.root or os.getcwd()), shell=True, **extra)
        except OSError as exc:
            raise ToolError(f"Не удалось запустить: {exc}") from exc
        return f"Приложение запущено: {command}"

    # -- dispatch ------------------------------------------------------
    def run(self, name: str, arguments: str) -> str:
        """Execute one tool call; *arguments* is the raw JSON the model sent."""
        handlers = {
            "read_file": self.read_file,
            "list_directory": self.list_directory,
            "search_in_project": self.search_in_project,
            "write_file": self.write_file,
            "run_terminal_command": self.run_terminal_command,
            "open_application": self.open_application,
        }
        handler = handlers.get(str(name))
        if handler is None:
            raise ToolError(f"Неизвестный инструмент: {name}")
        if not self._allowed(name):
            raise ToolError(f"Инструмент {name} запрещён настройками доступа агента.")
        try:
            payload = json.loads(arguments) if arguments else {}
        except ValueError as exc:
            raise ToolError(f"Некорректные аргументы инструмента: {exc}") from exc
        if not isinstance(payload, dict):
            raise ToolError("Аргументы инструмента должны быть объектом JSON.")
        try:
            return handler(**payload)
        except TypeError as exc:
            raise ToolError(f"Неверные аргументы для {name}: {exc}") from exc
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as tool output
            raise ToolError(f"Ошибка инструмента {name}: {exc}") from exc
