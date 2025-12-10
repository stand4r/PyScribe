import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum


from PyQt5.QtGui import QFont



class Language(Enum):
    PYTHON = "py"
    JAVASCRIPT = "js"
    TYPESCRIPT = "ts"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    CS = "cs"
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
        return []


class CSLanguageProvider(LanguageProvider):
    def get_config(self) -> LanguageConfig:
        keywords = [
            'abstract', 'as', 'base', 'bool', 'break', 'byte', 'case', 'catch',
            'char', 'checked', 'class', 'const', 'continue', 'decimal', 'default',
            'delegate', 'do', 'double', 'else', 'enum', 'event', 'explicit',
            'extern', 'false', 'finally', 'fixed', 'float', 'for', 'foreach',
            'goto', 'if', 'implicit', 'in', 'int', 'interface', 'internal',
            'is', 'lock', 'long', 'namespace', 'new', 'null', 'object', 'operator',
            'out', 'override', 'params', 'private', 'protected', 'public',
            'readonly', 'ref', 'return', 'sbyte', 'sealed', 'short', 'sizeof',
            'stackalloc', 'static', 'string', 'struct', 'switch', 'this', 'throw',
            'true', 'try', 'typeof', 'uint', 'ulong', 'unchecked', 'unsafe',
            'ushort', 'using', 'virtual', 'void', 'volatile', 'while',
            'get', 'set', 'value', 'where', 'yield', 'async', 'await', 'nameof',
            'var', 'dynamic', 'task', 'list', 'dictionary'
        ]
        
        syntax_rules = [
            SyntaxRule(r'//[^\n]*', "#6A9955"),  # Комментарии
            SyntaxRule(r'/\*.*?\*/', "#6A9955"),
            SyntaxRule(r'\bclass\s+(\w+)', "#D7BA7D", QFont.Normal, False),
            SyntaxRule(r'\binterface\s+(\w+)', "#D7BA7D", QFont.Normal, False),
            SyntaxRule(r'\bstruct\s+(\w+)', "#D7BA7D", QFont.Normal, False),
            SyntaxRule(r'\benum\s+(\w+)', "#D7BA7D", QFont.Normal, False),
            SyntaxRule(r'^\s*#\w+', "#D7BA7D"),  # Декораторы
            SyntaxRule(r'\b(None|True|False)\b', "#569CD6"),
            SyntaxRule(r'\b\d+\b', "#B5CEA8"),  # Числа
            SyntaxRule(r'\"[^\"]*\"', "#CE9178"),  # Строки
            SyntaxRule(r'\'[^\']*\'', "#CE9178")    
        ]
        
        return LanguageConfig(
            name="CSharp",
            extensions=["cs"],
            keywords=keywords,
            syntax_rules=syntax_rules,
            line_comment="//",
            block_comment_start='/*',
            block_comment_end='*/'
        )
    
    def analyze_code(self, code: str, analyzer: 'CodeAnalyzer'):
        pass
    
    def _analyze_with_regex(self, code: str, analyzer: 'CodeAnalyzer'):
        pass
    
    def get_completion_items(self, code: str) -> List[str]:
        return []


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
        return []


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
LanguageProviderFactory.register_provider(Language.CS, CSLanguageProvider())


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
