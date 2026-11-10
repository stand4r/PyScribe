"""PyScribe widgets/FindReplaceBar.py: in-editor find and replace overlay."""
import re
from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QRegExp
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QTextDocument
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QToolButton, QLabel,
    QPushButton, QFrame
)


class FindReplaceBar(QFrame):
    """Modern in-editor find & replace bar matching VS Code aesthetics."""

    def __init__(self, modern_editor, parent=None):
        super().__init__(parent)
        self.modern_editor = modern_editor
        self.editor = getattr(modern_editor, 'editor', modern_editor)
        self._matches = []
        self._current_index = -1
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor(140, 100, 20, 140))
        self._current_format = QTextCharFormat()
        self._current_format.setBackground(QColor(0, 120, 212, 180))
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("findReplaceBar")
        # Compact overlay styled by design/theme.qss (QFrame#findReplaceBar).

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # Row 1: Find row
        row_find = QHBoxLayout()
        row_find.setSpacing(6)

        icon_label = QLabel("🔍")
        row_find.addWidget(icon_label)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Найти в файле... (Enter: далее, Shift+Enter: назад)")
        self.find_input.textChanged.connect(self._on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)
        row_find.addWidget(self.find_input, 1)

        self.match_count_label = QLabel("0/0")
        self.match_count_label.setMinimumWidth(48)
        self.match_count_label.setAlignment(Qt.AlignCenter)
        row_find.addWidget(self.match_count_label)

        self.case_btn = QToolButton()
        self.case_btn.setText("Aa")
        self.case_btn.setCheckable(True)
        self.case_btn.setToolTip("Учитывать регистр (Match Case)")
        self.case_btn.toggled.connect(self._on_find_text_changed)
        row_find.addWidget(self.case_btn)

        self.word_btn = QToolButton()
        self.word_btn.setText("\\b")
        self.word_btn.setCheckable(True)
        self.word_btn.setToolTip("Слово целиком (Whole Word)")
        self.word_btn.toggled.connect(self._on_find_text_changed)
        row_find.addWidget(self.word_btn)

        self.prev_btn = QToolButton()
        set_line_icon(self.prev_btn, "up")
        self.prev_btn.setToolTip("Предыдущее совпадение (Shift+Enter)")
        self.prev_btn.clicked.connect(self.find_prev)
        row_find.addWidget(self.prev_btn)

        self.next_btn = QToolButton()
        set_line_icon(self.next_btn, "down")
        self.next_btn.setToolTip("Следующее совпадение (Enter)")
        self.next_btn.clicked.connect(self.find_next)
        row_find.addWidget(self.next_btn)

        self.toggle_replace_btn = QToolButton()
        set_line_icon(self.toggle_replace_btn, "replace")
        self.toggle_replace_btn.setCheckable(True)
        self.toggle_replace_btn.setToolTip("Показать/скрыть панель замены (Ctrl+H)")
        self.toggle_replace_btn.toggled.connect(self._toggle_replace_row)
        row_find.addWidget(self.toggle_replace_btn)

        self.close_btn = QToolButton()
        set_line_icon(self.close_btn, "close")
        self.close_btn.setToolTip("Закрыть (Escape)")
        self.close_btn.clicked.connect(self.hide_bar)
        row_find.addWidget(self.close_btn)

        root.addLayout(row_find)

        # Row 2: Replace row (optional)
        self.replace_widget = QWidget()
        row_replace = QHBoxLayout(self.replace_widget)
        row_replace.setContentsMargins(0, 0, 0, 0)
        row_replace.setSpacing(6)

        rep_icon = QLabel("⇄")
        row_replace.addWidget(rep_icon)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Заменить на...")
        self.replace_input.returnPressed.connect(self.replace_current)
        row_replace.addWidget(self.replace_input, 1)

        self.replace_btn = QPushButton("Заменить")
        self.replace_btn.setToolTip("Заменить текущее совпадение")
        self.replace_btn.clicked.connect(self.replace_current)
        row_replace.addWidget(self.replace_btn)

        self.replace_all_btn = QPushButton("Все")
        self.replace_all_btn.setToolTip("Заменить все совпадения")
        self.replace_all_btn.clicked.connect(self.replace_all)
        row_replace.addWidget(self.replace_all_btn)

        root.addWidget(self.replace_widget)
        self.replace_widget.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_bar()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            return
        super().keyPressEvent(event)

    def show_find(self):
        # Prefill with selected text if any
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            sel = cursor.selectedText().strip()
            if sel and '\n' not in sel:
                self.find_input.setText(sel)
        self.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._find_all()

    def show_replace(self):
        self.show_find()
        self.toggle_replace_btn.setChecked(True)
        self.replace_widget.show()
        self.replace_input.setFocus()

    def hide_bar(self):
        self.hide()
        self._clear_highlights()
        self.editor.setFocus()

    def _toggle_replace_row(self, checked):
        self.replace_widget.setVisible(checked)
        if checked:
            self.replace_input.setFocus()

    def _on_find_text_changed(self):
        self._find_all()

    def _find_all(self):
        query = self.find_input.text()
        self._matches = []
        self._current_index = -1
        if not query:
            self.match_count_label.setText("0/0")
            self._clear_highlights()
            return

        doc = self.editor.document()
        flags = QTextDocument.FindFlags()
        if self.case_btn.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.word_btn.isChecked():
            flags |= QTextDocument.FindWholeWords

        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(query, cursor, flags)
            if cursor.isNull() or not cursor.hasSelection():
                break
            self._matches.append(cursor)

        total = len(self._matches)
        if total == 0:
            self.match_count_label.setText("0/0")
            self._clear_highlights()
            return

        # Find match closest to current cursor
        editor_cursor = self.editor.textCursor()
        current_pos = editor_cursor.position()
        best_idx = 0
        for idx, match in enumerate(self._matches):
            if match.selectionStart() >= current_pos:
                best_idx = idx
                break

        self._current_index = best_idx
        self.match_count_label.setText(f"{best_idx + 1}/{total}")
        self._highlight_matches()
        self._scroll_to_current()

    def find_next(self):
        if not self._matches:
            self._find_all()
            return
        self._current_index = (self._current_index + 1) % len(self._matches)
        self.match_count_label.setText(f"{self._current_index + 1}/{len(self._matches)}")
        self._highlight_matches()
        self._scroll_to_current()

    def find_prev(self):
        if not self._matches:
            self._find_all()
            return
        self._current_index = (self._current_index - 1 + len(self._matches)) % len(self._matches)
        self.match_count_label.setText(f"{self._current_index + 1}/{len(self._matches)}")
        self._highlight_matches()
        self._scroll_to_current()

    def _scroll_to_current(self):
        if 0 <= self._current_index < len(self._matches):
            cur = self._matches[self._current_index]
            self.editor.setTextCursor(cur)
            self.editor.ensureCursorVisible()

    def _highlight_matches(self):
        extra_selections = []
        for i, match_cursor in enumerate(self._matches):
            selection = QtWidgets.QTextEdit.ExtraSelection()
            selection.cursor = match_cursor
            selection.format = self._current_format if i == self._current_index else self._highlight_format
            extra_selections.append(selection)

        # Merge with existing current-line highlight if any
        if hasattr(self.editor, 'highlight_current_line'):
            self.editor.setExtraSelections(extra_selections)

    def _clear_highlights(self):
        if hasattr(self.editor, 'highlight_current_line'):
            self.editor.highlight_current_line()
        else:
            self.editor.setExtraSelections([])

    def replace_current(self):
        if not self._matches or self._current_index < 0:
            return
        replacement = self.replace_input.text()
        cursor = self._matches[self._current_index]
        cursor.insertText(replacement)
        self._find_all()

    def replace_all(self):
        query = self.find_input.text()
        replacement = self.replace_input.text()
        if not query:
            return

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        try:
            # Replace in reverse order so positions don't shift
            for match in reversed(self._matches):
                match.insertText(replacement)
        finally:
            cursor.endEditBlock()
        self._find_all()
