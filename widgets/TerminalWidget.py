"""PyScribe widgets/TerminalWidget.py: integrated interactive terminal.

The terminal renders a *real* shell (PowerShell by default on Windows, bash/zsh
on POSIX) inside an editable text buffer with a prompt line you can type into.

Key behaviours
--------------
* Correct encoding for every platform (UTF-8 through ``chcp 65001`` on Windows,
  ``utf-8`` on POSIX) so Cyrillic paths and output are never mojibake.
* Prefers PowerShell for Windows so the displayed prompt ``user@host:path$``
  matches what the shell really prints.
* Inline completion popup (files, directories and commands) with keyboard
  navigation, instead of dumping a wall of matches into the buffer.
* Semantic colouring of output: errors, warnings, successes, paths, numbers.
* Smooth visual feedback: new-output highlight, command flash, exit-code badges,
  animated tab creation and completion popup.

Public classes: ``InteractiveTerminalEdit``, ``TerminalTab``, ``TerminalWidget``.
"""
import os
import base64
import platform
import time
import re
import shlex
import shutil
import socket
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from utils.settings_manager import get_settings_manager

IS_WINDOWS = platform.system() == "Windows"

# ANSI SGR colours -> hex used by _append_colored.
ANSI_COLORS = {
    30: "#5C6370", 31: "#F14C4C", 32: "#89D185", 33: "#CCA700", 34: "#75BEFF",
    35: "#C586C0", 36: "#29B8DB", 37: "#D4D4D4", 90: "#6E7681", 91: "#FF7B72",
    92: "#56D364", 93: "#E3B341", 94: "#79C0FF", 95: "#D2A8FF", 96: "#56D4DD",
    97: "#FFFFFF",
}

_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)([A-Za-z])")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class CompletionPopup(QtWidgets.QListWidget):
    """Lightweight, animated completion popup anchored under the typed token.

    A plain child widget of the terminal screen (not a top-level window): the
    terminal panel lives inside splitters/tab widgets whose layout would resize
    a *window* and hide it immediately.
    """

    accepted = QtCore.pyqtSignal(int)
    dismissed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("terminalCompletion")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        # Hidden by default: QListWidget children are shown together with their
        # parent, which would paint a stray popup box over the terminal.
        self.hide()
        self.setStyleSheet("""
            QListWidget#terminalCompletion {
                background: #10161F;
                border: 1px solid #22303F;
                border-radius: 6px;
                color: #C9D1D9;
                font-size: 12px;
                padding: 4px;
                outline: none;
            }
            QListWidget#terminalCompletion::item {
                padding: 3px 6px;
                border-radius: 4px;
                min-height: 20px;
            }
            QListWidget#terminalCompletion::item:selected {
                background: #1A3650;
                color: #00F2FE;
            }
        """)
        self._opacity = None
        self._anim = None
        self.itemClicked.connect(lambda item: self.accepted.emit(self.row(item)))

    # -- animation ---------------------------------------------------
    def _ensure_opacity(self):
        if self._opacity is None:
            self._opacity = QtWidgets.QGraphicsOpacityEffect(self)
            self._opacity.setOpacity(1.0)
            self.setGraphicsEffect(self._opacity)
        return self._opacity

    def show_items(self, items: List[Tuple[str, str]], anchor: QtCore.QPoint):
        """Show the popup; *anchor* is in parent coordinates, above the caret."""
        self.clear()
        for label, kind in items:
            icon_text = {"dir": "📁", "file": "📄", "cmd": "⚡"}.get(kind, "•")
            item = QtWidgets.QListWidgetItem(f"{icon_text}  {label}")
            item.setData(QtCore.Qt.UserRole, kind)
            self.addItem(item)
        rows = max(1, min(len(items), 8))
        row_h = max(22, self.fontMetrics().height() + 12)
        height = rows * row_h + 10
        width = min(520, max(240, max(
            (self.fontMetrics().horizontalAdvance(i[0]) for i in items), default=0) + 80))
        parent = self.parentWidget()
        pmax = parent.rect() if parent is not None else QtCore.QRect(0, 0, 800, 600)
        x = max(0, min(anchor.x(), pmax.width() - width))
        y = anchor.y()
        if y + height > pmax.height():
            y = max(0, pmax.height() - height)
        self.setGeometry(x, y, width, height)
        self.setCurrentRow(0)
        self.show()
        self.raise_()

        from widgets.animations import DURATION
        effect = self._ensure_opacity()
        effect.setOpacity(0.0)
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass
        self._anim = QtCore.QPropertyAnimation(effect, b"opacity", self)
        self._anim.setDuration(DURATION["fast"])
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def hide_popup(self):
        if not self.isVisible():
            return
        self.hide()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Tab):
            if self.currentItem() is not None:
                self.accepted.emit(self.currentRow())
            return
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide_popup()
            self.dismissed.emit()
            return
        super().keyPressEvent(event)


class InteractiveTerminalEdit(QtWidgets.QTextEdit):
    """Direct in-buffer interactive terminal screen.

    - Commands are typed directly at the prompt inside the terminal buffer
    - Prompt in clean, subtle Linux colours (``user@host:path$``)
    - Prior output / prompt can never be erased or edited
    - Readline-style shortcuts, history navigation and tab completion
    """

    def __init__(self, tab: 'TerminalTab', parent=None):
        super().__init__(parent)
        self.tab = tab
        self.prompt_pos = 0
        self.history: List[str] = []
        self.history_index = -1
        self.draft_text = ""
        self._history_restore_cursor = False
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.setObjectName("terminalScreen")
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

        self._popup = CompletionPopup(self)
        self._popup.accepted.connect(self._accept_completion)
        self._popup.dismissed.connect(self.setFocus)

        try:
            sm = get_settings_manager()
            self.terminal_font_size = int(sm.get_setting("terminal_font_size", 11))
            self.terminal_font_family = str(sm.get_setting("terminal_font", "Cascadia Mono"))
        except Exception:
            self.terminal_font_size = 11
            self.terminal_font_family = "Cascadia Mono"

        self._apply_font()

    # ------------------------------------------------------------------
    # Rendering / font
    # ------------------------------------------------------------------
    def _apply_font(self):
        term_font = QtGui.QFont(self.terminal_font_family, self.terminal_font_size)
        term_font.setStyleHint(QtGui.QFont.Monospace)
        term_font.setFixedPitch(True)
        term_font.setPixelSize(self._terminal_px())
        self.setFont(term_font)
        self.document().setDefaultFont(term_font)
        # Per-widget stylesheet: wins over the application theme so the user's
        # terminal font size is authoritative (the app-level QSS sets a generic
        # monospace size for QTextEdit#terminalScreen).
        self.setStyleSheet(f"""
            QTextEdit#terminalScreen {{
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: none;
                padding: 2px 6px;
                selection-background-color: #264F78;
                font-family: '{self.terminal_font_family}', 'Cascadia Code', 'Consolas', monospace;
                font-size: {term_font.pixelSize()}px;
            }}
        """)
        self.setCurrentCharFormat(self.get_input_format())

    def _terminal_px(self) -> int:
        """Terminal text size in device-independent pixels."""
        from app.ui_scale import scale_px

        return scale_px(max(11, round(int(self.terminal_font_size) * 1.34)))

    def _fmt_font(self) -> QtGui.QFont:
        font = QtGui.QFont(self.terminal_font_family)
        font.setPixelSize(self._terminal_px())
        font.setStyleHint(QtGui.QFont.Monospace)
        font.setFixedPitch(True)
        return font

    def get_input_format(self) -> QtGui.QTextCharFormat:
        fmt = QtGui.QTextCharFormat()
        fmt.setFont(self._fmt_font())
        fmt.setFontWeight(QtGui.QFont.Normal)
        fmt.setForeground(QtGui.QColor("#CCCCCC"))
        return fmt

    def _update_document_font_size(self):
        """Scale all existing text in the terminal buffer to the new font size."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QtGui.QTextCursor.Document)
        fmt = QtGui.QTextCharFormat()
        fmt.setFont(self._fmt_font())
        cursor.mergeCharFormat(fmt)
        cursor.clearSelection()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setCurrentCharFormat(self.get_input_format())
        self.ensureCursorVisible()

    def apply_terminal_settings(self):
        try:
            sm = get_settings_manager()
            self.terminal_font_size = int(sm.get_setting("terminal_font_size", 11))
            family = sm.get_setting("terminal_font", "Cascadia Mono")
            if family:
                self.terminal_font_family = str(family)
        except Exception:
            self.terminal_font_size = 11

        self._apply_font()
        self._update_document_font_size()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def wheelEvent(self, event):
        if event.modifiers() == QtCore.Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def _zoom_to(self, size: int):
        self.terminal_font_size = max(8, min(32, int(size)))
        self._apply_font()
        self._update_document_font_size()
        try:
            get_settings_manager().set_setting("terminal_font_size", self.terminal_font_size)
        except Exception:
            pass

    def zoom_in(self):
        self._zoom_to(self.terminal_font_size + 1)

    def zoom_out(self):
        self._zoom_to(self.terminal_font_size - 1)

    def reset_zoom(self):
        try:
            default_sz = int(get_settings_manager().get_setting("terminal_font_size", 11))
        except Exception:
            default_sz = 11
        self._zoom_to(default_sz)

    def zoom_by_wheel_animation(self, step: int):
        """Smooth wheel zoom: animate through one size step."""
        from widgets.animations import animate_property
        start = self.terminal_font_size
        target = max(8, min(32, start + step))
        if target == start:
            return
        anim = QtCore.QVariantAnimation(self)
        anim.setDuration(90)
        anim.setStartValue(start)
        anim.setEndValue(target)

        def _apply(v):
            self._zoom_to(int(v))

        anim.valueChanged.connect(_apply)
        anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        self._popup.hide_popup()
        super().mousePressEvent(event)
        self.setCurrentCharFormat(self.get_input_format())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.setCurrentCharFormat(self.get_input_format())

    def insertFromMimeData(self, source: QtCore.QMimeData):
        if not source.hasText():
            return
        text = source.text().replace("\r\n", "\n").replace("\r", "\n")
        # Multi-line paste should not execute commands — collapse to spaces.
        text = text.replace("\n", " ")
        cursor = self.textCursor()
        if cursor.position() < self.prompt_pos:
            cursor.movePosition(QtGui.QTextCursor.End)
            self.setTextCursor(cursor)
        cursor.insertText(text, self.get_input_format())
        self.ensureCursorVisible()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # While the shell echoes its own init line, swallow typing so the user
        # does not see their keystrokes mixed into that echo.
        if getattr(self.tab, "echo_is_pending", lambda: False)():
            if event.text() and not modifiers:
                return

        if self._popup.isVisible():
            if key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up):
                if key == QtCore.Qt.Key_Down:
                    self._popup.setCurrentRow(min(self._popup.currentRow() + 1, self._popup.count() - 1))
                else:
                    self._popup.setCurrentRow(max(self._popup.currentRow() - 1, 0))
                return
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Tab):
                self._accept_completion()
                return
            if key == QtCore.Qt.Key_Escape:
                self._popup.hide_popup()
                return

        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)

        # Zoom shortcuts
        if ctrl and key in (QtCore.Qt.Key_Equal, QtCore.Qt.Key_Plus):
            self.zoom_in()
            return
        if ctrl and key == QtCore.Qt.Key_Minus:
            self.zoom_out()
            return
        if ctrl and key == QtCore.Qt.Key_0:
            self.reset_zoom()
            return

        # Ctrl+C: copy if selected, otherwise cancel line / interrupt
        if ctrl and key == QtCore.Qt.Key_C:
            if self.textCursor().hasSelection():
                self.copy()
                return
            self.write_signal_interrupt()
            return

        # Ctrl+L: clear screen
        if ctrl and key == QtCore.Qt.Key_L:
            self.tab.clear()
            self.tab.print_prompt()
            return

        # Ctrl+U: clear current input line
        if ctrl and key == QtCore.Qt.Key_U:
            self._set_input_text("")
            return

        # Ctrl+A / Home -> start of command, Ctrl+E / End -> end
        if (ctrl and key == QtCore.Qt.Key_A) or (key == QtCore.Qt.Key_Home and not ctrl):
            cursor = self.textCursor()
            cursor.setPosition(self.prompt_pos)
            self.setTextCursor(cursor)
            return
        if (ctrl and key == QtCore.Qt.Key_E) or (key == QtCore.Qt.Key_End and not ctrl):
            cursor = self.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            self.setTextCursor(cursor)
            return

        # Ctrl+W: delete previous word (fallback for word-wise delete)
        if ctrl and key == QtCore.Qt.Key_W:
            self._delete_previous_word()
            return

        # Up / Down: history navigation
        if key == QtCore.Qt.Key_Up and not shift:
            self.history_up()
            return
        if key == QtCore.Qt.Key_Down and not shift:
            self.history_down()
            return

        # Tab: completion
        if key == QtCore.Qt.Key_Tab and not ctrl:
            self.autocomplete()
            return

        # Return / Enter: execute command
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            # If an IDE-launched program is waiting for stdin, feed the line to
            # it instead of sending a new shell command.
            if getattr(self.tab, "is_run_process_active", lambda: False)():
                line = self.get_current_command()
                self._set_input_text("")
                if getattr(self.tab, "send_run_input", lambda _t: False)(line):
                    self._insert_at_end(line)
                    self.tab.print_prompt()
                    return
            self._submit_line()
            return

        # Backspace: never delete the prompt itself
        if key == QtCore.Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.hasSelection():
                if cursor.selectionStart() < self.prompt_pos:
                    cursor.setPosition(self.prompt_pos)
                    cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
                    self.setTextCursor(cursor)
            elif cursor.position() <= self.prompt_pos:
                return

        # Never move the caret into the prompt area
        cursor = self.textCursor()
        if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Home) and cursor.position() <= self.prompt_pos:
            return
        if cursor.position() < self.prompt_pos and not cursor.hasSelection():
            cursor.movePosition(QtGui.QTextCursor.End)
            self.setTextCursor(cursor)

        if event.text():
            self.setCurrentCharFormat(self.get_input_format())

        super().keyPressEvent(event)
        # The buffer must keep the caret after the prompt.
        if self.textCursor().position() < self.prompt_pos:
            c = self.textCursor()
            c.movePosition(QtGui.QTextCursor.End)
            self.setTextCursor(c)

    def write_signal_interrupt(self):
        """Show ``^C`` on the current input line, interrupt the shell, re-prompt."""
        self.history_index = -1
        self.tab.interrupt()
        # The shell echoes ``^C`` itself once the control byte is consumed; the
        # local echo covers the "nothing running" case so the gesture always
        # produces visible feedback.
        self._insert_at_end("^C")
        self.tab.print_prompt()

    def _insert_at_end(self, text: str):
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText(text, self.get_input_format())
        self.prompt_pos = self.textCursor().position()

    def _delete_previous_word(self):
        text = self.get_current_command()
        rel_pos = max(0, self.textCursor().position() - self.prompt_pos)
        left = text[:rel_pos].rstrip()
        cut = max(left.rfind(' '), left.rfind('/'), left.rfind('\\')) + 1
        if cut <= 0:
            new_text = text[rel_pos:].lstrip()
            new_rel = 0
        else:
            new_text = left[:cut] + text[rel_pos:]
            new_rel = cut
        self._set_input_text(new_text)
        cursor = self.textCursor()
        cursor.setPosition(self.prompt_pos + new_rel)
        self.setTextCursor(cursor)

    def _submit_line(self):
        command = self.get_current_command().strip()
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText("\n", self.get_input_format())
        self.prompt_pos = self.textCursor().position()
        self.history_index = -1
        self.draft_text = ""
        if command:
            if not self.history or self.history[-1] != command:
                self.history.append(command)
            # Sharing history across tabs makes a multi-tab session natural.
            store = getattr(self.tab, 'shared_history', None)
            if store is not None and store is not self.history:
                if not store or store[-1] != command:
                    store.append(command)
                self.history = store
        self.tab.execute_command(command, typed_in_buffer=True)

    # ------------------------------------------------------------------
    # Command buffer helpers
    # ------------------------------------------------------------------
    def get_current_command(self) -> str:
        full = self.toPlainText()
        return full[self.prompt_pos:] if len(full) >= self.prompt_pos else ""

    def _set_input_text(self, text: str):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(self.prompt_pos)
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
        fmt = self.get_input_format()
        cursor.insertText(text, fmt)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setCurrentCharFormat(fmt)
        self.ensureCursorVisible()

    def history_up(self):
        if not self.history:
            return
        if self.history_index == -1:
            self.draft_text = self.get_current_command()
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self._set_input_text(self.history[self.history_index])

    def history_down(self):
        if not self.history or self.history_index == -1:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._set_input_text(self.history[self.history_index])
        else:
            self.history_index = -1
            self._set_input_text(self.draft_text)

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------
    def _token_at_cursor(self) -> Tuple[str, int]:
        text = self.get_current_command()
        rel_pos = max(0, self.textCursor().position() - self.prompt_pos)
        left = text[:rel_pos]
        match = re.search(r'([^\s\'"]*)$', left)
        if not match:
            return "", rel_pos
        return match.group(1), match.start(1)

    def autocomplete(self):
        working_dir = getattr(self.tab, 'working_dir', None) or os.getcwd()
        token, token_start = self._token_at_cursor()
        is_first_word = not token or not self.get_current_command()[:token_start].strip()

        items: List[Tuple[str, str]] = []
        token_dir = os.path.dirname(token)
        token_base = os.path.basename(token)
        # Handle quoted paths like "C:\Program Files/..."
        lookup_dir = working_dir
        if token_dir:
            lookup_dir = os.path.normpath(
                os.path.join(working_dir, token_dir.replace('/', os.sep))
            )

        try:
            entries = os.listdir(lookup_dir)
        except OSError:
            entries = []

        if token_base or token_dir:
            for entry in sorted(entries, key=str.lower):
                if not entry.lower().startswith(token_base.lower()):
                    continue
                full = os.path.join(lookup_dir, entry)
                kind = "dir" if os.path.isdir(full) else "file"
                display = (token_dir.replace('\\', '/') + '/' if token_dir else '') + entry
                items.append((display, kind))
        if is_first_word:
            command_items = [(c, "cmd") for c in self.tab.available_commands()
                             if c.lower().startswith(token_base.lower())]
            items = command_items + items

        if not items:
            self._popup.hide_popup()
            return

        if len(items) == 1:
            self._apply_completion(token_start, items[0][0], items[0][1])
            return

        # Common-prefix expansion first, then show the popup.
        if len(items) > 1 and all(kind != "cmd" for _, kind in items):
            common = os.path.commonprefix([label for label, _ in items])
            if len(common) > len(token):
                self._replace_token(token_start, common)
        anchor = self.cursorRect().bottomLeft()
        self._popup_items = items
        self._popup_token = (token_start, token, [label for label, _ in items])
        self._popup.show_items(items, anchor)

    def _apply_completion(self, token_start: int, label: str, kind: str):
        pad = "" if kind == "dir" else " "
        if kind == "dir" and not label.endswith(('/', '\\')):
            pad = "/"
        self._replace_token(token_start, label + pad)
        self._popup.hide_popup()

    def _accept_completion(self):
        idx = self._popup.currentRow()
        items = getattr(self, "_popup_items", []) or []
        if not (0 <= idx < len(items)):
            self._popup.hide_popup()
            return
        label, kind = items[idx]
        token_start, _token, _labels = getattr(self, "_popup_token", (0, "", []))
        self._apply_completion(token_start, label, kind)
        self.setFocus()

    def _replace_token(self, token_start: int, replacement: str):
        text = self.get_current_command()
        rel_pos = max(0, self.textCursor().position() - self.prompt_pos)
        new_text = text[:token_start] + replacement + text[rel_pos:]
        self._set_input_text(new_text)
        cur = self.textCursor()
        cur.setPosition(self.prompt_pos + token_start + len(replacement))
        self.setTextCursor(cur)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------
    def _context_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        act_copy = menu.addAction("Копировать")
        act_copy.setShortcut(QtGui.QKeySequence("Ctrl+Shift+C"))
        act_copy.setEnabled(bool(self.textCursor().hasSelection()))
        act_copy.triggered.connect(self.copy)
        act_paste = menu.addAction("Вставить")
        act_paste.setShortcut(QtGui.QKeySequence("Ctrl+Shift+V"))
        act_paste.triggered.connect(self.paste)
        menu.addSeparator()
        act_clear = menu.addAction("Очистить терминал")
        act_clear.triggered.connect(lambda: (self.tab.clear(), self.tab.print_prompt()))
        menu.exec_(self.mapToGlobal(pos))


_ANSI_STRIP_RE = re.compile(
    r"\x1b\][^\x07]*(?:\x07|$)"      # OSC (window title)
    r"|\x1b\[[0-9;?]*[A-Za-z]"         # CSI (colors, cursor)
    r"|\x1b[()][A-Za-z0-9]"             # charset selection
    r"|\x07"                            # bell
)


def _strip_ansi(text: str) -> str:
    """Remove terminal control sequences so bash/Git Bash output stays readable."""
    if not text or ("\x1b" not in text and "\x07" not in text):
        return text
    return _ANSI_STRIP_RE.sub("", text)


class TerminalTab(QtWidgets.QWidget):
    """One shell session rendered inside the terminal panel."""

    finished = QtCore.pyqtSignal()
    working_dir_changed = QtCore.pyqtSignal(str)
    command_finished = QtCore.pyqtSignal(int)   # exit code of the last command
    busy_changed = QtCore.pyqtSignal(bool)

    def __init__(self, tab_id, title="Терминал", working_dir=None, parent=None, shared_history=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self.title = title
        self.working_dir = working_dir or os.getcwd()
        self.process = None
        self._closing = False
        self.shell_program = None
        self.shell_args = None
        self._prompt_timer = None
        self._busy = False
        self._last_command = ""
        self._command_running = False
        self._init_echo_pending = 0
        self._init_echo_deadline = 0.0
        self._init_echo_timer = None
        self._internal_sync_lines = 0
        self._internal_sync_timer = None
        self._reprompt_retries = 0
        self.shared_history = shared_history if shared_history is not None else []
        self._build()
        QtCore.QTimer.singleShot(0, self.start_shell)

    # ------------------------------------------------------------------
    @staticmethod
    def get_linux_user_host():
        user = (os.getenv("USER") or os.getenv("USERNAME") or "user").lower()
        try:
            host = socket.gethostname().split(".")[0].lower() or "localhost"
        except Exception:
            host = "localhost"
        return user, host

    def format_linux_path(self, raw_path: str) -> str:
        if not raw_path:
            return "~"
        try:
            path = os.path.normpath(str(raw_path))
        except Exception:
            return str(raw_path)
        home = os.path.normpath(os.path.expanduser("~"))
        if path.lower() == home.lower():
            display = "~"
        elif path.lower().startswith(home.lower() + os.sep):
            rel = os.path.relpath(path, home).replace(os.sep, "/")
            display = f"~/{rel}"
        else:
            display = path.replace(os.sep, "/")

        parts = display.split("/")
        if len(display) > 42 and len(parts) > 3:
            display = f"{parts[0]}/.../{parts[-1]}"
        return display

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.screen = InteractiveTerminalEdit(self)
        layout.addWidget(self.screen)

    def available_commands(self) -> List[str]:
        """Command names available for first-word completion."""
        if IS_WINDOWS:
            builtins = [
                "cd", "cls", "clear", "dir", "echo", "exit", "git", "history", "pwd",
                "python", "py", "pip", "pytest", "npm", "npx", "node", "code", "type",
                "where", "set", "start", "tasklist", "terminal",
            ]
        else:
            builtins = ["cd", "ls", "pwd", "echo", "clear", "git", "python3", "pip", "make", "grep", "cat"]
        return builtins

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------
    def _fmt(self, **kwargs) -> QtGui.QTextCharFormat:
        fmt = QtGui.QTextCharFormat()
        fmt.setFont(self.screen._fmt_font())
        for key, value in kwargs.items():
            if key == "color":
                fmt.setForeground(QtGui.QColor(value))
            elif key == "bold":
                fmt.setFontWeight(QtGui.QFont.DemiBold if value else QtGui.QFont.Normal)
        return fmt

    def _insert_prompt_segments(self, cursor, user, host, path):
        cursor.insertText(f"{user}@{host}", self._fmt(color="#89D185", bold=True))
        cursor.insertText(":", self._fmt(color="#6E7681"))
        cursor.insertText(path, self._fmt(color="#75BEFF", bold=True))
        cursor.insertText("$ ", self._fmt(color="#D4D4D4"))

    def print_prompt(self, initial_text: str = ""):
        """Render the prompt at the end of the buffer exactly once.

        Nothing is drawn until the shell process is actually running, otherwise
        the user sees a prompt that then "jumps" down to a second, real one.
        """
        if self._prompt_timer:
            try:
                self._prompt_timer.stop()
            except Exception:
                pass

        if not self._shell_running():
            return
        # A REPL prints its own prompt (``>>>``); drawing ours on top of it
        # produced two prompts and looked broken.
        if self._stdin_is_interpret():
            return

        user, host = self.get_linux_user_host()
        path = self.format_linux_path(self.working_dir)
        prompt_plain = f"{user}@{host}:{path}$ "

        cursor = self.screen.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        full_text = self.screen.toPlainText()

        # Buffer already ends with exactly the prompt we want to show.
        last_line_start = full_text.rfind('\n') + 1
        last_line = full_text[last_line_start:]
        if not initial_text and last_line == prompt_plain:
            self.screen.prompt_pos = len(full_text)
            self.screen.setCurrentCharFormat(self.screen.get_input_format())
            return

        # The working directory changed: replace the empty prompt that still
        # shows the old path, instead of stacking a second prompt under it.
        if not initial_text and self._replace_stale_prompt(full_text, prompt_plain):
            full_text = self.screen.toPlainText()
            cursor = self.screen.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)

        # Make sure output and the prompt live on separate lines.
        if full_text and not full_text.endswith('\n'):
            cursor.movePosition(QtGui.QTextCursor.End)
            cursor.insertText("\n", self._fmt(color="#D4D4D4"))

        cursor.movePosition(QtGui.QTextCursor.End)
        self._insert_prompt_segments(cursor, user, host, path)
        if initial_text:
            cursor.insertText(initial_text, self.screen.get_input_format())
        self.screen.setTextCursor(cursor)
        self.screen.setCurrentCharFormat(self.screen.get_input_format())
        self.screen.prompt_pos = self.screen.textCursor().position()
        self.screen.ensureCursorVisible()

    def _last_line_is_empty_prompt(self, full_text: str, prompt_plain: str) -> bool:
        """True when the buffer already ends with the *current* prompt line."""
        last_line_start = full_text.rfind('\n') + 1
        last_line = full_text[last_line_start:]
        return bool(last_line) and last_line == prompt_plain

    def _replace_stale_prompt(self, full_text: str, prompt_plain: str) -> bool:
        """Replace an empty prompt showing a *different* path (dir changed).

        Returns True when the prompt line was removed, so print_prompt() can
        draw the current one without stacking a second prompt on top.
        """
        last_line_start = full_text.rfind('\n') + 1
        last_line = full_text[last_line_start:]
        if not last_line or last_line == prompt_plain:
            return False
        user, host = self.get_linux_user_host()
        if not last_line.startswith(f"{user}@{host}:") or not last_line.rstrip().endswith('$'):
            return False
        cursor = self.screen.textCursor()
        cursor.setPosition(last_line_start)
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.screen.setTextCursor(cursor)
        self.screen.prompt_pos = cursor.position()
        return True

    # ------------------------------------------------------------------
    # Shell process management
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_shell() -> Tuple[str, List[str]]:
        """Prefer PowerShell on Windows, keep bash/zsh on POSIX."""
        if IS_WINDOWS:
            pwsh = shutil.which("pwsh")
            if pwsh:
                return pwsh, ["-NoLogo", "-NoExit", "-NoProfile"]
            powershell = shutil.which("powershell")
            if powershell:
                return powershell, ["-NoLogo", "-NoExit", "-NoProfile"]
            git_bash = r"C:\Program Files\Git\bin\bash.exe"
            if os.path.exists(git_bash):
                return git_bash, ["--login", "-i"]
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return comspec, ["/Q", "/K"]
        shell = os.environ.get("SHELL", "/bin/bash")
        return shell, ["-i"]

    def _startup_script(self) -> str:
        """Shell-specific init that guarantees UTF-8 output and a silent prompt.

        The prompt must print nothing: PyScribe renders its own prompt, and any
        text the shell emits would be interleaved with real command output. The
        trailing here-string keeps PowerShell busy so it does not print its
        ``PS>`` continuation prompt after consuming stdin.
        """
        prog = (self.shell_program or "").lower()
        # An interpreter (python/node) understands none of the shell init code:
        # sending it there produced a SyntaxError at startup. It needs no init
        # at all, and it prints its own ``>>>`` prompt.
        if self._stdin_is_interpret():
            return ""
        if "bash" in prog or prog.endswith("sh.exe") or "zsh" in prog:
            # Git Bash on Windows understands only POSIX init. It used to get
            # `chcp 65001`, a cmd builtin, and kept printing its own loud
            # prompt with ANSI escapes.
            return ("export PS1='' PS2='' PROMPT_COMMAND=''; "
                    "export PYTHONIOENCODING=utf-8")
        if IS_WINDOWS and self._stdin_is_powershell():
            return (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
                "$OutputEncoding=[System.Text.Encoding]::UTF8;"
                "$global:LASTEXITCODE=0;"
                "function global:prompt { '' }"
            )
        if IS_WINDOWS:
            return "chcp 65001>nul"
        # POSIX: PS1 is rendered by PyScribe itself, silence the shell prompt.
        return "export PS1='' PS2=''; export PYTHONIOENCODING=utf-8"

    def _stdin_is_interpret(self) -> bool:
        """True for REPL programs (python/node) that take no shell init."""
        prog = (self.shell_program or "").lower()
        return any(name in prog for name in ("python", "node.exe", "irb", "ruby.exe"))

    def _stdin_is_powershell(self) -> bool:
        prog = (self.shell_program or "").lower()
        return IS_WINDOWS and "cmd.exe" not in prog and ("powershell" in prog or prog.endswith("pwsh.exe"))

    def _get_encoding(self):
        return "utf-8"

    def _decode(self, data) -> str:
        raw = bytes(data)
        try:
            text = raw.decode(self._get_encoding(), errors="replace")
        except Exception:
            text = raw.decode("latin-1", errors="replace")
        return _strip_ansi(text)

    def _set_busy(self, busy: bool):
        if self._busy == busy:
            return
        self._busy = busy
        try:
            self.busy_changed.emit(busy)
        except Exception:
            pass

    def start_shell(self, shell_program=None, shell_args=None, *args, **kwargs):
        """Start or restart the background shell process without throwing exceptions."""
        if self._prompt_timer:
            try:
                self._prompt_timer.stop()
            except Exception:
                pass

        if self.process and self.process.state() != QtCore.QProcess.NotRunning:
            # Detach the old process first: its `finished` signal would
            # otherwise schedule a restart that kills the shell we are about to
            # start, producing an endless «процесс завершён → перезапуск» loop
            # whenever the shell is switched or respawned.
            try:
                self.process.finished.disconnect(self._on_process_finished)
            except (TypeError, RuntimeError):
                pass
            try:
                self.process.kill()
                self.process.waitForFinished(300)
            except Exception:
                pass

        self._closing = False
        self.process = QtCore.QProcess(self)
        self.process.setWorkingDirectory(
            str(self.working_dir) if os.path.isdir(self.working_dir) else os.getcwd()
        )
        self.process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_process_finished)
        self.process.started.connect(self._on_process_started)
        try:
            env = QtCore.QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("PYTHONUTF8", "1")
            env.insert("PYTHONLEGACYWINDOWSSTDIO", "0")
            if IS_WINDOWS:
                env.insert("PYTHONLEGACYWINDOWSFSENCODING", "0")
            self.process.setProcessEnvironment(env)
        except Exception:
            pass
        if IS_WINDOWS and hasattr(self.process, "setCreateProcessArgumentsModifier"):
            # CREATE_NO_WINDOW prevents the child shell from opening a console window.
            self.process.setCreateProcessArgumentsModifier(
                lambda args: setattr(args, "flags", args.flags | 0x08000000)
            )

        prog = shell_program or self.shell_program
        s_args = shell_args if shell_args is not None else self.shell_args
        if prog:
            self.shell_program, self.shell_args = prog, list(s_args or [])
        else:
            self.shell_program, self.shell_args = self._detect_shell()

        self.process.start(self.shell_program, self.shell_args)
        # No prompt yet: _on_process_started() draws it once the shell exists.
        self._schedule_prompt(400)

    def _shell_running(self) -> bool:
        return bool(self.process and self.process.state() == QtCore.QProcess.Running)

    def _schedule_prompt(self, delay: int = 260):
        """Re-render the prompt once the shell has had time to start."""
        if self._prompt_timer is not None:
            try:
                self._prompt_timer.stop()
            except RuntimeError:
                pass
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._reprompt_when_ready)
        timer.start(delay)
        self._prompt_timer = timer

    def _reprompt_when_ready(self):
        if not self._shell_running():
            self._schedule_prompt(150)
            return
        # Let the shell finish consuming its init line before drawing the
        # prompt, so no stray echo/blank line can appear above it.
        if self.echo_is_pending() and self._reprompt_retries < 8:
            self._reprompt_retries += 1
            self._schedule_prompt(120)
            return
        self._reprompt_retries = 0
        self.print_prompt()

    def _on_process_started(self):
        """Run the init script as a *single* command line (mangled by the shell
        otherwise, since stdin is not a TTY)."""
        script = self._startup_script()
        if not script or self.process is None:
            return
        self._suppress_echo(script)
        try:
            self.process.write((script + self._eol()).encode("ascii", errors="replace"))
        except Exception:
            pass
        # The prompt is rendered only after the shell consumed its init line.
        self._schedule_prompt(220)

    def _suppress_echo(self, script: str):
        """Remember the init line so it is not rendered as user-typed text.

        The filter is *count based* (`_init_echo_pending` completed lines), not
        content based: matching on content also matched the user's own command
        echo (``[Console]::OutputEncoding=...``) and swallowed real output.
        """
        if not script.strip():
            return
        self._init_echo_pending = 1
        self._init_echo_deadline = time.monotonic() + 6.0
        timer = getattr(self, "_init_echo_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except RuntimeError:
                pass
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._clear_init_echo)
        timer.start(6000)
        self._init_echo_timer = timer

    def _clear_init_echo(self):
        self._init_echo_pending = 0
        self._init_echo_timer = None

    def note_buffer_growth(self, text: str):
        """No-op hook kept for backwards compatibility."""

    def echo_is_pending(self) -> bool:
        """True while the shell still owes us the echo of its init line."""
        if self._init_echo_pending <= 0:
            return False
        if time.monotonic() > self._init_echo_deadline:
            self._clear_init_echo()
            return False
        return True

    def _on_process_finished(self, exit_code, exit_status):
        if self._closing:
            return
        # Ignore late signals from a shell that was already replaced.
        if self.sender() is not None and self.sender() is not self.process:
            return
        self._set_busy(False)
        self.append_system_line(f"Процесс завершён (код {exit_code}). Перезапуск оболочки…")
        self.finished.emit()
        if getattr(self, "_restart_pending", False):
            return
        self._restart_pending = True
        QtCore.QTimer.singleShot(150, self._restart_shell)

    def _restart_shell(self):
        """Restart the shell once per exit, even if several signals arrive."""
        self._restart_pending = False
        if self._closing:
            return
        self.start_shell()

    # ------------------------------------------------------------------
    # Shell I/O
    # ------------------------------------------------------------------
    def _read_stdout(self):
        if self._closing or not self.process:
            return
        text = self._decode(self.process.readAllStandardOutput())
        if not text:
            return
        # Drop only the shell's echo of our own init line.
        text = self._drop_init_echo(text)
        if not text:
            return
        text = self._strip_shell_prompt(text)
        if not text:
            return
        self._append_colored(text, "output")
        if self._command_running and self._looks_like_result(text):
            self.mark_command_finished(0)

    def _drop_init_echo(self, text: str) -> str:
        """Remove the echo of the shell init line and internal ``cd`` lines.

        Echo detection is deterministic: the first *complete* line the shell
        prints after start is its echo of the init line (Windows PowerShell
        echoes everything it reads from a piped stdin). No content matching and
        no tail buffering is involved, so user output can never be lost.
        """
        pending = getattr(self, "_init_echo_pending", 0) or 0
        internal = getattr(self, "_internal_sync_lines", 0) or 0
        if pending <= 0 and internal <= 0:
            return text

        lines = text.split("\n")
        tail = lines.pop() if lines else ""  # incomplete last line
        out_lines = []
        for line in lines:
            if pending > 0 and not line.strip():
                # Blank line produced by the echo itself: harmless, drop it.
                continue
            if pending > 0:
                pending -= 1
                self._init_echo_pending = pending
                if pending <= 0:
                    self._clear_init_echo()
                continue
            if internal > 0 and self._is_internal_sync_line(line):
                internal -= 1
                self._internal_sync_lines = internal
                if internal <= 0:
                    self._clear_internal_sync()
                continue
            out_lines.append(line + "\n")

        # An unterminated tail cannot be echo (echo always ends with a newline),
        # so it is always real output and rendered immediately.
        return "".join(out_lines) + tail

    def _read_stderr(self):
        if self._closing or not self.process:
            return
        text = self._decode(self.process.readAllStandardError())
        if not text:
            return
        text = self._strip_shell_prompt(text)
        if text:
            self._append_colored(text, "error")

    def _prompt_regex(self) -> re.Pattern:
        """Regex matching the prompt line we render (use with re.escape'd prefix)."""
        user, host = self.get_linux_user_host()
        return re.compile(r"(?m)^" + re.escape(f"{user}@{host}:") + r"[^\r\n]*\$\s*$")

    def _strip_shell_prompt(self, text: str) -> str:
        """Remove shell prompts that leak into the captured output."""
        # Windows PowerShell prints a bare "PS>" when its stdin is a pipe.
        # Drop the marker *and* the blank line it would otherwise leave behind.
        text = re.sub(r"(?m)^[ \t]*PS>[ \t]*\r?\n?", "", text)
        text = text.replace("PS>", "")
        # Our own prompt echoed by the shell at a line start: "user@host:path$ ".
        text = self._prompt_regex().sub("", text)
        # Our prompt echoed *after* output on the same line (no preceding \n).
        user, host = self.get_linux_user_host()
        inline = re.compile(re.escape(f"{user}@{host}:") + r"[^\r\n$]*\$\s*")
        text = inline.sub("", text)
        # PowerShell prompt emitted before we replaced it ("PS C:\dir> ").
        text = re.sub(r"(?m)^[ \t]*PS [A-Za-z]:[^\r\n>]*>[ \t]*\r?\n?", "", text)
        # cmd.exe prompt ("C:\path>") at the end of a read chunk.
        text = re.sub(r"(?m)^[A-Za-z]:(\\|/)[^\r\n>]*>[ \t]*\r?\n?", "", text)
        return text

    # Markers that a command has finished (used for the busy indicator only).
    _RESULT_MARKERS = re.compile(
        r"\b(error|failed|failure|exception|traceback|success|successfully|done|completed|"
        r"ошибка|готово|не найдено|not found|command not found|is not recognized)\b",
        re.IGNORECASE,
    )

    def _looks_like_result(self, text: str) -> bool:
        return bool(self._RESULT_MARKERS.search(strip_ansi(text)))

    def write(self, text):
        if self.process and self.process.state() == QtCore.QProcess.Running:
            try:
                self.process.write(text.encode(self._get_encoding()))
                return True
            except Exception:
                return False
        return False

    # ------------------------------------------------------------------
    # Output rendering
    # ------------------------------------------------------------------
    _OUTPUT_ROLES = (
        (re.compile(r"\b(error|failed|failure|exception|traceback|fatal|cannot|ошибка)\b", re.I), "error"),
        (re.compile(r"\b(warning|deprecated|warn|предупреждение)\b", re.I), "warning"),
        (re.compile(r"\b(success|successfully|done|completed|ok)\b", re.I), "success"),
    )

    def _role_for_line(self, line: str) -> str:
        for pattern, role in self._OUTPUT_ROLES:
            if pattern.search(line):
                return role
        if re.match(r"^\s*[A-Za-z]:[\\/]|^\s*/[\w./-]+$", line):
            return "path"
        return "output"

    def _append_colored(self, text, role="output"):
        """Append shell output with per-line semantic colouring (ANSI aware)."""
        if not text:
            return
        text = text.replace("\r\n", "\n").replace("\r", "")
        cursor = self.screen.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        # Start on a fresh line: the buffer normally ends with the editable
        # prompt, and program output must never be glued onto it.
        if self._last_line_is_empty_prompt(self.screen.toPlainText(), ""):
            cursor.insertText("\n", self._fmt(color="#D4D4D4"))
        cursor.beginEditBlock()

        palette = {
            "system": "#75BEFF",
            "command": "#D4D4D4",
            "error": "#F14C4C",
            "warning": "#CCA700",
            "success": "#89D185",
            "path": "#75BEFF",
            "output": "#D4D4D4",
        }

        for chunk in self._split_ansi(text):
            if isinstance(chunk, tuple):
                color, piece = chunk
                fmt = self._fmt(color=color)
                cursor.insertText(piece, fmt)
                continue
            # Plain text: colour per line for readability.
            for i, line in enumerate(chunk.split("\n")):
                if i:
                    cursor.insertText("\n", self._fmt(color=palette["output"]))
                if not line:
                    continue
                line_role = role if role != "output" else self._role_for_line(line)
                cursor.insertText(line, self._fmt(color=palette.get(line_role, palette["output"])))

        cursor.endEditBlock()
        self.screen.setTextCursor(cursor)
        self.screen.prompt_pos = self.screen.textCursor().position()
        self.screen.setCurrentCharFormat(self.screen.get_input_format())
        self.screen.ensureCursorVisible()
        try:
            self.note_buffer_growth(strip_ansi(text))
        except Exception:
            pass

    @staticmethod
    def _split_ansi(text: str):
        """Split text into [(color, piece) | plain_piece] honouring SGR sequences."""
        out = []
        pos = 0
        color = None
        for match in _ANSI_RE.finditer(text):
            if match.start() > pos:
                out.append((color, text[pos:match.start()]) if color else text[pos:match.start()])
            params = match.group(1)
            if match.group(2) == "m":
                codes = [int(p) for p in params.split(";") if p.strip().isdigit()] or [0]
                for code in codes:
                    if code == 0:
                        color = None
                    elif code in ANSI_COLORS:
                        color = ANSI_COLORS[code]
            pos = match.end()
        if pos < len(text):
            out.append((color, text[pos:]) if color else text[pos:])
        return [c for c in out if not (isinstance(c, str) and not c)]

    def append_system_line(self, text):
        """Show an IDE-owned terminal line without sending it to the shell."""
        if not text:
            return
        try:
            full_text = self.screen.toPlainText()
            cursor = self.screen.textCursor()
        except RuntimeError:
            return  # widget already destroyed during shutdown
        cursor.movePosition(QtGui.QTextCursor.End)
        had_prompt = False
        user_draft = ""
        if self.screen.prompt_pos > 0:
            line_start = full_text.rfind('\n', 0, self.screen.prompt_pos) + 1
            current_prompt_line = full_text[line_start:self.screen.prompt_pos]
            if current_prompt_line.rstrip().endswith('$'):
                had_prompt = True
                user_draft = full_text[self.screen.prompt_pos:]
                cursor.setPosition(line_start)
                cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                self.screen.setTextCursor(cursor)
                self.screen.prompt_pos = cursor.position()

        lowered = str(text).lower()
        role = "system"
        if "error" in lowered or "failed" in lowered or "ошибка" in lowered:
            role = "error"
        elif "warning" in lowered or "предупреждение" in lowered:
            role = "warning"
        self._append_colored(str(text) + "\n", role)

        if had_prompt:
            self.print_prompt(initial_text=user_draft)

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------
    def _is_cd(self, command: str) -> bool:
        low = command.strip().lower()
        return low == "cd" or low.startswith("cd ") or low.startswith("cd\\") or low.startswith("cd/")

    def _cd_target(self, command: str) -> str:
        parts = command.strip().split(maxsplit=1)
        target = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else "~"
        if target.lower().startswith("/d "):
            target = target[3:].strip().strip('"').strip("'")
        return target

    def _resolve_dir(self, target: str) -> Optional[str]:
        if target in ("~", ""):
            # PowerShell uses $HOME; cmd/bash use ~ too.
            candidate = os.path.expanduser("~")
        else:
            candidate = target
            if not os.path.isabs(candidate):
                candidate = os.path.join(self.working_dir, candidate)
        candidate = os.path.normpath(candidate)
        return candidate if os.path.isdir(candidate) else None

    def execute_command(self, command: str, typed_in_buffer: bool = False):
        """Send a command to the shell.

        ``typed_in_buffer`` means the command was already echoed by the user's
        typing, so we must not echo it again.
        """
        cmd_stripped = command.strip()
        if not cmd_stripped:
            return

        lowered = cmd_stripped.lower()
        if lowered in ("clear", "cls"):
            self.clear()
            self.print_prompt()
            return
        if lowered == "pwd":
            self.append_system_line(str(self.working_dir).replace("\\", "/"))
            self.print_prompt()
            return
        if lowered == "history":
            for idx, item in enumerate(self.shared_history, 1):
                self.append_system_line(f"  {idx:4d}  {item}")
            self.print_prompt()
            return

        if self._is_cd(cmd_stripped):
            target = self._cd_target(cmd_stripped)
            new_dir = self._resolve_dir(target)
            if new_dir is None:
                self.append_system_line(f"cd: каталог не найден: {target}")
                self.print_prompt()
                return
            self.working_dir = new_dir
            self.working_dir_changed.emit(new_dir)
            if self.process and self.process.state() == QtCore.QProcess.Running:
                # Keep the shell in sync for relative paths in later commands.
                # The shell's echo of this internal sync line is suppressed.
                self._sync_cd(new_dir)
            self.print_prompt()
            return

        # pwd / history are handled by the real shell; this exit-code echo keeps
        # the busy indicator honest for every command.
        if not (self.process and self.process.state() == QtCore.QProcess.Running):
            self.append_system_line("Оболочка не запущена. Перезапуск…")
            self.start_shell()
            QtCore.QTimer.singleShot(400, lambda: self.write(cmd_stripped + self._eol()))
            return

        self._last_command = cmd_stripped
        self._command_running = True
        self._set_busy(True)
        self.write(self._shell_command_text(cmd_stripped) + self._eol())
        self.print_prompt()

    def _shell_command_text(self, command: str) -> str:
        """Adapt a user-typed command to the active shell.

        In PowerShell ``"C:\\path\\app.py"`` is a *string expression*, not a
        command, so IDE-injected paths must be prefixed with the call operator.
        """
        prog = (self.shell_program or "").lower()
        is_powershell = IS_WINDOWS and ("powershell" in prog or prog.endswith("pwsh.exe"))
        if not is_powershell:
            return command
        stripped = command.lstrip()
        if stripped.startswith(('"', "'")):
            return "& " + command
        return command

    def _eol(self) -> str:
        return "\r\n" if IS_WINDOWS else "\n"

    def _sync_cd(self, path):
        """Send an internal ``cd`` to the shell without echoing it to the buffer."""
        self._internal_sync_lines += 1
        timer = getattr(self, "_internal_sync_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except RuntimeError:
                pass
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._clear_internal_sync)
        timer.start(1500)
        self._internal_sync_timer = timer
        self.write(self._shell_cd_text(path) + self._eol())

    def _clear_internal_sync(self):
        self._internal_sync_lines = 0
        self._internal_sync_timer = None

    def _is_internal_sync_line(self, line: str) -> bool:
        """Recognise a ``cd`` command that PyScribe itself injected."""
        probe = line.strip()
        if not probe:
            return False
        for marker in self._INTERNAL_CD_MARKERS:
            if marker in probe:
                return True
        return False

    _INTERNAL_CD_MARKERS = (
        "Set-Location -LiteralPath",
        "Convert]::FromBase64String",
    )

    def _shell_cd_text(self, path) -> str:
        # ``path`` may arrive as pathlib.Path from the IDE run actions.
        path = str(path)
        prog = (self.shell_program or "").lower()
        if IS_WINDOWS and ("powershell" in prog or prog.endswith("pwsh.exe")):
            # Windows PowerShell 5.1 reads piped stdin with the OEM code page,
            # which corrupts non-ASCII paths (e.g. "...\Документы\...").
            # UTF-16LE + base64 keeps the command pure ASCII on the wire.
            encoded = base64.b64encode(path.encode("utf-16-le")).decode("ascii")
            return f"Set-Location -LiteralPath ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('{encoded}')))"
        if IS_WINDOWS and "bash" in prog:
            return f'cd "{path.replace(chr(92), chr(92) * 2)}"'
        if IS_WINDOWS:
            return f'cd /d "{path}"'
        return f"cd {shlex.quote(path)}"

    def submit_command(self, command: str):
        """Type *command* into the live shell and press Enter.

        ``run_command`` launches a standalone process, which is right for
        "run this file" but wrong for shell syntax: builtins (``cd``, ``dir``,
        ``echo``) and compound commands (``npm test``, ``a && b``) only work
        when the shell itself interprets the line.
        """
        command = str(command).strip()
        if not command:
            return
        if not self._shell_running():
            self.start_shell()
            QtCore.QTimer.singleShot(500, lambda: self.submit_command(command))
            return
        screen = self.screen
        screen._set_input_text(command)
        cursor = screen.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        screen.setTextCursor(cursor)
        screen._submit_line()

    def run_command(self, command: str):
        """Run an IDE-issued command in the terminal.

        The command is started as its own child process instead of being typed
        into the interactive shell: the shell never echoes it, its stdout and
        stderr are streamed straight into the buffer as they arrive, and the
        exit code is reported. This is why "Run file" reliably shows output
        even while the program is still running.
        """
        command = str(command).strip()
        if not command:
            return
        self.start_run_process(command)

    # ------------------------------------------------------------------
    # IDE run processes (separate channel)
    # ------------------------------------------------------------------
    def start_run_process(self, command: str):
        """Start *command* as a dedicated child process and stream its output."""
        self._last_command = command
        self._stop_run_process(kill=True)
        self.append_system_line(f"▶ {command}")

        proc = QtCore.QProcess(self)
        proc.setWorkingDirectory(
            str(self.working_dir) if os.path.isdir(str(self.working_dir)) else os.getcwd()
        )
        proc.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
        try:
            env = QtCore.QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("PYTHONUTF8", "1")
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("TERM", "xterm-256color")
            proc.setProcessEnvironment(env)
        except Exception:
            pass
        if IS_WINDOWS and hasattr(proc, "setCreateProcessArgumentsModifier"):
            proc.setCreateProcessArgumentsModifier(
                lambda args: setattr(args, "flags", args.flags | 0x08000000)
            )
        proc.readyReadStandardOutput.connect(lambda p=proc: self._read_run_stdout(p))
        proc.readyReadStandardError.connect(lambda p=proc: self._read_run_stderr(p))
        proc.finished.connect(
            lambda code, status, p=proc: self._on_run_finished(p, code, status)
        )
        proc.errorOccurred.connect(lambda err, p=proc: self._on_run_error(p, err))
        # Keep stdin open so interactive programs (input()/readline) do not hit
        # EOF immediately. Inconclusive input is fed from the terminal's own
        # input line below.
        proc.setInputChannelMode(QtCore.QProcess.ManagedInputChannel)

        program, args = self._split_command(command)
        self._run_process = proc
        self._run_started_at = time.monotonic()
        self._command_running = True
        self._set_busy(True)
        if program:
            proc.start(program, args)
        else:
            self.append_system_line("Не удалось разобрать команду запуска.")
            self.mark_command_finished(1)

    @staticmethod
    def _split_command(command: str):
        """Split a launch command into (program, args) honouring quotes.

        Runs directly inside a QProcess, so *every* argument is passed
        verbatim: no shell quoting is applied and quotes are only stripped.
        """
        text = command.strip()
        # Strip a leading call operator used for PowerShell paths.
        if text.startswith("& "):
            text = text[2:].strip()
        if not text:
            return None, []
        if IS_WINDOWS:
            # Windows command lines quote with "..." and never use \".
            tokens = []
            i, n = 0, len(text)
            while i < n:
                while i < n and text[i] in " \t":
                    i += 1
                if i >= n:
                    break
                if text[i] == '"':
                    i += 1
                    start = i
                    while i < n and text[i] != '"':
                        i += 1
                    tokens.append(text[start:i])
                    i += 1
                else:
                    start = i
                    while i < n and text[i] not in " \t":
                        i += 1
                    tokens.append(text[start:i])
        else:
            try:
                tokens = shlex.split(text)
            except ValueError:
                tokens = text.split()
        if not tokens:
            return None, []
        return tokens[0], tokens[1:]

    def _read_run_stdout(self, proc):
        if proc is not self._run_process:
            return
        try:
            text = self._decode(proc.readAllStandardOutput())
        except RuntimeError:
            return
        if text:
            self._append_colored(text.replace("\r\n", "\n").replace("\r", ""), "output")

    def _read_run_stderr(self, proc):
        if proc is not self._run_process:
            return
        try:
            text = self._decode(proc.readAllStandardError())
        except RuntimeError:
            return
        if text:
            self._append_colored(text.replace("\r\n", "\n").replace("\r", ""), "error")

    def _on_run_error(self, proc, err):
        if proc is not self._run_process:
            return
        if err == QtCore.QProcess.FailedToStart:
            self.append_system_line("Ошибка запуска: программа не найдена или недоступна.")
            self.mark_command_finished(1)

    def _on_run_finished(self, proc, exit_code, exit_status):
        if proc is not self._run_process:
            return
        # Flush whatever is still buffered in the pipe (the process object may
        # already be gone when this slot runs, so never let it raise).
        self._read_run_stdout(proc)
        self._read_run_stderr(proc)
        elapsed = max(0.0, time.monotonic() - getattr(self, "_run_started_at", time.monotonic()))
        crashed = exit_status != QtCore.QProcess.NormalExit
        code = -1 if crashed else int(exit_code)
        if code == 0:
            label = f"Завершено за {elapsed:.1f} с"
        else:
            label = f"Код выхода {code} · {elapsed:.1f} с"
        self.append_system_line(label)
        self._run_process = None
        try:
            proc.deleteLater()
        except RuntimeError:
            pass
        self.mark_command_finished(code)
        self.print_prompt()

    def _stop_run_process(self, kill: bool = True):
        proc = getattr(self, "_run_process", None)
        if proc is None:
            return
        self._run_process = None
        try:
            for signal in (proc.readyReadStandardOutput, proc.readyReadStandardError,
                           proc.finished, proc.errorOccurred):
                try:
                    signal.disconnect()
                except Exception:
                    pass
            if kill and proc.state() != QtCore.QProcess.NotRunning:
                proc.kill()
                proc.waitForFinished(500)
            proc.deleteLater()
        except RuntimeError:
            pass

    def is_run_process_active(self) -> bool:
        proc = getattr(self, "_run_process", None)
        return bool(proc is not None and proc.state() != QtCore.QProcess.NotRunning)

    def send_run_input(self, text: str) -> bool:
        """Feed a line of user input to the running IDE process (stdin)."""
        proc = getattr(self, "_run_process", None)
        if proc is None or proc.state() == QtCore.QProcess.NotRunning:
            return False
        try:
            proc.write((text + ("\r\n" if IS_WINDOWS else "\n")).encode("utf-8"))
            proc.waitForBytesWritten(50)
            return True
        except Exception:
            return False

    def mark_command_finished(self, exit_code: int = 0):
        self._command_running = False
        self._set_busy(False)
        try:
            self.command_finished.emit(int(exit_code))
        except Exception:
            pass

    def clear(self):
        self.screen.clear()
        self.screen.prompt_pos = 0

    def interrupt(self):
        """Ctrl+C: stop a running IDE process, otherwise signal the shell."""
        if self.is_run_process_active():
            proc = self._run_process
            self._run_process = None
            try:
                proc.kill()
            except RuntimeError:
                pass
            self.append_system_line("^C Процесс прерван пользователем.")
            self.mark_command_finished(130)
            self.print_prompt()
            return
        if not self.process:
            return
        try:
            self.process.write(b"\x03")
        except Exception:
            pass
        self._set_busy(False)

    def stop_process(self):
        self._stop_run_process(kill=True)
        process = self.process
        if process is None:
            return
        self._closing = True
        for signal in (process.readyReadStandardOutput, process.readyReadStandardError, process.finished):
            try:
                signal.disconnect()
            except Exception:
                pass
        if process.state() != QtCore.QProcess.NotRunning:
            try:
                process.kill()
                process.waitForFinished(1000)
            except Exception:
                pass
        try:
            process.deleteLater()
        except Exception:
            pass
        self.process = None

    def kill(self):
        self.stop_process()

    def closeEvent(self, event):
        self.stop_process()
        super().closeEvent(event)


class TerminalWidget(QtWidgets.QWidget):
    """VS Code / Linux-style integrated terminal panel with in-buffer typing."""

    directory_changed = QtCore.pyqtSignal(str)
    busy_changed = QtCore.pyqtSignal(bool)
    tab_count_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = {}
        self.next_tab_id = 1
        self.current_tab = None
        self._history: List[str] = []
        self._build()
        self.create_new_tab()

    def show_startup_banner(self):
        """Retained for API compatibility — intentionally does nothing.

        A newly opened terminal shows only the prompt (``dmitr@host:~/path$``):
        no welcome/help banner, and no extra prompt. Previously this method also
        forced a second ``print_prompt()`` which could duplicate the prompt line.
        """
        return

    # ------------------------------------------------------------------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.shell_button = QtWidgets.QToolButton()
        self.shell_button.setObjectName("terminalShellButton")
        self.shell_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.shell_button.setToolTip("Выбор оболочки (PowerShell / CMD / Git Bash)")
        menu = QtWidgets.QMenu(self.shell_button)
        menu.setObjectName("terminalShellMenu")

        self.available_shells = []
        if IS_WINDOWS:
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if pwsh:
                self.available_shells.append(("powershell", pwsh, ["-NoLogo", "-NoExit", "-NoProfile"]))
            git_bash = r"C:\Program Files\Git\bin\bash.exe"
            if os.path.exists(git_bash):
                self.available_shells.append(("bash", git_bash, ["--login", "-i"]))
            self.available_shells.append(("cmd", os.environ.get("COMSPEC", "cmd.exe"), ["/Q", "/K"]))
        else:
            self.available_shells.append(("bash", os.environ.get("SHELL", "/bin/bash"), ["-i"]))

        default_name = self.available_shells[0][0] if self.available_shells else "shell"
        self.shell_button.setText(f"{default_name} ▾")

        for shell_name, shell_prog, shell_args in self.available_shells:
            action = menu.addAction(shell_name)
            action.triggered.connect(
                lambda checked=False, s=(shell_name, shell_prog, shell_args): self.change_shell(*s)
            )
        self.shell_button.setMenu(menu)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setObjectName("terminalTabs")
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)

        # The shell selector lives on the left of the strip. New/stop/clear
        # actions are provided once by the panel toolbar (ConsoleWidget) so the
        # same buttons are not duplicated in two places.
        left_corner = QtWidgets.QWidget()
        left_corner.setObjectName("terminalCorner")
        left_l = QtWidgets.QHBoxLayout(left_corner)
        left_l.setContentsMargins(8, 0, 8, 0)
        left_l.setSpacing(4)
        left_l.addWidget(self.shell_button)
        self.tab_widget.setCornerWidget(left_corner, QtCore.Qt.TopLeftCorner)

        root.addWidget(self.tab_widget, 1)
        self.setObjectName("terminalWidget")

        # Single-terminal sessions hide the tab strip entirely (VS Code only
        # shows one when the panel is split into several terminals).
        self.tab_widget.setTabBarAutoHide(True)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+`"), self, activated=self.create_new_tab)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, activated=self.clear_current)

    # ------------------------------------------------------------------
    def change_shell(self, shell_name, shell_prog, shell_args):
        self.shell_button.setText(f"{shell_name} ▾")
        tab = self._current()
        if tab:
            tab.start_shell(shell_prog, shell_args)

    def create_new_tab(self, working_dir=None, *_args):
        tab_id = self.next_tab_id
        self.next_tab_id += 1
        tab = TerminalTab(
            tab_id, f"Терминал {tab_id}", working_dir or os.getcwd(), self,
            shared_history=self._history,
        )
        tab.working_dir_changed.connect(self.directory_changed.emit)
        tab.busy_changed.connect(self._on_tab_busy)
        self.tabs[tab_id] = tab
        index = self.tab_widget.addTab(tab, f"Терминал {tab_id}")
        self.tab_widget.setCurrentIndex(index)
        self.current_tab = tab_id
        self._animate_tab(index)
        self.tab_count_changed.emit(self.tab_widget.count())
        QtCore.QTimer.singleShot(80, tab.screen.setFocus)

    def _animate_tab(self, index: int):
        """Fade in a freshly created terminal tab."""
        try:
            from widgets.animations import fade_in
            tab = self.tab_widget.widget(index)
            if tab is not None:
                fade_in(tab, duration=180)
        except Exception:
            pass

    def _on_tab_busy(self, busy: bool):
        sender = self.sender()
        if sender is self._current():
            self.busy_changed.emit(bool(busy))

    def close_tab(self, index):
        if index < 0 or index >= self.tab_widget.count():
            return
        tab = self.tab_widget.widget(index)
        for tab_id, candidate in list(self.tabs.items()):
            if candidate is tab:
                candidate.stop_process()
                del self.tabs[tab_id]
                break
        self.tab_widget.removeTab(index)
        tab.deleteLater()
        if self.tab_widget.count() == 0:
            self.create_new_tab()
        self.tab_count_changed.emit(self.tab_widget.count())

    def close_current_tab(self):
        self.close_tab(self.tab_widget.currentIndex())

    def tab_changed(self, index):
        widget = self.tab_widget.widget(index)
        for tab_id, tab in self.tabs.items():
            if tab is widget:
                self.current_tab = tab_id
                self.busy_changed.emit(bool(getattr(tab, "_busy", False)))
                QtCore.QTimer.singleShot(50, tab.screen.setFocus)
                break

    def _current(self) -> Optional[TerminalTab]:
        return self.tabs.get(self.current_tab)

    def clear_current(self):
        tab = self._current()
        if tab:
            tab.clear()
            tab.print_prompt()
            tab.screen.setFocus()

    def kill_current(self):
        tab = self._current()
        if tab:
            tab.append_system_line("Завершение процесса…")
            tab.kill()
            QtCore.QTimer.singleShot(120, tab.start_shell)
            tab.screen.setFocus()

    def interrupt_current(self):
        tab = self._current()
        if tab:
            tab.interrupt()
            tab.screen.setFocus()

    def run_code(self, file_path, args="", working_dir=None):
        if working_dir:
            self.set_working_directory(working_dir)
        tab = self._current()
        if not tab:
            self.create_new_tab(working_dir)
            tab = self._current()
        path = os.path.abspath(str(file_path))

        custom_toolchains = {}
        try:
            from utils.settings_manager import settings_manager
            custom_toolchains = settings_manager.get_setting("toolchains", {}) or {}
        except Exception:
            pass

        command = None
        try:
            from utils.toolchain_detector import build_run_command_for_file
            command, _ = build_run_command_for_file(path, args, custom_toolchains)
        except Exception:
            pass

        if not command:
            suffix = os.path.splitext(path)[1].lower()
            quoted = f'"{path}"' if IS_WINDOWS else shlex.quote(path)
            if suffix == ".py":
                command = f'"{sys.executable}" {quoted} {args}'.strip()
            elif suffix == ".js":
                command = f'node {quoted} {args}'.strip()
            elif suffix in {".sh", ".bash"}:
                command = f'bash {quoted} {args}'.strip()
            elif suffix in {".bat", ".cmd"}:
                command = f'call {quoted} {args}'.strip()
            else:
                command = f'{quoted} {args}'.strip()

        if tab:
            tab.run_command(command)
            tab.screen.setFocus()

    def run_command(self, command, working_dir=None):
        """Run an arbitrary command in the integrated terminal.

        Shell syntax (builtins, ``&&``, ``pip install``) is interpreted by the
        live shell; use :meth:`run_file` when a standalone process with a
        streamed exit code is needed.
        """
        if working_dir:
            self.set_working_directory(working_dir)
        tab = self._current()
        if not tab:
            self.create_new_tab(working_dir)
            tab = self._current()
        if tab:
            tab.submit_command(str(command))
            tab.screen.setFocus()

    def run_file(self, command, working_dir=None):
        """Run *command* as its own process and stream its output."""
        if working_dir:
            self.set_working_directory(working_dir)
        tab = self._current()
        if not tab:
            self.create_new_tab(working_dir)
            tab = self._current()
        if tab:
            tab.run_command(str(command))
            tab.screen.setFocus()

    def set_working_directory(self, path):
        """Switch the working directory (accepts ``str`` or ``pathlib.Path``)."""
        path = str(path) if path is not None else os.getcwd()
        if not os.path.isdir(path):
            return
        tab = self._current()
        if tab and os.path.normpath(tab.working_dir) != os.path.normpath(path):
            tab.working_dir = path
            tab.working_dir_changed.emit(path)
            if tab.process and tab.process.state() != QtCore.QProcess.NotRunning:
                # Same internal-cd path as the typed ``cd`` command so the
                # echoed sync line is filtered out of the buffer.
                tab._sync_cd(path)
                tab.print_prompt()
            else:
                tab.start_shell()

    def apply_terminal_settings(self):
        for tab in self.tabs.values():
            if hasattr(tab, 'screen') and hasattr(tab.screen, 'apply_terminal_settings'):
                tab.screen.apply_terminal_settings()

    def shutdown(self):
        for tab in list(self.tabs.values()):
            try:
                tab.stop_process()
            except Exception:
                pass
        self.tabs.clear()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
