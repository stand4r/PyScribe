import ast
import re
import json
import subprocess
from os import remove
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint, QTimer, QProcess, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence, QTextCharFormat, QPainter, QPen, QLinearGradient
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QTextEdit


class Language(Enum):
    PYTHON = "py"
    CPP = "cpp"
    C = "c"
    JAVA = "java"
    JAVASCRIPT = "js"
    TYPESCRIPT = "ts"
    KOTLIN = "kt"
    PHP = "php"
    CSHARP = "cs"
    RUBY = "rb"
    GO = "go"
    LUA = "lua"
    RUST = "rs"
    HTML = "html"
    CSS = "css"


@dataclass
class SyntaxRule:
    pattern: str
    color: str
    weight: int = QFont.Normal
    italic: bool = False


@dataclass
class LanguageConfig:
    keywords: List[str]
    syntax_rules: List[SyntaxRule]
    auto_indent: bool = True
    brace_auto_close: bool = True
    line_comment: str = "//"
    block_comment_start: str = "/*"
    block_comment_end: str = "*/"


class SyntaxHighlighterFactory:
    """Фабрика для создания конфигураций подсветки синтаксиса"""
    
    @staticmethod
    def create_config(language: Language) -> LanguageConfig:
        keywords = KEYWORDS.get(language.value, [])
        syntax_rules = []
        
        # Базовые правила для всех языков
        base_rules = [
            (r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),  # Строки в двойных кавычках
            (r"'[^'\\]*(\\.[^'\\]*)*'", "#CE9178"),  # Строки в одинарных кавычках
            (r'\b(true|false|null)\b', "#569CD6"),  # Булевы значения и null
            (r'\b\d+\.?\d*([eE][+-]?\d+)?\b', "#B5CEA8"),  # Числа
            (r'\b0x[0-9a-fA-F]+\b', "#B5CEA8"),  # Шестнадцатеричные числа
        ]
        
        # Добавляем операторы
        operators = ['=', '==', '!=', '<', '<=', '>', '>=', '\+', '-', '\*', '/', '//', '\%', '\*\*', 
                    '\+=', '-=', '\*=', '/=', '\%=', '\+\+', '--', '&&', '\|\|', '!', '&', '\|', '\^', '~', '<<', '>>']
        
        for op in operators:
            base_rules.append((rf"\s*{op}\s*", "#D4D4D4"))
        
        # Добавляем ключевые слова
        for keyword in keywords:
            base_rules.append((rf"\b{keyword}\b", "#569CD6"))
        
        # Языко-специфичные правила
        if language == Language.PYTHON:
            base_rules.extend([
                (r'\b(class|def)\s+(\w+)', "#D7BA7D", QFont.Normal, False),  # Классы и функции
                (r'\b(self|cls)\b', "#569CD6"),  # Self/cls в Python
                (r'@\w+\b', "#D7BA7D"),  # Декораторы
                (r'#.*$', "#6A9955"),  # Комментарии Python
            ])
        elif language in [Language.C, Language.CPP]:
            base_rules.extend([
                (r'#include\s*<[^>]+>', "#569CD6"),  # Инклюды
                (r'#\w+', "#569CD6"),  # Директивы препроцессора
                (r'\b(std|main|printf|cout|cin)\b', "#DCDCAA"),  # Стандартные функции
            ])
        elif language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            base_rules.extend([
                (r'\b(function|var|let|const)\b', "#569CD6"),  # Объявления
                (r'\b(console|document|window)\b', "#4EC9B0"),  # Глобальные объекты
                (r'\b(export|import|from|default)\b', "#569CD6"),  # Модули
            ])
        elif language == Language.HTML:
            base_rules.extend([
                (r'<\/?[^>]+>', "#569CD6"),  # HTML теги
                (r'\b(src|href|class|id|style)\b', "#9CDCFE"),  # Атрибуты
            ])
        elif language == Language.CSS:
            base_rules.extend([
                (r'\.[\w-]+\b', "#D7BA7D"),  # CSS классы
                (r'#[\w-]+\b', "#D7BA7D"),  # CSS ID
                (r'\b[\w-]+\s*:', "#9CDCFE"),  # CSS свойства
            ])
        
        # Конвертируем в SyntaxRule
        for rule in base_rules:
            if len(rule) == 2:
                pattern, color = rule
                syntax_rules.append(SyntaxRule(pattern, color))
            elif len(rule) == 4:
                pattern, color, weight, italic = rule
                syntax_rules.append(SyntaxRule(pattern, color, weight, italic))
        
        # Определяем символы комментариев для языка
        line_comment = "//"
        block_comment_start = "/*"
        block_comment_end = "*/"
        
        if language == Language.PYTHON:
            line_comment = "#"
            block_comment_start = '"""'
            block_comment_end = '"""'
        
        return LanguageConfig(
            keywords=keywords,
            syntax_rules=syntax_rules,
            auto_indent=language in [Language.PYTHON, Language.C, Language.CPP, Language.JAVA, Language.JAVASCRIPT, Language.TYPESCRIPT],
            brace_auto_close=True,
            line_comment=line_comment,
            block_comment_start=block_comment_start,
            block_comment_end=block_comment_end
        )


# Глобальные константы
KEYWORDS = {
    "py": [
        "False", "None", "True", "and", "as", "assert", "async", "await", "break", 
        "class", "continue", "def", "del", "elif", "else", "except", "finally", 
        "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", 
        "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"
    ],
    "cpp": [
        "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit",
        "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch",
        "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const",
        "consteval", "constexpr", "const_cast", "continue", "co_await", "co_return",
        "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast",
        "else", "enum", "explicit", "export", "extern", "false", "float", "for", "friend",
        "goto", "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept",
        "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected",
        "public", "reflexpr", "register", "reinterpret_cast", "requires", "return",
        "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct",
        "switch", "synchronized", "template", "this", "thread_local", "throw", "true",
        "try", "typedef", "typeid", "typename", "union", "unsigned", "using", "virtual",
        "void", "volatile", "wchar_t", "while", "xor", "xor_eq"
    ],
    "js": [
        "abstract", "arguments", "await", "boolean", "break", "byte", "case", "catch",
        "char", "class", "const", "continue", "debugger", "default", "delete", "do",
        "double", "else", "enum", "eval", "export", "extends", "false", "final",
        "finally", "float", "for", "function", "goto", "if", "implements", "import",
        "in", "instanceof", "int", "interface", "let", "long", "native", "new",
        "null", "package", "private", "protected", "public", "return", "short",
        "static", "super", "switch", "synchronized", "this", "throw", "throws",
        "transient", "true", "try", "typeof", "var", "void", "volatile", "while",
        "with", "yield"
    ],
    "java": [
        "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
        "class", "const", "continue", "default", "do", "double", "else", "enum",
        "extends", "final", "finally", "float", "for", "goto", "if", "implements",
        "import", "instanceof", "int", "interface", "long", "native", "new",
        "package", "private", "protected", "public", "return", "short", "static",
        "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
        "transient", "try", "void", "volatile", "while"
    ]
}


class ModernSyntaxHighlighter(QSyntaxHighlighter):
    """Современный подсветчик синтаксиса с улучшенной производительностью"""
    # Кэш для форматирования
    _format_cache = {}

    def __init__(self, document, language_config: LanguageConfig):
        super().__init__(document)
        self.language_config = language_config
        self._rules = self._compile_rules()        
    
    def _compile_rules(self) -> List[Tuple[QRegExp, QTextCharFormat]]:
        rules = []
        
        # Компилируем правила с кэшированием форматов
        for rule in self.language_config.syntax_rules:
            regex = QRegExp(rule.pattern)
            fmt = self._get_cached_format(rule.color, rule.weight, rule.italic)
            rules.append((regex, fmt))
        
        return rules
    
    def _get_cached_format(self, color: str, weight: int = QFont.Normal, italic: bool = False) -> QTextCharFormat:
        cache_key = f"{color}_{weight}_{italic}"
        
        if cache_key not in self._format_cache:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(weight)
            fmt.setFontItalic(italic)
            self._format_cache[cache_key] = fmt
        
        return self._format_cache[cache_key]
    
    def highlightBlock(self, text: str):
        for regex, fmt in self._rules:
            index = regex.indexIn(text)
            while index >= 0:
                length = regex.matchedLength()
                self.setFormat(index, length, fmt)
                index = regex.indexIn(text, index + length)


class CodeAnalyzer:
    """Анализатор кода с улучшенной поддержкой языков"""
    
    def __init__(self, language: str):
        self.language = language
        self.defined_names: Set[str] = set(KEYWORDS.get(language, []))
    
    def analyze_code(self, code: str):
        try:
            if self.language == "py":
                self._analyze_python(code)
            elif self.language in ["c", "cpp"]:
                self._analyze_c_cpp(code)
            elif self.language == "java":
                self._analyze_java(code)
            elif self.language in ["js", "ts"]:
                self._analyze_javascript(code)
            else:
                self._analyze_generic(code)
        except Exception as e:
            print(f"Code analysis error: {e}")
    
    def _analyze_python(self, code: str):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    self.defined_names.add(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.defined_names.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.defined_names.add(node.module.split(".")[0])
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    self.defined_names.add(node.id)
        except SyntaxError:
            # Fallback to regex for invalid syntax
            self._analyze_with_regex(code, r'def\s+(\w+)\s*\(')
            self._analyze_with_regex(code, r'class\s+(\w+)')
            self._analyze_with_regex(code, r'(\w+)\s*=')
    
    def _analyze_c_cpp(self, code: str):
        self._analyze_with_regex(code, r'(\w+)\s*\([^)]*\)\s*\{')  # Functions
        self._analyze_with_regex(code, r'\b(\w+)\s*=\s*[^;]+;')  # Variables
        self._analyze_with_regex(code, r'class\s+(\w+)')  # Classes
        self._analyze_with_regex(code, r'struct\s+(\w+)')  # Structs
    
    def _analyze_java(self, code: str):
        self._analyze_with_regex(code, r'(public|private|protected)\s+\w+\s+(\w+)\s*\(')
        self._analyze_with_regex(code, r'class\s+(\w+)')
        self._analyze_with_regex(code, r'interface\s+(\w+)')
    
    def _analyze_javascript(self, code: str):
        self._analyze_with_regex(code, r'function\s+(\w+)\s*\(')
        self._analyze_with_regex(code, r'const\s+(\w+)\s*=')
        self._analyze_with_regex(code, r'let\s+(\w+)\s*=')
        self._analyze_with_regex(code, r'var\s+(\w+)\s*=')
        self._analyze_with_regex(code, r'class\s+(\w+)')
    
    def _analyze_generic(self, code: str):
        self._analyze_with_regex(code, r'function\s+(\w+)\s*\(')
        self._analyze_with_regex(code, r'def\s+(\w+)\s*\(')
        self._analyze_with_regex(code, r'class\s+(\w+)')
        self._analyze_with_regex(code, r'(\w+)\s*=')
    
    def _analyze_with_regex(self, code: str, pattern: str):
        matches = re.findall(pattern, code)
        for match in matches:
            if isinstance(match, tuple):
                self.defined_names.update(m for m in match if m and m.isidentifier())
            elif match and match.isidentifier():
                self.defined_names.add(match)
    
    def get_completion_list(self) -> List[str]:
        return sorted(self.defined_names)


class SmartCompleter(QCompleter):
    """Умный комплитер с кастомным отображением и анимациями"""
    
    insertText = pyqtSignal(str)
    
    def __init__(self, word_list: List[str], background_color: str, font_size: int, parent=None):
        super().__init__(word_list, parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterMode(Qt.MatchContains)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setMaxVisibleItems(8)
        
        # Настройка анимации
        self.animation = QPropertyAnimation(self.popup(), b"geometry")
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Стилизация попапа в стиле VS Code
        popup = self.popup()
        popup.setStyleSheet(f"""
            QListView {{
                background-color: {background_color};
                color: #D4D4D4;
                font-size: {font_size}pt;
                font-family: 'Segoe UI', 'Consolas', monospace;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                outline: none;
                padding: 4px 0px;
            }}
            QListView::item {{
                padding: 4px 12px;
                border: none;
                background-color: transparent;
            }}
            QListView::item:selected {{
                background-color: #094771;
                color: #FFFFFF;
                border: none;
            }}
            QListView::item:hover {{
                background-color: #2A2D2E;
            }}
        """)
        
        # Устанавливаем фиксированную ширину
        popup.setFixedWidth(300)
    
    def update_completions(self, word_list: List[str]):
        model = QStringListModel()
        model.setStringList(word_list)
        self.setModel(model)
    
    def complete(self, rect):
        # Анимированное появление
        popup = self.popup()
        start_rect = QRect(rect.x(), rect.y(), 0, 0)
        end_rect = QRect(rect.x(), rect.bottom() + 2, 300, 
                        min(self.maxVisibleItems() * popup.sizeHintForRow(0) + 10, 200))
        
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        super().complete(rect)
        self.animation.start()


class LineNumberArea(QWidget):
    """Область для отображения номеров строк с современным дизайном"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        
        # Анимация hover эффекта
        self.hover_animation = QPropertyAnimation(self, b"")
        self.hover_animation.setDuration(200)

    def line_number_area_width(self):
        """Вычисление ширины области номеров строк"""
        digits = len(str(max(1, self.blockCount())))
        space = 20 + self.fontMetrics().horizontalAdvance('9') * digits  # Исправление: horizontalAdvance вместо width
        return space
        
    def sizeHint(self):
        return QSize(self.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Основной редактор кода с расширенными функциями и анимациями"""
    
    # Сигналы
    textChangedAnimated = pyqtSignal()
    focusChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None, language: str = "", settings: dict = None):
        super().__init__(parent)
        self.settings = settings or {}
        self.language = language
        try:
            self.language_config = SyntaxHighlighterFactory.create_config(Language(language))
        except:
            # Fallback to Python if language not supported
            self.language_config = SyntaxHighlighterFactory.create_config(Language.PYTHON)
        
        self._setup_editor()
        self._setup_autocomplete()
        self._setup_line_numbers()
        
        # Анимации
        self.cursor_animation = QPropertyAnimation(self, b"")
        self.cursor_animation.setDuration(600)
        self.cursor_animation.setLoopCount(-1)
        
        # Таймер для отложенных операций
        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(self._delayed_analysis)
        
    def _setup_editor(self):
        """Настройка базовых параметров редактора"""
        font_size = int(self.settings.get("fontsize", 12))
        bg_color = self.settings.get("second_color", "#1E1E1E")
        text_color = self.settings.get("text_color", "#D4D4D4")
        
        # Устанавливаем современный шрифт
        font = QFont("Cascadia Code", font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        
        # Современный стиль в духе VS Code
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_color};
                color: {text_color};
                padding: 10px 0px;
                border: none;
                selection-background-color: #264F78;
                selection-color: #FFFFFF;
                font-family: 'Cascadia Code', 'Consolas', monospace;
            }}
            QPlainTextEdit:focus {{
                border: none;
                outline: none;
            }}
        """)
        
        self.tab_width = 4
        self.setTabStopDistance(self.tab_width * self.fontMetrics().width(' '))
        
        # Подсветка синтаксиса
        self.highlighter = ModernSyntaxHighlighter(
            self.document(), 
            self.language_config
        )
        
        # Включаем плавный скроллинг
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    
    def _setup_line_numbers(self):
        """Настройка области номеров строк"""
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        
        self.update_line_number_area_width()
        self.highlight_current_line()
    
    def _setup_autocomplete(self):
        """Настройка системы автодополнения"""
        self.analyzer = CodeAnalyzer(self.language)
        self.completer = SmartCompleter(
            [], 
            self.settings.get("second_color", "#1E1E1E"),
            int(self.settings.get("fontsize", 10))
        )
        self.completer.setWidget(self)
        self.completer.insertText.connect(self._insert_completion)
        
        # Таймер для отложенного автодополнения
        self.completion_timer = QTimer()
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self._trigger_completion)
    
    def line_number_area_width(self):
        """Вычисление ширины области номеров строк"""
        digits = len(str(max(1, self.blockCount())))
        space = 20 + self.fontMetrics().width('9') * digits
        return space
    
    def update_line_number_area_width(self):
        """Обновление ширины области номеров строк"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
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
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), 
                                              self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """Отрисовка номеров строк"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1E1E1E"))
        
        # Градиент для разделительной линии
        gradient = QLinearGradient(0, 0, self.line_number_area.width(), 0)
        gradient.setColorAt(0, QColor("#1E1E1E"))
        gradient.setColorAt(1, QColor("#2D3139"))
        painter.fillRect(QRect(self.line_number_area.width() - 2, 0, 2, self.height()), gradient)
        
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
                
                # Подсветка текущей строки
                if block_number + 1 == current_line:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.setFont(QFont("Cascadia Code", self.font().pointSize(), QFont.Bold))
                else:
                    painter.setPen(QColor("#6E7681"))
                    painter.setFont(self.font())
                
                # Исправление: правильное позиционирование текста
                painter.drawText(0, int(top), self.line_number_area.width() - 8, 
                            int(line_height),
                            Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        """Подсветка текущей строки"""
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
        
        self.setExtraSelections(extra_selections)
    
    def _insert_completion(self, completion: str):
        """Вставка выбранного автодополнения"""
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
    
    def _trigger_completion(self):
        """Активация автодополнения"""
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        prefix = tc.selectedText()
        
        if len(prefix) >= 1:  # Уменьшил минимальную длину для лучшего UX
            # Обновляем список автодополнений
            self.analyzer.analyze_code(self.toPlainText())
            self.completer.update_completions(self.analyzer.get_completion_list())
            
            self.completer.setCompletionPrefix(prefix)
            if self.completer.completionCount() > 0:
                self.completer.complete(self.cursorRect())
    
    def _delayed_analysis(self):
        """Отложенный анализ кода для производительности"""
        self.analyzer.analyze_code(self.toPlainText())
    
    def keyPressEvent(self, event):
        """Обработка нажатий клавиш с улучшенной логикой"""
        # Автодополнение
        if event.text() and not event.text().isspace():
            self.completion_timer.start(200)  # Уменьшил задержку для лучшего UX
        
        # Умное закрытие скобок
        if self.language_config.brace_auto_close:
            if self._handle_auto_closure(event):
                return
        
        # Умные отступы
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._handle_smart_indent()
            return
        
        # Комбинации клавиш для комплитера
        if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return) and self.completer.popup().isVisible():
            self.completer.popup().hide()
            if event.key() in (Qt.Key_Enter, Qt.Key_Return):
                return
        
        super().keyPressEvent(event)
        
        # Запускаем отложенный анализ
        self.analysis_timer.start(500)
    
    def _handle_auto_closure(self, event):
        """Автоматическое закрытие скобок и кавычек"""
        closure_map = {
            '"': '"', "'": "'", '(': ')', '[': ']', '{': '}'
        }
        
        if event.text() in closure_map:
            cursor = self.textCursor()
            cursor.insertText(event.text() + closure_map[event.text()])
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return True
        return False
    
    def _handle_smart_indent(self):
        """Умное добавление отступов"""
        cursor = self.textCursor()
        current_block = cursor.block()
        previous_text = current_block.previous().text()
        
        # Вычисляем базовый отступ
        indent = len(previous_text) - len(previous_text.lstrip())
        base_indent = ' ' * indent
        
        # Добавляем дополнительный отступ для определенных конструкций
        if self.language_config.auto_indent:
            if any(previous_text.strip().endswith(keyword) for keyword in [':', '{', '=>']):
                base_indent += ' ' * self.tab_width
        
        # Вставляем новую строку с отступом
        cursor.insertText('\n' + base_indent)


class ModernCodeEditor(QWidget):
    """Современный редактор кода с нумерацией строк и дополнительными функциями"""
    
    def __init__(self, parent=None, language: str = "", settings: dict = None):
        super().__init__(parent)
        self.language = language
        self.settings = settings or {}
        self.file_path = None
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_animations()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Основной редактор
        self.editor = CodeEditor(language=self.language, settings=self.settings)
        
        layout.addWidget(self.editor)
    
    def _setup_shortcuts(self):
        """Настройка горячих клавиш"""
        shortcuts = {
            "Ctrl+=": self._zoom_in,
            "Ctrl+-": self._zoom_out,
            "Ctrl+0": self._reset_zoom,
            "Ctrl+/": self._toggle_comment,
            "Ctrl+D": self._duplicate_line,
            "Ctrl+Shift+K": self._delete_line,
        }
        
        for key_sequence, callback in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.activated.connect(callback)
    
    def _setup_animations(self):
        """Настройка анимаций"""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.start()
    
    def _zoom_in(self):
        """Увеличение масштаба с анимацией"""
        font = self.editor.font()
        current_size = font.pointSize()
        
        if current_size < 30:
            font.setPointSize(current_size + 1)
            self.editor.setFont(font)
    
    def _zoom_out(self):
        """Уменьшение масштаба с анимацией"""
        font = self.editor.font()
        current_size = font.pointSize()
        
        if current_size > 6:
            font.setPointSize(current_size - 1)
            self.editor.setFont(font)
    
    def _reset_zoom(self):
        """Сброс масштаба к стандартному"""
        default_size = int(self.settings.get("fontsize", 14))
        font = QFont("Cascadia Code", default_size)
        self.editor.setFont(font)
    
    def _toggle_comment(self):
        """Комментирование/раскомментирование кода"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            cursor.setPosition(start)
            cursor.beginEditBlock()
            
            # Получаем символ комментария для текущего языка
            comment_char = self.editor.language_config.line_comment
            
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfLine)
            
            lines_commented = 0
            while cursor.position() < end:
                cursor_text = cursor.block().text()
                
                # Проверяем, комментирована ли уже строка
                if cursor_text.lstrip().startswith(comment_char):
                    # Раскомментировать
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 
                                      len(cursor_text) - len(cursor_text.lstrip()))
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(comment_char))
                    cursor.removeSelectedText()
                else:
                    # Закомментировать
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.insertText(comment_char + " ")
                
                lines_commented += 1
                if not cursor.movePosition(QTextCursor.Down):
                    break
            
            cursor.endEditBlock()
        else:
            # Комментирование одной строки
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor_text = cursor.block().text()
            comment_char = self.editor.language_config.line_comment
            
            if cursor_text.lstrip().startswith(comment_char):
                # Раскомментировать
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 
                                  len(cursor_text) - len(cursor_text.lstrip()))
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(comment_char))
                cursor.removeSelectedText()
            else:
                # Закомментировать
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.insertText(comment_char + " ")
    
    def _duplicate_line(self):
        """Дублирование текущей строки"""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        text = cursor.selectedText()
        
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.insertText("\n" + text)
    
    def _delete_line(self):
        """Удаление текущей строки"""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        cursor.removeSelectedText()
    
    def set_file_path(self, file_path: str):
        """Установка пути к файлу и обновление языка на основе расширения"""
        self.file_path = Path(file_path)
        
        # Автоматически определяем язык по расширению файла
        file_extension = self.file_path.suffix.lower()
        if file_extension:  # Убираем точку если есть
            file_extension = file_extension[1:]
            
        # Обновляем язык редактора если расширение изменилось
        if file_extension and file_extension != self.language:
            self.set_language(file_extension)
    
    def get_file_path(self) -> Optional[Path]:
        """Получение пути к файлу"""
        return self.file_path

    def get_file_name(self) -> str:
        """Получение имени файла"""
        return self.file_path.name if self.file_path else "Untitled"

    def save_file(self) -> bool:
        """Сохранение файла"""
        try:
            if self.file_path:
                self.file_path.write_text(self.get_code(), encoding='utf-8')
                return True
            return False
        except Exception as e:
            print(f"Save error: {e}")
            return False

    def save_file_as(self, file_path: str) -> bool:
        """Сохранение файла под новым именем"""
        try:
            self.set_file_path(file_path)
            return self.save_file()
        except Exception as e:
            print(f"Save as error: {e}")
            return False
    
    def get_code(self) -> str:
        """Получение кода из редактора"""
        return self.editor.toPlainText()
    
    def set_code(self, code: str):
        """Установка кода в редактор"""
        self.editor.setPlainText(code)
    
    def set_language(self, language: str):
        """Изменение языка программирования"""
        self.language = language
        try:
            self.editor.language_config = SyntaxHighlighterFactory.create_config(Language(language))
            self.editor.analyzer = CodeAnalyzer(language)
            self.editor.highlighter = ModernSyntaxHighlighter(
                self.editor.document(), 
                self.editor.language_config
            )
            # Перезапускаем анализ кода для нового языка
            self.editor.analyzer.analyze_code(self.get_code())
        except Exception as e:
            print(f"Error setting language {language}: {e}")
            # Fallback to Python if language not supported
            try:
                self.editor.language_config = SyntaxHighlighterFactory.create_config(Language.PYTHON)
            except:
                pass


# Пример использования
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # Настройки в стиле VS Code
    settings = {
        "fontsize": 14,
        "text_color": "#D4D4D4",
        "second_color": "#1E1E1E",
        "accent_color": "#007ACC"
    }
    
    # Создаем редактор с примером кода
    editor = ModernCodeEditor(language="py", settings=settings)
    
    example_code = '''# Пример Python кода с современной подсветкой
class Calculator:
    """Простой калькулятор с базовыми операциями"""
    
    def __init__(self):
        self.result = 0
    
    def add(self, x: float, y: float) -> float:
        """Сложение двух чисел"""
        self.result = x + y
        return self.result
    
    def multiply(self, x: float, y: float) -> float:
        """Умножение двух чисел"""
        self.result = x * y
        return self.result

def main():
    calc = Calculator()
    print(f"2 + 3 = {calc.add(2, 3)}")
    print(f"4 * 5 = {calc.multiply(4, 5)}")

if __name__ == "__main__":
    main()
'''
    
    editor.set_code(example_code)
    editor.setWindowTitle("Modern Code Editor - VS Code Style")
    editor.resize(800, 600)
    editor.show()
    
    sys.exit(app.exec_())