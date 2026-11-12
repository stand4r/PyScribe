"""PyScribe widgets/QCodeEditor.py: application module and reusable component."""
from core.activity_log import record_action
from core.logging_config import get_logger
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
import re
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from design.icons import line_icon, set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize, QEvent, QVariantAnimation
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence, QTextCharFormat, QPainter, QPen, QLinearGradient, QTextBlock, QMouseEvent, QKeyEvent, QWheelEvent, QTextDocument, QPaintEvent
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QTextEdit, QFrame, QToolButton
from core.language_services import *
def _ui_font(point_size: int = 9, **kwargs):
    """Interface font for painters (normal width, not the condensed default)."""
    try:
        from app.styling import ui_qfont
        return ui_qfont(point_size, **kwargs)
    except Exception:
        return QFont("Segoe UI", point_size)


def _ui_font_family() -> str:
    """Interface font for painter-built QFont objects (falls back gracefully)."""
    try:
        from app.styling import ui_font_family
        return ui_font_family()
    except Exception:
        return "Segoe UI"
try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename, get_lexer_by_name
    from pygments.token import Token
except ImportError:
    lex = get_lexer_for_filename = get_lexer_by_name = None
    Token = None
try:
    from core.workspace_index import WorkspaceIndex
except ImportError:
    WorkspaceIndex = None

try:
    from widgets.FindReplaceBar import FindReplaceBar
    from widgets.CodeLensBar import CodeLensBar
    CodeRadarWidget = CodeLensBar
except ImportError:
    # pyrefly: ignore[missing-import]
    from FindReplaceBar import FindReplaceBar
    # pyrefly: ignore[missing-import]
    from CodeLensBar import CodeLensBar
    CodeRadarWidget = CodeLensBar

class SelectionMode(Enum):
    """Режимы выделения текста"""
    NORMAL = "normal"
    RECTANGLE = "rectangle"


class EnhancedTextEdit(QPlainTextEdit):
    """Улучшенный текстовый редактор с поддержкой прямоугольного выделения"""
    
    rectangleSelectionChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_mode = SelectionMode.NORMAL
        self.rectangle_start_pos = QPoint()
        self.rectangle_end_pos = QPoint()
        self.is_selecting_rectangle = False
        
        # Дополнительные выделения для прямоугольного выделения
        self.rectangle_selections = []
        
        # Настройка для прямоугольного выделения
        self.setMouseTracking(True)
        
    def mousePressEvent(self, event: QMouseEvent):
        """Обработка нажатия мыши"""
        completer = getattr(self, "completer", None)
        if completer is not None and completer.popup().isVisible():
            completer.popup().hide()
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier:
            # Начало прямоугольного выделения (Alt+ЛКМ, как в VS Code)
            self.selection_mode = SelectionMode.RECTANGLE
            self.is_selecting_rectangle = True
            self.rectangle_start_pos = event.pos()
            self.rectangle_end_pos = event.pos()
            self.rectangle_selections.clear()
            self.rectangleSelectionChanged.emit(True)
            event.accept()
            return

        self.selection_mode = SelectionMode.NORMAL
        self.is_selecting_rectangle = False
        if self.rectangle_selections:
            self.rectangle_selections.clear()
            self.setExtraSelections([])
        self.rectangleSelectionChanged.emit(False)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Обработка движения мыши"""
        if self.is_selecting_rectangle:
            self.rectangle_end_pos = event.pos()
            self.update_rectangle_selection()
            self.viewport().update()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Обработка отпускания мыши"""
        if self.is_selecting_rectangle:
            self.is_selecting_rectangle = False
            self.finalize_rectangle_selection()
            self.update_rectangle_selection()
            self.viewport().update()
        else:
            super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        window = self.window()
        current = window.get_current_editor() if hasattr(window, "get_current_editor") else None
        file_path = getattr(current, "file_path", None)
        if file_path and hasattr(window, "run_target"):
            run_action = menu.addAction("Запустить")
            run_action.triggered.connect(lambda: window.run_target(str(file_path), False))
        if hasattr(window, "action_analyze_current_impact"):
            impact_action = menu.addAction("Анализ влияния")
            impact_action.triggered.connect(window.action_analyze_current_impact)
        menu.exec_(event.globalPos())

    def update_rectangle_selection(self):
        """Обновление прямоугольного выделения"""
        self.rectangle_selections.clear()
        
        # Получаем начальную и конечную позиции в координатах текста
        start_cursor = self.cursorForPosition(self.rectangle_start_pos)
        end_cursor = self.cursorForPosition(self.rectangle_end_pos)
        
        if not start_cursor.block().isValid() or not end_cursor.block().isValid():
            return
        
        # Определяем границы прямоугольника
        start_line = min(start_cursor.blockNumber(), end_cursor.blockNumber())
        end_line = max(start_cursor.blockNumber(), end_cursor.blockNumber())
        start_col = min(start_cursor.positionInBlock(), end_cursor.positionInBlock())
        end_col = max(start_cursor.positionInBlock(), end_cursor.positionInBlock())
        
        # Создаем выделения для каждой строки в прямоугольнике
        for line in range(start_line, end_line + 1):
            block = self.document().findBlockByNumber(line)
            if not block.isValid():
                continue
            cursor = QTextCursor(block)

            # Перемещаем курсор в пределах строки
            line_length = len(block.text())

            # Если строка достаточно длинная для выделения
            if start_col < line_length:
                actual_end_col = min(end_col, line_length)
                cursor.setPosition(block.position() + start_col)
                cursor.setPosition(block.position() + actual_end_col, QTextCursor.KeepAnchor)

                # Создаем дополнительное выделение
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor

                # Стиль для прямоугольного выделения
                selection.format.setBackground(QColor("#264F78"))
                selection.format.setForeground(QColor("#FFFFFF"))

                self.rectangle_selections.append(selection)

        self.setExtraSelections(list(self.rectangle_selections))
    
    def finalize_rectangle_selection(self):
        """Финализация прямоугольного выделения"""
        if self.rectangle_selections:
            # Устанавливаем курсор в начало выделения
            first_selection = self.rectangle_selections[0]
            self.setTextCursor(first_selection.cursor)
            self.setExtraSelections(self.rectangle_selections)
        else:
            self.setExtraSelections([])

    def paintEvent(self, event: QPaintEvent):
        """Отрисовка редактора с прямоугольным выделением"""
        # Сначала рисуем стандартный редактор
        super().paintEvent(event)

        # Если идет процесс прямоугольного выделения, рисуем прямоугольник
        if not self.is_selecting_rectangle:
            return
        painter = QPainter(self.viewport())
        try:
            painter.setPen(QPen(QColor("#007ACC"), 1, Qt.DashLine))
            painter.setBrush(QColor(0, 122, 204, 30))  # Полупрозрачная заливка
            rect = QRect(self.rectangle_start_pos, self.rectangle_end_pos).normalized()
            painter.drawRect(rect)
        finally:
            painter.end()

    def get_rectangle_selection_text(self) -> str:
        """Получение текста из прямоугольного выделения"""
        if not self.rectangle_selections:
            return ""

        lines = []
        for selection in self.rectangle_selections:
            text = selection.cursor.selectedText()
            if text:
                lines.append(text)

        return "\n".join(lines)

    def insert_text_in_rectangle(self, text: str):
        """Вставка текста в прямоугольное выделение"""
        if not self.rectangle_selections:
            return

        block_cursor = self.textCursor()
        block_cursor.beginEditBlock()
        try:
            # Запоминаем стартовые позиции до любой модификации документа,
            # иначе последующие курсоры "уедут" вместе со вставкой.
            starts = [selection.cursor.selectionStart() for selection in self.rectangle_selections]
            # Вставляем с конца документа, чтобы не сдвигать предыдущие позиции.
            lines_to_insert = text.split('\n')

            pairs = []
            for i, (start, selection) in enumerate(zip(starts, self.rectangle_selections)):
                insert_text = lines_to_insert[i] if i < len(lines_to_insert) else (lines_to_insert[-1] if lines_to_insert else "")
                pairs.append((start, selection.cursor.selectionEnd(), insert_text))

            for start, end, insert_text in sorted(pairs, key=lambda item: item[0], reverse=True):
                cur = QTextCursor(self.document())
                cur.setPosition(start)
                cur.setPosition(end, QTextCursor.KeepAnchor)
                cur.insertText(insert_text)
        finally:
            block_cursor.endEditBlock()

        # Восстанавливаем выделение после вставки
        self.update_rectangle_selection()
        self.viewport().update()

    def delete_rectangle_selection(self):
        """Удаление прямоугольного выделения"""
        if not self.rectangle_selections:
            return

        block_cursor = self.textCursor()
        block_cursor.beginEditBlock()
        try:
            ranges = [
                (selection.cursor.selectionStart(), selection.cursor.selectionEnd())
                for selection in self.rectangle_selections
            ]
            # С конца, чтобы позиции остались корректными.
            for start, end in sorted(ranges, key=lambda item: item[0], reverse=True):
                if end <= start:
                    continue
                cur = QTextCursor(self.document())
                cur.setPosition(start)
                cur.setPosition(end, QTextCursor.KeepAnchor)
                cur.removeSelectedText()
        finally:
            block_cursor.endEditBlock()

        self.rectangle_selections.clear()
        self.setExtraSelections([])
        self.selection_mode = SelectionMode.NORMAL
        self.rectangleSelectionChanged.emit(False)
        self.viewport().update()
    
    def copy_rectangle_selection(self):
        """Копирование прямоугольного выделения в буфер обмена"""
        text = self.get_rectangle_selection_text()
        if text:
            QApplication.clipboard().setText(text)
    
    def cut_rectangle_selection(self):
        """Вырезание прямоугольного выделения"""
        self.copy_rectangle_selection()
        self.delete_rectangle_selection()


class LineNumberArea(QWidget):
    """Область для отображения номеров строк"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)



class ModernSyntaxHighlighter(QSyntaxHighlighter):
    """
    Профессиональный подсветчик синтаксиса:
    - Полноценная поддержка многострочных комментариев и docstrings (/* ... */, \"\"\" ... \"\"\", ''' ... ''', <!-- ... -->, --[[ ... --]])
    - Автоматическое сохранение и передача состояния блоков через previousBlockState() / setCurrentBlockState()
    - Высокопроизводительный движок на базе скомпилированных регулярных выражений Python
    - Раздельная эстетичная подсветка: control flow, keywords, functions, classes, decorators, constants, numbers, strings
    - Надежная защита от ложного распознавания кода внутри комментариев и строк
    """
    STATE_NORMAL = 0
    STATE_C_COMMENT = 1          # /* ... */
    STATE_PY_TRIPLE_DOUBLE = 2   # """ ... """
    STATE_PY_TRIPLE_SINGLE = 3   # ''' ... '''
    STATE_HTML_COMMENT = 4       # <!-- ... -->
    STATE_LUA_COMMENT = 5        # --[[ ... --]]

    _format_cache = {}

    def __init__(self, document, language_config: LanguageConfig):
        super().__init__(document)
        self.language_config = language_config
        self.lang_name = (getattr(language_config, "name", "") or "").lower()

        # Check supported multiline types for this language
        self._is_python = self.lang_name in ("python", "py")
        self._supports_c_comments = self.lang_name in (
            "c", "cpp", "csharp", "cs", "java", "javascript", "js", "typescript", "ts",
            "tsx", "jsx", "go", "rust", "php", "css", "sql", "dart", "kotlin", "kt",
            "swift", "scala", "solidity"
        ) or getattr(language_config, "block_comment_start", "") == "/*"
        self._supports_html_comments = self.lang_name in ("html", "xml", "htm") or getattr(language_config, "block_comment_start", "") == "<!--"
        self._supports_lua_comments = self.lang_name in ("lua",)

        # Formats
        self._comment_format = self._get_cached_format("#6A9955", QFont.Normal, True)
        self._docstring_format = self._get_cached_format("#6A9955", QFont.Normal, True)
        self._string_format = self._get_cached_format("#CE9178", QFont.Normal, False)

        self._rules = self._compile_rules()

    def _get_cached_format(self, color: str, weight: int = QFont.Normal, italic: bool = False) -> QTextCharFormat:
        cache_key = f"{color}_{weight}_{italic}"
        if cache_key not in self._format_cache:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(weight)
            fmt.setFontItalic(italic)
            self._format_cache[cache_key] = fmt
        return self._format_cache[cache_key]

    def _compile_rules(self) -> List[Tuple[Any, QTextCharFormat]]:
        rules = []
        kw_list = set(self.language_config.keywords)
        if self.lang_name == "asm":
            patterns = [
                (r"^\s*[A-Za-z_.$?@][\w.$?@]*:", "#DCDCAA"),
                (r"(?i)\b(?:bits|use32|use64|section|segment|format|entry|include|"
                 r"global|extern|org|equ|align|db|dw|dd|dq|resb|resw|resd|resq|"
                 + "|".join(sorted(kw_list)) + r")\b", "#569CD6"),
                (r"(?i)\b(?:[re]?(?:ax|bx|cx|dx|si|di|sp|bp)|[abcd][lh]|"
                 r"r(?:[89]|1[0-5])[dwb]?|(?:xmm|ymm|zmm)\d+|[re]?ip)\b", "#4EC9B0"),
                (r"(?i)\b(?:0x[\da-f]+|[\da-f]+h|0b[01]+|\d+)\b", "#B5CEA8"),
            ]
            return [(re.compile(pattern), self._get_cached_format(color, QFont.Normal, False))
                    for pattern, color in patterns]

        # 1. Distinct control-flow keywords (VS Code purple #C586C0)
        flow_keywords = {
            "return", "yield", "if", "else", "elif", "for", "while", "do",
            "try", "except", "finally", "catch", "throw", "raise", "break",
            "continue", "switch", "case", "default", "goto", "with", "async", "await", "assert"
        }
        cf_matches = sorted(kw_list.intersection(flow_keywords), key=len, reverse=True)
        if cf_matches:
            p = r"\b(?:" + "|".join(re.escape(k) for k in cf_matches) + r")\b"
            rules.append((re.compile(p), self._get_cached_format("#C586C0", QFont.Normal, False)))

        # 2. Other keywords (VS Code blue #569CD6)
        other_keywords = sorted(kw_list - flow_keywords, key=len, reverse=True)
        if other_keywords:
            p = r"\b(?:" + "|".join(re.escape(k) for k in other_keywords) + r")\b"
            rules.append((re.compile(p), self._get_cached_format("#569CD6", QFont.Normal, False)))

        # 3. Built-in types & constants (teal #4EC9B0)
        builtins = [
            "int", "str", "float", "bool", "list", "dict", "tuple", "set", "bytes", "object",
            "None", "True", "False", "null", "undefined", "true", "false", "void", "char",
            "double", "long", "short", "byte", "string", "boolean", "number", "any"
        ]
        b_matches = [b for b in builtins if b not in kw_list]
        if b_matches:
            p = r"\b(?:" + "|".join(re.escape(b) for b in b_matches) + r")\b"
            rules.append((re.compile(p), self._get_cached_format("#4EC9B0", QFont.Normal, False)))

        # 4. Function definitions & calls (yellow #DCDCAA)
        rules.append((re.compile(r"\b([A-Za-z_]\w*)\s*(?=\()"), self._get_cached_format("#DCDCAA", QFont.Normal, False)))

        # 5. Class names / Types in PascalCase (teal #4EC9B0)
        rules.append((re.compile(r"\b[A-Z][a-zA-Z0-9_]*\b"), self._get_cached_format("#4EC9B0", QFont.Normal, False)))

        # 6. Decorators (@decorator) (gold #D7BA7D)
        rules.append((re.compile(r"@\w+\b"), self._get_cached_format("#D7BA7D", QFont.Normal, False)))

        # 7. Numbers (light green #B5CEA8)
        rules.append((re.compile(r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b"), self._get_cached_format("#B5CEA8", QFont.Normal, False)))

        # 8. Single-line strings (VS Code orange #CE9178)
        rules.append((re.compile(r'(?<!")"(?:\\.|[^"\\])*"(?!")'), self._string_format))
        rules.append((re.compile(r"(?<!')'(?:\\.|[^'\\])*'(?!')"), self._string_format))
        rules.append((re.compile(r"`(?:\\.|[^`\\])*`"), self._string_format))

        # 9. Single-line comments (green #6A9955)
        if self._is_python or self.lang_name in ("sh", "bash", "yaml", "yml", "r"):
            rules.append((re.compile(r"#.*$"), self._comment_format))
        elif self._supports_c_comments:
            rules.append((re.compile(r"//.*$"), self._comment_format))
        elif self.lang_name in ("sql", "lua"):
            rules.append((re.compile(r"--.*$"), self._comment_format))

        return rules

    def highlightBlock(self, text: str):
        if self.lang_name == "asm":
            for pattern, style in self._rules:
                for match in pattern.finditer(text):
                    self.setFormat(match.start(), len(match[0]), style)
            for match in re.finditer(r''' "[^"]*" | '[^']*' | ;.*$ ''', text, re.X):
                style = self._comment_format if match[0].startswith(";") else self._string_format
                self.setFormat(match.start(), len(match[0]), style)
            return
        if not text:
            prev = self.previousBlockState()
            self.setCurrentBlockState(prev if prev > 0 else self.STATE_NORMAL)
            return

        prev_state = self.previousBlockState()
        self.setCurrentBlockState(self.STATE_NORMAL)
        code_start = 0

        # Handle line starting inside an open multiline comment or docstring
        if prev_state == self.STATE_C_COMMENT and self._supports_c_comments:
            end_idx = text.find("*/")
            if end_idx == -1:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(self.STATE_C_COMMENT)
                return
            else:
                end_idx += 2
                self.setFormat(0, end_idx, self._comment_format)
                code_start = end_idx

        elif prev_state == self.STATE_PY_TRIPLE_DOUBLE and self._is_python:
            end_idx = text.find('"""')
            if end_idx == -1:
                self.setFormat(0, len(text), self._docstring_format)
                self.setCurrentBlockState(self.STATE_PY_TRIPLE_DOUBLE)
                return
            else:
                end_idx += 3
                self.setFormat(0, end_idx, self._docstring_format)
                code_start = end_idx

        elif prev_state == self.STATE_PY_TRIPLE_SINGLE and self._is_python:
            end_idx = text.find("'''")
            if end_idx == -1:
                self.setFormat(0, len(text), self._docstring_format)
                self.setCurrentBlockState(self.STATE_PY_TRIPLE_SINGLE)
                return
            else:
                end_idx += 3
                self.setFormat(0, end_idx, self._docstring_format)
                code_start = end_idx

        elif prev_state == self.STATE_HTML_COMMENT and self._supports_html_comments:
            end_idx = text.find("-->")
            if end_idx == -1:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(self.STATE_HTML_COMMENT)
                return
            else:
                end_idx += 3
                self.setFormat(0, end_idx, self._comment_format)
                code_start = end_idx

        elif prev_state == self.STATE_LUA_COMMENT and self._supports_lua_comments:
            end_idx = text.find("--]]")
            if end_idx == -1:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(self.STATE_LUA_COMMENT)
                return
            else:
                end_idx += 4
                self.setFormat(0, end_idx, self._comment_format)
                code_start = end_idx

        # Highlight code on the remainder of the line
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text, code_start):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        # Check for new multiline comments or docstrings opening on this line
        self._check_multiline_delimiters(text, code_start)

    def _check_multiline_delimiters(self, text: str, start_pos: int):
        i = start_pos
        n = len(text)

        if self._is_python:
            # Ordinary code lines have neither comment nor string delimiters;
            # scanning every character of them cost more than all regex rules
            # together when a big file was opened.
            if ('#' not in text and '"' not in text
                    and "'" not in text and '`' not in text):
                return
            while i < n:
                # Line comment '#' outside strings/docstrings
                if text[i] == '#':
                    break

                # Triple quote docstrings/multiline strings
                if i + 3 <= n and text[i:i+3] in ('"""', "'''"):
                    delim = text[i:i+3]
                    target_state = self.STATE_PY_TRIPLE_DOUBLE if delim == '"""' else self.STATE_PY_TRIPLE_SINGLE
                    close_pos = text.find(delim, i + 3)
                    if close_pos != -1:
                        self.setFormat(i, close_pos + 3 - i, self._docstring_format)
                        i = close_pos + 3
                        continue
                    else:
                        self.setFormat(i, n - i, self._docstring_format)
                        self.setCurrentBlockState(target_state)
                        break

                # Single-line string literals: skip content without triggering comments
                if text[i] in ('"', "'"):
                    q = text[i]
                    j = i + 1
                    while j < n:
                        if text[j] == '\\':
                            j += 2
                            continue
                        if text[j] == q:
                            j += 1
                            break
                        j += 1
                    i = j
                    continue

                i += 1

        elif self._supports_c_comments:
            if ('/' not in text and '"' not in text
                    and "'" not in text and '`' not in text):
                return
            while i < n:
                # Line comment '//' outside strings
                if i + 2 <= n and text[i:i+2] == '//':
                    break

                # Block comment '/*'
                if i + 2 <= n and text[i:i+2] == '/*':
                    close_pos = text.find("*/", i + 2)
                    if close_pos != -1:
                        self.setFormat(i, close_pos + 2 - i, self._comment_format)
                        i = close_pos + 2
                        continue
                    else:
                        self.setFormat(i, n - i, self._comment_format)
                        self.setCurrentBlockState(self.STATE_C_COMMENT)
                        break

                # String or character literals
                if text[i] in ('"', "'", '`'):
                    q = text[i]
                    j = i + 1
                    while j < n:
                        if text[j] == '\\':
                            j += 2
                            continue
                        if text[j] == q:
                            j += 1
                            break
                        j += 1
                    i = j
                    continue

                i += 1

        elif self._supports_html_comments:
            if '<' not in text and '"' not in text and "'" not in text:
                return
            while i < n:
                if i + 4 <= n and text[i:i+4] == '<!--':
                    close_pos = text.find("-->", i + 4)
                    if close_pos != -1:
                        self.setFormat(i, close_pos + 3 - i, self._comment_format)
                        i = close_pos + 3
                        continue
                    else:
                        self.setFormat(i, n - i, self._comment_format)
                        self.setCurrentBlockState(self.STATE_HTML_COMMENT)
                        break

                if text[i] in ('"', "'"):
                    q = text[i]
                    j = i + 1
                    while j < n:
                        if text[j] == '\\':
                            j += 2
                            continue
                        if text[j] == q:
                            j += 1
                            break
                        j += 1
                    i = j
                    continue

                i += 1

        elif self._supports_lua_comments:
            if '-' not in text and '[' not in text and '"' not in text and "'" not in text:
                return
            while i < n:
                if i + 4 <= n and text[i:i+4] == '--[[':
                    close_pos = text.find("--]]", i + 4)
                    if close_pos != -1:
                        self.setFormat(i, close_pos + 4 - i, self._comment_format)
                        i = close_pos + 4
                        continue
                    else:
                        self.setFormat(i, n - i, self._comment_format)
                        self.setCurrentBlockState(self.STATE_LUA_COMMENT)
                        break

                if i + 2 <= n and text[i:i+2] == '--':
                    break

                if text[i] in ('"', "'"):
                    q = text[i]
                    j = i + 1
                    while j < n:
                        if text[j] == '\\':
                            j += 2
                            continue
                        if text[j] == q:
                            j += 1
                            break
                        j += 1
                    i = j
                    continue

                i += 1


class CompletionDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#264F78"))
        kind = index.data(Qt.UserRole + 1) or "symbol"
        colors = {
            "keyword": "#569CD6",
            "class": "#4EC9B0",
            "function": "#DCDCAA",
            "member": "#DCDCAA",
            "module": "#C586C0",
            "builtin": "#C586C0",
            "local": "#9CDCFE",
            "workspace": "#4EC9B0"
        }
        badge = {"keyword": "KW", "class": "CLS", "function": "FN", "member": "MEM", "module": "MOD", "builtin": "SYS", "local": "VAR", "workspace": "WSP"}.get(kind, kind[:3].upper())
        painter.setPen(QColor(colors.get(kind, "#A8A8A8")))
        painter.setFont(_ui_font(8, bold=True))
        painter.drawText(option.rect.adjusted(8, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, badge)
        painter.setPen(QColor("#D4D4D4"))
        painter.setFont(_ui_font(10))
        painter.drawText(option.rect.adjusted(44, 0, -8, 0), Qt.AlignLeft | Qt.AlignVCenter, str(index.data(Qt.DisplayRole)))
        painter.restore()

class CompletionModel(QtCore.QAbstractListModel):
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.items = items or []
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.items)
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.items): return None
        item = self.items[index.row()]
        if role == Qt.DisplayRole: return item[0]
        if role == Qt.UserRole: return item[0]
        if role == Qt.UserRole + 1: return item[1]
        return None

class SmartCompleter(QCompleter):
    insertText = pyqtSignal(str)
    def __init__(self, word_list=None, background_color="#1E1E1E", font_size=13, parent=None):
        super().__init__(parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterMode(Qt.MatchStartsWith)
        self.setCompletionRole(Qt.DisplayRole)
        self.setModelSorting(QCompleter.UnsortedModel)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setMaxVisibleItems(10)
        self._items = []
        popup = self.popup()
        popup.setItemDelegate(CompletionDelegate(popup))
        popup.setObjectName("completionPopup")
        popup.setFocusPolicy(Qt.StrongFocus)
        popup.setAttribute(Qt.WA_InputMethodEnabled, True)
        popup.setStyleSheet(f"""
            QListView#completionPopup {{ background: {background_color}; color: #D4D4D4; border: 1px solid #2B2B2B; border-radius: 3px; padding: 4px; outline: none; }}
            QListView#completionPopup::item {{ min-height: 30px; padding: 0; border: none; }}
            QListView#completionPopup::item:selected {{ background: #264F78; color: #FFFFFF; }}
        """)
        popup.setMinimumWidth(420)
        popup.setMaximumWidth(680)
    def update_completions(self, items):
        model = CompletionModel(items, self)
        self._items = items
        self.setModel(model)
    def complete(self, rect):
        popup = self.popup()
        popup.setMinimumHeight(min(10, self.completionCount()) * 30 + 8)
        super().complete(rect)


class CodeEditor(EnhancedTextEdit):
    """Основной редактор кода с поддержкой различных языков и прямоугольного выделения"""
    
    textChangedAnimated = pyqtSignal()
    focusChanged = pyqtSignal(bool)

    def __init__(self, parent=None, language: str = "", settings: dict = None, workspace_index=None, extension_manager=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.language = language
        self.workspace_index = workspace_index
        self.extension_manager = extension_manager
        
        # Получаем конфигурацию языка
        self.language_config = self._get_language_config(language)
        
        self._setup_editor()
        self._setup_autocomplete()
        self._setup_line_numbers()
        
        # Таймеры для отложенных операций
        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(self._delayed_analysis)
        
        self.completion_timer = QTimer()
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self._trigger_completion)
        
        # Подключаем сигнал прямоугольного выделения
        self.rectangleSelectionChanged.connect(self._on_rectangle_selection_changed)
    
    def _get_language_config(self, language: str) -> LanguageConfig:
        """Получение конфигурации языка"""
        config = LanguageProviderFactory.get_language_config(language)
        if not config:
            # Конфигурация по умолчанию для неподдерживаемых языков
            config = LanguageConfig(
                name="Plain Text",
                extensions=["txt"],
                keywords=[],
                syntax_rules=[],
                auto_indent=False,
                brace_auto_close=False
            )
        return config
    
    def _setup_editor(self):
        """Настройка базовых параметров редактора"""
        font_size = int(self.settings.get("editor_font_size", self.settings.get("fontsize", 13)))
        font_family = str(self.settings.get("editor_font", "Cascadia Code"))
        bg_color = self.settings.get("editor_background", self.settings.get("second_color", "#1E1E1E"))
        text_color = self.settings.get("text_primary", self.settings.get("text_color", "#D4D4D4"))
        
        self._base_font_size = font_size
        self.current_font_size = font_size
        self._apply_font_size(font_size)

        # Document margin prevents text from clipping or clinging to line numbers
        if self.document():
            self.document().setDocumentMargin(4)
        
        # Word wrap setting
        wrap_enabled = bool(self.settings.get("word_wrap", False))
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if wrap_enabled else QPlainTextEdit.NoWrap)
        
        # Настройка табуляции
        self.tab_width = 4
        self.setTabStopDistance(self.tab_width * self.fontMetrics().width(' '))
        
        # Подсветка синтаксиса
        self.highlighter = ModernSyntaxHighlighter(self.document(), self.language_config)
        syntax_enabled = bool(self.settings.get("syntax_highlighting", True))
        if not syntax_enabled:
            self.highlighter.setDocument(None)
    
    def _setup_line_numbers(self):
        """Настройка области номеров строк"""
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.cursorPositionChanged.connect(self._reposition_completion)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        
        show_lines = bool(self.settings.get("show_line_numbers", True))
        self.line_number_area.setVisible(show_lines)
        self.update_line_number_area_width()
        self.highlight_current_line()

    def _on_cursor_position_changed(self):
        """Гарантирует видимость начала строки при навигации к первым символам."""
        if self.textCursor().positionInBlock() <= 2 and self.horizontalScrollBar().value() > 0:
            self.horizontalScrollBar().setValue(0)

    def set_line_numbers_visible(self, visible: bool):
        if hasattr(self, 'line_number_area'):
            self.line_number_area.setVisible(bool(visible))
            self.update_line_number_area_width()

    def set_syntax_highlighting_enabled(self, enabled: bool):
        if hasattr(self, 'highlighter'):
            self.highlighter.setDocument(self.document() if enabled else None)
    
    def _setup_autocomplete(self):
        """Настройка системы автодополнения"""
        self.analyzer = CodeAnalyzer(self.language)
        self.completer = SmartCompleter(
            [], 
            self.settings.get("editor_background", self.settings.get("second_color", "#1E1E1E")),
            int(self.settings.get("editor_font_size", self.settings.get("fontsize", 13)))
        )
        self.completer.setWidget(self)
        self.completer.insertText.connect(self._insert_completion)
    
    def _on_rectangle_selection_changed(self, active: bool):
        """Обработка изменения режима прямоугольного выделения"""
        if active:
            # Меняем курсор на крестик для прямоугольного выделения
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            # Возвращаем стандартный курсор
            self.viewport().setCursor(Qt.IBeamCursor)
    
    def _reposition_completion(self):
        if hasattr(self, "completer") and self.completer.popup().isVisible():
            self.completer.complete(self.cursorRect())

    def setFont(self, font: QFont):
        super().setFont(font)
        if hasattr(self, "document") and self.document():
            self.document().setDefaultFont(font)
            self.document().setDocumentMargin(4)
        fm = self.fontMetrics()
        char_w = fm.horizontalAdvance(' ') if hasattr(fm, 'horizontalAdvance') else fm.width(' ')
        self.setTabStopDistance(getattr(self, 'tab_width', 4) * char_w)
        if hasattr(self, 'line_number_area'):
            self.line_number_area.setFont(font)
            self.update_line_number_area_width()
            self.line_number_area.update()
        cf = self.currentCharFormat()
        cf.setFont(font)
        pt = font.pointSize()
        if pt <= 0:
            pt = font.pixelSize()
        if pt > 0:
            cf.setFontPointSize(pt)
        self.setCurrentCharFormat(cf)
        # Возвращаемся к началу строки после смены шрифта (дальше в очереди
        # событий), чтобы не обращаться к уже удалённому виджету.
        QTimer.singleShot(0, self._scroll_back_to_line_start)

    def _scroll_back_to_line_start(self):
        try:
            self.horizontalScrollBar().setValue(0)
        except (RuntimeError, AttributeError):
            pass

    def _apply_font_size(self, size: int):
        """Гарантированное масштабирование шрифта редактора, синхронизирующее исходный и вводимый текст."""
        size = max(7, min(48, int(size)))
        self.current_font_size = size
        font_family = str(self.settings.get("editor_font", "Cascadia Code")) or self.font().family()
        new_font = QFont(font_family, size)
        new_font.setPointSize(size)
        new_font.setStyleHint(QFont.Monospace)
        
        self.setFont(new_font)
        
        # Обновляем форматирование всего существующего текста в документе
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            doc = self.document()
            if doc and not doc.isEmpty():
                c = QTextCursor(doc)
                c.select(QTextCursor.Document)
                fmt = QTextCharFormat()
                fmt.setFont(new_font)
                fmt.setFontPointSize(size)
                c.mergeCharFormat(fmt)
        finally:
            cursor.endEditBlock()
            
        # Синхронизируем формат для всех вновь вводимых символов
        cf = self.currentCharFormat()
        cf.setFont(new_font)
        cf.setFontPointSize(size)
        self.setCurrentCharFormat(cf)
        
        self.settings["editor_font_size"] = size
        p = self.parent()
        if p and hasattr(p, 'settings') and isinstance(p.settings, dict):
            p.settings["editor_font_size"] = size

    def _zoom_in(self):
        curr = getattr(self, 'current_font_size', None)
        if not curr or curr <= 0:
            curr = self.font().pointSize()
        if not curr or curr <= 0:
            curr = getattr(self, '_base_font_size', 13)
        self._apply_font_size(curr + 1)

    def _zoom_out(self):
        curr = getattr(self, 'current_font_size', None)
        if not curr or curr <= 0:
            curr = self.font().pointSize()
        if not curr or curr <= 0:
            curr = getattr(self, '_base_font_size', 13)
        self._apply_font_size(curr - 1)

    def _reset_zoom(self):
        base = getattr(self, '_base_font_size', 13)
        self._apply_font_size(base)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def run_selected_code(self):
        """Execute the selected code snippet in the integrated terminal."""
        cursor = self.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n').strip()
        if not selected:
            selected = cursor.block().text().strip()
        if not selected:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Выделите фрагмент кода для запуска")
            return

        main_win = self.window()
        console_widget = getattr(main_win, 'console_widget', None)
        if console_widget:
            if hasattr(main_win, 'set_console_visibility'):
                main_win.set_console_visibility(True)
            elif hasattr(main_win, 'toggle_terminal') and not getattr(main_win, 'terminal_visible', True):
                main_win.toggle_terminal()
            if hasattr(console_widget, 'set_current_tab'):
                console_widget.set_current_tab("Terminal")
            terminal = console_widget.get_terminal()
            if terminal:
                current_tab = getattr(terminal, '_current', lambda: None)()
                if current_tab and hasattr(current_tab, 'execute_command'):
                    escaped = selected.replace('"', '\\"').replace('\n', '; ')
                    cmd = f'python -c "{escaped}"'
                    current_tab.execute_command(cmd)
                    return
        QtWidgets.QMessageBox.information(self, "Запуск фрагмента кода", f"Фрагмент кода отправлен на запуск:\n\n{selected[:200]}")

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        # Code Navigation & Cross-Language Analysis
        act_goto_def = menu.addAction(line_icon("code"), "Перейти к определению")
        act_goto_def.setShortcut(QKeySequence("F12"))
        act_goto_def.triggered.connect(self.action_goto_definition)

        act_find_ref = menu.addAction(line_icon("search"), "Найти ссылки")
        act_find_ref.setShortcut(QKeySequence("Shift+F12"))
        act_find_ref.triggered.connect(self.action_find_references)

        act_openapi = menu.addAction("Перейти по контракту OpenAPI")
        act_openapi.triggered.connect(self.action_goto_openapi)

        act_call_hierarchy = menu.addAction("Иерархия вызовов")
        act_call_hierarchy.triggered.connect(self.action_show_call_hierarchy)

        menu.addSeparator()

        cursor = self.textCursor()
        selected_text = cursor.selectedText().replace('\u2029', '\n').strip()
        has_selection = bool(selected_text)

        # 1. Run snippet option if code is selected
        if has_selection:
            act_run = menu.addAction(line_icon("play"), "Запустить выделенный фрагмент кода")
            act_run.setShortcut(QKeySequence("Ctrl+Enter"))
            act_run.triggered.connect(self.run_selected_code)
            menu.addSeparator()

        # 2. Clean Code submenu
        clean_menu = menu.addMenu("✨ Чистый код")
        if has_selection:
            act_clean_sel = clean_menu.addAction("Рефакторинг выделенного фрагмента (Clean Code)")
            act_clean_sel.triggered.connect(self._format_selection_clean_code)
        act_clean_all = clean_menu.addAction("Форматировать весь файл (Clean Code + PEP-8)")
        act_clean_all.triggered.connect(self._format_entire_file_clean_code)

        # 3. Documentation submenu
        doc_menu = menu.addMenu("📝 Документация")
        if has_selection:
            act_doc_sel = doc_menu.addAction("Документировать выделенный код")
            act_doc_sel.triggered.connect(self._generate_docstring_selection)
        act_doc_all = doc_menu.addAction("Документировать весь файл")
        act_doc_all.triggered.connect(self._generate_docstrings_entire_file)

        menu.addSeparator()

        # 4. Impact & Run file
        window = self.window()
        current = window.get_current_editor() if hasattr(window, "get_current_editor") else None
        file_path = getattr(current, "file_path", None)
        if file_path and hasattr(window, "run_target"):
            run_file_act = menu.addAction("Запустить весь файл")
            run_file_act.triggered.connect(lambda: window.run_target(str(file_path), False))

        if hasattr(window, "action_analyze_current_impact"):
            impact_action = menu.addAction("Анализ влияния изменений файла")
            impact_action.triggered.connect(window.action_analyze_current_impact)

        menu.addSeparator()
        ai_menu = menu.addMenu("⚡ Code Intelligence")
        act_explain = ai_menu.addAction(line_icon("search"), "Интеллектуальный разбор кода")
        act_explain.triggered.connect(self._explain_code_intelligence)
        act_prep = ai_menu.addAction(line_icon("info"), "Архитектурный анализ и вопросы для Code Review")
        act_prep.triggered.connect(self._explain_code_intelligence)

        menu.exec_(event.globalPos())

    def get_file_path(self) -> Optional[str]:
        p = self._get_modern_editor_parent()
        if p and getattr(p, "file_path", None):
            return str(p.file_path)
        return getattr(self, "_file_path", None)

    def _get_symbol_under_cursor(self) -> Tuple[str, int, int]:
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock()
        sel = cursor.selectedText().strip()
        if sel and "\n" not in sel and len(sel) < 100:
            return sel, line, col
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText().strip()
        return word, line, col

    def _jump_to_location(self, loc):
        if not loc or not getattr(loc, "file_path", None):
            return
        win = self.window()
        file_path = str(loc.file_path)
        line = getattr(loc, "line", 1) or 1
        col = getattr(loc, "col", 0) or 0

        current_fp = self.get_file_path()
        if current_fp and Path(current_fp).resolve() == Path(file_path).resolve():
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Start)
            for _ in range(max(0, line - 1)):
                cursor.movePosition(QTextCursor.Down)
            if col > 0:
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, col)
            self.setTextCursor(cursor)
            self.centerCursor()
            self.setFocus()
            return

        if hasattr(win, "open_analysis_location"):
            win.open_analysis_location(file_path, line)
        elif hasattr(win, "file_manager") and hasattr(win.file_manager, "open_file"):
            win.file_manager.open_file(file_path)
            ed = win.get_current_editor() if hasattr(win, "get_current_editor") else None
            if ed and hasattr(ed, "editor"):
                c = ed.editor.textCursor()
                c.movePosition(QTextCursor.Start)
                for _ in range(max(0, line - 1)):
                    c.movePosition(QTextCursor.Down)
                if col > 0:
                    c.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, col)
                ed.editor.setTextCursor(c)
                ed.editor.centerCursor()
                ed.editor.setFocus()

    def action_goto_definition(self):
        word, line, col = self._get_symbol_under_cursor()
        file_path = self.get_file_path()
        if not file_path:
            file_path = "untitled.py" if self.language in ("py", "python") else f"untitled.{self.language or 'txt'}"

        from core.code_analysis.service import UnifiedCodeAnalysisService
        service = UnifiedCodeAnalysisService.get_instance()
        service.on_document_changed(file_path, self.toPlainText())

        locations = service.goto_definition(
            file_path, line, col,
            current_line_text=self.textCursor().block().text(),
            symbol_name=word
        )
        if not locations:
            win = self.window()
            if hasattr(win, "status_bar"):
                win.status_bar.showMessage(f"Определение для '{word}' не найдено", 3000)
            return

        if len(locations) == 1:
            self._jump_to_location(locations[0])
        else:
            from widgets.SymbolNavigationDialog import show_symbol_dialog
            show_symbol_dialog(
                self,
                f"Определения для '{word}' ({len(locations)})",
                locations,
                on_select=self._jump_to_location
            )

    def action_find_references(self):
        word, line, col = self._get_symbol_under_cursor()
        file_path = self.get_file_path()
        if not file_path:
            file_path = "untitled.py" if self.language in ("py", "python") else f"untitled.{self.language or 'txt'}"

        from core.code_analysis.service import UnifiedCodeAnalysisService
        service = UnifiedCodeAnalysisService.get_instance()
        service.on_document_changed(file_path, self.toPlainText())

        locations = service.find_references(
            file_path, line, col,
            symbol_name=word,
            include_declaration=True
        )
        if not locations:
            win = self.window()
            if hasattr(win, "status_bar"):
                win.status_bar.showMessage(f"Ссылки для '{word}' не найдены", 3000)
            return

        from widgets.SymbolNavigationDialog import show_symbol_dialog
        show_symbol_dialog(
            self,
            f"Ссылки на '{word}' ({len(locations)})",
            locations,
            on_select=self._jump_to_location
        )

    def action_goto_openapi(self):
        word, line, col = self._get_symbol_under_cursor()
        file_path = self.get_file_path()
        if not file_path:
            return
        from core.code_analysis.service import UnifiedCodeAnalysisService
        service = UnifiedCodeAnalysisService.get_instance()
        service.on_document_changed(file_path, self.toPlainText())

        locations = service.resolve_openapi(file_path, line, col, current_line_text=self.textCursor().block().text())
        if not locations:
            win = self.window()
            if hasattr(win, "status_bar"):
                win.status_bar.showMessage("Связанный контракт OpenAPI не найден", 3000)
            return

        if len(locations) == 1:
            self._jump_to_location(locations[0])
        else:
            from widgets.SymbolNavigationDialog import show_symbol_dialog
            show_symbol_dialog(
                self,
                f"Связи OpenAPI для '{word or 'маршрута'}' ({len(locations)})",
                locations,
                on_select=self._jump_to_location
            )

    def action_show_call_hierarchy(self):
        word, line, col = self._get_symbol_under_cursor()
        file_path = self.get_file_path()
        if not file_path:
            return
        from core.code_analysis.service import UnifiedCodeAnalysisService
        from core.code_analysis.lsp_client import LspLocation
        service = UnifiedCodeAnalysisService.get_instance()
        service.on_document_changed(file_path, self.toPlainText())

        incoming, outgoing = service.get_call_hierarchy(file_path, line, col)
        locs: List[LspLocation] = []
        for it in incoming:
            locs.append(LspLocation(
                file_path=it.file_path,
                line=it.line,
                col=it.col,
                preview=f"Входящий вызов из {it.name}",
                kind="semantic",
                badge=f"[Вызов: {it.name}]",
            ))
        for it in outgoing:
            locs.append(LspLocation(
                file_path=it.file_path,
                line=it.line,
                col=it.col,
                preview=f"Исходящий вызов к {it.name}",
                kind="semantic",
                badge=f"[Вызов: {it.name}]",
            ))

        if not locs:
            win = self.window()
            if hasattr(win, "status_bar"):
                win.status_bar.showMessage(f"Иерархия вызовов для '{word}' не найдена (требуется LSP)", 3000)
            return

        from widgets.SymbolNavigationDialog import show_symbol_dialog
        show_symbol_dialog(
            self,
            f"Иерархия вызовов '{word}' ({len(locs)})",
            locs,
            on_select=self._jump_to_location
        )

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Обработка отпускания мыши (включая Ctrl+Click для перехода к определению)."""
        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            cursor = self.cursorForPosition(event.pos())
            self.setTextCursor(cursor)
            self.action_goto_definition()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _format_selection_clean_code(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, 'code_lens') and p.code_lens:
            p.code_lens.format_selection()
        else:
            try:
                from widgets.CodeLensBar import CleanCodeRefactorer
                cursor = self.textCursor()
                sel = cursor.selectedText().replace('\u2029', '\n')
                if sel:
                    cursor.insertText(CleanCodeRefactorer.refactor_code(sel))
            except Exception:
                pass

    def _format_entire_file_clean_code(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, 'code_lens') and p.code_lens:
            p.code_lens.format_entire_file()
        else:
            try:
                from widgets.CodeLensBar import CleanCodeRefactorer
                self.setPlainText(CleanCodeRefactorer.refactor_code(self.toPlainText()))
            except Exception:
                pass

    def _generate_docstring_selection(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, 'code_lens') and p.code_lens:
            p.code_lens.generate_docstring_current()

    def _generate_docstrings_entire_file(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, 'code_lens') and p.code_lens:
            p.code_lens.generate_docstrings_entire_file()

    def _explain_code_intelligence(self):
        cursor = self.textCursor()
        selected_text = cursor.selectedText().replace('\u2029', '\n').strip()
        if not selected_text:
            selected_text = cursor.block().text().strip()
        if not selected_text:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Выделите фрагмент кода или строку для анализа")
            return

        try:
            from services.code_intelligence_service import CodeIntelligenceService
            from widgets.CodeExplainerDialog import CodeExplainerDialog
            data = CodeIntelligenceService.explain_code_snippet(selected_text, getattr(self, 'language', 'python'))
            dlg = CodeExplainerDialog(data, selected_text, self)
            dlg.exec_()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Ошибка разбора", f"Не удалось разобрать фрагмент: {exc}")

    # Backward compatibility alias
    _student_explain_code = _explain_code_intelligence

    def line_number_area_width(self):
        """Вычисление ширины области номеров строк с аккуратным отступом"""
        digits = len(str(max(1, self.blockCount())))
        fm = self.fontMetrics()
        digit_w = fm.horizontalAdvance('9') if hasattr(fm, 'horizontalAdvance') else fm.width('9')
        # left padding (8) + digits width + right margin before separator (6)
        space = max(34, 8 + digit_w * max(2, digits) + 6)
        return space
    
    def update_line_number_area_width(self, _=None):
        """Обновление ширины области номеров строк и геометрии полосы."""
        if hasattr(self, 'line_number_area') and not self.line_number_area.isVisible():
            self.setViewportMargins(0, 0, 0, 0)
            return
        w = self.line_number_area_width()
        self.setViewportMargins(w, 0, 0, 0)
        if hasattr(self, 'line_number_area'):
            cr = self.contentsRect()
            self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), w, cr.height()))
            self.line_number_area.update()
    
    def update_line_number_area(self, rect, dy):
        """Обновление области номеров строк"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "completer") and self.completer.popup().isVisible():
            self.completer.complete(self.cursorRect())
        self.update_line_number_area_width()
    
    def line_number_area_paint_event(self, event):
        """Отрисовка номеров строк с четким разделителем"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.palette().base())
        
        # Разделительная линия
        area_w = self.line_number_area.width()
        painter.setPen(QPen(QColor("#2B2B2B"), 1))
        painter.drawLine(area_w - 1, 0, area_w - 1, self.line_number_area.height())
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        current_line = self.textCursor().blockNumber() + 1
        font_metrics = self.fontMetrics()
        line_height = font_metrics.height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                
                pt = self.font().pointSize()
                if pt <= 0:
                    pt = self.font().pixelSize()
                if pt <= 0:
                    pt = 13
                if block_number + 1 == current_line:
                    painter.setPen(QColor("#00F2FE"))
                    painter.setFont(QFont(self.font().family(), pt, QFont.Bold))
                else:
                    painter.setPen(QColor("#6E7681"))
                    painter.setFont(self.font())
                
                painter.drawText(0, int(top), area_w - 6, 
                                int(line_height), Qt.AlignRight | Qt.AlignVCenter, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def _find_matching_bracket(self, text: str, bracket: str, pos: int) -> int:
        pairs = {'(': ')', '[': ']', '{': '}', ')': '(', ']': '[', '}': '{'}
        opening = '([{'
        is_forward = bracket in opening
        target = pairs.get(bracket)
        if not target:
            return -1
        step = 1 if is_forward else -1
        depth = 0
        cur = pos + step
        limit = min(len(text), cur + 3000) if is_forward else max(0, cur - 3000)
        while 0 <= cur < len(text) and (cur <= limit if is_forward else cur >= limit):
            ch = text[cur]
            if ch == bracket:
                depth += 1
            elif ch == target:
                if depth == 0:
                    return cur
                depth -= 1
            cur += step
        return -1

    def _get_bracket_selections(self) -> List[QTextEdit.ExtraSelection]:
        selections = []
        tc = self.textCursor()
        text = self.toPlainText()
        pos = tc.position()
        if not text:
            return selections

        bracket_pos = -1
        bracket_char = ''
        if pos < len(text) and text[pos] in "()[]{}":
            bracket_pos = pos
            bracket_char = text[pos]
        elif pos > 0 and text[pos - 1] in "()[]{}":
            bracket_pos = pos - 1
            bracket_char = text[pos - 1]

        if bracket_pos != -1:
            match_pos = self._find_matching_bracket(text, bracket_char, bracket_pos)
            bracket_format = QTextCharFormat()
            bracket_format.setBackground(QColor("#3B5166"))
            bracket_format.setForeground(QColor("#FFFFFF"))

            # Highlight current bracket
            sel1 = QTextEdit.ExtraSelection()
            c1 = self.textCursor()
            c1.setPosition(bracket_pos)
            c1.setPosition(bracket_pos + 1, QTextCursor.KeepAnchor)
            sel1.cursor = c1
            sel1.format = bracket_format
            selections.append(sel1)

            if match_pos != -1:
                sel2 = QTextEdit.ExtraSelection()
                c2 = self.textCursor()
                c2.setPosition(match_pos)
                c2.setPosition(match_pos + 1, QTextCursor.KeepAnchor)
                sel2.cursor = c2
                sel2.format = bracket_format
                selections.append(sel2)
            else:
                warn_format = QTextCharFormat()
                warn_format.setBackground(QColor("#5A1D1D"))
                warn_format.setForeground(QColor("#FF8080"))
                sel1.format = warn_format

        return selections

    def _get_occurrence_selections(self) -> List[QTextEdit.ExtraSelection]:
        selections = []
        tc = self.textCursor()
        if tc.hasSelection():
            word = tc.selectedText().strip()
        else:
            word_cur = QTextCursor(tc)
            word_cur.select(QTextCursor.WordUnderCursor)
            word = word_cur.selectedText().strip()

        if not word or len(word) < 2 or not word.isidentifier():
            return selections

        doc = self.document()
        find_cur = QTextCursor(doc)
        occurrence_format = QTextCharFormat()
        occurrence_format.setBackground(QColor("#243B53"))

        count = 0
        while count < 80:
            find_cur = doc.find(word, find_cur, QTextDocument.FindWholeWords)
            if find_cur.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.cursor = find_cur
            sel.format = occurrence_format
            selections.append(sel)
            count += 1

        return selections

    def highlight_current_line(self):
        """Подсветка текущей строки, парных скобок и контекстных вхождений идентификатора"""
        extra_selections = []
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2D3139")
            line_color.setAlpha(80)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        # Подсветка одинаковых вхождений идентификатора/слова
        extra_selections.extend(self._get_occurrence_selections())

        # Подсветка парных скобок
        extra_selections.extend(self._get_bracket_selections())
        
        # Добавляем прямоугольные выделения, если они есть
        if hasattr(self, 'rectangle_selections'):
            extra_selections.extend(self.rectangle_selections)
        
        self.setExtraSelections(extra_selections)

    # ------------------------------------------------------------------
    # Line operations (VS Code semantics)
    # ------------------------------------------------------------------

    def _selected_block_range(self):
        """Return (first_block_number, last_block_number) touched by the selection."""
        cursor = self.textCursor()
        doc = self.document()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        first = doc.findBlock(start_pos).blockNumber()
        last_block = doc.findBlock(end_pos)
        # If the selection ends exactly at the start of a block, that block is
        # not really included (VS Code behaves the same way).
        if last_block.blockNumber() > first and last_block.position() == end_pos:
            last = last_block.blockNumber() - 1
        else:
            last = last_block.blockNumber()
        return first, last

    def _document_lines(self) -> List[str]:
        return self.toPlainText().split('\n')

    def _replace_document_lines(self, lines: List[str], anchor_block: int, anchor_col: int,
                                select_blocks: Optional[Tuple[int, int]] = None):
        """Re-write the document in one undo step and restore the cursor/selection."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            full = QTextCursor(self.document())
            full.select(QTextCursor.Document)
            full.removeSelectedText()
            full.insertText('\n'.join(lines))
        finally:
            cursor.endEditBlock()

        doc = self.document()
        anchor_block = max(0, min(anchor_block, doc.blockCount() - 1))
        block = doc.findBlockByNumber(anchor_block)
        col = max(0, min(anchor_col, len(block.text())))
        new_cursor = QTextCursor(block)
        new_cursor.setPosition(block.position() + col)
        if select_blocks:
            first, last = select_blocks
            first = max(0, min(first, doc.blockCount() - 1))
            last = max(first, min(last, doc.blockCount() - 1))
            start = doc.findBlockByNumber(first).position()
            end_block = doc.findBlockByNumber(last)
            end = end_block.position() + len(end_block.text())
            if last == doc.blockCount() - 1:
                end = doc.characterCount() - 1
            new_cursor.setPosition(start)
            new_cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.setTextCursor(new_cursor)

    def _move_line_up(self):
        """Переместить текущую строку/блок вверх (Alt+Up)"""
        first, last = self._selected_block_range()
        if first <= 0:
            return
        cursor = self.textCursor()
        col = cursor.positionInBlock()
        had_selection = cursor.hasSelection()
        lines = self._document_lines()
        block_lines = lines[first:last + 1]
        del lines[first:last + 1]
        new_first = first - 1
        lines[new_first:new_first] = block_lines
        self._replace_document_lines(
            lines, new_first, col,
            select_blocks=(new_first, last - 1) if had_selection else None,
        )

    def _move_line_down(self):
        """Переместить текущую строку/блок вниз (Alt+Down)"""
        first, last = self._selected_block_range()
        lines = self._document_lines()
        if last >= len(lines) - 1:
            return
        cursor = self.textCursor()
        col = cursor.positionInBlock()
        had_selection = cursor.hasSelection()
        for i in range(last, first - 1, -1):
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
        self._replace_document_lines(
            lines, first + 1, col,
            select_blocks=(first + 1, last + 1) if had_selection else None,
        )

    def _duplicate_block_up(self):
        """Дублировать текущую строку/блок вверх (Shift+Alt+Up)"""
        first, last = self._selected_block_range()
        lines = self._document_lines()
        block_lines = lines[first:last + 1]
        lines[first:first] = block_lines
        cursor = self.textCursor()
        self._replace_document_lines(
            lines, first, cursor.positionInBlock(),
            select_blocks=(first, first + (last - first)),
        )

    def _duplicate_block_down(self):
        """Дублировать текущую строку/блок вниз (Shift+Alt+Down)"""
        first, last = self._selected_block_range()
        lines = self._document_lines()
        block_lines = lines[first:last + 1]
        lines[last + 1:last + 1] = block_lines
        cursor = self.textCursor()
        self._replace_document_lines(
            lines, first + (last - first) + 1, cursor.positionInBlock(),
            select_blocks=(first + (last - first) + 1, last + (last - first) + 1),
        )

    def _duplicate_line_up(self):
        """Дублировать строку/блок вверх (Shift+Alt+Up)"""
        self._duplicate_block_up()

    def _duplicate_line_down(self):
        """Дублировать строку/блок вниз (Shift+Alt+Down)"""
        self._duplicate_block_down()

    def _delete_block(self):
        """Удалить текущую строку/блок (Ctrl+Shift+K), корректно обрабатывая последнюю строку."""
        first, last = self._selected_block_range()
        lines = self._document_lines()
        del lines[first:last + 1]
        if not lines:
            lines = ['']
        anchor = min(first, len(lines) - 1)
        cursor = self.textCursor()
        self._replace_document_lines(lines, anchor, cursor.positionInBlock())

    def _select_next_occurrence(self):
        """Выбрать следующее вхождение слова или текущее слово (Ctrl+D)"""
        tc = self.textCursor()
        if not tc.hasSelection():
            tc.select(QTextCursor.WordUnderCursor)
            self.setTextCursor(tc)
            return

        selected = tc.selectedText()
        doc = self.document()
        find_cur = doc.find(selected, tc, QTextDocument.FindCaseSensitively)
        if find_cur.isNull():
            # Зацикливание к началу документа
            find_cur = doc.find(selected, 0, QTextDocument.FindCaseSensitively)
        if not find_cur.isNull():
            self.setTextCursor(find_cur)
    
    def _insert_completion(self, completion: str):
        """Вставить выбранный вариант и закрыть список подсказок."""
        completion = str(completion).split("\t", 1)[0]
        prefix = str(self.completer.completionPrefix())
        tc = self.textCursor()
        if prefix:
            tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
            tc.removeSelectedText()
        tc.insertText(completion)
        self.setTextCursor(tc)
        self.completer.popup().hide()
        self.setFocus(Qt.OtherFocusReason)

    def _accept_completion(self):
        popup = self.completer.popup()
        index = popup.currentIndex()
        if not index.isValid() and self.completer.completionCount():
            index = self.completer.completionModel().index(0, 0)
        if index.isValid():
            self._insert_completion(index.data(Qt.DisplayRole))
        else:
            popup.hide()
    
    def _trigger_completion(self):
        """Интеллектуальное автодополнение (Jedi IntelliSense + Workspace Index + AST + Extensions)."""
        tc = self.textCursor()
        text = self.toPlainText()
        position = tc.position()
        before = text[:position]
        match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", before)
        prefix = match.group(0) if match else ""
        explicit = getattr(self, "_explicit_completion", False)
        self._explicit_completion = False

        if not prefix and not explicit and not before.endswith('.'):
            self.completer.popup().hide()
            return

        completion_items = {}

        # 1. Интеллектуальный анализатор Python через Jedi
        is_python = self.language.lower() in ("python", "py", "") or getattr(self.language_config, "name", "").lower() == "python"
        if is_python:
            try:
                import jedi
                parent_mod = self._get_modern_editor_parent()
                file_path = str(parent_mod.file_path) if parent_mod and getattr(parent_mod, 'file_path', None) else "temp.py"
                script = jedi.Script(code=text, path=file_path)
                cur_line = tc.blockNumber() + 1
                cur_col = tc.positionInBlock()
                jedi_results = script.complete(line=cur_line, column=cur_col)
                for item in jedi_results:
                    k = "function" if item.type in ("function", "method") else ("class" if item.type == "class" else ("module" if item.type in ("module", "package") else ("keyword" if item.type == "keyword" else "local")))
                    completion_items[item.name] = k
            except Exception:
                pass

        # 2. Ключевые слова синтаксиса языка
        for word in self.language_config.keywords:
            if str(word) not in completion_items:
                completion_items[str(word)] = "keyword"

        # 3. Символы из локального синтаксического AST анализатора
        try:
            self.analyzer.analyze_code(text)
            for word in self.analyzer.get_completion_list():
                if str(word) not in completion_items:
                    completion_items[str(word)] = "keyword" if str(word) in self.language_config.keywords else "local"
        except Exception:
            pass

        # 4. Проектный индекс рабочей области (Workspace Index)
        if self.workspace_index is not None:
            for word in self.workspace_index.complete(prefix, self.language):
                if word not in completion_items:
                    completion_items[word] = "workspace"
            member_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_][A-Za-z0-9_]*$", before)
            if member_match:
                owner = member_match.group(1)
                class_match = re.search(rf"\b{re.escape(owner)}\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
                if class_match:
                    for word in self.workspace_index.complete_members(class_match.group(1), prefix):
                        completion_items[word] = "member"

        # 5. Провайдеры автодополнения из установленных расширений
        if self.extension_manager is not None:
            for provider in self.extension_manager.get_completion_providers():
                try:
                    if hasattr(provider, "complete"):
                        try:
                            items = provider.complete(self, prefix)
                        except TypeError:
                            items = provider.complete(text, self.language, prefix)
                        for item in items or []:
                            label = getattr(item, "label", str(item))
                            completion_items[str(label)] = "builtin"
                except Exception as exc:
                    logger.exception("Completion provider error")

        if prefix:
            filtered = sorted([(w, k) for w, k in completion_items.items() if w and w.lower().startswith(prefix.lower())], key=lambda x: x[0].lower())
        else:
            filtered = sorted([(w, k) for w, k in completion_items.items() if w], key=lambda x: x[0].lower())[:80]

        self.completer.update_completions(filtered)
        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount() > 0:
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            self.completer.complete(self.cursorRect())
            popup.show()
            popup.raise_()
        else:
            self.completer.popup().hide()

    def _delayed_analysis(self):
        """Отложенный анализ кода"""
        self.analyzer.analyze_code(self.toPlainText())
    
    def _get_modern_editor_parent(self):
        p = self.parent()
        while p and not hasattr(p, 'show_find_bar'):
            p = p.parent()
        return p

    def _indent_selection(self):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        doc = self.document()
        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        tab_spaces = " " * getattr(self, 'tab_width', 4)

        cursor.beginEditBlock()
        try:
            block = start_block
            while block.isValid():
                c = QTextCursor(block)
                c.insertText(tab_spaces)
                if block == end_block:
                    break
                block = block.next()
        finally:
            cursor.endEditBlock()

    def _unindent_selection(self):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        doc = self.document()
        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        tab_w = getattr(self, 'tab_width', 4)

        cursor.beginEditBlock()
        try:
            block = start_block
            while block.isValid():
                text = block.text()
                c = QTextCursor(block)
                spaces_to_remove = 0
                for char in text[:tab_w]:
                    if char == ' ':
                        spaces_to_remove += 1
                    elif char == '\t':
                        spaces_to_remove = 1
                        break
                    else:
                        break
                if spaces_to_remove > 0:
                    c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, spaces_to_remove)
                    c.removeSelectedText()
                if block == end_block:
                    break
                block = block.next()
        finally:
            cursor.endEditBlock()

    def _toggle_comment_current(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, '_toggle_comment'):
            p._toggle_comment()

    def _duplicate_line_current(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, '_duplicate_line'):
            p._duplicate_line()

    def _delete_line_current(self):
        p = self._get_modern_editor_parent()
        if p and hasattr(p, '_delete_line'):
            p._delete_line()

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш с расширенными возможностями"""
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shift = bool(event.modifiers() & Qt.ShiftModifier)
        alt = bool(event.modifiers() & Qt.AltModifier)

        # F12: перейти к определению (Go to Definition), Shift+F12: найти ссылки (Find References)
        if event.key() == Qt.Key_F12:
            if shift:
                self.action_find_references()
            else:
                self.action_goto_definition()
            event.accept()
            return

        # 0. Масштабирование шрифта редактора (Ctrl++, Ctrl+=, Ctrl+-, Ctrl+_, Ctrl+0, Numpad)
        is_zoom_in = ctrl and not alt and event.key() in (Qt.Key_Equal, Qt.Key_Plus)
        is_zoom_out = ctrl and not alt and event.key() in (Qt.Key_Minus, Qt.Key_Underscore)
        is_zoom_reset = ctrl and not alt and event.key() == Qt.Key_0

        if is_zoom_in:
            self._zoom_in()
            event.accept()
            return
        if is_zoom_out:
            self._zoom_out()
            event.accept()
            return
        if is_zoom_reset:
            self._reset_zoom()
            event.accept()
            return

        # 1. Ctrl+Space: автодополнение
        if ctrl and event.key() == Qt.Key_Space:
            self._explicit_completion = True
            self._trigger_completion()
            return

        # 2. Перемещение строк вверх/вниз (Alt+Up, Alt+Down)
        #    Shift+Alt+<стрелка> обрабатывается раньше, чтобы не конфликтовать.
        if alt and not ctrl and (event.key() in (Qt.Key_Up, Qt.Key_Down)):
            if shift:
                if event.key() == Qt.Key_Up:
                    self._duplicate_line_up()
                else:
                    self._duplicate_line_down()
            elif event.key() == Qt.Key_Up:
                self._move_line_up()
            else:
                self._move_line_down()
            return

        # 4. Выбор следующего вхождения (Ctrl+D)
        if ctrl and not shift and not alt and event.key() == Qt.Key_D:
            self._select_next_occurrence()
            return

        # 5. Прямоугольное выделение
        if event.key() == Qt.Key_Escape and self.selection_mode == SelectionMode.RECTANGLE:
            # Leaving rectangle mode with Esc used to live in a second, dead
            # keyPressEvent definition that the class body overrode.
            self.selection_mode = SelectionMode.NORMAL
            self.rectangle_selections.clear()
            self.rectangleSelectionChanged.emit(False)
            self.viewport().update()
            return
        if self.selection_mode == SelectionMode.RECTANGLE and self.rectangle_selections:
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self.delete_rectangle_selection()
                return
            elif ctrl and event.key() == Qt.Key_C:
                self.copy_rectangle_selection()
                return
            elif ctrl and event.key() == Qt.Key_X:
                self.cut_rectangle_selection()
                return
            elif event.key() in (Qt.Key_Enter, Qt.Key_Return):
                self.insert_text_in_rectangle("\n")
                return
            elif event.text() and not event.modifiers():
                self.insert_text_in_rectangle(event.text())
                return

        # 6. Отступы блоков клавишами Tab / Shift+Tab
        if event.key() == Qt.Key_Backtab or (event.key() == Qt.Key_Tab and shift):
            self._unindent_selection()
            return
        elif event.key() == Qt.Key_Tab and not self.completer.popup().isVisible():
            if self.textCursor().hasSelection():
                self._indent_selection()
                return

        # 7. Горячие клавиши рабочей среды.
        # Важно: НЕ перехватываем стандартные клавиши редактирования текста
        # (Ctrl+C/V/X/A/Z/Y/D/W/Del) — их обрабатывает сам QPlainTextEdit,
        # а действия уровня приложения приходят через QShortcut в главном окне.
        if ctrl and event.key() == Qt.Key_P:
            win = self.window()
            if shift and hasattr(win, 'show_command_palette'):
                win.show_command_palette()
                return
            if not shift and hasattr(win, 'action_quick_open'):
                win.action_quick_open()
                return
        if event.key() == Qt.Key_F1:
            win = self.window()
            if hasattr(win, 'show_command_palette'):
                win.show_command_palette()
                return
        if event.key() == Qt.Key_F5:
            win = self.window()
            if ctrl and hasattr(win, 'action_run_project'):
                win.action_run_project()
                return
            if hasattr(win, 'action_run_file'):
                win.action_run_file()
                return
        if ctrl and event.key() == Qt.Key_G:
            win = self.window()
            if hasattr(win, 'action_goto_line'):
                win.action_goto_line()
                return
        if ctrl and shift and event.key() == Qt.Key_B:
            p = self._get_modern_editor_parent()
            if p and hasattr(p, 'toggle_code_lens'):
                p.toggle_code_lens()
                return
        if ctrl and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            p = self._get_modern_editor_parent()
            if p and hasattr(p, '_run_current_block_shortcut'):
                p._run_current_block_shortcut()
                return
        if ctrl and (event.key() in (Qt.Key_QuoteLeft, Qt.Key_AsciiTilde) or event.text() == '`'):
            win = self.window()
            if hasattr(win, 'toggle_terminal'):
                win.toggle_terminal()
                return
        if ctrl and (event.key() == Qt.Key_Backslash or event.text() == '\\'):
            win = self.window()
            if hasattr(win, 'toggle_sidebar'):
                win.toggle_sidebar()
                return
        if ctrl and shift and event.key() == Qt.Key_F:
            win = self.window()
            if hasattr(win, '_focus_search'):
                win._focus_search()
                return
        if ctrl and event.key() == Qt.Key_Slash:
            self._toggle_comment_current()
            return
        if ctrl and shift and event.key() == Qt.Key_K:
            self._delete_line_current()
            return
        if ctrl and not shift and event.key() == Qt.Key_F:
            p = self._get_modern_editor_parent()
            if p:
                p.show_find_bar()
                return
        if ctrl and not shift and event.key() == Qt.Key_H:
            p = self._get_modern_editor_parent()
            if p:
                p.show_replace_bar()
                return

        # 8. Удаление парных скобок и кавычек при Backspace
        if event.key() == Qt.Key_Backspace and not self.textCursor().hasSelection():
            cursor = self.textCursor()
            block_text = cursor.block().text()
            pos = cursor.positionInBlock()
            if 0 < pos < len(block_text):
                prev_ch = block_text[pos - 1]
                next_ch = block_text[pos]
                pairs = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
                if pairs.get(prev_ch) == next_ch:
                    cursor.deletePreviousChar()
                    cursor.deleteChar()
                    self.setTextCursor(cursor)
                    return

        # 9. Автозакрытие скобок и пропуск закрывающих
        if getattr(self.language_config, 'brace_auto_close', True):
            if self._handle_auto_closure(event):
                return

        # 10. Умные отступы при Enter с расщеплением фигурных скобок
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._handle_smart_indent()
            return

        # 11. Комплитер
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return):
                self._accept_completion()
                return
            if event.key() == Qt.Key_Escape:
                self.completer.popup().hide()
                return
            if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
                QtWidgets.QApplication.sendEvent(self.completer.popup(), event)
                return

        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.completer.popup().hide()

        if event.text() and not event.text().isspace() and not ctrl:
            self.completion_timer.start(120)

        super().keyPressEvent(event)
        self.analysis_timer.start(500)

    def _handle_auto_closure(self, event):
        """Автоматическое закрытие скобок и кавычек с поддержкой пропуска и оборачивания выделения"""
        closure_map = {'"': '"', "'": "'", '(': ')', '[': ']', '{': '}'}
        closing_chars = {')', ']', '}', '"', "'"}
        char = event.text()

        if char in closing_chars:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                block_text = cursor.block().text()
                pos = cursor.positionInBlock()
                if pos < len(block_text) and block_text[pos] == char:
                    cursor.movePosition(QTextCursor.Right)
                    self.setTextCursor(cursor)
                    return True

        if char in closure_map:
            cursor = self.textCursor()
            if cursor.hasSelection():
                sel = cursor.selectedText()
                cursor.insertText(char + sel + closure_map[char])
                return True
            else:
                cursor.insertText(char + closure_map[char])
                cursor.movePosition(QTextCursor.Left)
                self.setTextCursor(cursor)
                return True
        return False

    def _handle_smart_indent(self):
        """Умное добавление отступов при нажатии Enter с расщеплением фигурных скобок"""
        cursor = self.textCursor()
        current_block = cursor.block()
        line_text = current_block.text() if current_block.isValid() else ""

        col = cursor.positionInBlock()
        prefix = line_text[:col]
        indent = len(prefix) - len(prefix.lstrip(' \t'))
        base_indent = prefix[:indent]
        tab_spaces = ' ' * getattr(self, 'tab_width', 4)

        # Расщепление при нажатии Enter между парными скобками: {} или () или []
        if 0 < col < len(line_text):
            prev_ch = line_text[col - 1]
            next_ch = line_text[col]
            if (prev_ch == '{' and next_ch == '}') or (prev_ch == '(' and next_ch == ')') or (prev_ch == '[' and next_ch == ']'):
                cursor.beginEditBlock()
                cursor.insertText('\n' + base_indent + tab_spaces + '\n' + base_indent)
                cursor.movePosition(QTextCursor.Up)
                cursor.movePosition(QTextCursor.EndOfLine)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                return

        if getattr(self, 'language_config', None) and getattr(self.language_config, 'auto_indent', False):
            if prefix.rstrip().endswith((':', '{', '[', '(', '=>')):
                base_indent += tab_spaces

        cursor.insertText('\n' + base_indent)
    
    def set_language(self, language: str):
        """Изменение языка программирования"""
        self.language = language
        self.language_config = self._get_language_config(language)
        self.analyzer = CodeAnalyzer(language)
        self.highlighter = ModernSyntaxHighlighter(self.document(), self.language_config)
        self.analyzer.analyze_code(self.toPlainText())


class ModernCodeEditor(QWidget):
    """Современный редактор кода с поддержкой различных языков и прямоугольного выделения"""
    
    rectangleSelectionActive = pyqtSignal(bool)
    
    def __init__(self, parent=None, language: str = "", settings: dict = None, workspace_index=None, extension_manager=None):
        super().__init__(parent)
        self.language = language
        self.settings = settings or {}
        self.workspace_index = workspace_index
        self.extension_manager = extension_manager
        self.file_path = None
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_status_bar()
    
    def set_completion_context(self, workspace_index=None, extension_manager=None):
        self.workspace_index = workspace_index
        self.extension_manager = extension_manager
        self.editor.workspace_index = workspace_index
        self.editor.extension_manager = extension_manager

    def _setup_ui(self):
        """Настройка пользовательского интерфейса с поиском и кодовым радаром."""
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        
        # 1. Основной редактор кода
        self.editor = CodeEditor(language=self.language, settings=self.settings, workspace_index=self.workspace_index, extension_manager=self.extension_manager)
        self._root_layout.addWidget(self.editor, 1)

        # 2. Панель быстрого поиска и замены (Ctrl+F / Ctrl+H)
        try:
            self.find_bar = FindReplaceBar(self)
            self.find_bar.hide()
            self._root_layout.insertWidget(0, self.find_bar)
        except Exception:
            self.find_bar = None

        # 3. PyScribe CodeLens & Context Action Hub (Умная навигация и экспресс-действия)
        try:
            self.code_lens = CodeLensBar(self)
            insert_idx = 1 if (hasattr(self, 'find_bar') and self.find_bar) else 0
            self._root_layout.insertWidget(insert_idx, self.code_lens)
            self.code_radar = self.code_lens  # backwards-compatibility alias
        except Exception:
            self.code_lens = None
            self.code_radar = None
    
    def _setup_status_bar(self):
        """Настройка компактного статус-бара редактора с переключателем CodeLens."""
        self.status_bar_frame = QFrame()
        self.status_bar_frame.setObjectName("editorStatusBarFrame")
        # Styling comes from design/theme.qss (QFrame#editorStatusBarFrame +
        # QToolButton.statusActionBtn) so the strip matches every other bar.
        sb_layout = QHBoxLayout(self.status_bar_frame)
        sb_layout.setContentsMargins(10, 0, 10, 0)
        sb_layout.setSpacing(6)

        self.status_bar = QLabel()
        self.status_bar.setObjectName("editorStatusBar")
        sb_layout.addWidget(self.status_bar)

        sb_layout.addStretch(1)

        # Центральная часть: индикатор занятости (stop_busy_indicator / start_busy_indicator)
        self.center_status_widget = QWidget()
        center_layout = QHBoxLayout(self.center_status_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        try:
            from widgets.LoadingSpinner import MiniSpinner
            self.editor_spinner = MiniSpinner(self.center_status_widget)
            self.editor_spinner.hide()
            center_layout.addWidget(self.editor_spinner)
        except Exception:
            self.editor_spinner = None

        self.center_status_label = QLabel("")
        self.center_status_label.setObjectName("editorCenterStatus")
        center_layout.addWidget(self.center_status_label)
        sb_layout.addWidget(self.center_status_widget)

        sb_layout.addStretch(1)

        # 1. Action: Clean Code Menu
        self.clean_code_btn = QtWidgets.QToolButton()
        self.clean_code_btn.setProperty("class", "statusActionBtn")
        self.clean_code_btn.setText("Форматирование")
        set_line_icon(self.clean_code_btn, "code")
        self.clean_code_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.clean_code_btn.setToolTip("Форматирование по принципам Clean Code и PEP-8")
        clean_menu = QtWidgets.QMenu(self.clean_code_btn)
        clean_menu.setStyleSheet("QMenu { background: #121822; border: 1px solid #1C2533; color: #E6EDF3;  font-size: 12px; border-radius: 6px; padding: 4px; } QMenu::item { padding: 4px 12px; border-radius: 4px; } QMenu::item:selected { background: #1A3650; color: #00F2FE; }")

        act_clean_all = clean_menu.addAction("Форматировать весь файл")
        act_clean_all.triggered.connect(self.format_entire_file)

        act_clean_sel = clean_menu.addAction("Форматировать выделенный фрагмент")
        act_clean_sel.triggered.connect(self.format_selection)

        self.clean_code_btn.setMenu(clean_menu)
        sb_layout.addWidget(self.clean_code_btn)

        # 2. Action: Documentation Menu
        self.docstring_btn = QtWidgets.QToolButton()
        self.docstring_btn.setProperty("class", "statusActionBtn")
        self.docstring_btn.setText("Автодокументирование")
        set_line_icon(self.docstring_btn, "document")
        self.docstring_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.docstring_btn.setToolTip("Генерация структурированных описаний и комментариев для функций, классов и всего файла")
        doc_menu = QtWidgets.QMenu(self.docstring_btn)
        doc_menu.setStyleSheet("QMenu { background: #121822; border: 1px solid #1C2533; color: #E6EDF3;  font-size: 12px; border-radius: 6px; padding: 4px; } QMenu::item { padding: 4px 12px; border-radius: 4px; } QMenu::item:selected { background: #1A3650; color: #00F2FE; }")

        act_doc_curr = doc_menu.addAction("Документировать текущий блок / функцию / класс")
        act_doc_curr.triggered.connect(self.generate_docstring_current)

        act_doc_all = doc_menu.addAction("Документировать весь файл")
        act_doc_all.triggered.connect(self.generate_docstrings_entire_file)

        self.docstring_btn.setMenu(doc_menu)
        sb_layout.addWidget(self.docstring_btn)

        # 3. Action: CodeLens Toggle
        self.lens_toggle_btn = QtWidgets.QToolButton()
        self.lens_toggle_btn.setObjectName("lensToggleBtn")
        self.lens_toggle_btn.setText("CodeLens")
        self.lens_toggle_btn.setToolTip("Включить / скрыть панель CodeLens и экспресс-действий (Ctrl+Shift+B)")
        self.lens_toggle_btn.clicked.connect(self.toggle_code_lens)
        sb_layout.addWidget(self.lens_toggle_btn)

        self._root_layout.addWidget(self.status_bar_frame, 0)

        # Подключаем сигналы для обновления статус-бара
        self.editor.cursorPositionChanged.connect(self.update_status_bar)
        self.editor.textChanged.connect(self.update_status_bar)
        self.editor.rectangleSelectionChanged.connect(self._on_rectangle_selection_status)
    
    def _on_rectangle_selection_status(self, active: bool):
        """Обновление статуса прямоугольного выделения"""
        self.rectangleSelectionActive.emit(active)
        self.update_status_bar()
    
    def update_status_bar(self):
        """Обновление статус-бара"""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        lines = self.editor.document().blockCount()
        
        # Информация о выделении
        if self.editor.selection_mode == SelectionMode.RECTANGLE and self.editor.rectangle_selections:
            rect_info = f" [RECT: {len(self.editor.rectangle_selections)} lines]"
        else:
            rect_info = ""
        
        # Информация о режиме
        mode = "RECT" if self.editor.selection_mode == SelectionMode.RECTANGLE else "INS"
        wrap_info = " | Wrap: ON" if self.editor.lineWrapMode() == QPlainTextEdit.WidgetWidth else ""
        
        self.status_bar.setText(f"Ln {line}, Col {column} | Lines: {lines} | Mode: {mode}{rect_info}{wrap_info}")
    
    def _setup_shortcuts(self):
        """Настройка горячих клавиш с контекстом WidgetWithChildrenShortcut"""
        shortcuts = {
            "Ctrl+=": self._zoom_in,
            "Ctrl++": self._zoom_in,
            "Ctrl+Shift+=": self._zoom_in,
            "Ctrl+Shift++": self._zoom_in,
            "Ctrl+-": self._zoom_out,
            "Ctrl+_": self._zoom_out,
            "Ctrl+0": self._reset_zoom,
            "Ctrl+/": self._toggle_comment,
            "Ctrl+D": self.editor._select_next_occurrence,
            "Ctrl+Shift+K": self._delete_line,
            "Alt+Up": self.editor._move_line_up,
            "Alt+Down": self.editor._move_line_down,
            "Shift+Alt+Up": self.editor._duplicate_line_up,
            "Shift+Alt+Down": self.editor._duplicate_line_down,
            "Ctrl+F": self.show_find_bar,
            "Ctrl+H": self.show_replace_bar,
            "Ctrl+Shift+B": self.toggle_code_lens,
            "Ctrl+Shift+R": self.toggle_code_lens,
            "Ctrl+Return": self._run_current_block_shortcut,
            "Ctrl+Enter": self._run_current_block_shortcut,
            "Alt+Z": self.toggle_word_wrap,
            "Escape": self._on_escape_pressed,
            "Alt+C": self._copy_rectangle,
            "Alt+X": self._cut_rectangle,
            "Alt+V": self._paste_rectangle,
            "Alt+Delete": self._delete_rectangle,
        }
        
        self._shortcuts = []
        for key_sequence, callback in shortcuts.items():
            sc = QShortcut(QKeySequence(key_sequence), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(callback)
            self._shortcuts.append(sc)

    def _on_escape_pressed(self):
        if hasattr(self, 'find_bar') and self.find_bar and self.find_bar.isVisible():
            self.find_bar.hide_bar()
            return
        if self.editor.selection_mode == SelectionMode.RECTANGLE:
            self._cancel_rectangle_selection()

    def show_find_bar(self):
        if hasattr(self, 'find_bar') and self.find_bar:
            self.find_bar.show_find()

    def show_replace_bar(self):
        if hasattr(self, 'find_bar') and self.find_bar:
            self.find_bar.show_replace()

    def toggle_code_lens(self):
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.setVisible(not self.code_lens.isVisible())

    def toggle_code_radar(self):
        self.toggle_code_lens()

    def _run_current_block_shortcut(self):
        if hasattr(self.editor, 'run_selected_code') and self.editor.textCursor().hasSelection():
            self.editor.run_selected_code()
            return
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.run_current_block()

    def toggle_word_wrap(self):
        current_mode = self.editor.lineWrapMode()
        new_mode = QPlainTextEdit.NoWrap if current_mode == QPlainTextEdit.WidgetWidth else QPlainTextEdit.WidgetWidth
        self.editor.setLineWrapMode(new_mode)
        self.update_status_bar()

    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)

    def undo(self):
        self.editor.undo()

    def redo(self):
        self.editor.redo()

    def cut(self):
        self.editor.cut()

    def copy(self):
        self.editor.copy()

    def paste(self):
        self.editor.paste()

    def selectAll(self):
        self.editor.selectAll()

    def select_all(self):
        self.editor.selectAll()

    def textCursor(self):
        return self.editor.textCursor()

    def setTextCursor(self, cursor):
        self.editor.setTextCursor(cursor)

    def document(self):
        return self.editor.document()

    def setFocus(self, reason=Qt.OtherFocusReason):
        self.editor.setFocus(reason)
    
    def format_entire_file(self):
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.format_entire_file()

    def format_selection(self):
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.format_selection()

    def action_goto_definition(self):
        return self.editor.action_goto_definition()

    def action_find_references(self):
        return self.editor.action_find_references()

    def action_goto_openapi(self):
        return self.editor.action_goto_openapi()

    def action_show_call_hierarchy(self):
        return self.editor.action_show_call_hierarchy()

    def generate_docstring_current(self):
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.generate_docstring_current()

    def generate_docstrings_entire_file(self):
        if hasattr(self, 'code_lens') and self.code_lens:
            self.code_lens.generate_docstrings_entire_file()

    def _zoom_in(self):
        """Увеличение масштаба"""
        self.editor._zoom_in()

    def _zoom_out(self):
        """Уменьшение масштаба"""
        self.editor._zoom_out()

    def _reset_zoom(self):
        """Сброс масштаба"""
        self.editor._reset_zoom()

    def start_busy_indicator(self, message: str = "Выполняется операция..."):
        """Показ анимации и текста статуса в центре строки редактора"""
        if hasattr(self, 'editor_spinner') and self.editor_spinner:
            self.editor_spinner.show()
            self.editor_spinner.start()
        if hasattr(self, 'center_status_label') and self.center_status_label:
            self.center_status_label.setText(message)
            self.center_status_label.setStyleSheet("color: #00F2FE;  font-size: 11px; font-weight: 500;")
        self._animate_status_strip(active=True)

    def stop_busy_indicator(self, ready_message: str = "Готово"):
        """Остановка анимации и показ сообщения готовности в центре строки редактора"""
        if hasattr(self, 'editor_spinner') and self.editor_spinner:
            self.editor_spinner.stop()
            self.editor_spinner.hide()
        if hasattr(self, 'center_status_label') and self.center_status_label:
            self.center_status_label.setText(ready_message)
            self.center_status_label.setStyleSheet("color: #38E1FF;  font-size: 11px; font-weight: 500;")
        self._animate_status_strip(active=False)

    def _animate_status_strip(self, active: bool):
        """Мягкое появление / затухание полосы статуса редактора."""
        label = getattr(self, 'center_status_label', None)
        if label is None:
            return
        try:
            from widgets.animations import fade_in, fade_out, DURATION
        except Exception:
            return
        if active:
            fade_in(label, duration=DURATION["fast"])
        else:
            fade_out(label, duration=DURATION["slow"])

    def flash_status(self, color: str = "#00F2FE"):
        """Подсветка нижней строки статуса при сохранении/запуске."""
        try:
            from widgets.animations import flash
            frame = getattr(self, 'status_bar_frame', None)
            if frame is not None:
                flash(frame, color=color)
        except Exception:
            pass
    
    def _toggle_comment(self):
        """Комментирование / раскомментирование строк (Bash/Vim-style, как в VS Code).

        Выбранные строки обрабатываются целиком: если ВСЕ непустые строки уже
        закомментированы — комментарий снимается, иначе комментарий добавляется
        наружу отступа (с сохранением относительных отступов).
        """
        cursor = self.editor.textCursor()
        first, last = self.editor._selected_block_range()
        comment_char = getattr(self.editor.language_config, 'line_comment', '#') or '#'
        if not comment_char.strip():
            return

        doc = self.editor.document()
        block_texts = [doc.findBlockByNumber(i).text() for i in range(first, last + 1)]

        def _leading_ws(text: str) -> int:
            return len(text) - len(text.lstrip(' \t'))

        def _is_commented(text: str) -> bool:
            stripped = text.strip()
            return bool(stripped) and text.lstrip().startswith(comment_char)

        non_empty = [t for t in block_texts if t.strip()]
        all_commented = bool(non_empty) and all(_is_commented(t) for t in non_empty)

        new_texts = []
        if all_commented:
            for text in block_texts:
                indent = _leading_ws(text)
                body = text[indent:]
                if body.startswith(comment_char):
                    body = body[len(comment_char):]
                    # Убираем ровно один пробел, который добавляли при комментировании.
                    if body.startswith(' '):
                        body = body[1:]
                new_texts.append(text[:indent] + body)
        else:
            min_indent = min(
                (_leading_ws(t) for t in block_texts if t.strip()), default=0
            )
            for text in block_texts:
                if not text.strip():
                    new_texts.append(text)
                    continue
                indent = _leading_ws(text)
                rel = indent - min_indent
                body = text[indent:]
                new_texts.append(' ' * (min_indent + rel) + comment_char + ' ' + body)

        lines = self.editor._document_lines()
        lines[first:last + 1] = new_texts
        anchor_col = cursor.positionInBlock()
        had_selection = cursor.hasSelection()
        self.editor._replace_document_lines(
            lines, first, min(anchor_col, len(new_texts[0]) if new_texts else 0),
            select_blocks=(first, last) if had_selection else None,
        )
    
    def _duplicate_line(self):
        """Дублирование текущей строки/блока (VS Code semantics)."""
        self.editor._duplicate_block_down()

    def _delete_line(self):
        """Удаление текущей строки/блока."""
        self.editor._delete_block()
    
    def _start_rectangle_selection(self):
        """Начало прямоугольного выделения (обрабатывается в mousePressEvent)"""
        pass
    
    def _cancel_rectangle_selection(self):
        """Отмена прямоугольного выделения"""
        self.editor.selection_mode = SelectionMode.NORMAL
        if hasattr(self.editor, 'rectangle_selections'):
            self.editor.rectangle_selections.clear()
        self.editor.setExtraSelections([])
        self.rectangleSelectionActive.emit(False)
        self.update_status_bar()
    
    def _copy_rectangle(self):
        """Копирование прямоугольного выделения"""
        self.editor.copy_rectangle_selection()
    
    def _cut_rectangle(self):
        """Вырезание прямоугольного выделения"""
        self.editor.cut_rectangle_selection()
    
    def _paste_rectangle(self):
        """Вставка в прямоугольное выделение"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and self.editor.selection_mode == SelectionMode.RECTANGLE:
            self.editor.insert_text_in_rectangle(text)
    
    def _delete_rectangle(self):
        """Удаление прямоугольного выделения"""
        self.editor.delete_rectangle_selection()
    
    def set_file_path(self, file_path: str):
        """Установка пути к файлу и автоматическое определение языка"""
        self.file_path = Path(file_path)
        
        file_extension = self.file_path.suffix.lower()
        if file_extension:
            file_extension = file_extension[1:]
            
        if file_extension and file_extension != self.language:
            self.set_language_by_extension(file_extension)

        try:
            from core.code_analysis.service import UnifiedCodeAnalysisService
            UnifiedCodeAnalysisService.get_instance().on_document_opened(str(self.file_path), self.get_code())
        except Exception:
            pass
    
    def set_language_by_extension(self, extension: str):
        """Установка языка по расширению файла"""
        provider = LanguageProviderFactory.get_provider_by_extension(extension)
        if provider:
            self.set_language(extension.lstrip("."))
    
    def set_language(self, language: str):
        """Явная установка языка"""
        self.language = language
        self.editor.set_language(language)
    
    def get_file_path(self) -> Optional[Path]:
        return self.file_path

    def get_file_name(self) -> str:
        return self.file_path.name if self.file_path else "Untitled"

    def save_file(self) -> bool:
        try:
            if not self.file_path:
                return False
            # Never overwrite a binary file with UTF-8 text.
            suffix = self.file_path.suffix.lower()
            if suffix in {".bin", ".exe", ".out", ".dll", ".so", ".dylib",
                          ".elf", ".hex", ".rom", ".img", ".iso", ".dat"}:
                return False
            self.file_path.write_text(self.get_code(), encoding="utf-8", newline="")
            record_action("file_saved")
            if hasattr(self.editor, "document") and self.editor.document():
                self.editor.document().setModified(False)
            try:
                from core.code_analysis.service import UnifiedCodeAnalysisService
                UnifiedCodeAnalysisService.get_instance().on_document_saved(str(self.file_path))
            except Exception:
                pass
            return True
        except Exception as e:
            logger.exception("Save error")
            return False

    def save_file_as(self, file_path: str) -> bool:
        try:
            self.set_file_path(file_path)
            return self.save_file()
        except Exception as e:
            logger.exception("Save as error")
            return False
    
    def get_code(self) -> str:
        return self.editor.toPlainText()
    
    def set_code(self, code: str):
        self.editor.setPlainText(code)
        # The editor already types with the configured font, so re-formatting
        # the whole document is only needed when the sizes are out of sync.
        # Doing it unconditionally cost ~200 ms per opened file (the whole
        # document is selected and merged into a new char format) and that
        # freeze was visible as stalled animations on every tab open.
        current_size = self.editor.font().pointSize()
        if current_size <= 0:
            current_size = self.editor.font().pixelSize()
        desired = int(self.settings.get("editor_font_size",
                                        self.settings.get("fontsize", 13)) or 13)
        if current_size <= 0:
            current_size = desired
        if current_size != desired:
            self.editor._apply_font_size(desired)
        if hasattr(self.editor, "document") and self.editor.document():
            self.editor.document().setModified(False)

    def is_modified(self) -> bool:
        if hasattr(self.editor, "document") and self.editor.document():
            return self.editor.document().isModified()
        return False



logger = get_logger("QCodeEditor")
