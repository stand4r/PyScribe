"""PyScribe widgets/CodeLensBar.py: Intelligent Code Navigation, Clean Code & Quick Actions Hub.

Combines real-time telemetry from radar with modern IDE productivity tools:
- Breadcrumbs (File › Class › Method) with 1-click symbol picker outline
- Clean Code Refactoring & Advanced AST Auto-formatting (both for selection and full file)
- High-quality Docstring & Comment Generator (for selection, current function, or entire file)
- Code Telemetry & Algorithmic Complexity HUD popup
- Instant Run Block / Selection in the integrated terminal
- Live AST syntax validation chip
- Project-wide symbol reference search
"""
from __future__ import annotations

import ast
import os
import re
from typing import List, Tuple, Optional, Dict, Any

from design.icons import line_icon, set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QToolButton, QMenu, QAction,
    QApplication, QPlainTextEdit, QMessageBox, QDialog, QVBoxLayout,
    QTextEdit
)


class CodeSymbol:
    """Represents a navigable AST symbol in the document."""
    def __init__(self, name: str, kind: str, line: int, end_line: int, parent_name: Optional[str] = None):
        self.name = name
        self.kind = kind  # 'class' or 'function' or 'method'
        self.line = line
        self.end_line = end_line
        self.parent_name = parent_name


class CleanCodeRefactorer:
    """Advanced Clean Code refactoring and formatting engine supporting Python and multi-language files."""

    @classmethod
    def format_code(cls, code: str, language: str = "py") -> str:
        """Format and clean code according to Clean Code and formatting principles."""
        if not code.strip():
            return code

        lang = (language or "").lower().lstrip(".")
        lines = code.splitlines()
        cleaned_lines = []
        prev_blank = 0

        for line in lines:
            r_line = line.rstrip()
            if not r_line:
                prev_blank += 1
                if prev_blank <= 2:
                    cleaned_lines.append("")
            else:
                prev_blank = 0
                if lang in ("py", "python"):
                    mod_line = cls._clean_syntax_line(r_line)
                else:
                    mod_line = r_line
                cleaned_lines.append(mod_line)

        if lang in ("py", "python"):
            result_lines = cls._normalize_declarations_spacing(cleaned_lines)
        else:
            result_lines = cleaned_lines

        result = "\n".join(result_lines)
        if result and not result.endswith('\n'):
            result += '\n'
        return result

    @classmethod
    def _clean_syntax_line(cls, line: str) -> str:
        """Apply Clean Code micro-refactorings without breaking string literals."""
        line = re.sub(r'\bif\s+([A-Za-z0-9_\.]+)\s*==\s*True\s*:', r'if \1:', line)
        line = re.sub(r'\bif\s+([A-Za-z0-9_\.]+)\s*==\s*False\s*:', r'if not \1:', line)
        line = re.sub(r'\bif\s+([A-Za-z0-9_\.]+)\s*!=\s*True\s*:', r'if not \1:', line)
        line = re.sub(r'\bif\s+([A-Za-z0-9_\.]+)\s*==\s*None\s*:', r'if \1 is None:', line)
        line = re.sub(r'\bif\s+([A-Za-z0-9_\.]+)\s*!=\s*None\s*:', r'if \1 is not None:', line)
        if not ('"' in line or "'" in line):
            line = re.sub(r'(?<=[a-zA-Z0-9_])\s*==\s*(?=[a-zA-Z0-9_])', ' == ', line)
            line = re.sub(r'(?<=[a-zA-Z0-9_])\s*!=\s*(?=[a-zA-Z0-9_])', ' != ', line)
            line = re.sub(r'(?<=[a-zA-Z0-9_])\s*<=\s*(?=[a-zA-Z0-9_])', ' <= ', line)
            line = re.sub(r'(?<=[a-zA-Z0-9_])\s*>=\s*(?=[a-zA-Z0-9_])', ' >= ', line)
        return line

    @classmethod
    def _normalize_declarations_spacing(cls, lines: List[str]) -> List[str]:
        """Ensure top-level classes/defs have 2 blank lines, and inner methods have 1."""
        output = []
        for i, line in enumerate(lines):
            if (line.startswith("def ") or line.startswith("class ") or line.startswith("async def ")) and i > 0:
                while len(output) > 0 and output[-1] == "":
                    output.pop()
                output.append("")
                output.append("")
            elif (re.match(r'^\s{4}(def|async def)\s+', line)) and i > 0:
                while len(output) > 0 and output[-1] == "":
                    output.pop()
                output.append("")
            output.append(line)
        return output


class DocumentationGenerator:
    """Generates structured, professional, context-rich docstrings and comments across languages."""

    VERBS = {
        'get': 'Возвращает',
        'fetch': 'Выполняет запрос и извлекает',
        'retrieve': 'Извлекает из хранилища',
        'find': 'Выполняет поиск и возвращает',
        'search': 'Ищет элементы по критериям',
        'set': 'Устанавливает новое значение для',
        'update': 'Обновляет параметры',
        'modify': 'Модифицирует состояние',
        'create': 'Создает и инициализирует новый экземпляр',
        'build': 'Конструирует объект',
        'make': 'Формирует',
        'generate': 'Генерирует',
        'delete': 'Удаляет',
        'remove': 'Удаляет из коллекции',
        'clear': 'Очищает содержимое',
        'is': 'Проверяет, является ли',
        'has': 'Проверяет наличие',
        'can': 'Проверяет возможность',
        'check': 'Выполняет валидацию и проверку',
        'validate': 'Проверяет корректность структуры и значений',
        'parse': 'Выполняет синтаксический разбор',
        'format': 'Форматирует представление',
        'render': 'Отрисовывает графические элементы',
        'handle': 'Обрабатывает событие или входящие данные',
        'on': 'Обработчик события для',
        'send': 'Отправляет сетевое сообщение или запрос',
        'post': 'Публикует данные',
        'save': 'Сохраняет состояние в постоянное хранилище',
        'write': 'Записывает данные в целевой поток или файл',
        'read': 'Считывает данные из ресурса',
        'load': 'Загружает и десериализует',
        'open': 'Открывает ресурс или дескриптор',
        'close': 'Закрывает и освобождает системные ресурсы',
        'start': 'Запускает процесс или таймер',
        'stop': 'Останавливает выполнение',
        'run': 'Выполняет запуск рабочего процесса',
        'execute': 'Исполняет команду или алгоритм',
        'calculate': 'Вычисляет расчетное значение',
        'compute': 'Рассчитывает параметры',
        'count': 'Подсчитывает количество',
        'convert': 'Преобразует входные данные в целевой формат',
        'transform': 'Трансформирует структуру данных',
        'reset': 'Сбрасывает в исходное состояние по умолчанию',
        'init': 'Инициализирует базовые компоненты',
        'apply': 'Применяет настройки или изменения',
        'sync': 'Синхронизирует состояние между компонентами',
        'register': 'Регистрирует новый обработчик или компонент',
        'unregister': 'Отменяет регистрацию компонента',
        'connect': 'Устанавливает соединение',
        'disconnect': 'Разрывает соединение',
        'emit': 'Инициирует генерацию сигнала или события',
        'dispatch': 'Диспетчеризует действие в обработчик',
        'process': 'Обрабатывает последовательность элементов',
        'filter': 'Фильтрует набор данных по условию',
        'sort': 'Выполняет сортировку элементов',
    }

    PARAM_DOCS = {
        ('path', 'file_path', 'filepath', 'filename'): 'Путь к целевому файлу или директории в файловой системе.',
        ('url', 'uri', 'endpoint'): 'Сетевой адрес или URL-эндпоинт для отправки запроса.',
        ('timeout',): 'Максимальное время ожидания ответа в секундах.',
        ('data', 'payload', 'body', 'content'): 'Полезная нагрузка или входные данные для обработки.',
        ('id', 'user_id', 'item_id', 'guid', 'uuid'): 'Уникальный идентификатор целевой сущности.',
        ('config', 'settings', 'options', 'params'): 'Словарь или объект параметров конфигурации.',
        ('callback', 'handler', 'func'): 'Функция обратного вызова, вызываемая по завершении операции.',
        ('limit', 'max_items', 'count', 'size'): 'Максимальное количество возвращаемых или обрабатываемых элементов.',
        ('offset', 'page', 'index', 'idx'): 'Смещение или индекс начального элемента для выборки.',
        ('force', 'override', 'overwrite'): 'Флаг принудительного выполнения без дополнительных подтверждений.',
        ('enabled', 'is_active', 'visible'): 'Флаг активации или отображения соответствующего режима.',
        ('context', 'ctx'): 'Контекст выполнения с метаданными операции.',
        ('encoding',): "Символьная кодировка текстовых данных (например, 'utf-8').",
        ('buffer',): 'Буфер бинарных данных для чтения или записи.',
        ('key',): 'Ключ доступа или идентификатор параметра.',
        ('name',): 'Имя или символьное обозначение объекта.',
        ('host',): 'Сетевой хост или IP-адрес удаленного сервера.',
        ('port',): 'Сетевой порт сервиса.',
    }

    CLASS_ROLES = {
        'manager': 'Менеджер: координирует жизненный цикл, распределение задач и управление состоянием.',
        'controller': 'Контроллер: обрабатывает команды, маршрутизирует операции и связывает модель с представлением.',
        'service': 'Сервис: инкапсулирует бизнес-логику и сервисные операции доменной области.',
        'repository': 'Репозиторий: обеспечивает уровень абстракции для доступа к данным и постоянному хранилищу.',
        'parser': 'Парсер: выполняет синтаксический анализ, валидацию и преобразование входных структур данных.',
        'widget': 'Виджет UI: отвечает за визуальное отображение и обработку пользовательских событий.',
        'view': 'Представление UI: формирует графический интерфейс для пользователя.',
        'handler': 'Обработчик: выполняет целевую обработку специфичных событий и сигналов.',
        'client': 'Клиент: предоставляет сетевой интерфейс для взаимодействия с внешним API.',
        'factory': 'Фабрика: отвечает за конструирование и инициализацию экземпляров объектов.',
        'model': 'Модель данных: определяет структуру сущности и правила валидации полей.',
        'provider': 'Провайдер: поставляет данные или конфигурационные ресурсы для подсистем.',
        'adapter': 'Адаптер: согласует интерфейсы несовместимых компонентов.',
    }

    @classmethod
    def describe_name(cls, name: str) -> str:
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+', name)
        words = [w.lower() for w in words] or [name.lower()]
        verb = words[0]
        rest = " ".join(words[1:]) if len(words) > 1 else ""
        if verb in cls.VERBS:
            action = cls.VERBS[verb]
            if rest:
                return f"{action} {rest}."
            return f"{action} соответствующий объект."
        return f"Выполняет операцию {name.replace('_', ' ')}."

    @classmethod
    def describe_param(cls, arg_name: str, type_str: str = "") -> str:
        clean = arg_name.lower().strip('_')
        for keys, desc in cls.PARAM_DOCS.items():
            if clean in keys:
                return desc
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+', clean)
        if words:
            return f"Параметр {clean.replace('_', ' ')}."
        return f"Значение аргумента `{arg_name}`."

    @classmethod
    def generate_function_docstring(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Create a comprehensive docstring for a Python function or method."""
        indent = " " * (func_node.col_offset + 4)
        summary = cls.describe_name(func_node.name)
        args_info = []
        for a in func_node.args.args:
            if a.arg in ('self', 'cls'):
                continue
            type_hint = ""
            if a.annotation:
                try:
                    type_hint = f" ({ast.unparse(a.annotation)})"
                except Exception:
                    pass
            desc = cls.describe_param(a.arg, type_hint)
            args_info.append(f"{indent}    {a.arg}{type_hint}: {desc}")

        return_hint = ""
        has_returns = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(func_node))
        has_yields = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(func_node))
        if getattr(func_node, 'returns', None):
            try:
                return_hint = ast.unparse(func_node.returns)
            except Exception:
                pass

        raises_info = []
        for n in ast.walk(func_node):
            if isinstance(n, ast.Raise):
                exc_name = ""
                if isinstance(n.exc, ast.Name):
                    exc_name = n.exc.id
                elif isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Name):
                    exc_name = n.exc.func.id
                if exc_name and exc_name not in raises_info:
                    raises_info.append(exc_name)

        doc = f'\n{indent}"""{summary}\n'
        if args_info:
            doc += f'\n{indent}Args:\n' + "\n".join(args_info) + "\n"
        if has_yields:
            doc += f'\n{indent}Yields:\n{indent}    Генератор элементов в процессе выполнения.\n'
        elif return_hint or has_returns:
            ret_type_str = f"{return_hint}: " if return_hint else ""
            if func_node.name.startswith(('is_', 'has_', 'can_', 'check_', 'should_')):
                ret_desc = "True, если проверка пройдена успешно; иначе False."
            else:
                ret_desc = "Результат выполнения операции или результирующий объект."
            doc += f'\n{indent}Returns:\n{indent}    {ret_type_str}{ret_desc}\n'
        if raises_info:
            doc += f'\n{indent}Raises:\n'
            for r in raises_info:
                doc += f'{indent}    {r}: При возникновении ошибки в процессе выполнения.\n'
        doc += f'{indent}"""'
        return doc

    @classmethod
    def generate_class_docstring(cls, class_node: ast.ClassDef) -> str:
        """Create a structured docstring for a Python class."""
        indent = " " * (class_node.col_offset + 4)
        bases = [b.id for b in class_node.bases if hasattr(b, 'id')]
        bases_str = f" Наследует: {', '.join(bases)}." if bases else ""

        class_lower = class_node.name.lower()
        role = "Инкапсулирует бизнес-логику и состояние объекта."
        for suffix, desc in cls.CLASS_ROLES.items():
            if class_lower.endswith(suffix):
                role = desc
                break

        attributes = []
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
                                attr_name = target.attr
                                if not attr_name.startswith('__') and attr_name not in [a[0] for a in attributes]:
                                    attr_desc = cls.describe_param(attr_name)
                                    attributes.append((attr_name, attr_desc))

        methods = [n.name for n in class_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith('_')]
        methods_str = f"\n{indent}Ключевые методы: {', '.join(methods)}." if methods else ""

        doc = f'\n{indent}"""Класс `{class_node.name}`.{bases_str}\n\n{indent}{role}\n'
        if attributes:
            doc += f'\n{indent}Attributes:\n'
            for a_name, a_desc in attributes:
                doc += f'{indent}    {a_name}: {a_desc}\n'
        if methods_str:
            doc += f'{methods_str}\n'
        doc += f'{indent}"""'
        return doc

    @classmethod
    def generate_multilang_docstring(
        cls, name: str, kind: str, lang: str, params: List[str] = None, return_type: str = "", indent: str = ""
    ) -> str:
        """Create structured docstrings formatted for specific programming languages."""
        lang = (lang or "").lower().lstrip(".")
        params = params or []
        summary = cls.describe_name(name) if kind != 'class' else f"Класс `{name}`."

        if lang in ('js', 'ts', 'jsx', 'tsx'):
            lines = [f"{indent}/**", f"{indent} * {summary}"]
            if params:
                lines.append(f"{indent} *")
                for p in params:
                    desc = cls.describe_param(p)
                    lines.append(f"{indent} * @param {p} {desc}")
            if return_type or kind != 'class':
                lines.append(f"{indent} * @returns {return_type or 'Результат выполнения операции.'}")
            lines.append(f"{indent} */")
            return "\n".join(lines) + "\n"

        elif lang in ('c', 'cpp', 'cc', 'cxx', 'h', 'hpp', 'cs', 'csharp', 'java', 'kt', 'kotlin', 'php'):
            lines = [f"{indent}/**", f"{indent} * {summary}"]
            if params:
                for p in params:
                    desc = cls.describe_param(p)
                    lines.append(f"{indent} * @param {p} {desc}")
            if return_type or kind != 'class':
                lines.append(f"{indent} * @return {return_type or 'Результат выполнения.'}")
            lines.append(f"{indent} */")
            return "\n".join(lines) + "\n"

        elif lang in ('go', 'golang'):
            return f"{indent}// {name} {summary[0].lower() + summary[1:] if len(summary) > 1 else summary}\n"

        elif lang in ('rs', 'rust'):
            lines = [f"{indent}/// {summary}"]
            if params:
                lines.append(f"{indent}///")
                lines.append(f"{indent}/// # Arguments")
                for p in params:
                    desc = cls.describe_param(p)
                    lines.append(f"{indent}/// * `{p}` - {desc}")
            return "\n".join(lines) + "\n"

        else:
            return f"{indent}/* {summary} */\n"


class CompactOutlinePopup(QDialog):
    """Compact, scrollable symbol outline popup with instant search filtering."""
    def __init__(self, symbols: List[CodeSymbol], on_jump, parent=None, title_text="Структура файла"):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.symbols = sorted(symbols, key=lambda s: s.line)
        self.on_jump = on_jump
        self.setFixedSize(460, 360)
        self.setStyleSheet("""
            QDialog {
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
            QLineEdit {
                background: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #FFFFFF;

                font-size: 13px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border-color: #58A6FF;
            }
            QListWidget {
                background: transparent;
                border: none;
                color: #E6EDF3;

                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: #21262D;
            }
            QListWidget::item:selected {
                background: #1F6FEB;
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        title = QLabel(f"{title_text} ({len(self.symbols)})")
        title.setStyleSheet("font-weight: bold; color: #58A6FF; font-size: 12px;")
        top_row.addWidget(title)
        top_row.addStretch()
        hint = QLabel("Esc — закрыть · Enter — перейти")
        hint.setStyleSheet("color: #8B949E; font-size: 11px;")
        top_row.addWidget(hint)
        layout.addLayout(top_row)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Фильтр: введите имя функции или класса…")
        self.search_input.textChanged.connect(self._filter_items)
        self.search_input.returnPressed.connect(self._select_current)
        layout.addWidget(self.search_input)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_activated)
        self.list_widget.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self.list_widget, 1)

        self._populate_list("")
        QTimer.singleShot(0, self.search_input.setFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            self.list_widget.setFocus()
            if self.list_widget.count() > 0 and self.list_widget.currentRow() == -1:
                self.list_widget.setCurrentRow(0)
            return
        elif event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _filter_items(self, text: str):
        self._populate_list(text.strip().lower())

    def _populate_list(self, query: str):
        self.list_widget.clear()
        for sym in self.symbols:
            display_name = f"{sym.parent_name}.{sym.name}" if sym.parent_name else sym.name
            if query and query not in display_name.lower():
                continue
            icon = "⚙️" if sym.kind in ('class', 'struct', 'interface', 'trait') else "🔹"
            kind_label = (
                "Класс" if sym.kind == 'class'
                else "Структура" if sym.kind == 'struct'
                else "Интерфейс" if sym.kind == 'interface'
                else "Трейт" if sym.kind == 'trait'
                else "Метод" if sym.kind == 'method'
                else "Функция"
            )
            item_text = f"{icon}  {display_name}  ·  {kind_label} (стр. {sym.line})"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, sym.line)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _select_current(self):
        item = self.list_widget.currentItem()
        if item:
            self._on_item_activated(item)

    def _on_item_activated(self, item):
        line = item.data(Qt.UserRole)
        if line and self.on_jump:
            self.on_jump(line)
        self.accept()


GENERIC_LANG_PATTERNS: Dict[str, List[Tuple[str, str]]] = {
    'js': [
        ('class', r'^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_$]+)'),
        ('interface', r'^\s*(?:export\s+)?interface\s+([A-Za-z0-9_$]+)'),
        ('function', r'^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*([A-Za-z0-9_$]+)\s*\('),
        ('function', r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>'),
        ('method', r'^\s*(?:(?:public|private|protected|static|async|get|set)\s+)*([A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{'),
    ],
    'cpp': [
        ('class', r'^\s*(?:class|struct)\s+([A-Za-z0-9_]+)(?:\s*:[^{]*)?\s*\{'),
        ('function', r'^\s*(?:[A-Za-z0-9_<>:*&]+\s+)+([A-Za-z0-9_]+)\s*\([^;{)]*\)\s*(?:const)?\s*\{'),
    ],
    'cs': [
        ('class', r'^\s*(?:(?:public|private|protected|internal|abstract|sealed|static|partial)\s+)*(?:class|struct|interface|record)\s+([A-Za-z0-9_]+)'),
        ('method', r'^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|async)\s+)+[A-Za-z0-9_<>\[\],\s]+\s+([A-Za-z0-9_]+)\s*\('),
    ],
    'java': [
        ('class', r'^\s*(?:(?:public|private|protected|abstract|final|static)\s+)*(?:class|interface|enum|record)\s+([A-Za-z0-9_]+)'),
        ('method', r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)+[A-Za-z0-9_<>\[\],\s]+\s+([A-Za-z0-9_]+)\s*\('),
    ],
    'go': [
        ('struct', r'^\s*type\s+([A-Za-z0-9_]+)\s+struct\s*\{'),
        ('interface', r'^\s*type\s+([A-Za-z0-9_]+)\s+interface\s*\{'),
        ('method', r'^\s*func\s*\([^)]+\)\s*([A-Za-z0-9_]+)\s*\('),
        ('function', r'^\s*func\s+([A-Za-z0-9_]+)\s*\('),
    ],
    'rust': [
        ('struct', r'^\s*(?:pub(?:\([^)]+\))?\s+)?(?:struct|enum|union)\s+([A-Za-z0-9_]+)'),
        ('trait', r'^\s*(?:pub(?:\([^)]+\))?\s+)?trait\s+([A-Za-z0-9_]+)'),
        ('class', r'^\s*(?:pub(?:\([^)]+\))?\s+)?impl(?:\s+[A-Za-z0-9_<>]+)?\s+(?:for\s+)?([A-Za-z0-9_]+)'),
        ('function', r'^\s*(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\('),
    ],
    'php': [
        ('class', r'^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+([A-Za-z0-9_]+)'),
        ('method', r'^\s*(?:(?:public|protected|private|static|final)\s+)+function\s+([A-Za-z0-9_]+)\s*\('),
        ('function', r'^\s*function\s+([A-Za-z0-9_]+)\s*\('),
    ],
    'py': [
        ('class', r'^\s*class\s+([A-Za-z0-9_]+)'),
        ('function', r'^\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)'),
    ],
}


class CodeLensBar(QFrame):
    """PyScribe CodeLens & Context Action Hub."""

    actionTriggered = pyqtSignal(str)

    def __init__(self, modern_editor, parent=None):
        super().__init__(parent)
        self.modern_editor = modern_editor
        self.editor = getattr(modern_editor, 'editor', modern_editor)
        self._symbols: List[CodeSymbol] = []
        self._syntax_error_line: Optional[int] = None
        self._current_scope = {"class": None, "function": None}

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._refresh_lens)

        self._setup_ui()
        self._connect_signals()
        self._refresh_lens()

    def _setup_ui(self):
        self.setObjectName("codeLensBar")
        # Visual styling (row height, fonts, chip colours) lives in
        # design/theme.qss so the breadcrumb strip matches the status strip.

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        # 1. Breadcrumbs: File
        self.file_btn = QToolButton()
        self.file_btn.setProperty("class", "lensCrumbBtn")
        self.file_btn.setText("Файл")
        set_line_icon(self.file_btn, "document", 14)
        self.file_btn.setToolTip("Текущий файл. Нажмите для структуры символов (Outline).")
        self.file_btn.clicked.connect(self._show_outline_menu)
        layout.addWidget(self.file_btn)

        # Divider 1
        self.div_class = QLabel("›")
        self.div_class.setProperty("class", "lensDivider")
        self.div_class.hide()
        layout.addWidget(self.div_class)

        # Breadcrumbs: Class
        self.class_btn = QToolButton()
        self.class_btn.setProperty("class", "lensCrumbBtn")
        self.class_btn.setToolTip("Текущий класс. Нажмите для перехода к классам.")
        self.class_btn.hide()
        self.class_btn.clicked.connect(self._show_classes_menu)
        layout.addWidget(self.class_btn)

        # Divider 2
        self.div_func = QLabel("›")
        self.div_func.setProperty("class", "lensDivider")
        self.div_func.hide()
        layout.addWidget(self.div_func)

        # Breadcrumbs: Function/Method
        self.func_btn = QToolButton()
        self.func_btn.setProperty("class", "lensCrumbBtn")
        self.func_btn.setToolTip("Текущая функция / метод. Нажмите для перехода к функциям.")
        self.func_btn.hide()
        self.func_btn.clicked.connect(self._show_functions_menu)
        layout.addWidget(self.func_btn)

        layout.addStretch(1)

        # 2. Markdown preview — only for .md files, sits in the lens row like a
        #    VS Code code lens action.
        self.preview_btn = QToolButton()
        self.preview_btn.setProperty("class", "lensActionBtn")
        self.preview_btn.setText("Предпросмотр   ")
        self.preview_btn.setToolTip("Открыть отрисованный Markdown (Ctrl+Shift+V)")
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        self.preview_btn.hide()
        layout.addWidget(self.preview_btn)

        # 3. Syntax Status Chip
        self.syntax_badge = QToolButton()
        self._set_syntax_badge("Синтаксис ОК")
        self.syntax_badge.setCursor(Qt.PointingHandCursor)
        self.syntax_badge.setToolTip("Статус синтаксиса Python. Нажмите, чтобы открыть компактную структуру (Outline) или перейти к ошибке.")
        self.syntax_badge.clicked.connect(self._on_syntax_badge_clicked)
        layout.addWidget(self.syntax_badge)

        layout.addSpacing(6)
        for name, tooltip, orientation in (
            ("split_right_btn", "Разделить редактор вправо", Qt.Horizontal),
            ("split_down_btn", "Разделить редактор вниз", Qt.Vertical),
            ("unsplit_btn", "Объединить группы редактора", None),
        ):
            button = QToolButton(self)
            button.setObjectName(name)
            button.setProperty("class", "lensActionBtn")
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setIcon(self._split_icon(orientation))
            button.clicked.connect(
                lambda checked=False, direction=orientation: self._on_split_clicked(direction)
            )
            setattr(self, name, button)
            layout.addWidget(button)

        layout.addSpacing(6)

        # 3. Action: Clean Code Menu
        self.clean_code_btn = QToolButton()
        self.clean_code_btn.setProperty("class", "lensActionBtn")
        self.clean_code_btn.setText("Форматирование  ")
        self.clean_code_btn.setPopupMode(QToolButton.InstantPopup)
        self.clean_code_btn.setToolTip("Форматирование по принципам Clean Code ")
        clean_menu = QMenu(self.clean_code_btn)
        clean_menu.setStyleSheet("QMenu { background: #1C2128; border: 1px solid #30363D; color: #E6EDF3;  font-size: 12px; } QMenu::item:selected { background: #1F6FEB; }")

        act_clean_all = clean_menu.addAction("Форматировать весь файл ")
        act_clean_all.triggered.connect(self.format_entire_file)

        act_clean_sel = clean_menu.addAction("Форматировать выделенный фрагмент")
        act_clean_sel.triggered.connect(self.format_selection)

        self.clean_code_btn.setMenu(clean_menu)
        # Кнопка форматирования перенесена в нижний статус-бар редактора
        self.clean_code_btn.hide()

        # 4. Action: Documentation Menu
        self.docstring_btn = QToolButton()
        self.docstring_btn.setProperty("class", "lensActionBtn")
        self.docstring_btn.setText("Документация   ")
        self.docstring_btn.setPopupMode(QToolButton.InstantPopup)
        self.docstring_btn.setToolTip("Генерация структурированных описаний и комментариев для функций, классов и всего файла")
        doc_menu = QMenu(self.docstring_btn)
        doc_menu.setStyleSheet("QMenu { background: #1C2128; border: 1px solid #30363D; color: #E6EDF3;  font-size: 12px; } QMenu::item:selected { background: #1F6FEB; }")

        act_doc_curr = doc_menu.addAction("Документировать текущий блок / функцию / класс")
        act_doc_curr.triggered.connect(self.generate_docstring_current)

        act_doc_all = doc_menu.addAction("Документировать весь файл)")
        act_doc_all.triggered.connect(self.generate_docstrings_entire_file)

        self.docstring_btn.setMenu(doc_menu)
        # Кнопка автодокументирования перенесена в нижний статус-бар редактора
        self.docstring_btn.hide()

    def _split_icon(self, orientation):
        name = "split-right" if orientation == Qt.Horizontal else "split-down" if orientation == Qt.Vertical else "unsplit"
        return line_icon(name)

    def _on_split_clicked(self, orientation):
        window = getattr(self.modern_editor, 'main_window', None) or self.window()
        action = getattr(window, 'unsplit_editor' if orientation is None else 'split_editor', None)
        if not callable(action):
            return
        # The clicked editor may belong to the currently inactive group.
        group, index = window.find_tab_for_widget(self.modern_editor)
        if group is not None:
            group.setCurrentIndex(index)
            window._set_active_group(group)
        if orientation is None:
            action()
        else:
            action(orientation=orientation)

    def _connect_signals(self):
        if hasattr(self.editor, 'cursorPositionChanged'):
            self.editor.cursorPositionChanged.connect(self._schedule_refresh)
        if hasattr(self.editor, 'textChanged'):
            self.editor.textChanged.connect(self._schedule_refresh)

    def _schedule_refresh(self):
        self._debounce_timer.start(200)

    def _detect_language(self) -> str:
        """Detect language of current editor file."""
        lang = getattr(self.modern_editor, 'language', '') or getattr(self.editor, 'language', '')
        if lang:
            return str(lang).lower().strip().lstrip('.')
        filepath = getattr(self.modern_editor, 'file_path', None)
        if filepath:
            ext = os.path.splitext(filepath)[1].lstrip('.').lower()
            if ext:
                return ext
        return 'py'

    def _parse_generic_symbols_with_status(self, code: str, lang: str) -> Tuple[List[CodeSymbol], Optional[Dict[str, Any]]]:
        """Generic symbol parser using regex and brace balancing for JS/TS/C/C++/C#/Java/Go/Rust/PHP."""
        symbols = []
        syntax_error = None
        lang_norm = (lang or "").lower().strip().lstrip(".")

        if lang_norm in ('javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx'):
            pattern_key = 'js'
        elif lang_norm in ('c', 'cpp', 'c++', 'h', 'hpp', 'cxx', 'cc'):
            pattern_key = 'cpp'
        elif lang_norm in ('c#', 'cs', 'csharp'):
            pattern_key = 'cs'
        elif lang_norm in ('java',):
            pattern_key = 'java'
        elif lang_norm in ('go', 'golang'):
            pattern_key = 'go'
        elif lang_norm in ('rust', 'rs'):
            pattern_key = 'rust'
        elif lang_norm in ('php',):
            pattern_key = 'php'
        elif lang_norm in ('py', 'python'):
            pattern_key = 'py'
        else:
            pattern_key = 'js'

        patterns = GENERIC_LANG_PATTERNS.get(pattern_key, GENERIC_LANG_PATTERNS['js'])
        lines = code.splitlines()

        open_braces = 0
        brace_stack = []
        first_unmatched_close = None

        for idx, line in enumerate(lines):
            line_num = idx + 1
            stripped = line.strip()

            if stripped.startswith(('//', '#', '/*', '*', '*/')):
                continue

            matched = False
            for kind, pat in patterns:
                m = re.match(pat, line)
                if m:
                    sym_name = m.group(1)
                    parent = None
                    if brace_stack:
                        for _, p_idx in reversed(brace_stack):
                            if p_idx < len(symbols) and symbols[p_idx].kind in ('class', 'struct', 'interface', 'trait'):
                                parent = symbols[p_idx].name
                                if kind == 'function':
                                    kind = 'method'
                                break
                    elif pattern_key == 'py':
                        line_indent = len(line) - len(line.lstrip())
                        for prev_sym in reversed(symbols):
                            if prev_sym.kind == 'class':
                                prev_indent = len(lines[prev_sym.line - 1]) - len(lines[prev_sym.line - 1].lstrip())
                                if line_indent > prev_indent:
                                    parent = prev_sym.name
                                    if kind == 'function':
                                        kind = 'method'
                                    break

                    symbols.append(CodeSymbol(sym_name, kind, line_num, line_num + 5, parent))
                    matched = True
                    break

            if pattern_key != 'py':
                c_open = line.count('{')
                c_close = line.count('}')
                for _ in range(c_open):
                    open_braces += 1
                    brace_stack.append((line_num, len(symbols) - 1 if matched else -1))
                for _ in range(c_close):
                    open_braces -= 1
                    if open_braces < 0 and first_unmatched_close is None:
                        first_unmatched_close = line_num
                    if brace_stack:
                        b_line, b_sym_idx = brace_stack.pop()
                        if 0 <= b_sym_idx < len(symbols):
                            symbols[b_sym_idx].end_line = max(symbols[b_sym_idx].line, line_num)

        if pattern_key == 'py':
            for sym in symbols:
                sym_line_idx = sym.line - 1
                if sym_line_idx < len(lines):
                    base_indent = len(lines[sym_line_idx]) - len(lines[sym_line_idx].lstrip())
                    end = len(lines)
                    for next_idx in range(sym_line_idx + 1, len(lines)):
                        nxt = lines[next_idx]
                        if not nxt.strip():
                            continue
                        nxt_indent = len(nxt) - len(nxt.lstrip())
                        if nxt_indent <= base_indent:
                            end = next_idx
                            break
                    sym.end_line = max(sym.line, end)

        if pattern_key != 'py':
            if open_braces > 0 and brace_stack:
                unclosed_line = brace_stack[-1][0]
                syntax_error = {'line': unclosed_line, 'text': f"Незакрытая скобка {{ (стр. {unclosed_line})"}
            elif open_braces < 0:
                syntax_error = {'line': first_unmatched_close or 1, 'text': f"Лишняя скобка }} (стр. {first_unmatched_close or 1})"}

        return symbols, syntax_error

    def _refresh_lens(self):
        code = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1

        # 1. Update file label
        filepath = getattr(self.modern_editor, 'file_path', None)
        filename = os.path.basename(filepath) if filepath else "Без имени"
        self.file_btn.setText(filename)

        # 1b. Markdown gets a preview action in the lens row; hidden otherwise.
        lang = self._detect_language()
        is_markdown = lang in ('md', 'markdown', 'mdown', 'mkd')
        self.preview_btn.setVisible(is_markdown)
        if is_markdown:
            self.syntax_badge.hide()
        else:
            self.syntax_badge.show()

        # 2. Parse symbols and AST
        self._parse_symbols(code)

        # 3. Find current scope and telemetry
        curr_class = None
        curr_func = None
        for sym in self._symbols:
            if sym.line <= line <= sym.end_line:
                if sym.kind in ('class', 'struct', 'interface', 'trait'):
                    curr_class = sym.name
                elif sym.kind in ('function', 'method'):
                    curr_func = sym.name

        self._current_scope = {"class": curr_class, "function": curr_func}

        if curr_class:
            self.div_class.show()
            self.class_btn.setText(f"    {curr_class}    ")
            self.class_btn.show()
        else:
            self.div_class.hide()
            self.class_btn.hide()

        if curr_func:
            self.div_func.show()
            self.func_btn.setText(f"   {curr_func}()    ")
            self.func_btn.show()
        else:
            self.div_func.hide()
            self.func_btn.hide()

    def _on_preview_clicked(self):
        """Ask the workbench to open the rendered Markdown preview."""
        filepath = getattr(self.modern_editor, 'file_path', None)
        self.actionTriggered.emit("preview_markdown")
        window = getattr(self.modern_editor, 'main_window', None)
        if window is None:
            window = self.window()
        action = getattr(window, 'action_preview_markdown', None)
        if callable(action):
            try:
                action()
                return
            except Exception:
                pass
        # Fall back to opening the file through the file manager.
        manager = getattr(window, 'file_manager', None)
        if manager is not None and filepath and hasattr(manager, 'open_markdown_file'):
            manager.open_markdown_file(str(filepath))

    def _parse_symbols(self, code: str):
        self._symbols = []
        self._syntax_error_line = None

        if not code.strip():
            self._set_syntax_badge("Синтаксис")
            return

        lang = self._detect_language()
        is_python = lang in ('py', 'python')

        if is_python:
            try:
                tree = ast.parse(code)
                self._set_syntax_badge("Python ОК")

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        end_lineno = getattr(node, 'end_lineno', node.lineno + 10)
                        self._symbols.append(CodeSymbol(node.name, 'class', node.lineno, end_lineno))
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                item_end = getattr(item, 'end_lineno', item.lineno + 5)
                                self._symbols.append(CodeSymbol(item.name, 'method', item.lineno, item_end, node.name))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not any(s.name == node.name and s.line == node.lineno for s in self._symbols):
                            end_lineno = getattr(node, 'end_lineno', node.lineno + 5)
                            self._symbols.append(CodeSymbol(node.name, 'function', node.lineno, end_lineno))

            except SyntaxError as exc:
                self._syntax_error_line = exc.lineno or 1
                self._set_syntax_badge(f"Синтаксис: строка {self._syntax_error_line}", error=True)
                # Generic fallback so outline and navigation work even during syntax errors
                generic_syms, _ = self._parse_generic_symbols_with_status(code, 'py')
                self._symbols = generic_syms
            except Exception:
                pass
        else:
            # Multi-language parsing for JS, TS, C, C++, C#, Java, Go, Rust, PHP, etc.
            self._symbols, syntax_err = self._parse_generic_symbols_with_status(code, lang)
            if syntax_err:
                self._syntax_error_line = syntax_err.get('line', 1)
                self._set_syntax_badge(syntax_err["text"], error=True)
                self.syntax_badge.setToolTip("Обнаружен дисбаланс фигурных скобок.")
            else:
                # Only Python gets a real parser; other languages are checked
                # for balanced braces, so do not claim full validation.
                self._set_syntax_badge(f"{lang.upper()} · скобки OK")
                self.syntax_badge.setToolTip("Проверен баланс фигурных скобок (полный разбор доступен для Python).")

    def _set_syntax_badge(self, text, *, error=False):
        self.syntax_badge.setText(text)
        self.syntax_badge.setObjectName("syntaxStatusErr" if error else "syntaxStatusGood")
        self.syntax_badge.setStyleSheet("")
        set_line_icon(self.syntax_badge, "warning" if error else "check", size=12)

    def _on_syntax_badge_clicked(self):
        if self._syntax_error_line:
            self._jump_to_line(self._syntax_error_line)
        else:
            self._show_outline_menu()

    def _jump_to_line(self, line: int):
        cursor = self.editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, max(0, line - 1))
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self.editor.centerCursor()

    def _show_outline_menu(self):
        if not self._symbols:
            QMessageBox.information(self, "Структура файла", "В текущем файле не найдено объявлений классов или функций.")
            return
        popup = CompactOutlinePopup(self._symbols, self._jump_to_line, self, "Структура файла (Outline)")
        pt = self.syntax_badge.mapToGlobal(QtCore.QPoint(0, self.syntax_badge.height() + 4))
        screen_geo = QApplication.desktop().availableGeometry(pt)
        if pt.x() + popup.width() > screen_geo.right():
            pt.setX(screen_geo.right() - popup.width() - 10)
        if pt.y() + popup.height() > screen_geo.bottom():
            pt.setY(pt.y() - popup.height() - self.syntax_badge.height() - 8)
        popup.move(pt)
        popup.exec_()

    def _show_classes_menu(self):
        classes = [s for s in self._symbols if s.kind in ('class', 'struct', 'interface', 'trait')]
        if not classes:
            return
        popup = CompactOutlinePopup(classes, self._jump_to_line, self, "Классы и структуры")
        pt = self.class_btn.mapToGlobal(QtCore.QPoint(0, self.class_btn.height() + 4))
        popup.move(pt)
        popup.exec_()

    def _show_functions_menu(self):
        funcs = [s for s in self._symbols if s.kind in ('function', 'method')]
        if not funcs:
            return
        popup = CompactOutlinePopup(funcs, self._jump_to_line, self, "Функции и методы")
        pt = self.func_btn.mapToGlobal(QtCore.QPoint(0, self.func_btn.height() + 4))
        popup.move(pt)
        popup.exec_()

    def run_current_block(self):
        """Execute the current selection or current function in the integrated terminal."""
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n').strip()

        code_to_run = selected
        target_name = "выделенного фрагмента"
        if not code_to_run:
            line = cursor.blockNumber() + 1
            for sym in self._symbols:
                if sym.kind in ('function', 'method') and sym.line <= line <= sym.end_line:
                    lines = self.editor.toPlainText().splitlines()
                    code_to_run = "\n".join(lines[sym.line - 1:sym.end_line])
                    target_name = f"функции {sym.name}()"
                    break

        if not code_to_run:
            code_to_run = cursor.block().text().strip()
            target_name = "текущей строки"

        if not code_to_run:
            QMessageBox.information(self, "Запуск блока", "Нет выделенного кода или активной функции для выполнения.")
            return

        main_win = self.window()
        console_widget = getattr(main_win, 'console_widget', None)
        if console_widget:
            if hasattr(main_win, 'set_console_visibility'):
                main_win.set_console_visibility(True)
            if hasattr(console_widget, 'set_current_tab'):
                console_widget.set_current_tab("Терминал")
            terminal = console_widget.get_terminal()
            if terminal and hasattr(terminal, 'tabs'):
                current_tab = getattr(terminal, '_current', lambda: None)()
                if current_tab:
                    escaped = code_to_run.replace('"', '\\"').replace('\n', '; ')
                    cmd = f'python -c "{escaped}"'
                    current_tab.execute_command(cmd)
                    return

        QMessageBox.information(self, "Запуск блока", f"Код {target_name} отправлен на выполнение:\n\n{code_to_run[:200]}")

    def format_entire_file(self):
        """Clean and format the entire file according to Clean Code and PEP-8."""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        try:
            text = self.editor.toPlainText()
            lang = self._detect_language()
            formatted = CleanCodeRefactorer.format_code(text, language=lang)
            pos = cursor.position()
            self.editor.setPlainText(formatted)
            new_cursor = self.editor.textCursor()
            new_cursor.setPosition(min(pos, len(formatted)))
            self.editor.setTextCursor(new_cursor)
        finally:
            cursor.endEditBlock()

    def format_selection(self):
        """Format only the selected block of code or current line."""
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.format_entire_file()
            return

        cursor.beginEditBlock()
        try:
            selected_text = cursor.selectedText().replace('\u2029', '\n')
            lang = self._detect_language()
            formatted = CleanCodeRefactorer.format_code(selected_text, language=lang).rstrip('\n')
            cursor.insertText(formatted)
        finally:
            cursor.endEditBlock()

    def generate_docstring_current(self):
        """Generate high-quality documentation for the function or class under cursor, or selected block."""
        cursor = self.editor.textCursor()
        line_idx = cursor.blockNumber() + 1
        code = self.editor.toPlainText()
        lang = self._detect_language()

        if lang in ('py', 'python'):
            try:
                tree = ast.parse(code)
                # 1. Search for function first
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.lineno <= line_idx <= getattr(node, 'end_lineno', node.lineno + 10):
                            doc = DocumentationGenerator.generate_function_docstring(node)
                            lines = code.splitlines()
                            lines[node.lineno - 1] += doc

                            cursor.beginEditBlock()
                            self.editor.setPlainText("\n".join(lines))
                            self._jump_to_line(node.lineno + 2)
                            cursor.endEditBlock()
                            return

                # 2. Search for class
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if node.lineno <= line_idx <= getattr(node, 'end_lineno', node.lineno + 10):
                            doc = DocumentationGenerator.generate_class_docstring(node)
                            lines = code.splitlines()
                            lines[node.lineno - 1] += doc

                            cursor.beginEditBlock()
                            self.editor.setPlainText("\n".join(lines))
                            self._jump_to_line(node.lineno + 2)
                            cursor.endEditBlock()
                            return
            except Exception:
                pass

        # 3. Multi-language or generic symbol fallback
        target_sym = None
        for sym in sorted(self._symbols, key=lambda s: (s.line <= line_idx <= max(s.line, s.end_line), -s.line), reverse=True):
            if sym.line <= line_idx <= max(sym.line, sym.end_line):
                target_sym = sym
                break

        if not target_sym:
            for sym in self._symbols:
                if sym.line == line_idx:
                    target_sym = sym
                    break

        if target_sym:
            lines = code.splitlines()
            if target_sym.line - 1 < len(lines):
                target_line = lines[target_sym.line - 1]
                indent = " " * (len(target_line) - len(target_line.lstrip()))
                params = []
                param_m = re.search(r'\((.*?)\)', target_line)
                if param_m:
                    raw_args = param_m.group(1).split(',')
                    for a in raw_args:
                        a_clean = a.strip()
                        if a_clean and a_clean not in ('self', 'cls', 'this'):
                            p_name = a_clean.split(':')[0].split('=')[0].strip().split()[-1].lstrip('*&')
                            if p_name and p_name.isidentifier():
                                params.append(p_name)

                if lang in ('py', 'python'):
                    body_indent = indent + "    "
                    doc = DocumentationGenerator.describe_name(target_sym.name)
                    doc_block = f'\n{body_indent}"""{doc}\n'
                    if params:
                        doc_block += f'\n{body_indent}Args:\n'
                        for p in params:
                            doc_block += f'{body_indent}    {p}: {DocumentationGenerator.describe_param(p)}\n'
                    doc_block += f'{body_indent}"""'
                    lines[target_sym.line - 1] += doc_block
                else:
                    doc = DocumentationGenerator.generate_multilang_docstring(
                        target_sym.name, target_sym.kind, lang, params, indent=indent
                    )
                    doc_lines = doc.rstrip('\n').splitlines()
                    for dl in reversed(doc_lines):
                        lines.insert(target_sym.line - 1, dl)

                cursor.beginEditBlock()
                self.editor.setPlainText("\n".join(lines))
                self._jump_to_line(target_sym.line)
                cursor.endEditBlock()
                return

        # 4. If selected text or arbitrary block, insert explanatory header
        if cursor.hasSelection():
            cursor.beginEditBlock()
            selected = cursor.selectedText().replace('\u2029', '\n')
            pfx = "//" if lang not in ('py', 'python') else "#"
            commented = f"{pfx} --- Логический блок ---\n" + "\n".join(f"{pfx} {l}" if l.strip() else "" for l in selected.splitlines()) + f"\n{selected}"
            cursor.insertText(commented)
            cursor.endEditBlock()
            return

        QMessageBox.information(self, "Генератор Docstring", "Установите курсор внутрь функции, метода или класса для добавления описания.")

    def generate_docstrings_entire_file(self):
        """Generate high-quality documentation for all classes, functions and module in the entire file."""
        code = self.editor.toPlainText()
        if not code.strip():
            return

        lang = self._detect_language()
        is_python = lang in ('py', 'python')
        filepath = getattr(self.modern_editor, 'file_path', None)
        filename = os.path.basename(filepath) if filepath else "модуля"

        if is_python:
            try:
                tree = ast.parse(code)
                has_module_doc = ast.get_docstring(tree) is not None
                lines = code.splitlines()
                insertions = []

                if not has_module_doc:
                    classes_count = len([n for n in tree.body if isinstance(n, ast.ClassDef)])
                    funcs_count = len([n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
                    mod_doc = (
                        f'"""Модуль {filename}.\n\n'
                        f'Предоставляет компоненты и функции для работы проекта ({classes_count} классов, {funcs_count} функций).\n'
                        f'"""\n'
                    )
                    insertions.append((1, mod_doc, True))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if ast.get_docstring(node) is None:
                            doc = DocumentationGenerator.generate_function_docstring(node)
                            insertions.append((node.lineno, doc, False))
                    elif isinstance(node, ast.ClassDef):
                        if ast.get_docstring(node) is None:
                            doc = DocumentationGenerator.generate_class_docstring(node)
                            insertions.append((node.lineno, doc, False))

                if not insertions:
                    QMessageBox.information(self, "Документирование", "Все функции и классы в файле уже имеют документацию!")
                    return

                insertions.sort(key=lambda x: x[0], reverse=True)
                cursor = self.editor.textCursor()
                cursor.beginEditBlock()
                try:
                    for line_no, doc_text, is_mod in insertions:
                        if is_mod:
                            lines.insert(0, doc_text.rstrip('\n'))
                        else:
                            lines[line_no - 1] += doc_text
                    self.editor.setPlainText("\n".join(lines))
                finally:
                    cursor.endEditBlock()

                QMessageBox.information(self, "Документирование завершено", f"Успешно созданы описания и docstrings для {len(insertions)} компонентов файла!")
                return
            except SyntaxError:
                pass

        # Multi-language or generic symbol fallback
        if not self._symbols:
            self._parse_symbols(code)
        if not self._symbols:
            QMessageBox.information(self, "Документирование", "В файле не найдено функций или классов для документирования.")
            return

        lines = code.splitlines()
        syms_sorted = sorted(self._symbols, key=lambda s: s.line, reverse=True)
        count = 0

        for sym in syms_sorted:
            line_idx = sym.line - 1
            if line_idx >= len(lines):
                continue

            prev_idx = line_idx - 1
            if prev_idx >= 0 and any(lines[prev_idx].strip().startswith(p) for p in ('*/', '///', '//', '*', '#', '"""', "'''")):
                continue

            target_line = lines[line_idx]
            indent = " " * (len(target_line) - len(target_line.lstrip()))
            params = []
            param_m = re.search(r'\((.*?)\)', target_line)
            if param_m:
                raw_args = param_m.group(1).split(',')
                for a in raw_args:
                    a_clean = a.strip()
                    if a_clean and a_clean not in ('self', 'cls', 'this'):
                        p_name = a_clean.split(':')[0].split('=')[0].strip().split()[-1].lstrip('*&')
                        if p_name and p_name.isidentifier():
                            params.append(p_name)

            doc = DocumentationGenerator.generate_multilang_docstring(
                sym.name, sym.kind, lang, params, indent=indent
            )
            doc_lines = doc.rstrip('\n').splitlines()
            for dl in reversed(doc_lines):
                lines.insert(line_idx, dl)
            count += 1

        if count == 0:
            QMessageBox.information(self, "Документирование", "Все функции и классы в файле уже имеют описания!")
            return

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        try:
            self.editor.setPlainText("\n".join(lines))
        finally:
            cursor.endEditBlock()

        QMessageBox.information(self, "Документирование завершено", f"Успешно созданы описания для {count} компонентов файла!")

    def find_symbol_references(self):
        """Find occurrences of the word/symbol under cursor in the current project."""
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QtGui.QTextCursor.WordUnderCursor)
        word = cursor.selectedText().strip()

        if not word:
            return

        main_win = self.window()
        search_panel = getattr(main_win, 'search_panel', None)
        # SearchPanel exposes ``query`` (a QLineEdit) and ``search()``.
        if search_panel is not None and hasattr(search_panel, 'query'):
            if hasattr(main_win, 'activity_bar'):
                main_win.activity_bar.set_activity("search")
            search_panel.query.setText(word)
            if hasattr(search_panel, 'search'):
                search_panel.search()
            return

        # Fallback: in-file find bar.
        if hasattr(self.modern_editor, 'show_find_bar'):
            self.modern_editor.show_find_bar()
            find_bar = getattr(self.modern_editor, 'find_bar', None)
            if find_bar is not None:
                find_bar.find_input.setText(word)
                find_bar.find_next()
