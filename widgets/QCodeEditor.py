import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize, QEvent
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence, QTextCharFormat, QPainter, QPen, QLinearGradient, QTextBlock, QMouseEvent, QKeyEvent
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QTextEdit
from utils.CodeAnalyzer import *

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
        if event.modifiers() & Qt.AltModifier:
            # Начало прямоугольного выделения
            self.selection_mode = SelectionMode.RECTANGLE
            self.is_selecting_rectangle = True
            self.rectangle_start_pos = event.pos()
            self.rectangle_end_pos = event.pos()
            self.rectangleSelectionChanged.emit(True)
        else:
            self.selection_mode = SelectionMode.NORMAL
            self.is_selecting_rectangle = False
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
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатия клавиш"""
        # Alt + мышка уже обрабатывается в mousePressEvent
        # Alt + клавиши для управления прямоугольным выделением
        if event.key() == Qt.Key_Escape and self.selection_mode == SelectionMode.RECTANGLE:
            self.selection_mode = SelectionMode.NORMAL
            self.rectangle_selections.clear()
            self.rectangleSelectionChanged.emit(False)
            self.viewport().update()
            return
            
        super().keyPressEvent(event)
    
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
            cursor = QTextCursor(self.document().findBlockByNumber(line))
            
            # Перемещаем курсор в пределах строки
            line_text = cursor.block().text()
            line_length = len(line_text)
            
            # Если строка достаточно длинная для выделения
            if start_col <= line_length:
                actual_end_col = min(end_col, line_length)
                cursor.setPosition(cursor.block().position() + start_col)
                cursor.setPosition(cursor.block().position() + actual_end_col, QTextCursor.KeepAnchor)
                
                # Создаем дополнительное выделение
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                
                # Стиль для прямоугольного выделения
                selection.format.setBackground(QColor("#264F78"))
                selection.format.setForeground(QColor("#FFFFFF"))
                selection.format.setProperty(QTextCharFormat.FullWidthSelection, False)
                
                self.rectangle_selections.append(selection)
    
    def finalize_rectangle_selection(self):
        """Финализация прямоугольного выделения"""
        if self.rectangle_selections:
            # Устанавливаем курсор в начало выделения
            first_selection = self.rectangle_selections[0]
            self.setTextCursor(first_selection.cursor)
            
            # Устанавливаем дополнительные выделения
            self.setExtraSelections(self.rectangle_selections)
        else:
            self.setExtraSelections([])
    
    def paintEvent(self, event):
        """Отрисовка редактора с прямоугольным выделением"""
        # Сначала рисуем стандартный редактор
        super().paintEvent(event)
        
        # Если идет процесс прямоугольного выделения, рисуем прямоугольник
        if self.is_selecting_rectangle:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor("#007ACC"), 1, Qt.DashLine))
            painter.setBrush(QColor(0, 122, 204, 30))  # Полупрозрачная заливка
            
            # Вычисляем прямоугольник
            rect = QRect(self.rectangle_start_pos, self.rectangle_end_pos).normalized()
            painter.drawRect(rect)
    
    def get_rectangle_selection_text(self) -> str:
        """Получение текста из прямоугольного выделения"""
        if not self.rectangle_selections:
            return ""
        
        lines = []
        for selection in self.rectangle_selections:
            cursor = selection.cursor
            text = cursor.selectedText()
            lines.append(text)
        
        return "\n".join(lines)
    
    def insert_text_in_rectangle(self, text: str):
        """Вставка текста в прямоугольное выделение"""
        if not self.rectangle_selections:
            return
        
        # Начинаем редактирование
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        try:
            # Разбиваем вставляемый текст на строки
            lines_to_insert = text.split('\n')
            
            # Вставляем текст в каждую строку выделения
            for i, selection in enumerate(self.rectangle_selections):
                if i < len(lines_to_insert):
                    insert_text = lines_to_insert[i]
                else:
                    # Если строк меньше, чем выделений, используем последнюю строку
                    insert_text = lines_to_insert[-1] if lines_to_insert else ""
                
                selection.cursor.insertText(insert_text)
            
            # Обновляем выделение
            self.update_rectangle_selection()
            
        finally:
            cursor.endEditBlock()
    
    def delete_rectangle_selection(self):
        """Удаление прямоугольного выделения"""
        if not self.rectangle_selections:
            return
        
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        try:
            # Удаляем текст в каждом выделении
            for selection in self.rectangle_selections:
                selection.cursor.removeSelectedText()
            
            # Очищаем выделения
            self.rectangle_selections.clear()
            self.setExtraSelections([])
            
        finally:
            cursor.endEditBlock()
    
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


class CodeEditor(EnhancedTextEdit):
    """Основной редактор кода с поддержкой различных языков и прямоугольного выделения"""
    
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
    
    def _on_rectangle_selection_changed(self, active: bool):
        """Обработка изменения режима прямоугольного выделения"""
        if active:
            # Меняем курсор на крестик для прямоугольного выделения
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            # Возвращаем стандартный курсор
            self.viewport().setCursor(Qt.IBeamCursor)
    
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
        
        # Добавляем прямоугольные выделения, если они есть
        if hasattr(self, 'rectangle_selections'):
            extra_selections.extend(self.rectangle_selections)
        
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
        """Обработка нажатий клавиш с поддержкой прямоугольного выделения"""
        # Если активно прямоугольное выделение, обрабатываем специальные команды
        if self.selection_mode == SelectionMode.RECTANGLE and self.rectangle_selections:
            if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
                self.delete_rectangle_selection()
                return
            elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
                self.copy_rectangle_selection()
                return
            elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_X:
                self.cut_rectangle_selection()
                return
            elif event.key() in (Qt.Key_Enter, Qt.Key_Return):
                # Вставка новой строки в каждую строку прямоугольного выделения
                self.insert_text_in_rectangle("\n")
                return
            elif event.text() and not event.modifiers():
                # Вставка текста в прямоугольное выделение
                self.insert_text_in_rectangle(event.text())
                return
        
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
    """Современный редактор кода с поддержкой различных языков и прямоугольного выделения"""
    
    rectangleSelectionActive = pyqtSignal(bool)
    
    def __init__(self, parent=None, language: str = "", settings: dict = None):
        super().__init__(parent)
        self.language = language
        self.settings = settings or {}
        self.file_path = None
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_status_bar()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.editor = CodeEditor(language=self.language, settings=self.settings)
        layout.addWidget(self.editor)
    
    def _setup_status_bar(self):
        """Настройка статус-бара"""
        self.status_bar = QLabel()
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #1E1E1E;
                color: #D4D4D4;
                padding: 4px 8px;
                border-top: 1px solid #3C3C3C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
        """)
        
        layout = self.layout()
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        # Добавляем статус-бар в основной layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(status_layout)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Устанавливаем новый layout
        self.setLayout(main_layout)
        
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
        
        self.status_bar.setText(f"Ln {line}, Col {column} | Lines: {lines} | Mode: {mode}{rect_info}")
    
    def _setup_shortcuts(self):
        """Настройка горячих клавиш"""
        shortcuts = {
            "Ctrl+=": self._zoom_in,
            "Ctrl+-": self._zoom_out,
            "Ctrl+0": self._reset_zoom,
            "Ctrl+/": self._toggle_comment,
            "Ctrl+D": self._duplicate_line,
            "Ctrl+Shift+K": self._delete_line,
            "Alt+LeftButton": self._start_rectangle_selection,
            "Escape": self._cancel_rectangle_selection,
            "Alt+C": self._copy_rectangle,
            "Alt+X": self._cut_rectangle,
            "Alt+V": self._paste_rectangle,
            "Alt+Delete": self._delete_rectangle,
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


# Демонстрационный пример использования
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    settings = {
        "fontsize": 14,
        "text_color": "#D4D4D4",
        "second_color": "#1E1E1E",
        "accent_color": "#007ACC"
    }
    
    # Создаем редактор с примером кода
    editor = ModernCodeEditor(language="py", settings=settings)
    
    example_code = '''# Пример кода для демонстрации прямоугольного выделения
# Нажмите Alt и выделите прямоугольник мышкой

class User:
    def __init__(self, name, age, email):
        self.name = name
        self.age = age
        self.email = email
    
    def display_info(self):
        print(f"Name: {self.name}")
        print(f"Age: {self.age}")
        print(f"Email: {self.email}")

# Список пользователей
users = [
    User("Alice", 25, "alice@example.com"),
    User("Bob", 30, "bob@example.com"),
    User("Charlie", 35, "charlie@example.com"),
]

# Вывод информации
for user in users:
    user.display_info()
'''
    
    editor.set_code(example_code)
    editor.setWindowTitle("Modern Code Editor - Rectangle Selection Demo")
    editor.resize(800, 600)
    editor.show()
    
    # Выводим горячие клавиши для прямоугольного выделения
    print("=" * 60)
    print("ПРЯМОУГОЛЬНОЕ ВЫДЕЛЕНИЕ - ГОРЯЧИЕ КЛАВИШИ:")
    print("=" * 60)
    print("Alt + ЛКМ - Начать прямоугольное выделение")
    print("Alt + C - Копировать прямоугольное выделение")
    print("Alt + X - Вырезать прямоугольное выделение")
    print("Alt + V - Вставить в прямоугольное выделение")
    print("Alt + Delete - Удалить прямоугольное выделение")
    print("Escape - Отменить прямоугольное выделение")
    print("=" * 60)
    
    sys.exit(app.exec_())