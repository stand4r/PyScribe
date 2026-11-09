"""PyScribe AI agent panel — DeepSeek Harness / opencode style chat UI.

Layout reference (measured from DeepSeek Harness):

* transcript is a *centered column* (~740px wide) on a near-black canvas,
* user messages are **right-aligned rounded bubbles** (#2C2C2E, 2xl radius),
* assistant messages are plain text on the canvas with **muted step chips**
  above them (``> Ran commands``, ``Read images``) instead of a loud header,
* the composer is a **floating rounded box** (#2C2C2E, ~1.6xl radius) pinned to
  the bottom, with the placeholder as the main affordance and a compact toolbar
  row (``+`` / context / send) inside it,
* chrome is quiet: no neon accents, no coloured headers, 13-14px text.

The panel keeps the same public API used by ``ModernMainWindow`` and the tests
(``send_message``, ``send_with_context``, ``apply_last_code``,
``copy_last_answer``, ``stop_request``, ``clear_conversation``, ``refresh_status``).
"""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from core.logging_config import get_logger
from design.icons import codicon_icon
from services.ai_commands import COMMANDS, find_command, parse_input
from services.ai_providers import PROVIDERS, get_provider, models_for
from services.ai_service import AIMessage, AIService, AIError, extract_code_blocks
from services.mcp_client import MCPClient, MCPServerConfig, parse_servers, run_tool

logger = get_logger("ai_agent")

SCOPE_LABELS = {
    "none": "без контекста",
    "file": "текущий файл",
    "project": "проект",
}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "target", ".idea", ".mypy_cache", ".pytest_cache",
}

# Canvas / surface colours of the reference UI.
CANVAS = "#151517"
SIDEBAR = "#1B1B1C"
SURFACE = "#2C2C2E"
SURFACE_HOVER = "#343436"
TEXT = "#E7E7E7"
TEXT_MUTED = "#8C8C8E"
TEXT_DIM = "#6E6E70"
BUBBLE_TEXT = "#EDEDED"

QUICK_ACTIONS = (
    ("Объяснить", "Объясни, что делает этот код, шаг за шагом."),
    ("Найти ошибки", "Найди возможные ошибки и потенциальные падения в этом коде."),
    ("Отрефакторить", "Отрефактори код по принципам Clean Code и покажи исправленный вариант."),
    ("Тесты", "Сгенерируй модульные тесты (pytest) для этого кода."),
    ("Документация", "Добавь docstring'и и комментарии к публичным функциям и классам."),
    ("Ревью", "Сделай короткое code review: сильные стороны и что улучшить."),
)


class _ModelsWorker(QtCore.QThread):
    """Fetches the provider's model list without blocking the UI thread."""

    loaded = QtCore.pyqtSignal(list)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, service: AIService, parent=None):
        super().__init__(parent)
        self.service = service

    def run(self):
        try:
            self.loaded.emit(list(self.service.list_models()))
        except Exception as exc:  # noqa: BLE001 - surfacing to the UI is enough
            self.failed.emit(str(exc))


class _RequestStopped(Exception):
    """Raised inside the streaming callback to abort a request immediately."""


def _dispatch_tool(local_tools, mcp_clients, name: str, args) -> str:
    """Route one tool call to the local project tools or to an MCP server."""
    if local_tools is not None:
        try:
            return local_tools.run(name, json.dumps(args or {}, ensure_ascii=False))
        except Exception as exc:  # ToolError, or a rejected confirmation
            return f"Ошибка: {exc}"
    if mcp_clients:
        try:
            return run_tool(mcp_clients, name, args)
        except Exception as exc:
            return f"Ошибка MCP-инструмента: {exc}"
    return f"Инструмент {name} недоступен."


class AIWorker(QtCore.QThread):
    """Runs one chat request off the UI thread and streams chunks."""

    chunk = QtCore.pyqtSignal(str)
    reasoning = QtCore.pyqtSignal(str)
    tool_started = QtCore.pyqtSignal(str, object)
    tool_finished = QtCore.pyqtSignal(object)
    finished_ok = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, service: AIService, prompt: str,
                 history: Optional[List[AIMessage]] = None,
                 context: Optional[str] = None, parent=None,
                 tools: Optional[List[dict]] = None,
                 tool_runner=None, on_tool=None,
                 mcp_servers: Optional[List[MCPServerConfig]] = None,
                 mcp_clients: Optional[dict] = None,
                 local_tools=None):
        super().__init__(parent)
        self.service = service
        self.prompt = prompt
        self.history = history or []
        self.context = context
        self.tools = tools or []
        self.tool_runner = tool_runner
        self.on_tool = on_tool
        self._stop = False
        self._buffer: List[str] = []
        # MCP: connecting spawns processes, so it happens here — never on the UI
        # thread. ``mcp_clients`` lets a previous request's servers be reused.
        self.mcp_servers = mcp_servers or []
        self.mcp_clients: dict = dict(mcp_clients or {})
        self.mcp_errors: List[str] = []
        # File / terminal / application tools confined to the open project.
        self.local_tools = local_tools
        # True when the provider stopped because the output budget ran out.
        self.truncated = False
        # Token accounting reported by the provider, when available.
        self.usage: dict = {}
        self.reasoning_text = ""
        self.stop_reason = ""
        self.tool_runs: list = []

    def stop(self):
        self._stop = True

    def _enforce_teaching(self, answer: str) -> str:
        """Keep a teaching-mode answer from handing over the solution.

        The prompt asks the model to hold back, but models slip. One corrective
        retry is attempted; if the retry also dumps code, the block is removed
        and a guiding question is appended instead.
        """
        from services.ai_service import (
            TEACHING_RETRY_NUDGE, enforce_teaching_rules, has_forbidden_solution)

        if not has_forbidden_solution(answer):
            return answer
        try:
            history = list(self.history) + [
                AIMessage("user", self.prompt),
                AIMessage("assistant", answer),
            ]
            retry = self.service.converse(
                TEACHING_RETRY_NUDGE, history, self.context)
        except Exception:  # noqa: BLE001 - fall back to filtering the first answer
            retry = ""
        if retry and not has_forbidden_solution(retry):
            return retry
        return enforce_teaching_rules(retry or answer, self.service)

    def _connect_mcp(self) -> List[dict]:
        tools: List[dict] = []
        for config in self.mcp_servers:
            client = self.mcp_clients.get(config.name)
            if client is None:
                client = MCPClient(config, timeout=15)
                try:
                    client.connect()
                except Exception as exc:  # noqa: BLE001
                    # Never cache a failed client: it would never be retried.
                    client.close()
                    self.mcp_errors.append(f"{config.label}: {exc}")
                    continue
                self.mcp_clients[config.name] = client
            tools.extend(tool.as_openai_tool() for tool in client.tools)
        return tools

    def run(self):
        try:
            def emit(piece: str):
                if self._stop:
                    # Unwind the streaming generator so the HTTP response is
                    # closed and the thread actually ends instead of draining
                    # the whole answer in the background.
                    raise _RequestStopped()
                self._buffer.append(piece)
                self.chunk.emit(piece)

            def emit_reasoning(piece: str):
                if self._stop or not piece:
                    return
                self.reasoning_text += piece
                self.reasoning.emit(piece)

            tools = list(self.tools)
            restricted = self.local_tools is not None and self.local_tools.access_mode != "full"
            if restricted:
                tools = []
            tool_runner = self.tool_runner
            mcp_tools: List[dict] = []
            if self.mcp_servers and not restricted:
                mcp_tools = self._connect_mcp()

            local_names = set()
            if self.local_tools is not None:
                try:
                    local_defs = self.local_tools.definitions()
                except Exception:
                    local_defs = []
                tools = tools + local_defs
                local_names = {item["function"]["name"] for item in local_defs}
            tools = tools + mcp_tools

            if restricted or local_names or self.mcp_clients:
                tool_runner = lambda name, args: _dispatch_tool(
                    self.local_tools if name in local_names else None,
                    {} if restricted else self.mcp_clients, name, args)

            def on_tool_started(name, args):
                self.tool_started.emit(name, args)
                if self.on_tool:
                    self.on_tool(name, args)

            answer = self.service.converse(
                self.prompt, self.history, self.context,
                tools=tools or None,
                tool_runner=tool_runner,
                on_text=emit,
                on_tool=on_tool_started,
                on_tool_end=lambda run: self.tool_finished.emit(run),
                on_reasoning=emit_reasoning,
                should_stop=lambda: self._stop,
            )
            if self.service.is_teaching and not self._stop:
                answer = self._enforce_teaching(answer)
            self.truncated = bool(getattr(self.service, "truncated", False))
            self.usage = dict(getattr(self.service, "last_usage", {}) or {})
            self.stop_reason = str(getattr(self.service, "last_stop_reason", "") or "")
            self.tool_runs = list(getattr(self.service, "last_tool_runs", []) or [])
            self.finished_ok.emit("" if self._stop else answer)
        except _RequestStopped:
            self.finished_ok.emit("")
        except AIError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - never crash the UI thread
            logger.exception("AI request failed")
            self.failed.emit(f"Ошибка ИИ-запроса: {exc}")


class _WidgetDocumentInterface(QtCore.QObject):
    """QTextObjectInterface that renders a QWidget inside a QTextDocument."""

    def __init__(self, widget: QtWidgets.QWidget):
        super().__init__()
        self.widget = widget

    def intrinsicSize(self, doc, pos_in_document, fmt):
        """Report the widget's size; the bubble stretches to the text width."""
        try:
            width = max(180, int(doc.textWidth()) - 24)
            bubble = self.widget
            if hasattr(bubble, "set_available_width"):
                bubble.set_available_width(width)
            bubble.setFixedWidth(width)
            # Apply the constraint and let the layout do its own measuring —
            # heightForWidth() before a layout pass returns 0 for rich text.
            if bubble.layout() is not None:
                bubble.layout().activate()
            height = max(28, bubble.sizeHint().height())
            bubble.setMinimumHeight(height)
            bubble.setMaximumHeight(height)
            bubble.resize(width, height)
            return QtCore.QSizeF(float(width), float(height))
        except RuntimeError:
            return QtCore.QSizeF(120.0, 30.0)

    def drawObject(self, painter, rect, doc, pos_in_document, fmt):
        try:
            if not self.widget.isVisible():
                self.widget.show()
            if self.widget.width() != int(rect.width()):
                self.widget.resize(int(rect.width()), int(rect.height()))
            painter.save()
            # Painter is already translated to the object origin: draw at (0,0).
            self.widget.render(painter, QtCore.QPoint(0, 0))
            painter.restore()
        except RuntimeError:
            pass


class _CompletionPopup(QtWidgets.QListWidget):
    """Inline popup for ``/`` commands and ``@`` file mentions."""

    accepted = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiCompletion")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.hide()
        self.itemClicked.connect(lambda _item: self.accepted.emit())

    def show_items(self, items, anchor: QtCore.QPoint):
        self.clear()
        for label, kind, detail in items:
            icon = {"dir": "📁", "file": "📄", "cmd": "›"}.get(kind, "•")
            item = QtWidgets.QListWidgetItem(f"{icon}  {label}")
            item.setToolTip(detail or label)
            item.setData(QtCore.Qt.UserRole, label)
            self.addItem(item)
        rows = max(1, min(len(items), 8))
        row_h = max(20, self.fontMetrics().height() + 8)
        parent = self.parentWidget()
        max_h = parent.height() if parent else 320
        height = min(rows * row_h + 6, max(120, int(max_h * 0.45)))
        width = min(max(220, parent.width() - 20 if parent else 260), 420)
        self.setGeometry(max(0, min(anchor.x(), (parent.width() if parent else width) - width)),
                         max(0, anchor.y() - height), width, height)
        self.setCurrentRow(0)
        self.show()
        self.raise_()

    def current_label(self) -> str:
        item = self.currentItem()
        return str(item.data(QtCore.Qt.UserRole)) if item is not None else ""

    def move_selection(self, delta: int):
        row = self.currentRow()
        self.setCurrentRow(max(0, min(self.count() - 1, row + delta)))

    def hide_popup(self):
        self.hide()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Tab):
            self.accepted.emit()
            return
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide_popup()
            return
        super().keyPressEvent(event)


class _TranscriptView(QtWidgets.QTextBrowser, QtGui.QTextObjectInterface):
    """Read-only transcript that can host real widgets (chat bubbles).

    PyQt5 only dispatches ``intrinsicSize``/``drawObject`` when the handler
    object also inherits ``QTextObjectInterface``, so the view implements both
    the widget and the document-object interface.
    """

    USER_OBJECT_TYPE = int(QtGui.QTextFormat.UserObject) + 10
    # Custom QTextFormat property carrying the widget itself.
    WIDGET_PROPERTY = int(QtGui.QTextFormat.UserProperty) + 1
    # Inline object height, stored on the format (also a user property).
    HEIGHT_PROPERTY = int(QtGui.QTextFormat.UserProperty) + 2
    WIDTH_PROPERTY = int(QtGui.QTextFormat.UserProperty) + 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interfaces = {}
        try:
            self.document().documentLayout().registerHandler(self.USER_OBJECT_TYPE, self)
        except Exception:
            logger.exception("Не удалось зарегистрировать обработчик объектов в чате")

    def register_widget(self, widget: QtWidgets.QWidget):
        widget.setParent(self)
        widget.hide()
        self._interfaces[id(widget)] = _WidgetDocumentInterface(widget)

    def _widget_from(self, fmt):
        widget = fmt.property(self.WIDGET_PROPERTY)
        return widget if isinstance(widget, QtWidgets.QWidget) else None

    def intrinsicSize(self, doc, posInDocument, fmt):
        widget = self._widget_from(fmt)
        if widget is None:
            return QtCore.QSizeF(1, 1)
        interface = self._interfaces.get(id(widget)) or _WidgetDocumentInterface(widget)
        self._interfaces[id(widget)] = interface
        return interface.intrinsicSize(doc, posInDocument, fmt)

    def drawObject(self, painter, rect, doc, posInDocument, fmt):
        widget = self._widget_from(fmt)
        if widget is None:
            return
        interface = self._interfaces.get(id(widget)) or _WidgetDocumentInterface(widget)
        self._interfaces[id(widget)] = interface
        interface.drawObject(painter, rect, doc, posInDocument, fmt)

class _ComposerInput(QtWidgets.QPlainTextEdit):
    """Auto-growing multi-line input (Enter sends, Shift+Enter inserts a line)."""

    submitted = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiInput")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setPlaceholderText("Спросите что-нибудь о коде")
        self.setTabChangesFocus(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._min_height = 56
        self._max_height = 210
        self.setFixedHeight(self._min_height)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        doc_height = self.document().size().height()
        margins = self.contentsMargins()
        wanted = int(doc_height) + margins.top() + margins.bottom() + 6
        wanted = max(self._min_height, min(self._max_height, wanted))
        if wanted != self.height():
            self.setFixedHeight(wanted)
            # Keep the composer anchored to the bottom while it grows.
            self.updateGeometry()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                super().keyPressEvent(event)
                return
            if event.modifiers() & QtCore.Qt.ControlModifier:
                super().keyPressEvent(event)
                return
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class _RoundActionButton(QtWidgets.QAbstractButton):
    """Circular action button painted by hand (send / stop).

    QSS ``border-radius`` on a QToolButton did not round the background here,
    so the send button looked like a blue square. Painting the circle directly
    is deterministic on Windows.
    """

    def __init__(self, glyph: str, tooltip: str = "", diameter: int = 30,
                 accent: bool = True, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._diameter = diameter
        self._accent = accent
        self.setFixedSize(diameter, diameter)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setToolTip(tooltip)

    def set_glyph(self, glyph: str):
        self._glyph = glyph
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if not self.isEnabled():
            background = QtGui.QColor("#313134")
            text_color = QtGui.QColor("#6E6E70")
        elif self._accent:
            background = QtGui.QColor("#3B82F6" if self.underMouse() else "#2F6FEB")
            text_color = QtGui.QColor("#FFFFFF")
        else:
            background = QtGui.QColor("#4A4A4C" if self.underMouse() else "#3A3A3C")
            text_color = QtGui.QColor("#E7E7E7")
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(rect)
        font = QtGui.QFont(self.font())
        font.setPointSize(max(9, int(self._diameter * 0.42)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(rect, QtCore.Qt.AlignCenter, self._glyph)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _ContextChip(QtWidgets.QToolButton):
    """Small pill in the composer toolbar (file / selection / problems)."""

    def __init__(self, text: str, tip: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setToolTip(tip)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setObjectName("aiChip")
        self.setFocusPolicy(QtCore.Qt.NoFocus)


class AIAgentPanel(QtWidgets.QWidget):
    """Chat panel for the PyScribe AI agent (DeepSeek Harness style)."""

    # Emitted (tool name, short arguments) whenever the model calls an MCP tool.
    _tool_called = QtCore.pyqtSignal(str, str)
    _approval_requested = QtCore.pyqtSignal(object, object, object, object, object)

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setObjectName("aiAgentPanel")
        self._history: List[AIMessage] = []
        self._worker: Optional[AIWorker] = None
        self._models_worker: Optional[_ModelsWorker] = None
        self._current_answer: List[str] = []
        self._stream_open = False
        # Queued prompts, connected MCP clients and added bubbles.
        self._queue: list = []
        self._mcp_clients: dict = {}
        self._bubbles: list = []
        self._last_request = None
        self._history_before_request = 0
        self._reasoning_chars = 0
        self._tool_counters: dict = {}
        self._session_root = None
        self._session_stats: Optional[dict] = None
        self._request_started: Optional[float] = None
        self._activity_label: Optional[QtWidgets.QLabel] = None
        self._tool_called.connect(self._on_tool_called)
        self._approval_requested.connect(self._on_approval_requested)
        self._build()

    def _on_tool_called(self, name: str, arguments: str):
        """MCP tool trace — one transient line while the request runs."""
        self._show_activity(f"{name}", "›")

    def _on_tool_started(self, name: str, args) -> None:
        """Show the tool currently running in one mutable activity line."""
        self._show_activity(self._tool_line(name, args), "›")
        counters = getattr(self, "_tool_counters", None)
        if counters is not None:
            counters[str(name)] = counters.get(str(name), 0) + 1

    @staticmethod
    def _tool_line(name: str, args) -> str:
        """``read_file · lib/parser.py`` — the target, never the whole JSON."""
        target = ""
        if isinstance(args, dict):
            for key in ("path", "file", "query", "command", "program"):
                value = args.get(key)
                if value:
                    target = str(value)
                    break
        target = " ".join(target.split())
        if len(target) > 72:
            target = target[:71] + "…"
        return f"{name} · {target}" if target else str(name)

    def _on_tool_finished(self, run) -> None:
        """Update the transient line; nothing stays in the transcript."""
        try:
            name = str(getattr(run, "name", "") or "")
            ok = bool(getattr(run, "ok", True))
            repeated = bool(getattr(run, "repeated", False))
            arguments = getattr(run, "arguments", {}) or {}
            output = str(getattr(run, "output", "") or "")
        except Exception:  # noqa: BLE001 - never break the transcript
            return
        if repeated:
            return
        target = ""
        if isinstance(arguments, dict):
            target = str(arguments.get("path") or arguments.get("program") or "")
        if not ok:
            first = output.strip().splitlines()[0][:160] if output.strip() else "ошибка"
            self._show_activity(f"{name}" + (f" · {target}" if target else "")
                                + f": {first}", "✗")
            return
        if name == "write_file":
            verb = "создан" if "Создан" in output else "изменён"
            self._show_activity(f"{verb} · {target or 'файл'}", "✓")
        elif name == "run_terminal_command":
            first = output.strip().splitlines()[0][:80] if output.strip() else "готово"
            self._show_activity(first, "✓")

    @staticmethod
    def _short_json(value) -> str:
        try:
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value)
        text = text or ""
        if text == "{}":
            return ""
        return text[:300] + ("…" if len(text) > 300 else "")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Transcript: a scroll area whose content is a centered column.
        self.transcript = QtWidgets.QScrollArea()
        self.transcript.setObjectName("aiTranscript")
        self.transcript.setWidgetResizable(True)
        self.transcript.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.transcript.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Messages are real widgets in a vertical layout (Telegram style).
        # A QTextDocument cannot measure rich-text bubbles reliably, and plain
        # labels scroll natively inside a scroll area, so no document layout is
        # involved in positioning messages.
        self.chat = QtWidgets.QWidget()
        self.chat.setObjectName("aiChatColumn")
        self.messages = QtWidgets.QVBoxLayout(self.chat)
        self.messages.setContentsMargins(10, 8, 10, 8)
        self.messages.setSpacing(2)
        self.messages.addStretch(1)

        column_host = QtWidgets.QWidget()
        column_host.setObjectName("aiColumnHost")
        host_layout = QtWidgets.QHBoxLayout(column_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        host_layout.addWidget(self.chat)
        self.transcript.setWidget(column_host)
        root.addWidget(self.transcript, 1)

        # No quick-action button grid: the secondary actions live in the
        # right-click menu (see _show_context_menu) to keep the panel quiet.
        root.addWidget(self._build_composer())

        self._append_welcome()
        self._welcome_visible = True
        self.refresh_status()
        try:
            self._refresh_menus()
        except Exception:
            logger.exception("Не удалось построить меню модели/контекста")
        # A saved "project" scope with no project open would silently fall back
        # to the editor folder; normalise it at construction time.
        try:
            self.sync_scope_with_project()
        except Exception:
            logger.exception("Не удалось согласовать контекст с проектом")

    # ------------------------------------------------------------------
    # Context menu (right click)
    # ------------------------------------------------------------------
    def _build_context_menu(self) -> QtWidgets.QMenu:
        """Actions that used to be buttons, now on right click."""
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("aiContextMenu")

        quick = menu.addMenu("Быстрые действия")
        quick.setObjectName("aiContextMenu")
        for label, prompt in QUICK_ACTIONS:
            action = quick.addAction(label)
            action.setToolTip(prompt)
            action.triggered.connect(lambda _=False, p=prompt: self.send_with_context(p))

        menu.addSeparator()
        act_stop = menu.addAction("Остановить ответ")
        act_stop.setEnabled(self._worker is not None)
        act_stop.triggered.connect(self.stop_request)

        act_retry = menu.addAction("Повторить запрос")
        act_retry.setEnabled(getattr(self, "_last_request", None) is not None
                             and self._worker is None)
        act_retry.triggered.connect(self.regenerate_last)

        act_copy = menu.addAction("Скопировать последний ответ")
        act_copy.setEnabled(bool("".join(self._current_answer)))
        act_copy.triggered.connect(self.copy_last_answer)

        act_apply = menu.addAction("Применить код из ответа")
        act_apply.setEnabled(bool(extract_code_blocks("".join(self._current_answer))))
        act_apply.triggered.connect(self.apply_last_code)

        act_export = menu.addAction("Экспортировать диалог…")
        act_export.setEnabled(bool(self.transcript_text().strip()))
        act_export.triggered.connect(self.export_conversation)

        if self.pending_count():
            act_clear_queue = menu.addAction(f"Очистить очередь ({self.pending_count()})")
            act_clear_queue.triggered.connect(self.clear_queue)

        menu.addSeparator()
        ctx = menu.addMenu("Контекст запроса")
        ctx.setObjectName("aiContextMenu")
        for box, label, tip in (
            (self.include_file, "Текущий файл", "Прикреплять содержимое файла"),
            (self.include_selection, "Выделение / строка", "Прикреплять выделенный фрагмент"),
            (self.include_problems, "Проблемы проекта", "Прикреплять список проблем"),
        ):
            action = ctx.addAction(label)
            action.setCheckable(True)
            action.setChecked(box.isChecked())
            action.setToolTip(tip)
            action.toggled.connect(box.setChecked)

        menu.addSeparator()
        act_clear = menu.addAction("Новый диалог")
        act_clear.triggered.connect(self.clear_conversation)
        act_settings = menu.addAction("Настройки ИИ-агента…")
        act_settings.triggered.connect(self._open_settings)
        return menu

    def _show_context_menu(self, global_pos: QtCore.QPoint):
        menu = self._build_context_menu()
        menu.exec_(global_pos)
        menu.deleteLater()

    def contextMenuEvent(self, event):
        self._show_context_menu(event.globalPos())
        event.accept()

    def _build_header(self) -> QtWidgets.QWidget:
        header = QtWidgets.QFrame()
        header.setObjectName("aiHeader")
        try:
            from app.ui_scale import scale_px
            header.setFixedHeight(scale_px(40))
        except Exception:  # noqa: BLE001 - headless/tests
            header.setFixedHeight(40)
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        title = QtWidgets.QLabel("ИИ-агент")
        title.setObjectName("aiHeaderTitle")
        layout.addWidget(title)

        # Quiet marker shown only while the Socratic mode is active.
        self.mode_badge = QtWidgets.QLabel("наставник")
        self.mode_badge.setObjectName("aiModeBadge")
        self.mode_badge.setToolTip("Агент ведёт вопросами и не выдаёт готовое решение")
        self.mode_badge.hide()
        layout.addWidget(self.mode_badge)
        layout.addStretch(1)

        from services.agent_tools import ACCESS_MODES

        # Per-request switches: reasoning depth and agent permissions. They sit
        # on the same row as the title so the header stays one compact strip.
        self.reasoning_btn = QtWidgets.QToolButton()
        self.reasoning_btn.setObjectName("aiAccessMode")
        self.reasoning_btn.setAccessibleName("Уровень размышлений")
        self.reasoning_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.reasoning_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.reasoning_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.reasoning_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                          QtWidgets.QSizePolicy.Fixed)
        self._reasoning_menu = QtWidgets.QMenu(self.reasoning_btn)
        self.reasoning_btn.setMenu(self._reasoning_menu)
        layout.addWidget(self.reasoning_btn)

        self.access_button = QtWidgets.QToolButton()
        self.access_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                          QtWidgets.QSizePolicy.Fixed)
        self.access_button.setObjectName("aiAccessMode")
        self.access_button.setAccessibleName("Разрешения агента")
        self.access_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.access_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.access_button)
        menu.setObjectName("aiAccessMenu")
        group = QtWidgets.QActionGroup(menu)
        group.setExclusive(True)
        self._access_actions = {}
        for key, label in ACCESS_MODES.items():
            action = menu.addAction(label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda checked=False, mode=key: self._change_access_mode(mode))
            self._access_actions[key] = action
        menu.aboutToShow.connect(self._sync_access_button)
        self.access_button.setMenu(menu)
        self._sync_access_button()
        layout.addWidget(self.access_button)

        self.status_dot = QtWidgets.QLabel("")
        self.status_dot.setObjectName("aiStatusDot")
        layout.addWidget(self.status_dot)

        # A single "more" button opens the same right-click menu, so the panel
        # keeps only one visible control besides the composer.
        self.more_btn = self._icon_button("more", "Действия ИИ-агента")
        self.more_btn.clicked.connect(
            lambda: self._show_context_menu(self.more_btn.mapToGlobal(QtCore.QPoint(0, self.more_btn.height())))
        )
        layout.addWidget(self.more_btn)

        # Kept for API compatibility with callers that hide the settings entry.
        self.settings_btn = self.more_btn
        self.clear_btn = self.more_btn
        return header

    def _icon_button(self, icon_name, tip):
        button = QtWidgets.QToolButton()
        button.setObjectName("aiIconButton")
        button.setIcon(codicon_icon(icon_name, 16, "#A0A0A2"))
        button.setIconSize(QtCore.QSize(16, 16))
        button.setFixedSize(24, 24)
        button.setToolTip(tip)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setAutoRaise(True)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        return button

    def _build_composer(self) -> QtWidgets.QWidget:
        """Floating rounded composer with an inline toolbar (DSH style)."""
        wrapper = QtWidgets.QWidget()
        wrapper.setObjectName("aiComposerWrap")
        outer_layout = QtWidgets.QVBoxLayout(wrapper)
        outer_layout.setContentsMargins(10, 0, 10, 8)
        outer_layout.setSpacing(4)

        card_row = QtWidgets.QWidget()
        wrap_layout = QtWidgets.QHBoxLayout(card_row)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)
        wrap_layout.addStretch(1)

        self.composer = QtWidgets.QFrame()
        self.composer.setObjectName("aiComposer")
        box = QtWidgets.QVBoxLayout(self.composer)
        box.setContentsMargins(12, 10, 10, 8)
        box.setSpacing(8)

        self.input = _ComposerInput(self.composer)
        self.input.setPlaceholderText("Спросите что-нибудь…")
        self.input.setMinimumHeight(44)
        self.input.submitted.connect(self.send_message)
        self.input.textChanged.connect(self._on_composer_text_changed)
        self.input.installEventFilter(self)
        self.input.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.input.mapToGlobal(pos))
        )
        box.addWidget(self.input)
        # Inline completion for "/" commands and "@" mentions.
        self.completion = _CompletionPopup(self)
        self.completion.accepted.connect(self._accept_completion)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        # Context flags stay available to the code, but no longer occupy the
        # composer: they are toggled from the right-click menu.
        self.include_file = _ContextChip("Файл", "Прикрепить содержимое текущего файла")
        self.include_selection = _ContextChip("Выделение", "Прикрепить выделенный фрагмент")
        self.include_problems = _ContextChip("Проблемы", "Прикрепить список проблем проекта")
        for chip in (self.include_file, self.include_selection, self.include_problems):
            chip.hide()

        self.scope_btn = QtWidgets.QToolButton()
        self.scope_btn.setObjectName("aiScopeButton")
        self.scope_btn.setToolTip("Что прикреплять к запросу (Ctrl+Shift+C)")
        self.scope_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.scope_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.scope_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._scope_menu = QtWidgets.QMenu(self.scope_btn)
        self.scope_btn.setMenu(self._scope_menu)
        toolbar.addWidget(self.scope_btn)

        self.model_btn = QtWidgets.QToolButton()
        self.model_btn.setObjectName("aiModelButton")
        self.model_btn.setToolTip("Выбор модели (Ctrl+Shift+M)")
        self.model_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.model_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.model_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._model_menu = QtWidgets.QMenu(self.model_btn)
        self.model_btn.setMenu(self._model_menu)
        toolbar.addWidget(self.model_btn)
        toolbar.addStretch()

        self.stop_btn = _RoundActionButton("■", "Остановить ответ (Esc)", 30, accent=False)
        self.stop_btn.setToolTip("Остановить ответ (Esc)")
        self.stop_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.stop_btn.setVisible(False)
        self.stop_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.stop_btn.clicked.connect(self.stop_request)
        toolbar.addWidget(self.stop_btn)

        self.send_btn = _RoundActionButton("↑", "Отправить (Enter)", 30, accent=True)
        self.send_btn.setToolTip("Отправить (Enter)")
        self.send_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.send_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.send_btn.clicked.connect(self.send_message)
        toolbar.addWidget(self.send_btn)
        box.addLayout(toolbar)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("aiStatusLine")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        box.addWidget(self.status_label)

        # Queued-message hint (only visible while a queue exists).
        self.queue_chip = QtWidgets.QLabel("")
        self.queue_chip.setObjectName("aiQueueChip")
        self.queue_chip.setVisible(False)
        box.addWidget(self.queue_chip)

        wrap_layout.addWidget(self.composer, 100)
        wrap_layout.addStretch(1)
        outer_layout.addWidget(card_row)

        # Session metrics under the composer, mirroring the harness status line:
        # answers · steps · tok/s · tokens · cache hit rate.
        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setObjectName("aiStatsLine")
        self.stats_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.stats_label.setVisible(False)
        outer_layout.addWidget(self.stats_label)
        return wrapper

    # ------------------------------------------------------------------
    # Status / configuration
    # ------------------------------------------------------------------
    def _service(self) -> AIService:
        from utils.settings_manager import get_settings_manager
        settings = get_settings_manager().get_all_settings()
        return AIService(config=settings)

    # ------------------------------------------------------------------
    # MCP
    # ------------------------------------------------------------------
    def _mcp_server_configs(self) -> List[MCPServerConfig]:
        """Configured MCP servers (parsing only — cheap, safe on the UI thread)."""
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        if not sm.get_setting("ai_mcp_enabled", True):
            return []
        try:
            servers = parse_servers(sm.get_setting("ai_mcp_servers", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP config: %s", exc)
            self._append_step(f"Конфигурация MCP некорректна: {exc}", "!")
            return []
        return [s for s in servers if s.enabled]

    def _project_root(self) -> Optional[str]:
        """Root of the open project, or None when nothing is open."""
        window = self.window()
        project = getattr(window, "current_project", None)
        root = getattr(project, "root_path", None) if project else None
        if root and Path(str(root)).is_dir():
            return str(Path(str(root)))
        return None

    def _access_mode(self):
        from services.agent_tools import normalize_access_mode
        from utils.settings_manager import get_settings_manager
        return normalize_access_mode(get_settings_manager().get_setting("ai_access_mode", "full"))

    def _sync_access_button(self):
        from services.agent_tools import ACCESS_MODES, ACCESS_SHORT
        mode = self._access_mode()
        self.access_button.setText(ACCESS_SHORT.get(mode, ACCESS_MODES[mode]))
        self.access_button.setToolTip("Разрешения агента: " + ACCESS_MODES[mode] +
                                      ". Изменения применяются со следующего запроса.")
        for key, action in self._access_actions.items():
            action.setChecked(key == mode)

    def _change_access_mode(self, mode):
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_access_mode"] = mode
        sm.save_settings()
        self._sync_access_button()

    def _build_local_tools(self):
        """Project tools (files, terminal, apps) for the agent."""
        from services.agent_tools import LocalToolbox
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        return LocalToolbox(
            self._project_root(),
            confirm=self._request_tool_approval,
            allow_write=bool(sm.get_setting("ai_allow_file_edits", True)),
            allow_commands=bool(sm.get_setting("ai_allow_commands", True)),
            access_mode=self._access_mode(),
        )

    def _request_tool_approval(self, kind: str, title: str, details: str) -> bool:
        """Ask the user to allow a mutating tool call (called from the worker)."""
        import threading
        event = threading.Event()
        result = {"ok": False}
        try:
            self._approval_requested.emit(kind, title, details, event, result)
        except RuntimeError:
            return False
        event.wait(180)
        return bool(result.get("ok"))

    def _on_approval_requested(self, kind, title, details, event, result):
        """Show the confirmation dialog on the UI thread."""
        try:
            box = QtWidgets.QMessageBox(self.window())
            box.setIcon(QtWidgets.QMessageBox.Question)
            box.setWindowTitle("Подтверждение действия агента")
            box.setText(str(title))
            box.setInformativeText(str(details)[:1500])
            if len(str(details)) > 1500:
                box.setDetailedText(str(details))
            box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            box.setDefaultButton(QtWidgets.QMessageBox.No)
            box.button(QtWidgets.QMessageBox.Yes).setText("Разрешить")
            box.button(QtWidgets.QMessageBox.No).setText("Отклонить")
            result["ok"] = box.exec_() == QtWidgets.QMessageBox.Yes
        finally:
            event.set()

    def _collect_tools(self) -> List[dict]:
        """Tools of already-connected MCP servers (no blocking I/O).

        Connection happens inside AIWorker: spawning a server and waiting for
        its handshake on the UI thread froze the window for up to 25 s.
        """
        clients = getattr(self, "_mcp_clients", {}) or {}
        tools = []
        for client in clients.values():
            tools.extend(tool.as_openai_tool() for tool in client.tools)
        return tools

    def _refresh_mode_menu(self, current: str = None):
        """Rebuild the solve/teach picker and keep the button label in sync."""
        from services.ai_service import (
            TEACHING_MODE_HINTS, TEACHING_MODE_LABELS,
            TEACH_STRICTNESS_HINTS, TEACH_STRICTNESS_LABELS)

        service = self._service()
        current = current or service.mode
        if not hasattr(self, "_mode_menu") or self._mode_menu is None:
            self._mode_menu = QtWidgets.QMenu(self)
        self._mode_menu.clear()
        self._mode_actions = {}
        for key in ("solve", "teach"):
            action = self._mode_menu.addAction(TEACHING_MODE_LABELS[key])
            action.setCheckable(True)
            action.setChecked(key == current)
            action.setToolTip(TEACHING_MODE_HINTS[key])
            action.setData(key)
            action.triggered.connect(lambda _=False, k=key: self.set_mode(k))
            self._mode_actions[key] = action

        # Strictness applies only to the tutor; keep it visible but disabled
        # in solve mode so its purpose is discoverable.
        self._mode_menu.addSeparator()
        strictness_menu = self._mode_menu.addMenu("Строгость наставника")
        strictness_menu.setObjectName("aiContextMenu")
        strictness_menu.setEnabled(current == "teach")
        level = service.teach_strictness
        self._strictness_actions = {}
        for key in ("soft", "normal", "strict"):
            action = strictness_menu.addAction(TEACH_STRICTNESS_LABELS[key])
            action.setCheckable(True)
            action.setChecked(key == level)
            action.setToolTip(TEACH_STRICTNESS_HINTS[key])
            action.setData(key)
            action.triggered.connect(
                lambda _=False, k=key: self.set_strictness(k))
            self._strictness_actions[key] = action
        mode_btn = getattr(self, "mode_btn", None)
        if mode_btn is not None:
            mode_btn.setText(TEACHING_MODE_LABELS.get(current, current))
            mode_btn.setToolTip(TEACHING_MODE_HINTS.get(current, ""))
            self._set_button_label(mode_btn, TEACHING_MODE_LABELS.get(current, current))
            # QSS colouring for the tutor mode is driven by a dynamic property.
            mode_btn.setProperty("teach", "true" if current == "teach" else "false")
            try:
                mode_btn.style().unpolish(mode_btn)
                mode_btn.style().polish(mode_btn)
                mode_btn.update()
            except Exception:
                pass
        self._fit_composer_buttons()
        # A quiet marker in the panel header while the tutor mode is on.
        badge = getattr(self, "mode_badge", None)
        if badge is not None:
            badge.setVisible(current == "teach")
            if current == "teach":
                short = {"soft": "мягкий", "normal": "обычный",
                         "strict": "строгий"}.get(level, level)
                badge.setText(f"наставник · {short}")
                badge.setToolTip(
                    f"Наставник, строгость «{TEACH_STRICTNESS_LABELS.get(level)}»: "
                    f"{TEACH_STRICTNESS_HINTS.get(level, '')}")

    def _set_button_label(self, button, text: str):
        """Remember the full label so it can be elided when space is short."""
        button._full_label = text
        button.setText(text)

    def _fit_composer_buttons(self):
        """Fit the three composer chips next to the send button.

        Three pickers overflowed a narrow sidebar and the last chip was cut off
        mid-word. Here each chip gets an explicit maximum width and an elided
        label, so the row always fits instead of being clipped by the layout.
        """
        composer = getattr(self, "composer", None)
        buttons = [getattr(self, name, None)
                   for name in ("mode_btn", "scope_btn", "model_btn")]
        buttons = [b for b in buttons if b is not None]
        if composer is None or not buttons:
            return
        PAD = 18          # 8 px padding left/right + 2 px border from the QSS
        SPACING = 6
        send_width = self.send_btn.width() if hasattr(self, "send_btn") else 28
        composer_width = composer.width()
        if composer_width < 120:
            composer_width = max(120, self.width() - 20)
        available = composer_width - 26 - send_width - SPACING * len(buttons) - 6
        if available <= 0:
            return

        labels = {b: getattr(b, "_full_label", b.text()) for b in buttons}

        def _needed(button) -> int:
            metrics = button.fontMetrics()
            advance = metrics.horizontalAdvance(labels[button])
            if advance <= 0:
                advance = len(labels[button]) * 7   # no usable font metrics
            return advance + PAD

        needed = {b: _needed(b) for b in buttons}
        total = sum(needed.values())

        if total <= available:
            for button in buttons:
                button.setMaximumWidth(16777215)
                if button.text() != labels[button]:
                    button.setText(labels[button])
            return

        # Give the model name the leftover space: it is the longest label and
        # the most acceptable one to truncate.
        model = getattr(self, "model_btn", None)
        others = [b for b in buttons if b is not model]
        fixed = sum(needed[b] for b in others)
        budgets = {}
        if model is not None and fixed + 70 <= available:
            for button in others:
                budgets[button] = needed[button]
            budgets[model] = max(70, available - fixed)
        else:
            ratio = available / float(total)
            for button in buttons:
                budgets[button] = max(52, int(needed[button] * ratio))

        for button in buttons:
            budget = budgets[button]
            text_budget = max(20, budget - PAD)
            metrics = button.fontMetrics()
            text = metrics.elidedText(labels[button], QtCore.Qt.ElideRight,
                                      text_budget)
            if not text or text == labels[button]:
                text = self._manual_elide(labels[button], text_budget)
            button.setText(text)
            button.setMaximumWidth(budget)

    @staticmethod
    def _manual_elide(text: str, budget_px: int) -> str:
        """Fallback elision when font metrics are unavailable."""
        if budget_px <= 0:
            return text
        # Roughly 7 px per character at the chip font size.
        keep = max(3, budget_px // 7)
        if keep >= len(text):
            return text
        return text[:keep].rstrip() + "…"

    def set_mode(self, mode: str) -> bool:
        """Switch the agent between "solve" and "teach" and persist it."""
        from services.ai_service import TEACHING_MODE_LABELS
        mode = str(mode or "").strip().lower()
        if mode not in TEACHING_MODE_LABELS:
            self._append_notice(
                "Неизвестный режим. Доступно: /mode solve или /mode teach.", "warn")
            return False
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_mode"] = mode
        sm.save_settings()
        self._refresh_mode_menu(mode)
        self._append_step(f"Режим: {TEACHING_MODE_LABELS[mode]}", "◆")
        return True

    def set_strictness(self, level: str) -> bool:
        """Set how much code the tutor may show: soft | normal | strict."""
        from services.ai_service import (
            TEACH_STRICTNESS_HINTS, TEACH_STRICTNESS_LABELS)
        level = str(level or "").strip().lower()
        if level not in TEACH_STRICTNESS_LABELS:
            self._append_notice(
                "Неизвестная строгость. Доступно: /strictness soft|normal|strict.",
                "warn")
            return False
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_teach_strictness"] = level
        sm.save_settings()
        self._refresh_mode_menu()
        self._append_step(
            f"Строгость наставника: {TEACH_STRICTNESS_LABELS[level]} "
            f"({TEACH_STRICTNESS_HINTS[level]})", "◆")
        return True

    # ------------------------------------------------------------------
    # Reasoning depth (auto / none / low / medium / high)
    # ------------------------------------------------------------------
    def _reasoning_effort(self) -> str:
        from services.ai_service import REASONING_EFFORTS
        from utils.settings_manager import get_settings_manager
        value = str(get_settings_manager().get_setting("ai_reasoning_effort", "auto") or "auto")
        value = value.strip().lower()
        return value if value in REASONING_EFFORTS else "auto"

    def _refresh_reasoning_menu(self):
        from services.ai_service import (REASONING_EFFORTS, REASONING_HINTS,
                                         REASONING_LABELS, REASONING_SHORT)
        button = getattr(self, "reasoning_btn", None)
        if button is None:
            return
        current = self._reasoning_effort()
        self._reasoning_menu.clear()
        self._reasoning_actions = {}
        for key in REASONING_EFFORTS:
            action = self._reasoning_menu.addAction(REASONING_LABELS[key])
            action.setCheckable(True)
            action.setChecked(key == current)
            action.setToolTip(REASONING_HINTS[key])
            action.setData(key)
            action.triggered.connect(
                lambda _=False, k=key: self._set_reasoning_effort(k))
            self._reasoning_actions[key] = action
        self._refresh_reasoning_label()
        button.setToolTip("Уровень размышлений: " + REASONING_LABELS[current]
                          + " — " + REASONING_HINTS[current])

    def _refresh_reasoning_label(self) -> None:
        """«Мысли: Авто» on a wide panel, compact «Авто» on a narrow one."""
        button = getattr(self, "reasoning_btn", None)
        if button is None:
            return
        from services.ai_service import REASONING_SHORT
        current = self._reasoning_effort()
        short = REASONING_SHORT.get(current, current)
        text = ("Мысли: " + short) if self.width() >= 430 else short
        self._set_button_label(button, text)

    def _set_reasoning_effort(self, level: str) -> bool:
        from services.ai_service import (REASONING_EFFORTS, REASONING_HINTS,
                                         REASONING_LABELS)
        level = str(level or "").strip().lower()
        aliases = {"off": "none", "disabled": "none", "default": "auto",
                   "minimal": "low", "max": "high"}
        level = aliases.get(level, level)
        if level not in REASONING_EFFORTS:
            self._append_notice(
                "Неизвестный уровень размышлений. Доступно: "
                "/reasoning auto|none|low|medium|high", "warn")
            return False
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_reasoning_effort"] = level
        sm.save_settings()
        self._refresh_reasoning_menu()
        self._append_step(
            f"Размышления: {REASONING_LABELS[level]} — {REASONING_HINTS[level]}", "◆")
        return True

    def _refresh_menus(self):
        """Rebuild the model and context pickers from current settings.

        The context list is a *radio* group: exactly one scope can be active,
        never two at once. Providers whose API has no key are not offered.
        """
        service = self._service()
        self._load_provider_keys()
        self._sync_access_button()
        current_scope = self._scope()

        # Context scope — exclusive selection.
        self._scope_menu.clear()
        self._scope_group = QtWidgets.QActionGroup(self)
        self._scope_group.setExclusive(True)
        for key, label in SCOPE_LABELS.items():
            action = self._scope_menu.addAction(label)
            action.setCheckable(True)
            action.setActionGroup(self._scope_group)
            action.setChecked(key == current_scope)
            action.setData(key)
            action.triggered.connect(lambda _=False, k=key: self._set_scope(k))
        self._scope_actions = {a.data(): a for a in self._scope_menu.actions()}
        self._set_button_label(self.scope_btn,
                               SCOPE_LABELS.get(current_scope, current_scope))
        self.scope_btn.setToolTip("Контекст запроса: " + SCOPE_LABELS.get(current_scope, ""))

        self._refresh_mode_menu(service.mode)
        self._refresh_reasoning_menu()

        # Models: only providers with a usable API (key present, or local server).
        self._model_menu.clear()
        spec = service.provider
        ready = {s.key for s in PROVIDERS.values() if self._provider_ready(s)}
        if spec.key not in ready and not spec.local:
            # The active provider has no key: say so instead of listing models
            # that cannot answer.
            warn = self._model_menu.addAction("Нет API-ключа для " + spec.label)
            warn.setEnabled(False)
            hint = self._model_menu.addAction("Настройки → ИИ-агент")
            hint.triggered.connect(self._open_settings)

        if spec.key in ready:
            head = self._model_menu.addAction(spec.label)
            head.setEnabled(False)
            self._model_menu.addSeparator()
            for model in models_for(spec.key):
                label = model.label + (" · бесплатно" if model.free else "")
                action = self._model_menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(model.id == service.model)
                action.setToolTip(model.id + ((" — " + model.note) if model.note else ""))
                action.triggered.connect(lambda _=False, m=model.id: self._set_model(m))
            self._model_menu.addSeparator()

        for other in PROVIDERS.values():
            if other.key == spec.key or not other.models:
                continue
            if other.key not in ready:
                continue
            sub = self._model_menu.addMenu(other.label)
            for model in other.models:
                act = sub.addAction(model.label + (" · бесплатно" if model.free else ""))
                act.setToolTip(model.id)
                act.triggered.connect(
                    lambda _=False, p=other.key, m=model.id: self._switch_provider_model(p, m)
                )
        fetch = self._model_menu.addAction("Загрузить список моделей…")
        fetch.triggered.connect(lambda: self._show_models(service))
        self.refresh_model_label()

    def _load_provider_keys(self):
        """Collect which providers already have an API key configured."""
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        settings = sm.get_all_settings()
        keys = {str(settings.get("ai_provider") or "deepseek"):
                str(settings.get("ai_api_key") or "").strip()}
        # Optional per-provider key store: {"openai": "sk-...", "gemini": "AIza..."}
        extra = settings.get("ai_provider_keys") or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                if str(value or "").strip():
                    keys[str(key)] = str(value).strip()
        self._provider_keys = keys

    def _switch_provider_model(self, provider_key: str, model_id: str):
        from utils.settings_manager import get_settings_manager
        spec = get_provider(provider_key)
        sm = get_settings_manager()
        sm.settings["ai_provider"] = spec.key
        sm.settings["ai_base_url"] = spec.base_url
        sm.settings["ai_model"] = model_id
        sm.save_settings()
        self._refresh_menus()
        self.refresh_status()
        self._append_step(f"{spec.label} · {model_id}")

    def _provider_ready(self, spec) -> bool:
        """A provider appears in the picker only when its API is usable."""
        if spec.local:
            return True          # local servers need no key
        key = getattr(self, "_provider_keys", {}).get(spec.key, "")
        return bool(key)

    def refresh_model_label(self):
        service = self._service()
        model = service.model or "модель не выбрана"
        self._set_button_label(self.model_btn, model)
        self.model_btn.setToolTip(f"{service.provider.label} · {service.model}")
        self._fit_composer_buttons()

    def refresh_status(self):
        service = self._service()
        problem = service.configuration_problem()
        if problem:
            self.status_dot.setVisible(True)
            self.status_dot.setText("⚠")
            self.status_dot.setToolTip(problem)
            self.status_label.setText(problem)
            self.status_label.setVisible(True)
            self.send_btn.setEnabled(False)
            self.send_btn.setToolTip(problem)
        else:
            self.status_dot.setVisible(False)
            self.status_label.setVisible(False)
            self.status_label.setText("")
            self.send_btn.setEnabled(self._worker is None)
            self.send_btn.setToolTip(f"Отправить ({service.model})")

    def _open_settings(self):
        if self.main_window is not None and hasattr(self.main_window, "action_open_settings"):
            self.main_window.action_open_settings()

    # ------------------------------------------------------------------
    # Transcript rendering
    # ------------------------------------------------------------------
    def _at_bottom(self) -> bool:
        bar = self.transcript.verticalScrollBar()
        return bar.value() >= bar.maximum() - 60

    def _scroll_to_bottom(self, force: bool = False):
        bar = self.transcript.verticalScrollBar()
        if force or self._at_bottom():
            bar.setValue(bar.maximum())

    def _add_message_widget(self, widget: QtWidgets.QWidget, stretch: int = 0):
        """Append a widget above the trailing stretch of the messages layout."""
        self.messages.insertWidget(self.messages.count() - 1, widget, stretch)

    def _append_html(self, html_text: str, force_scroll: bool = True):
        """Append a small rich-text line (step chips, notices)."""
        label = QtWidgets.QLabel(html_text)
        label.setTextFormat(QtCore.Qt.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._add_message_widget(label)
        if force_scroll:
            QtCore.QTimer.singleShot(0, self._scroll_to_latest)

    def _clear_welcome(self):
        """Drop the greeting as soon as a conversation starts."""
        if not getattr(self, "_welcome_visible", False):
            return
        self._welcome_visible = False
        widget = getattr(self, "_welcome_widget", None)
        self._welcome_widget = None
        if widget is not None:
            try:
                self.messages.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
            except RuntimeError:
                pass

    def _append_welcome(self):
        rows = "".join(
            f'<tr><td style="color:{TEXT_DIM}; padding:0 8px 0 0; vertical-align:top;">·</td>'
            f'<td style="color:{TEXT_MUTED}; padding:0 0 6px 0;">{html.escape(tip)}</td></tr>'
            for tip in (
                "/ — команды · @ — файл проекта",
                "/mode teach — наставник, /mode solve — обычный режим",
                "Enter — отправить · Shift+Enter — новая строка",
            )
        )
        label = QtWidgets.QLabel(
            f'<div style="margin:18px 4px 14px 4px;">'
            f'<div style="color:{TEXT}; font-size:16px; margin-bottom:8px;">Чем помочь?</div>'
            f'<table cellspacing="0" cellpadding="0">{rows}</table></div>')
        label.setObjectName("aiWelcome")
        label.setTextFormat(QtCore.Qt.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self._welcome_widget = label
        self._welcome_visible = True
        self._add_message_widget(label)

    def _insert_bubble(self, bubble, first_margin: int = 0):
        """Append a chat bubble widget to the message list, animated in."""
        self._add_message_widget(bubble)
        self._bubbles = getattr(self, "_bubbles", [])
        self._bubbles.append(bubble)
        self._relayout_transcript()
        self._animate_message_in(bubble)
        QtCore.QTimer.singleShot(0, self._scroll_to_latest)
        return bubble

    @staticmethod
    def _animate_message_in(bubble_):
        """Fade + slide a new message into place (respects reduced motion)."""
        try:
            from widgets.animations import fade_in, DURATION
            fade_in(bubble_, duration=DURATION["fast"])
        except Exception:
            pass

    def showEvent(self, event):
        """Fade the transcript in the first time the agent view is opened."""
        super().showEvent(event)
        if getattr(self, "_shown_once", False):
            return
        self._shown_once = True
        try:
            from widgets.animations import fade_in, DURATION
            fade_in(self.transcript, duration=DURATION["normal"])
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_transcript()
        self._fit_composer_buttons()
        # The composer gets its final width only after the layout pass.
        QtCore.QTimer.singleShot(0, self._fit_composer_buttons)
        self._refresh_reasoning_label()

    def _relayout_transcript(self):
        """Re-measure every bubble after a width change or a text update."""
        width = max(160, self.transcript.viewport().width())
        for bubble in getattr(self, "_bubbles", []) or []:
            try:
                if bubble.isVisible() or bubble.parent() is not None:
                    bubble.apply_width(width)
            except RuntimeError:
                continue
        if self._at_bottom():
            QtCore.QTimer.singleShot(0, self._scroll_to_latest)

    def _remove_widget(self, widget):
        """Detach and destroy a message widget."""
        try:
            self.messages.removeWidget(widget)
        except (RuntimeError, TypeError):
            pass
        bubbles = getattr(self, "_bubbles", None)
        if bubbles is not None and widget in bubbles:
            bubbles.remove(widget)
        try:
            widget.setParent(None)
            widget.deleteLater()
        except RuntimeError:
            pass

    def transcript_text(self) -> str:
        """Plain text of every message (used by tests and by "copy answer")."""
        chunks = []
        for index in range(self.messages.count()):
            item = self.messages.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None:
                continue
            if isinstance(widget, _UserBubble):
                chunks.append(widget.label.text())
            elif isinstance(widget, QtWidgets.QLabel):
                raw = widget.text()
                if widget.textFormat() == QtCore.Qt.RichText:
                    # Step chips carry inline styling; export/copy must not see
                    # raw <div style=...> markup.
                    document = QtGui.QTextDocument()
                    document.setHtml(raw)
                    chunks.append(document.toPlainText())
                else:
                    chunks.append(raw)
        return "\n".join(chunks)

    def _append_user(self, text: str) -> "_UserBubble":
        """Right-aligned Telegram-style outgoing bubble.

        QTextDocument drops ``border-radius`` on table cells, so the bubble is a
        real widget embedded through a registered ``QTextObjectInterface`` — the
        only way to get true round corners inside a QTextBrowser.
        """
        grouped = getattr(self, "_last_author", None) == "user"
        self._last_author = "user"
        self._clear_welcome()
        bubble = _UserBubble(text, side="out", grouped=grouped)
        return self._insert_bubble(bubble, 0 if grouped else 6)

    def _scroll_to_latest(self):
        try:
            bar = self.transcript.verticalScrollBar()
            bar.setValue(bar.maximum())
        except RuntimeError:
            pass

    def _append_step(self, text: str, icon: str = ">"):
        """Muted one-line activity chip (``› Ran commands``)."""
        safe = html.escape(text)
        self._append_html(
            f'<div style="margin:4px 0 4px 4px; color:{TEXT_MUTED};'
            f' font-size:{self._meta_px()}px;">'
            f'<span style="color:{TEXT_DIM};">{html.escape(icon)}</span>&nbsp;&nbsp;{safe}</div>'
        )

    @staticmethod
    def _meta_px() -> int:
        """Size of service lines — one step below the chat body, but readable."""
        try:
            from widgets.ChatMessage import chat_font_px
            return max(12, chat_font_px() - 3)
        except Exception:  # noqa: BLE001
            return 13

    # -- transient activity line (tool trace, removed when the answer lands) --
    def _show_activity(self, text: str, icon: str = "›"):
        """Show the tool that is running right now in one mutable line.

        The line is a live status, not history: it is replaced as tools change
        and removed in ``_on_finished``/``_on_failed``, so the transcript ends
        up containing only the explanation. This is what used to leave
        ``› run_terminal_command · …`` lines behind after every answer.
        """
        label = getattr(self, "_activity_label", None)
        if label is None:
            label = QtWidgets.QLabel("")
            label.setObjectName("aiActivityLine")
            label.setTextFormat(QtCore.Qt.RichText)
            label.setWordWrap(True)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self._add_message_widget(label)
            self._activity_label = label
        label.setText(
            f'<div style="margin:4px 0 4px 4px; color:{TEXT_MUTED};'
            f' font-size:{self._meta_px()}px;">'
            f'<span style="color:{TEXT_DIM};">{html.escape(icon)}</span>&nbsp;&nbsp;'
            f'{html.escape(text)}</div>')
        self._scroll_to_bottom()

    def _clear_activity(self):
        """Remove the live tool line — invoked whenever a request ends."""
        label = getattr(self, "_activity_label", None)
        self._activity_label = None
        if label is None:
            return
        try:
            self.messages.removeWidget(label)
            label.setParent(None)
            label.deleteLater()
        except RuntimeError:
            pass

    def _append_assistant(self, text: str, mark_thinking: bool = True,
                          streaming: bool = False) -> "_UserBubble":
        """Incoming Telegram-style bubble carrying the rendered markdown answer.

        When ``mark_thinking`` is set the bubble is registered as the live
        "thinking" message so it can be removed the moment the answer arrives.
        """
        grouped = getattr(self, "_last_author", None) == "assistant"
        self._last_author = "assistant"
        from widgets.ChatMessage import AssistantMessage
        body = AssistantMessage(text)
        bubble = _UserBubble(text, side="in", grouped=grouped, body_widget=body)
        bubble.copy_requested.connect(self._copy_bubble_text)
        bubble.regenerate_requested.connect(self._regenerate_from_bubble)
        self._insert_bubble(bubble, 0 if grouped else 6)
        if mark_thinking:
            if getattr(self, "_thinking_bubbles", None) is None:
                self._thinking_bubbles = []
            self._thinking_bubbles.append(bubble)
        return bubble

    def _assistant_html(self, text: str, streaming: bool = False) -> str:
        """Bubble body: the answer markdown, sized for the chat font."""
        body = _markdown_to_html(text)
        if streaming:
            body += (f'<div style="color:{TEXT_DIM}; font-size:11px; margin-top:4px;">'
                     'печатает…</div>')
        return f'<div style="color:{TEXT};">{body}</div>'

    def _copy_bubble_text(self, bubble=None):
        """Copy one assistant answer to the clipboard."""
        text = getattr(bubble, "_text", "") or ""
        if not text.strip():
            return
        try:
            QtWidgets.QApplication.clipboard().setText(text)
            self._append_step("Скопировано в буфер обмена", "⧉")
        except Exception:
            logger.exception("Не удалось скопировать ответ")

    def _regenerate_from_bubble(self, _bubble=None):
        """Ask the model to answer the last request again."""
        try:
            self.regenerate_last()
        except Exception:
            logger.exception("Не удалось повторить запрос")

    def _drop_thinking(self):
        """Remove every "thinking" bubble (reasoning) once the answer is known.

        The raw streamed text is only a placeholder while the model is working;
        leaving it behind is what made reasoning look stuck in the chat.
        """
        bubbles = getattr(self, "_thinking_bubbles", None) or []
        if not bubbles:
            return
        self._thinking_bubbles = []
        for bubble in bubbles:
            self._remove_widget(bubble)
        self._thinking_bubble = None

    def _append_notice(self, text: str, kind: str = "info"):
        color = "#E2B86B" if kind == "warn" else TEXT_MUTED
        self._append_html(
            f'<div style="margin:6px 0; color:{color};'
            f' font-size:{self._meta_px()}px;">{html.escape(text)}</div>'
        )

    def clear_conversation(self):
        self.stop_request()
        # A worker that was running for the old dialog must not deliver its
        # answer (or auto-send the old queue) into the fresh conversation.
        self._discard_worker()
        self._queue = []
        self._last_request = None
        self._history_before_request = 0
        self._reasoning_chars = 0
        self._render_queue_chip()
        self._history.clear()
        self._forget_chat_session()
        self._current_answer.clear()
        self._stream_open = False
        self._thinking_bubbles = []
        self._thinking_bubble = None
        self._bubbles = []
        self._welcome_visible = False
        self._welcome_widget = None
        self._last_author = None
        self._entries_cache = None
        self._reset_session_stats()
        self._clear_activity()
        # Drop every message widget, leaving the trailing stretch in place.
        while self.messages.count() > 1:
            item = self.messages.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._append_welcome()

    # ------------------------------------------------------------------
    # Chat session persistence (project/.pyscribe/ai_chat.json)
    # ------------------------------------------------------------------
    def _session_path(self) -> Optional[Path]:
        window = self.main_window
        project = getattr(window, "current_project", None) if window else None
        root = getattr(project, "root_path", None) if project else None
        if not root:
            return None
        try:
            return Path(str(root)) / ".pyscribe" / "ai_chat.json"
        except (OSError, ValueError):
            return None

    def save_chat_session(self) -> None:
        """Persist the conversation so it survives an IDE restart."""
        path = self._session_path()
        if path is None or not self._history:
            return
        try:
            import datetime
            payload = {
                "version": 1,
                "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "messages": [message.as_dict() for message in self._history],
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        except OSError:
            logger.debug("Не удалось сохранить сессию чата", exc_info=True)

    def load_chat_session(self) -> int:
        """Restore the saved conversation; returns how many messages were loaded."""
        path = self._session_path()
        if path is None or not path.is_file():
            return 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(messages, list):
            return 0
        restored = [
            AIMessage(str(item.get("role") or "user"), str(item.get("content") or ""))
            for item in messages
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ]
        if not restored:
            return 0
        self._history = restored
        self._append_html(
            f'<p align="center" style="margin:10px 0 6px 0; color:{TEXT_DIM};'
            f' font-size:{self._meta_px()}px;">Восстановлен диалог: {len(restored)} сообщений'
            f' &nbsp;·&nbsp; /clear — начать заново</p>')
        return len(restored)

    def _forget_chat_session(self) -> None:
        path = self._session_path()
        try:
            if path is not None and path.is_file():
                path.unlink()
        except OSError:
            pass

    def _discard_worker(self):
        """Detach the current worker so its signals no longer reach this panel."""
        self._clear_activity()
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        try:
            worker.stop()
        except RuntimeError:
            return
        for signal in (worker.chunk, worker.reasoning, worker.tool_started,
                       worker.tool_finished, worker.finished_ok, worker.failed):
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
        try:
            worker.finished.disconnect()
        except (TypeError, RuntimeError):
            pass
        worker.deleteLater()

    def shutdown(self):
        """Stop the worker and terminate every MCP server this panel started."""
        self.stop_request()
        self._discard_worker()
        models_worker = self._models_worker
        self._models_worker = None
        if models_worker is not None:
            try:
                models_worker.wait(2000)
            except RuntimeError:
                pass
        for client in list(getattr(self, "_mcp_clients", {}).values()):
            try:
                client.close()
            except Exception:
                pass
        self._mcp_clients = {}

    def closeEvent(self, event):
        """Never leave child MCP processes or a live request behind."""
        self.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------
    def _collect_context(self) -> str:
        window = self.main_window
        if window is None:
            return ""
        editor = window.get_current_editor() if hasattr(window, "get_current_editor") else None
        file_path = getattr(editor, "file_path", None) if editor else None
        language = getattr(editor, "language", "") if editor else ""
        code = None
        selection = None
        if editor is not None:
            text_editor = getattr(editor, "editor", None)
            if text_editor is not None:
                cursor = text_editor.textCursor()
                if cursor.hasSelection():
                    selection = cursor.selectedText().replace("\u2029", "\n")
            if self.include_file.isChecked() or selection:
                code = editor.get_code() if hasattr(editor, "get_code") else None
            if not selection and self.include_selection.isChecked() and text_editor is not None:
                block = text_editor.textCursor().block().text()
                selection = block or None
        problems = None
        if self.include_problems.isChecked():
            try:
                console = getattr(window, "console_widget", None)
                lst = getattr(console, "problems_list", None) if console else None
                if lst is not None:
                    problems = [lst.item(i).text() for i in range(min(lst.count(), 40))]
            except Exception:
                problems = None
        return AIService.build_context_block(
            file_path=str(file_path) if file_path else None,
            code=code,
            language=language,
            selection=selection,
            problems=problems,
        )

    def _collect_file_context(self) -> str:
        """Context for the ``file`` scope: the editor contents (+ selection)."""
        window = self.main_window
        if window is None:
            return ""
        editor = window.get_current_editor() if hasattr(window, "get_current_editor") else None
        if editor is None:
            return ""
        file_path = getattr(editor, "file_path", None)
        language = getattr(editor, "language", "")
        code = editor.get_code() if hasattr(editor, "get_code") else None
        selection = None
        text_editor = getattr(editor, "editor", None)
        if text_editor is not None:
            cursor = text_editor.textCursor()
            if cursor.hasSelection():
                selection = cursor.selectedText().replace("\u2029", "\n")
        problems = None
        try:
            console = getattr(window, "console_widget", None)
            lst = getattr(console, "problems_list", None) if console else None
            if lst is not None:
                problems = [lst.item(i).text() for i in range(min(lst.count(), 40))]
        except Exception:
            problems = None
        return AIService.build_context_block(
            file_path=str(file_path) if file_path else None,
            code=code,
            language=language,
            selection=selection,
            problems=problems,
        )

    def _context_summary(self) -> str:
        parts = []
        if self.include_file.isChecked():
            parts.append("файл")
        if self.include_selection.isChecked():
            parts.append("выделение")
        if self.include_problems.isChecked():
            parts.append("проблемы")
        return ", ".join(parts) if parts else "без контекста"

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def send_with_context(self, prompt: str):
        self._send(prompt, self._context_for(None))

    # ------------------------------------------------------------------
    # Commands, mentions and scoped context
    # ------------------------------------------------------------------
    def _scope(self) -> str:
        from utils.settings_manager import get_settings_manager
        value = str(get_settings_manager().get_setting("ai_context_scope", "none") or "none")
        return value if value in ("project", "file", "none") else "none"

    def _set_scope(self, scope: str):
        if scope not in SCOPE_LABELS:
            return
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_context_scope"] = scope
        sm.save_settings()
        # Keep the radio menu in sync with the chosen scope.
        actions = getattr(self, "_scope_actions", {}) or {}
        for key, action in actions.items():
            action.setChecked(key == scope)
        self._set_button_label(self.scope_btn, SCOPE_LABELS[scope])
        self.scope_btn.setToolTip("Контекст запроса: " + SCOPE_LABELS[scope])
        self._append_step(f"Контекст: {SCOPE_LABELS[scope]}")

    def sync_scope_with_project(self):
        """Pick a sensible context when the workspace changes.

        * opening a project selects ``project`` (unless the user deliberately
          picked a different scope for this project before);
        * closing the project falls back to ``none``;
        * ``file`` chosen explicitly is never overwritten.

        The previous version forced ``project``/``none`` on every call, which
        silently reverted the "текущий файл" option back to a project scope.
        """
        window = self.main_window
        project = getattr(window, "current_project", None) if window else None
        root = getattr(project, "root_path", None) if project else None
        current = self._scope()
        # The "@" completion list belongs to the previous workspace otherwise.
        self._entries_cache = None
        # Restore the saved conversation once per project.
        if root and str(root) != getattr(self, "_session_root", None):
            self._session_root = str(root)
            self.load_chat_session()
        elif not root:
            self._session_root = None
        if root:
            # A project is open: keep an explicit "file" choice, otherwise use
            # the project-wide context.
            if current == "file":
                self._refresh_menus()
                return
            wanted = "project"
        else:
            # Nothing to attach project-wide; keep "file" (it still resolves to
            # the open editor) and only drop a project scope.
            wanted = "none" if current == "project" else current
        if current == wanted:
            self._refresh_menus()
            return
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_context_scope"] = wanted
        sm.save_settings()
        self._refresh_menus()

    def _collect_project_context(self, mentions=None) -> str:
        """Attach @-mentioned files, or a compact project map.

        File contents come from the stat-cache in ``services.ai_context``: an
        unchanged file is sent from memory, so repeated requests and repeated
        @-mentions do not re-read the disk.
        """
        window = self.main_window
        if window is None:
            return ""
        root = None
        try:
            project = getattr(window, "current_project", None)
            root = Path(getattr(project, "root_path", "")) if project else None
        except Exception:
            root = None
        if root is None or not root.is_dir():
            editor = window.get_current_editor() if hasattr(window, "get_current_editor") else None
            file_path = getattr(editor, "file_path", None) if editor else None
            if file_path:
                root = Path(str(file_path)).parent
        if root is None or not root.is_dir():
            return ""
        from services.ai_context import render_project_context
        return render_project_context(root, mentions)

    def send_message(self):
        raw = self.input.toPlainText().strip()
        if not raw:
            return
        parsed = parse_input(raw)
        if parsed.is_command and self._run_command(parsed):
            self.input.clear()
            return
        mentions = parsed.mentions
        text = parsed.text or raw
        self.input.clear()
        self._clear_welcome()
        context = self._context_for(mentions)
        self._send(text, context, mentions=mentions)

    def _context_for(self, mentions=None) -> str:
        if self._access_mode() == "write_only":
            return ""
        scope = self._scope()
        if mentions:
            base = self._collect_project_context(mentions)
            return (base + "\n\n" + self._collect_file_context()) if self._scope() == "file" else base
        if scope == "project":
            return self._collect_project_context(None)
        if scope == "file":
            return self._collect_file_context()
        return ""

    def _run_command(self, parsed) -> bool:
        """Execute a slash command; returns True when it was handled."""
        command = parsed.command
        arg = parsed.command_arg
        service = self._service()
        if command.name == "help":
            lines = "\n".join(f"**{c.usage}** — {c.description}" for c in COMMANDS)
            self._append_assistant("Команды чата:\n\n" + lines +
                                   "\n\n`@путь/к/файлу` — прикрепить файл проекта.",
                                   mark_thinking=False)
            return True
        if command.name == "clear":
            self.clear_conversation()
            return True
        if command.name == "stop":
            self.stop_request()
            return True
        if command.name == "model":
            if arg:
                self._set_model(arg)
            else:
                self._append_step(f"Модель: {service.model} · {service.provider.label}")
            return True
        if command.name == "provider":
            if arg:
                self._set_provider(arg)
            else:
                self._append_step(f"Провайдер: {service.provider.label}")
            return True
        if command.name == "models":
            self._show_models(service)
            return True
        if command.name == "free":
            self._show_free_models()
            return True
        if command.name == "context":
            if arg in SCOPE_LABELS:
                self._set_scope(arg)
            else:
                self._append_step(f"Контекст: {SCOPE_LABELS.get(self._scope())} "
                                  "· /context project|file|none")
            return True
        if command.name == "mode":
            from services.ai_service import TEACHING_MODE_LABELS
            if arg in TEACHING_MODE_LABELS:
                self.set_mode(arg)
            else:
                self._append_step(
                    f"Режим: {TEACHING_MODE_LABELS.get(service.mode, service.mode)} "
                    "· /mode solve|teach")
            return True
        if command.name == "strictness":
            from services.ai_service import TEACH_STRICTNESS_LABELS
            if arg in TEACH_STRICTNESS_LABELS:
                self.set_strictness(arg)
            else:
                self._append_step(
                    "Строгость наставника: "
                    f"{TEACH_STRICTNESS_LABELS.get(service.teach_strictness)} "
                    "· /strictness soft|normal|strict")
            return True
        if command.name == "reasoning":
            from services.ai_service import REASONING_HINTS, REASONING_LABELS
            if arg:
                self._set_reasoning_effort(arg)
            else:
                current = self._reasoning_effort()
                self._append_step(
                    f"Размышления: {REASONING_LABELS[current]} — {REASONING_HINTS[current]} "
                    "· /reasoning auto|none|low|medium|high")
            return True
        if command.name == "mcp":
            self._show_mcp()
            return True
        prompts = {
            "explain": "Объясни этот код шаг за шагом.",
            "tests": "Сгенерируй модульные тесты (pytest) для этого кода.",
            "fix": "Найди ошибки в этом коде и покажи исправленный вариант.",
            "review": "Сделай короткое code review: сильные и слабые места.",
        }
        if command.name in prompts:
            self._send(prompts[command.name], self._context_for(None))
            return True
        return False

    def _show_models(self, service):
        """Ask the provider for its model list in the background.

        This used to be a blocking HTTP GET on the UI thread (timeout up to
        180 s), which froze the whole window while it waited.
        """
        if getattr(self, "_models_worker", None) is not None:
            self._append_step("Список моделей уже загружается…")
            return
        provider_label = service.provider.label
        self._append_step(f"Запрашиваю модели {provider_label}…")

        worker = _ModelsWorker(service, self)

        def _loaded(ids):
            self._append_step(f"Модели {provider_label}: {len(ids)}")
            self._append_assistant(
                "\n".join(f"- `{m}`" for m in ids[:60]) or "Список пуст.",
                mark_thinking=False)

        def _failed(message):
            self._append_notice(f"Список моделей недоступен: {message}", "warn")

        def _done():
            self._models_worker = None

        worker.loaded.connect(_loaded)
        worker.failed.connect(_failed)
        worker.finished.connect(_done)
        self._models_worker = worker
        worker.start()

    def _show_free_models(self):
        from services.ai_providers import models_for
        lines = []
        for spec in PROVIDERS.values():
            free = [m for m in models_for(spec.key) if m.free]
            if not free:
                continue
            lines.append(f"**{spec.label}** — ключ: {spec.key_url}")
            lines.extend(f"- `{m.id}` — {m.label}" for m in free)
        self._append_assistant("Бесплатные варианты:\n\n" + "\n".join(lines) +
                               "\n\nСменить: `/provider openrouter` и `/model <id>`.",
                               mark_thinking=False)

    def _show_mcp(self):
        servers = getattr(self, "_mcp_clients", {}) or {}
        if not servers:
            self._append_step("MCP: серверы не подключены (Настройки → ИИ-агент → MCP)")
            return
        lines = []
        for key, client in servers.items():
            names = ", ".join(t.name for t in client.tools) or "нет инструментов"
            lines.append(f"**{key}** ({client.config.transport}) — {names}")
        self._append_assistant("MCP-серверы:\n\n" + "\n".join(lines), mark_thinking=False)

    def _set_model(self, model: str):
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_model"] = model.strip()
        sm.save_settings()
        self.refresh_model_label()
        self._append_step(f"Модель: {model.strip()}")

    def _set_provider(self, key: str):
        from services.ai_providers import PROVIDERS, get_provider
        key = key.strip().lower()
        spec = get_provider(key)
        if key not in PROVIDERS:
            self._append_notice(f"Неизвестный провайдер «{key}». "
                                f"Доступны: {', '.join(PROVIDERS)}", "warn")
            return
        from utils.settings_manager import get_settings_manager
        sm = get_settings_manager()
        sm.settings["ai_provider"] = spec.key
        sm.settings["ai_base_url"] = spec.base_url
        sm.settings["ai_model"] = spec.default_model
        sm.save_settings()
        self.refresh_model_label()
        self._append_step(f"Провайдер: {spec.label} · модель {spec.default_model or '—'}")

    def _send(self, prompt: str, context: str, mentions=None):
        # A message typed while the model is still answering is queued instead
        # of being rejected; it is sent automatically when the current answer
        # finishes (see _drain_queue).
        if self._worker is not None:
            self._enqueue(prompt, context, mentions)
            return
        service = self._service()
        problem = service.configuration_problem()
        if problem:
            self._append_notice("⚠ " + problem, "warn")
            self.refresh_status()
            return
        self._clear_welcome()
        self._append_user(prompt)
        self._clear_activity()
        self._current_answer.clear()
        self._stream_open = False
        self._tool_counters = {}
        self.send_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.status_label.setVisible(False)

        access_mode = self._access_mode()
        if access_mode == "write_only":
            context = ""
        worker = AIWorker(service, prompt, [] if access_mode == "write_only" else list(self._history), context, self,
                          mcp_servers=self._mcp_server_configs(),
                          mcp_clients=getattr(self, "_mcp_clients", {}),
                          local_tools=self._build_local_tools())
        worker.chunk.connect(self._on_chunk)
        worker.reasoning.connect(self._on_reasoning)
        worker.tool_started.connect(self._on_tool_started)
        worker.tool_finished.connect(self._on_tool_finished)
        worker.finished_ok.connect(lambda answer: self._on_finished(prompt, answer))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._cleanup_worker)
        self._last_request = (prompt, context, mentions)
        self._history_before_request = len(self._history)
        self._request_started = time.monotonic()
        self._worker = worker
        worker.start()

    # ------------------------------------------------------------------
    # Message queue
    # ------------------------------------------------------------------
    def _enqueue(self, prompt: str, context: str, mentions=None):
        if getattr(self, "_queue", None) is None:
            self._queue = []
        self._queue.append((prompt, context, mentions))
        self._render_queue_chip()

    def clear_queue(self) -> int:
        """Drop every queued message. Returns how many were discarded."""
        count = len(getattr(self, "_queue", []) or [])
        self._queue = []
        self._render_queue_chip()
        if count:
            self._append_notice(f"Очередь очищена ({count}).")
        return count

    def _render_queue_chip(self):
        """Small hint above the composer showing how many messages wait."""
        count = len(getattr(self, "_queue", []) or [])
        chip = getattr(self, "queue_chip", None)
        if chip is None:
            return
        try:
            from widgets.animations import fade_in, fade_out, DURATION
            duration = DURATION["fast"]
        except Exception:
            fade_in = fade_out = None
            duration = 120
        if count:
            chip.setText(f"В очереди сообщений: {count}")
            if chip.isHidden():
                chip.show()
                if fade_in is not None:
                    try:
                        fade_in(chip, duration=duration)
                        return
                    except Exception:
                        pass
            return
        if fade_out is not None:
            try:
                fade_out(chip, duration=duration)
            except Exception:
                chip.setVisible(False)
        else:
            chip.setVisible(False)
        # Safety net: never leave a stale "N in queue" chip on screen.
        def _force_hide():
            try:
                if not self.pending_count():
                    chip.setVisible(False)
            except RuntimeError:
                # The panel (and the chip) may be gone by then.
                pass

        QtCore.QTimer.singleShot(duration + 60, _force_hide)

    def _drain_queue(self):
        """Send the next queued message once the current answer is done."""
        queue = getattr(self, "_queue", None) or []
        if not queue:
            self._render_queue_chip()
            return
        prompt, context, mentions = queue.pop(0)
        self._render_queue_chip()
        QtCore.QTimer.singleShot(0, lambda: self._send(prompt, context, mentions))

    def pending_count(self) -> int:
        return len(getattr(self, "_queue", []) or [])

    def _on_chunk(self, piece: str):
        """Show live reasoning in a single temporary "thinking" bubble.

        The bubble is only a placeholder while the model works. It is removed in
        ``_on_finished`` and replaced by the final rendered answer, so no
        reasoning text survives in the transcript.
        """
        self._current_answer.append(piece)
        if not self._stream_open:
            self._stream_open = True
            self._thinking_bubbles = []
            bubble = _UserBubble(self._thinking_placeholder(), side="in")
            bubble.label.setTextFormat(QtCore.Qt.PlainText)
            bubble.setObjectName("aiThinkingBubble")
            self._thinking_bubbles.append(bubble)
            self._thinking_bubble = bubble
            self._insert_bubble(bubble)
            self._relayout_transcript()
            self._pulse_thinking()
            return
        bubble = getattr(self, "_thinking_bubble", None)
        if bubble is None:
            return
        # Only the hint is shown; the reasoning text itself is never rendered.
        try:
            bubble.label.setText(self._thinking_placeholder())
            self._relayout_transcript()
        except RuntimeError:
            pass

    def _pulse_thinking(self):
        """Gently pulse the "thinking" bubble so it reads as live activity."""
        bubble = getattr(self, "_thinking_bubble", None)
        if bubble is None:
            return
        try:
            from widgets.animations import pulse
            pulse(bubble.pill, times=1, duration=900)
        except Exception:
            pass

    def _thinking_placeholder(self) -> str:
        """Live status line shown while the model works."""
        text = "Думает…"
        reasoning = getattr(self, "_reasoning_chars", 0)
        if reasoning and self._show_reasoning():
            # Approximate word count keeps the line short but shows progress.
            text += f"  ·  размышлений: ≈{max(1, reasoning // 5)} слов"
        return text

    @staticmethod
    def _show_reasoning() -> bool:
        try:
            from utils.settings_manager import get_settings_manager
            return bool(get_settings_manager().get_setting("ai_show_reasoning", True))
        except Exception:
            return True

    def _on_reasoning(self, piece: str):
        """Track the model's reasoning without printing it into the chat.

        Reasoning is shown only as a live progress hint and is discarded when
        the answer arrives, so it never clutters the transcript.
        """
        self._reasoning_chars = getattr(self, "_reasoning_chars", 0) + len(piece or "")
        bubble = getattr(self, "_thinking_bubble", None)
        if bubble is None:
            return
        try:
            bubble.label.setText(self._thinking_placeholder())
            self._relayout_transcript()
        except RuntimeError:
            pass

    def _on_finished(self, prompt: str, answer: str):
        # Everything streamed so far was "thinking" — reasoning, drafts, partial
        # markdown. Telegram-style chat keeps only the final message, so drop it
        # and render the finished answer once, in a single clean bubble.
        self._stream_open = False
        self._answer_truncated = bool(getattr(self._worker, "truncated", False))
        usage = dict(getattr(self._worker, "usage", {}) or {})
        # Keep the servers this request connected so the next one reuses them.
        clients = dict(getattr(self._worker, "mcp_clients", {}) or {})
        if clients:
            self._mcp_clients = clients
        for error in list(getattr(self._worker, "mcp_errors", []) or []):
            self._append_notice(f"MCP недоступен — {error}", "warn")
        self._clear_activity()
        self._drop_thinking()
        self._reasoning_chars = 0
        if answer:
            self._append_assistant(answer, mark_thinking=False)
            if getattr(self, "_answer_truncated", False):
                # The provider hit its own output ceiling even after automatic
                # continuations; there is no local token limit to raise any more.
                self._append_notice(
                    "⚠ Провайдер оборвал ответ на своём лимите вывода. "
                    "Напишите «продолжи» или смените модель на более мощную.", "warn")
            self._record_session_stats(usage)
            self._history.append(AIMessage("user", prompt))
            self._history.append(AIMessage("assistant", answer))
            self.save_chat_session()
        else:
            self._append_notice("Запрос остановлен.")
        self._last_author = "assistant"
        QtCore.QTimer.singleShot(0, self._scroll_to_latest)
        self.refresh_status()

    def _record_session_stats(self, usage: dict) -> None:
        """Accumulate session metrics and refresh the footer under the composer."""
        stats = getattr(self, "_session_stats", None)
        if stats is None:
            stats = self._session_stats = {
                "answers": 0, "steps": 0, "tokens": 0, "prompt": 0, "seconds": 0.0,
            }
        started = getattr(self, "_request_started", None)
        elapsed = max(0.05, time.monotonic() - started) if started else 0.0
        self._request_started = None
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        stats["answers"] += 1
        stats["steps"] += sum((getattr(self, "_tool_counters", {}) or {}).values())
        if isinstance(completion_tokens, int):
            stats["tokens"] += completion_tokens
        if isinstance(prompt_tokens, int):
            stats["prompt"] += prompt_tokens
        stats["seconds"] += elapsed
        self._update_stats_line()

    def _update_stats_line(self) -> None:
        label = getattr(self, "stats_label", None)
        stats = getattr(self, "_session_stats", None)
        if label is None:
            return
        if not stats or not stats.get("answers"):
            label.setVisible(False)
            return
        tokens = int(stats.get("tokens", 0))
        seconds = max(0.1, float(stats.get("seconds", 0.0)))
        speed = int(tokens / seconds) if tokens else 0
        try:
            from services.ai_context import context_cache_stats
            cache = context_cache_stats()
            total = int(cache.get("hits", 0)) + int(cache.get("misses", 0))
            hit = int(round(100.0 * cache.get("hits", 0) / total)) if total else 0
        except Exception:
            hit = 0
        parts = [f"{stats['answers']} отв."]
        if stats.get("steps"):
            parts.append(f"{stats['steps']} шагов")
        if speed:
            parts.append(f"{speed} tok/s")
        if tokens:
            parts.append(f"{tokens} tok")
        if hit:
            parts.append(f"кэш {hit}%")
        label.setText(" · ".join(parts))
        label.setVisible(True)

    def _reset_session_stats(self) -> None:
        self._session_stats = None
        self._request_started = None
        label = getattr(self, "stats_label", None)
        if label is not None:
            label.setText("")
            label.setVisible(False)

    def regenerate_last(self) -> bool:
        """Re-send the most recent user message, replacing its answer."""
        request = getattr(self, "_last_request", None)
        if request is None or self._worker is not None:
            return False
        prompt, context, mentions = request
        # Truncate back to the point the request started from. Blindly popping
        # the last two entries would delete an earlier successful turn when the
        # previous attempt failed or was stopped before touching the history.
        keep = getattr(self, "_history_before_request", None)
        if isinstance(keep, int) and 0 <= keep <= len(self._history):
            del self._history[keep:]
        self._send(prompt, context, mentions)
        return True

    def _replace_stream_with_markdown(self, answer: str):
        """Kept for compatibility: drop the placeholder and render the answer."""
        self._drop_thinking()
        self._append_assistant(answer, mark_thinking=False)

    def _on_failed(self, message: str):
        self._stream_open = False
        self._clear_activity()
        self._drop_thinking()
        self._append_notice("⚠ " + message, "warn")

    def _cleanup_worker(self):
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self.stop_btn.setVisible(False)
        self.send_btn.setEnabled(True)
        self.refresh_status()
        # Keep a queued conversation flowing.
        self._drain_queue()

    def stop_request(self):
        if self._worker is not None:
            self._worker.stop()

    def keyPressEvent(self, event):
        # Esc stops a streaming answer, like the reference chat UIs.
        if event.key() == QtCore.Qt.Key_Escape and self._worker is not None:
            self.stop_request()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Inline completion for "/" commands and "@" mentions
    # ------------------------------------------------------------------
    def _project_entries(self):
        """(relative path, kind) pairs of the open project (cached)."""
        if getattr(self, "_entries_cache", None) is not None:
            return self._entries_cache
        entries = []
        window = self.main_window
        try:
            project = getattr(window, "current_project", None) if window else None
            root = Path(getattr(project, "root_path", "")) if project else None
            if root is None or not root.is_dir():
                editor = window.get_current_editor() if window else None
                fp = getattr(editor, "file_path", None) if editor else None
                root = Path(str(fp)).parent if fp else None
            if root and root.is_dir():
                from core.ignore_rules import walk_files
                scan = walk_files(root, extensions=None, max_files=1200,
                                  max_bytes=4 * 1024 * 1024)
                for path in scan.files:
                    try:
                        rel = path.relative_to(root)
                    except ValueError:
                        continue
                    entries.append((rel.as_posix(), "file"))
        except Exception:
            entries = []
        self._entries_cache = entries
        return entries

    def _current_token(self) -> Optional[str]:
        text = self.input.toPlainText()
        match = re.search(r"(?:^|\s)([/@][^\s]*)$", text)
        return match.group(1) if match else None

    def _update_completion(self):
        token = self._current_token()
        if not token or len(token) > 60:
            self.completion.hide_popup()
            return
        items = []
        if token.startswith("/"):
            needle = token[1:].lower()
            for command in COMMANDS:
                if not needle or command.name.startswith(needle):
                    items.append(("/" + command.name, "cmd", command.description))
        else:
            from services.ai_commands import mention_candidates
            for rel, kind in mention_candidates(self._project_entries(), token[1:], limit=10):
                items.append(("@" + rel, kind, rel))
        if not items:
            self.completion.hide_popup()
            return
        anchor = self.input.mapTo(self, QtCore.QPoint(8, self.input.y() + self.input.height()))
        self._completion_items = items
        self.completion.show_items(items, QtCore.QPoint(8, max(0, anchor.y())))

    def _accept_completion(self):
        items = getattr(self, "_completion_items", [])
        if not items:
            return
        choice = self.completion.current_label()
        if not choice:
            return
        text = self.input.toPlainText()
        token = self._current_token() or ""
        start = len(text) - len(token)
        new_text = text[:start] + choice + " "
        self.input.setPlainText(new_text)
        cursor = self.input.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.input.setTextCursor(cursor)
        self.completion.hide_popup()

    def _completion_navigate(self, delta: int) -> bool:
        if not self.completion.isVisible():
            return False
        self.completion.move_selection(delta)
        return True

    def _on_composer_text_changed(self):
        self._update_completion()

    def eventFilter(self, watched, event):
        """Intercept Up/Down/Tab/Enter while the completion popup is open."""
        if watched is self.input and event.type() == QtCore.QEvent.KeyPress:
            if self.completion.isVisible():
                if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                    self.completion.move_selection(-1 if event.key() == QtCore.Qt.Key_Up else 1)
                    return True
                if event.key() == QtCore.Qt.Key_Tab:
                    self._accept_completion()
                    return True
                if event.key() == QtCore.Qt.Key_Escape:
                    self.completion.hide_popup()
                    return True
                if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    self._accept_completion()
                    return True
            elif event.key() == QtCore.Qt.Key_Tab:
                if self._current_token():
                    self._update_completion()
                    return True
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Actions on the answer
    # ------------------------------------------------------------------
    def apply_last_code(self) -> bool:
        """Append the first code block of the last answer into the editor."""
        answer = "".join(self._current_answer)
        if not answer:
            return False
        blocks = extract_code_blocks(answer)
        if not blocks:
            return False
        window = self.main_window
        editor = window.get_current_editor() if window and hasattr(window, "get_current_editor") else None
        if editor is None or not hasattr(editor, "editor"):
            return False
        code = blocks[0].rstrip("\n")
        text_editor = editor.editor
        cursor = text_editor.textCursor()
        text_editor.setFocus()
        cursor.beginEditBlock()
        try:
            cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
            prefix = "\n\n" if text_editor.toPlainText().strip() else ""
            cursor.insertText(prefix + code + "\n")
            start = cursor.position() - len(code) - 1
            cursor.setPosition(max(0, start))
            cursor.setPosition(max(0, start) + len(code), QtGui.QTextCursor.KeepAnchor)
        finally:
            cursor.endEditBlock()
        text_editor.setTextCursor(cursor)
        self._append_step("Код вставлен в редактор", "✓")
        return True

    def copy_last_answer(self) -> bool:
        answer = "".join(self._current_answer)
        if not answer:
            return False
        QtWidgets.QApplication.clipboard().setText(answer)
        self._append_step("Ответ скопирован", "✓")
        return True

    def conversation_markdown(self) -> str:
        """The whole dialog as Markdown, for export."""
        lines = ["# Диалог с ИИ-агентом PyScribe", ""]
        model = self._service().model
        lines.append(f"Модель: `{model}`")
        lines.append(f"Контекст: {SCOPE_LABELS.get(self._scope(), self._scope())}")
        lines.append("")
        for message in self._history:
            who = "Вы" if message.role == "user" else "ИИ-агент"
            lines.append(f"## {who}")
            lines.append("")
            lines.append(message.content.strip())
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def export_conversation(self) -> bool:
        """Save the dialog to a Markdown file chosen by the user."""
        if not self._history:
            self._append_notice("Пока нечего экспортировать — задайте вопрос.", "warn")
            return False
        suggested = str(Path.home() / "Desktop" / "ai-dialog.md")
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Экспорт диалога", suggested, "Markdown (*.md);;Текст (*.txt)")
        if not path:
            return False
        try:
            Path(path).write_text(self.conversation_markdown(), encoding="utf-8")
        except OSError as exc:
            self._append_notice(f"⚠ Не удалось сохранить файл: {exc}", "warn")
            return False
        self._append_step(f"Диалог сохранён: {Path(path).name}", "✓")
        return True


# ----------------------------------------------------------------------
# Markdown helpers
# ----------------------------------------------------------------------
def _stream_format() -> QtGui.QTextCharFormat:
    fmt = QtGui.QTextCharFormat()
    fmt.setForeground(QtGui.QColor(TEXT))
    return fmt


class _BubbleFrame(QtWidgets.QFrame):
    """Container for one chat message.

    The panel used to paint Telegram-style gradient bubbles with a corner tail,
    which read as a messenger rather than a developer tool. Modern IDE chats
    (DeepSeek Harness, Claude, Antigravity) use a flat layout instead: the
    assistant answers sit directly on the background as readable text, and only
    the user's message gets a compact pill. Styling lives in ``theme.qss``.
    """

    def __init__(self, side: str, grouped: bool, parent=None):
        super().__init__(parent)
        self._side = side
        self._grouped = grouped
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setObjectName(
            "aiUserBubblePill" if side == "out" else "aiAssistantBubbleBody")


class _UserBubble(QtWidgets.QWidget):
    """One chat message.

    Assistant messages render as a flat block of markdown with a quiet action
    row that appears on hover (copy / regenerate). The user's message is a
    compact right-aligned pill. This follows the layout used by modern IDE
    chats instead of a messenger-style bubble thread.
    """

    copy_requested = QtCore.pyqtSignal(object)
    regenerate_requested = QtCore.pyqtSignal(object)

    def __init__(self, text: str, parent=None, side: str = "out", grouped: bool = False,
                 body_html: Optional[str] = None, body_widget=None):
        super().__init__(parent)
        self._text = text
        self._side = side
        self._grouped = grouped
        # The widget stretches across the row so alignment works; the visible
        # pill inside hugs its content.
        self.setObjectName("aiUserBubble" if side == "out" else "aiAssistantBubble")
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        # The widget must stay at its content height; without a fixed policy the
        # row stretch makes each bubble fill the viewport and look airy.
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        outer = QtWidgets.QHBoxLayout(self)
        # Generous gap between messages, tight gap inside one author's group.
        self._top = 4 if grouped else 18
        self._bottom = 2
        outer.setContentsMargins(0, self._top, 0, self._bottom)
        outer.setSpacing(0)
        if side == "out":
            outer.addStretch(1)

        self.pill = _BubbleFrame(side, grouped, self)
        self.pill.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                QtWidgets.QSizePolicy.Minimum)
        pill_layout = QtWidgets.QVBoxLayout(self.pill)
        if side == "out":
            pill_layout.setContentsMargins(14, 10, 14, 10)
        else:
            # Assistant answers are plain text on the panel background.
            pill_layout.setContentsMargins(6, 2, 12, 2)
        pill_layout.setSpacing(0)

        if body_widget is not None:
            # Compound body: prose with rounded inline-code chips plus code
            # snippets rendered by the editor core (see widgets/ChatMessage.py).
            self.label = body_widget
            pill_layout.addWidget(body_widget)
        elif body_html is not None:
            # A QLabel with rich text grows and wraps correctly on its own;
            # QTextBrowser (a scroll area) collapses inside a tight layout, so it
            # must not be used for bubble bodies.
            self.label = QtWidgets.QLabel(self.pill)
            self.label.setObjectName("aiAssistantBubbleText")
            self.label.setTextFormat(QtCore.Qt.RichText)
            self.label.setWordWrap(True)
            self.label.setTextInteractionFlags(
                QtCore.Qt.TextSelectableByMouse | QtCore.Qt.LinksAccessibleByMouse)
            self.label.setOpenExternalLinks(True)
            self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            self.label.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                     QtWidgets.QSizePolicy.Minimum)
            self.label.setText(body_html)
        else:
            self.label = QtWidgets.QLabel(text, self.pill)
            self.label.setObjectName("aiUserBubbleText" if side == "out" else "aiAssistantBubbleText")
            self.label.setTextFormat(QtCore.Qt.PlainText)
            self.label.setWordWrap(True)
            self.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            self.label.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                     QtWidgets.QSizePolicy.Minimum)
        pill_layout.addWidget(self.label)

        # Push the content to the top and keep the pill height content-driven.
        pill_layout.addStretch(1)

        # Hover actions for assistant messages (copy / regenerate).
        self.actions = None
        if side == "in":
            self.actions = QtWidgets.QWidget(self.pill)
            self.actions.setObjectName("aiMessageActions")
            row = QtWidgets.QHBoxLayout(self.actions)
            row.setContentsMargins(0, 4, 0, 0)
            row.setSpacing(4)
            self.copy_btn = QtWidgets.QToolButton(self.actions)
            self.copy_btn.setObjectName("aiMessageAction")
            self.copy_btn.setText("Копировать")
            self.copy_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.copy_btn.setFocusPolicy(QtCore.Qt.NoFocus)
            self.copy_btn.clicked.connect(lambda: self.copy_requested.emit(self))
            row.addWidget(self.copy_btn)
            self.retry_btn = QtWidgets.QToolButton(self.actions)
            self.retry_btn.setObjectName("aiMessageAction")
            self.retry_btn.setText("Повторить")
            self.retry_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.retry_btn.setFocusPolicy(QtCore.Qt.NoFocus)
            self.retry_btn.clicked.connect(lambda: self.regenerate_requested.emit(self))
            row.addWidget(self.retry_btn)
            row.addStretch(1)
            self.actions.hide()
            pill_layout.addWidget(self.actions)

        outer.addWidget(self.pill, 0)
        if side == "in":
            outer.addStretch(1)

    # -- hover actions -------------------------------------------------
    def enterEvent(self, event):
        if self.actions is not None and self._text:
            self.actions.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.actions is not None:
            self.actions.hide()
        super().leaveEvent(event)

    @property
    def side(self) -> str:
        return self._side

    def set_available_width(self, width: int):
        """Cap the bubble width so it reads as a chat bubble, not a column."""
        cap = 560 if self._side == "in" else 420
        self.label.setMaximumWidth(min(max(120, width - 60), cap))

    def apply_width(self, width: int):
        """Constrain the bubble to ``width`` and re-measure it."""
        body = getattr(self, "label", None)
        if isinstance(body, QtWidgets.QWidget) and hasattr(body, "set_width"):
            available = max(220, width - 44)
            body.set_width(available)
            self.pill.setMaximumWidth(available)
            self.updateGeometry()
            return
        if self._side == "in":
            # Assistant answers use the full column width, minus the scrollbar
            # and a little breathing room.
            available = max(200, width - 44)
            cap = available
        else:
            available = max(160, int(width * 0.78))
            cap = 460
        text_width = max(80, min(available, cap) - 22)
        self.label.setMaximumWidth(text_width)
        # Clear the pill's cached constraint first, otherwise the layout reuses
        # the previous (possibly too narrow) width.
        self.pill.setMaximumWidth(16777215)
        self.adjustSize()
        hint = self.pill.sizeHint()
        self.pill.setMaximumWidth(max(80, min(hint.width(), min(available, cap))))
        self.updateGeometry()

    def adjustSize(self):
        body = getattr(self, "label", None)
        if isinstance(body, QtWidgets.QWidget) and hasattr(body, "set_width"):
            body.set_width(max(220, self.width() - 34))
            super().adjustSize()
            return
        if self._side == "in":
            self.label.setMaximumWidth(1200)
        else:
            self.label.setMaximumWidth(460)
        super().adjustSize()


def _markdown_to_html(text: str) -> str:
    """Render the markdown an assistant actually emits into safe rich text.

    Covers paragraphs, headings, ordered/unordered lists, tables, quotes,
    horizontal rules, links and fenced code blocks. Every code block gets a
    small header with its language so answers read like documentation instead
    of one undifferentiated wall of text.
    """
    lines = str(text).splitlines()
    blocks: List[str] = []
    paragraph: List[str] = []
    code_lines: List[str] = []
    code_lang = ""
    in_code = False

    def _inline(value: str) -> str:
        safe = html.escape(value)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", safe)
        safe = re.sub(r"`([^`]+)`",
                      f'<span style="background:{SURFACE}; color:{TEXT}; '
                      'border-radius:4px; padding:1px 4px;">\\1</span>', safe)
        safe = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                      r'<a href="\2" style="color:#6FA8DC; text-decoration:none;">\1</a>',
                      safe)
        return safe

    def _flush_paragraph():
        if not paragraph:
            return
        joined = "<br>".join(paragraph)
        blocks.append(f'<div style="margin:0 0 10px 0;">{joined}</div>')
        paragraph.clear()

    def _flush_code():
        if not code_lines:
            return
        body = html.escape("\n".join(code_lines)).rstrip("\n")
        header = ""
        if code_lang:
            header = (
                f'<div style="background:{SURFACE}; color:{TEXT_MUTED}; '
                f'font-size:11px; padding:4px 10px; border-bottom:1px solid #262628;">'
                f'{html.escape(code_lang)}</div>')
        blocks.append(
            f'<div style="margin:10px 0;">'
            f'<div style="background:{SURFACE}; border:1px solid #262628; '
            f'border-radius:8px; overflow:hidden;">{header}'
            f'<pre style="background:{SURFACE}; border:none; padding:10px 12px; '
            f'margin:0; color:{TEXT}; font-family:\'Cascadia Mono\',Consolas,monospace; '
            f'font-size:12px; line-height:1.5; white-space:pre-wrap;">{body}</pre>'
            f'</div></div>')
        code_lines.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                _flush_code()
                in_code = False
                code_lang = ""
            else:
                _flush_paragraph()
                in_code = True
                code_lang = stripped[3:].strip() or ""
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue

        # Table: a header row followed by a |---|---| separator.
        if (stripped.startswith("|") and index + 1 < len(lines)
                and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[index + 1])
                and "-" in lines[index + 1]):
            _flush_paragraph()
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            index += 2
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append([c.strip() for c in lines[index].strip().strip("|").split("|")])
                index += 1
            head_html = "".join(
                f'<th style="text-align:left; padding:5px 10px; color:{TEXT_MUTED}; '
                f'font-weight:600; border-bottom:1px solid #2B2B2D;">{_inline(c)}</th>'
                for c in header_cells)
            body_html = ""
            for cells in rows:
                padded = (cells + [""] * len(header_cells))[:len(header_cells)]
                body_html += "<tr>" + "".join(
                    f'<td style="padding:5px 10px; border-bottom:1px solid #232325;">{_inline(c)}</td>'
                    for c in padded) + "</tr>"
            blocks.append(
                f'<table cellspacing="0" cellpadding="0" width="100%" '
                f'style="margin:10px 0; border-collapse:collapse; font-size:12.5px;">'
                f'<tr>{head_html}</tr>{body_html}</table>')
            continue

        if not stripped:
            _flush_paragraph()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            _flush_paragraph()
            level = len(heading.group(1))
            size = {1: 17, 2: 15.5, 3: 14, 4: 13.5}.get(level, 13)
            top = 16 if level <= 2 else 12
            blocks.append(
                f'<div style="margin:{top}px 0 6px 0; font-size:{size}px; '
                f'font-weight:600; color:{TEXT};">{_inline(heading.group(2))}</div>')
            index += 1
            continue

        if re.match(r"^\s*([-*+])\s+", line):
            _flush_paragraph()
            items = []
            while index < len(lines) and re.match(r"^\s*([-*+])\s+", lines[index]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[index])
                items.append(
                    f'<div style="margin:2px 0 2px 2px;">'
                    f'<span style="color:{TEXT_MUTED};">•</span>&nbsp;&nbsp;{_inline(content)}</div>')
                index += 1
            blocks.append(f'<div style="margin:0 0 10px 0;">{"".join(items)}</div>')
            continue

        ordered = re.match(r"^\s*(\d+)[.)]\s+", line)
        if ordered:
            _flush_paragraph()
            items = []
            counter = int(ordered.group(1))
            while index < len(lines):
                match = re.match(r"^\s*(\d+)[.)]\s+", lines[index])
                if not match:
                    break
                content = re.sub(r"^\s*\d+[.)]\s+", "", lines[index])
                items.append(
                    f'<div style="margin:2px 0 2px 2px;">'
                    f'<span style="color:{TEXT_MUTED};">{counter}.</span>&nbsp;&nbsp;'
                    f'{_inline(content)}</div>')
                counter += 1
                index += 1
            blocks.append(f'<div style="margin:0 0 10px 0;">{"".join(items)}</div>')
            continue

        if stripped.startswith(">"):
            _flush_paragraph()
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(_inline(lines[index].strip().lstrip(">").strip()))
                index += 1
            # QLabel rich text ignores `border-left`, so the accent bar is a
            # one-pixel table cell with a background colour.
            blocks.append(
                f'<table cellspacing="0" cellpadding="0" style="margin:8px 0;"><tr>'
                f'<td width="3" bgcolor="#3F3F42"></td>'
                f'<td style="padding:4px 10px; color:{TEXT_MUTED};">'
                f'{"<br>".join(quote)}</td></tr></table>')
            continue

        if re.match(r"^\s*(---+|\*\*\*+)\s*$", line):
            _flush_paragraph()
            blocks.append('<div style="margin:12px 0; border-top:1px solid #2B2B2D;"></div>')
            index += 1
            continue

        paragraph.append(_inline(stripped))
        index += 1

    _flush_paragraph()
    if in_code:
        _flush_code()
    return "".join(blocks)
