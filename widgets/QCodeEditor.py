import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence, QTextCharFormat, QPainter, QPen, QLinearGradient
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QTextEdit


class Language(Enum):
    PYTHON = "py"
    JAVASCRIPT = "js"
    TYPESCRIPT = "ts"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    CSHARP = "cs"
    PHP = "php"
    RUBY = "rb"
    GO = "go"
    RUST = "rs"
    KOTLIN = "kt"
    SWIFT = "swift"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    MARKDOWN = "md"
    DOCKERFILE = "dockerfile"
    BASH = "sh"
    PLAINTEXT = "txt"


@dataclass
class SyntaxRule:
    pattern: str
    color: str
    weight: int = QFont.Normal
    italic: bool = False


@dataclass
class LanguageConfig:
    name: str
    extensions: List[str]
    keywords: List[str]
    syntax_rules: List[SyntaxRule]
    auto_indent: bool = True
    brace_auto_close: bool = True
    line_comment: str = "//"
    block_comment_start: str = "/*"
    block_comment_end: str = "*/"
    string_delimiters: List[str] = None
    
    def __post_init__(self):
        if self.string_delimiters is None:
            self.string_delimiters = ['"', "'"]


class LanguageProvider(ABC):
    """Абстрактный базовый класс для провайдеров языков"""
    
    @abstractmethod
    def get_config(self) -> LanguageConfig:
        pass
    
    @abstractmethod
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        pass
    
    @abstractmethod
    def get_completion_items(self, code: str) -> List[str]:
        pass


class PythonLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await", "break", 
            "class", "continue", "def", "del", "elif", "else", "except", "finally", 
            "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", 
            "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"
        ]
        
        syntax_rules = [
            SyntaxRule(r'#.*$', "#6A9955"),  # Комментарии
            SyntaxRule(r'\b(class|def)\s+(\w+)', "#D7BA7D", QFont.Normal, False),
            SyntaxRule(r'\b(self|cls)\b', "#569CD6"),
            SyntaxRule(r'@\w+\b', "#D7BA7D"),  # Декораторы
            SyntaxRule(r'\b(None|True|False)\b', "#569CD6"),
            SyntaxRule(r'\b\d+\.?\d*([eE][+-]?\d+)?\b', "#B5CEA8"),  # Числа
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),  # Строки
            SyntaxRule(r"'[^'\\]*(\\.[^'\\]*)*'", "#CE9178"),
        ]
        
        return LanguageConfig(
            name="Python",
            extensions=["py", "pyw"],
            keywords=keywords,
            syntax_rules=syntax_rules,
            line_comment="#",
            block_comment_start='"""',
            block_comment_end='"""'
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    analyzer.add_defined_name(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analyzer.add_defined_name(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analyzer.add_defined_name(node.module.split(".")[0])
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    analyzer.add_defined_name(node.id)
        except SyntaxError:
            self._analyze_with_regex(code, analyzer)
    
    def _analyze_with_regex(self, code: str, analyzer: 'CodeAnalyzer'):
        patterns = [
            r'def\s+(\w+)\s*\(',
            r'class\s+(\w+)',
            r'(\w+)\s*=',
            r'from\s+(\w+)',
            r'import\s+(\w+)'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                if isinstance(match, tuple):
                    for m in match:
                        if m and m.isidentifier():
                            analyzer.add_defined_name(m)
                elif match and match.isidentifier():
                    analyzer.add_defined_name(match)
    
    def get_completion_items(self, code: str) -> List[str]:
        return []  # Можно расширить специфичными для Python completion items


class JavaScriptLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        keywords = [
            "abstract", "arguments", "await", "boolean", "break", "byte", "case", "catch",
            "char", "class", "const", "continue", "debugger", "default", "delete", "do",
            "double", "else", "enum", "eval", "export", "extends", "false", "final",
            "finally", "float", "for", "function", "goto", "if", "implements", "import",
            "in", "instanceof", "int", "interface", "let", "long", "native", "new",
            "null", "package", "private", "protected", "public", "return", "short",
            "static", "super", "switch", "synchronized", "this", "throw", "throws",
            "transient", "true", "try", "typeof", "var", "void", "volatile", "while",
            "with", "yield"
        ]
        
        syntax_rules = [
            SyntaxRule(r'//.*$', "#6A9955"),  # Комментарии
            SyntaxRule(r'/\*[\s\S]*?\*/', "#6A9955"),  # Блочные комментарии
            SyntaxRule(r'\b(function|class|const|let|var)\b', "#569CD6"),
            SyntaxRule(r'\b(console|document|window|this)\b', "#4EC9B0"),
            SyntaxRule(r'\b(export|import|from|default)\b', "#569CD6"),
            SyntaxRule(r'\b(true|false|null|undefined)\b', "#569CD6"),
            SyntaxRule(r'\b\d+\.?\d*([eE][+-]?\d+)?\b', "#B5CEA8"),
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),
            SyntaxRule(r"'[^'\\]*(\\.[^'\\]*)*'", "#CE9178"),
            SyntaxRule(r'`[^`\\]*(\\.[^`\\]*)*`', "#CE9178"),  # Template literals
        ]
        
        return LanguageConfig(
            name="JavaScript",
            extensions=["js", "jsx"],
            keywords=keywords,
            syntax_rules=syntax_rules
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'class\s+(\w+)',
            r'const\s+(\w+)\s*=',
            r'let\s+(\w+)\s*=',
            r'var\s+(\w+)\s*=',
            r'(\w+)\s*:\s*function'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                if match and match.isidentifier():
                    analyzer.add_defined_name(match)
    
    def get_completion_items(self, code: str) -> List[str]:
        return ["console", "document", "window", "alert", "fetch"]


class HTMLLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        syntax_rules = [
            SyntaxRule(r'<!--.*?-->', "#6A9955"),  # Комментарии
            SyntaxRule(r'<\/?[^>]+>', "#569CD6"),  # HTML теги
            SyntaxRule(r'\b(src|href|class|id|style|alt|title)\b', "#9CDCFE"),  # Атрибуты
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),
            SyntaxRule(r"'[^'\\]*(\\.[^'\\]*)*'", "#CE9178"),
        ]
        
        return LanguageConfig(
            name="HTML",
            extensions=["html", "htm"],
            keywords=[],
            syntax_rules=syntax_rules,
            auto_indent=False,
            brace_auto_close=False
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        # HTML не требует сложного анализа для автодополнения
        pass
    
    def get_completion_items(self, code: str) -> List[str]:
        return ["div", "span", "p", "a", "img", "script", "style"]


class CSSLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        syntax_rules = [
            SyntaxRule(r'\/\*[\s\S]*?\*\/', "#6A9955"),  # Комментарии
            SyntaxRule(r'\.[\w-]+\b', "#D7BA7D"),  # CSS классы
            SyntaxRule(r'#[\w-]+\b', "#D7BA7D"),  # CSS ID
            SyntaxRule(r'\b[\w-]+\s*:', "#9CDCFE"),  # CSS свойства
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),
        ]
        
        return LanguageConfig(
            name="CSS",
            extensions=["css"],
            keywords=[],
            syntax_rules=syntax_rules,
            auto_indent=True,
            brace_auto_close=True
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        patterns = [
            r'\.([\w-]+)\s*\{',
            r'#([\w-]+)\s*\{',
            r'@(\w+)'  # CSS directives
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                if match:
                    analyzer.add_defined_name(match)
    
    def get_completion_items(self, code: str) -> List[str]:
        return ["color", "background", "font-size", "margin", "padding"]


class JSONLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        syntax_rules = [
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"\s*:', "#9CDCFE"),  # Ключи
            SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', "#CE9178"),  # Строки
            SyntaxRule(r'\b(true|false|null)\b', "#569CD6"),
            SyntaxRule(r'\b\d+\.?\d*([eE][+-]?\d+)?\b', "#B5CEA8"),
        ]
        
        return LanguageConfig(
            name="JSON",
            extensions=["json"],
            keywords=[],
            syntax_rules=syntax_rules,
            auto_indent=True,
            brace_auto_close=True
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        try:
            data = json.loads(code)
            self._extract_keys(data, analyzer)
        except:
            pass
    
    def _extract_keys(self, data, analyzer: 'CodeAnalyzer', prefix=""):
        if isinstance(data, dict):
            for key in data.keys():
                analyzer.add_defined_name(key)
                self._extract_keys(data[key], analyzer, f"{prefix}.{key}" if prefix else key)
        elif isinstance(data, list):
            for item in data:
                self._extract_keys(item, analyzer, prefix)
    
    def get_completion_items(self, code: str) -> List[str]:
        return []  # JSON completion зависит от структуры данных


class LanguageProviderFactory:
    """Фабрика для создания и управления провайдерами языков"""
    
    _providers: Dict[str, LanguageProvider] = {}
    _extension_map: Dict[str, str] = {}
    
    @classmethod
    def register_provider(cls, language: Language, provider: LanguageProvider):
        """Регистрация провайдера для языка"""
        config = provider.get_config()
        cls._providers[language.value] = provider
        
        # Регистрируем расширения файлов
        for ext in config.extensions:
            cls._extension_map[ext] = language.value
    
    @classmethod
    def get_provider(cls, language: str) -> Optional[LanguageProvider]:
        """Получение провайдера по идентификатору языка"""
        return cls._providers.get(language)
    
    @classmethod
    def get_provider_by_extension(cls, extension: str) -> Optional[LanguageProvider]:
        """Получение провайдера по расширению файла"""
        language = cls._extension_map.get(extension.lower())
        return cls.get_provider(language) if language else None
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Получение списка поддерживаемых расширений"""
        return list(cls._extension_map.keys())
    
    @classmethod
    def get_language_config(cls, language: str) -> Optional[LanguageConfig]:
        """Получение конфигурации языка"""
        provider = cls.get_provider(language)
        return provider.get_config() if provider else None


# Регистрация провайдеров по умолчанию
LanguageProviderFactory.register_provider(Language.PYTHON, PythonLanguageProvider())
LanguageProviderFactory.register_provider(Language.JAVASCRIPT, JavaScriptLanguageProvider())
LanguageProviderFactory.register_provider(Language.HTML, HTMLLanguageProvider())
LanguageProviderFactory.register_provider(Language.CSS, CSSLanguageProvider())
LanguageProviderFactory.register_provider(Language.JSON, JSONLanguageProvider())


class CodeAnalyzer:
    """Анализатор кода с поддержкой различных языков"""
    
    def __init__(self, language: str):
        self.language = language
        self.provider = LanguageProviderFactory.get_provider(language)
        self.defined_names: Set[str] = set()
        
        # Добавляем ключевые слова языка
        if self.provider:
            config = self.provider.get_config()
            self.defined_names.update(config.keywords)
    
    def analyze_code(self, code: str):
        """Анализ кода с использованием зарегистрированного провайдера"""
        self.defined_names.clear()
        
        if self.provider:
            # Добавляем ключевые слова обратно после очистки
            config = self.provider.get_config()
            self.defined_names.update(config.keywords)
            
            # Запускаем специфичный для языка анализ
            self.provider.analyze_code(code, self)
        else:
            # Общий анализ для неподдерживаемых языков
            self._analyze_generic(code)
    
    def add_defined_name(self, name: str):
        """Добавление определенного имени в список автодополнения"""
        if name and name.isidentifier():
            self.defined_names.add(name)
    
    def _analyze_generic(self, code: str):
        """Общий анализ для неподдерживаемых языков"""
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'def\s+(\w+)\s*\(',
            r'class\s+(\w+)',
            r'(\w+)\s*='
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                if match and match.isidentifier():
                    self.add_defined_name(match)
    
    def get_completion_list(self) -> List[str]:
        """Получение списка для автодополнения"""
        completion_list = sorted(self.defined_names)
        
        # Добавляем специфичные для языка completion items
        if self.provider:
            completion_list.extend(self.provider.get_completion_items(""))
        
        return completion_list


class ModernSyntaxHighlighter(QSyntaxHighlighter):
    """Современный подсветчик синтаксиса с поддержкой различных языков"""
    
    _format_cache = {}

    def __init__(self, document, language_config: LanguageConfig):
        super().__init__(document)
        self.language_config = language_config
        self._rules = self._compile_rules()
    
    def _compile_rules(self) -> List[Tuple[QRegExp, QTextCharFormat]]:
        """Компиляция правил подсветки"""
        rules = []
        
        for rule in self.language_config.syntax_rules:
            regex = QRegExp(rule.pattern)
            fmt = self._get_cached_format(rule.color, rule.weight, rule.italic)
            rules.append((regex, fmt))
        
        return rules
    
    def _get_cached_format(self, color: str, weight: int = QFont.Normal, italic: bool = False) -> QTextCharFormat:
        """Получение кэшированного формата текста"""
        cache_key = f"{color}_{weight}_{italic}"
        
        if cache_key not in self._format_cache:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(weight)
            fmt.setFontItalic(italic)
            self._format_cache[cache_key] = fmt
        
        return self._format_cache[cache_key]
    
    def highlightBlock(self, text: str):
        """Подсветка блока текста"""
        for regex, fmt in self._rules:
            index = regex.indexIn(text)
            while index >= 0:
                length = regex.matchedLength()
                self.setFormat(index, length, fmt)
                index = regex.indexIn(text, index + length)


class SmartCompleter(QCompleter):
    """Умный комплитер с кастомным отображением"""
    
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
        
        # Стилизация попапа
        self._style_popup(background_color, font_size)
    
    def _style_popup(self, background_color: str, font_size: int):
        """Стилизация всплывающего окна"""
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
        popup.setFixedWidth(300)
    
    def update_completions(self, word_list: List[str]):
        """Обновление списка автодополнений"""
        model = QStringListModel()
        model.setStringList(word_list)
        self.setModel(model)
    
    def complete(self, rect):
        """Анимированное отображение автодополнения"""
        popup = self.popup()
        start_rect = QRect(rect.x(), rect.y(), 0, 0)
        end_rect = QRect(rect.x(), rect.bottom() + 2, 300, 
                        min(self.maxVisibleItems() * popup.sizeHintForRow(0) + 10, 200))
        
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        super().complete(rect)
        self.animation.start()


class LineNumberArea(QWidget):
    """Область для отображения номеров строк"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Основной редактор кода с поддержкой различных языков"""
    
    textChangedAnimated = pyqtSignal()
    focusChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None, language: str = "", settings: dict = None):
        super().__init__(parent)
        self.settings = settings or {}
        self.language = language
        
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
        font_size = int(self.settings.get("fontsize", 12))
        bg_color = self.settings.get("second_color", "#1E1E1E")
        text_color = self.settings.get("text_color", "#D4D4D4")
        
        # Устанавливаем шрифт
        font = QFont("Cascadia Code", font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        
        # Стилизация
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
        
        # Настройка табуляции
        self.tab_width = 4
        self.setTabStopDistance(self.tab_width * self.fontMetrics().width(' '))
        
        # Подсветка синтаксиса
        self.highlighter = ModernSyntaxHighlighter(self.document(), self.language_config)
    
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
        
        # Разделительная линия
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
                
                if block_number + 1 == current_line:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.setFont(QFont("Cascadia Code", self.font().pointSize(), QFont.Bold))
                else:
                    painter.setPen(QColor("#6E7681"))
                    painter.setFont(self.font())
                
                painter.drawText(0, int(top), self.line_number_area.width() - 8, 
                            int(line_height), Qt.AlignRight, number)
            
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
        
        if len(prefix) >= 1:
            self.analyzer.analyze_code(self.toPlainText())
            self.completer.update_completions(self.analyzer.get_completion_list())
            
            self.completer.setCompletionPrefix(prefix)
            if self.completer.completionCount() > 0:
                self.completer.complete(self.cursorRect())
    
    def _delayed_analysis(self):
        """Отложенный анализ кода"""
        self.analyzer.analyze_code(self.toPlainText())
    
    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if event.text() and not event.text().isspace():
            self.completion_timer.start(200)
        
        # Автозакрытие скобок
        if self.language_config.brace_auto_close:
            if self._handle_auto_closure(event):
                return
        
        # Умные отступы
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._handle_smart_indent()
            return
        
        # Обработка комплитера
        if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return) and self.completer.popup().isVisible():
            self.completer.popup().hide()
            if event.key() in (Qt.Key_Enter, Qt.Key_Return):
                return
        
        super().keyPressEvent(event)
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
        
        indent = len(previous_text) - len(previous_text.lstrip())
        base_indent = ' ' * indent
        
        if self.language_config.auto_indent:
            if any(previous_text.strip().endswith(keyword) for keyword in [':', '{', '=>']):
                base_indent += ' ' * self.tab_width
        
        cursor.insertText('\n' + base_indent)
    
    def set_language(self, language: str):
        """Изменение языка программирования"""
        self.language = language
        self.language_config = self._get_language_config(language)
        self.analyzer = CodeAnalyzer(language)
        self.highlighter = ModernSyntaxHighlighter(self.document(), self.language_config)
        self.analyzer.analyze_code(self.toPlainText())


class ModernCodeEditor(QWidget):
    """Современный редактор кода с поддержкой различных языков"""
    
    def __init__(self, parent=None, language: str = "", settings: dict = None):
        super().__init__(parent)
        self.language = language
        self.settings = settings or {}
        self.file_path = None
        
        self._setup_ui()
        self._setup_shortcuts()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
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
    
    def _zoom_in(self):
        """Увеличение масштаба"""
        font = self.editor.font()
        current_size = font.pointSize()
        if current_size < 30:
            font.setPointSize(current_size + 1)
            self.editor.setFont(font)
    
    def _zoom_out(self):
        """Уменьшение масштаба"""
        font = self.editor.font()
        current_size = font.pointSize()
        if current_size > 6:
            font.setPointSize(current_size - 1)
            self.editor.setFont(font)
    
    def _reset_zoom(self):
        """Сброс масштаба"""
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
            
            comment_char = self.editor.language_config.line_comment
            
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfLine)
            
            while cursor.position() < end:
                cursor_text = cursor.block().text()
                
                if cursor_text.lstrip().startswith(comment_char):
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 
                                      len(cursor_text) - len(cursor_text.lstrip()))
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(comment_char))
                    cursor.removeSelectedText()
                else:
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.insertText(comment_char + " ")
                
                if not cursor.movePosition(QTextCursor.Down):
                    break
            
            cursor.endEditBlock()
        else:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor_text = cursor.block().text()
            comment_char = self.editor.language_config.line_comment
            
            if cursor_text.lstrip().startswith(comment_char):
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 
                                  len(cursor_text) - len(cursor_text.lstrip()))
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(comment_char))
                cursor.removeSelectedText()
            else:
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
        """Установка пути к файлу и автоматическое определение языка"""
        self.file_path = Path(file_path)
        
        file_extension = self.file_path.suffix.lower()
        if file_extension:
            file_extension = file_extension[1:]
            
        if file_extension and file_extension != self.language:
            self.set_language_by_extension(file_extension)
    
    def set_language_by_extension(self, extension: str):
        """Установка языка по расширению файла"""
        provider = LanguageProviderFactory.get_provider_by_extension(extension)
        if provider:
            config = provider.get_config()
            self.set_language(config.name.lower())
    
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
            if self.file_path:
                self.file_path.write_text(self.get_code(), encoding='utf-8')
                return True
            return False
        except Exception as e:
            print(f"Save error: {e}")
            return False

    def save_file_as(self, file_path: str) -> bool:
        try:
            self.set_file_path(file_path)
            return self.save_file()
        except Exception as e:
            print(f"Save as error: {e}")
            return False
    
    def get_code(self) -> str:
        return self.editor.toPlainText()
    
    def set_code(self, code: str):
        self.editor.setPlainText(code)


# Пример использования и демонстрация расширяемости
if __name__ == "__main__":
    import sys
    
    # Пример добавления нового провайдера для TypeScript
    class TypeScriptLanguageProvider(JavaScriptLanguageProvider):
        def get_config(self) -> LanguageConfig:
            base_config = super().get_config()
            
            # Добавляем TypeScript-специфичные ключевые слова
            ts_keywords = base_config.keywords + [
                "type", "interface", "implements", "namespace", "abstract",
                "public", "private", "protected", "readonly", "enum"
            ]
            
            ts_syntax_rules = base_config.syntax_rules + [
                SyntaxRule(r'\b(type|interface|enum)\b', "#569CD6"),
                SyntaxRule(r'\b(public|private|protected|readonly)\b', "#569CD6"),
            ]
            
            return LanguageConfig(
                name="TypeScript",
                extensions=["ts", "tsx"],
                keywords=ts_keywords,
                syntax_rules=ts_syntax_rules
            )
    
    # Регистрируем новый провайдер
    LanguageProviderFactory.register_provider(Language.TYPESCRIPT, TypeScriptLanguageProvider())
    
    app = QApplication(sys.argv)
    
    settings = {
        "fontsize": 14,
        "text_color": "#D4D4D4",
        "second_color": "#1E1E1E",
        "accent_color": "#007ACC"
    }
    
    # Демонстрация работы с разными языками
    editor = ModernCodeEditor(language="py", settings=settings)
    
    example_code = '''# Пример Python кода
class Calculator:
    def add(self, x: float, y: float) -> float:
        return x + y
'''
    
    editor.set_code(example_code)
    editor.setWindowTitle("Modern Code Editor - Multi Language Support")
    editor.resize(800, 600)
    editor.show()
    
    print("Supported extensions:", LanguageProviderFactory.get_supported_extensions())
    
    sys.exit(app.exec_())