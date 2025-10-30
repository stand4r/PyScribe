# widgets/ConsoleWidget.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                            QTextEdit, QListWidget, QListWidgetItem, QPushButton,
                            QLabel, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from .TerminalWidget import TerminalWidget

class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Создаем табвиджет для вкладок
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.South)
        
        # Стиль для табов
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #1E1E1E;
            }
            QTabBar::tab {
                background-color: #2D2D30;
                color: #CCCCCC;
                padding: 8px 16px;
                border: 1px solid #555555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border-color: #0078D4;
            }
            QTabBar::tab:hover:!selected {
                background-color: #383838;
            }
        """)
        
        # Вкладка Problems
        self.problems_widget = self.create_problems_tab()
        self.tab_widget.addTab(self.problems_widget, "Problems")
        
        # Вкладка Output
        self.output_widget = self.create_output_tab()
        self.tab_widget.addTab(self.output_widget, "Output")
        
        # Вкладка Terminal
        self.terminal_widget = TerminalWidget(self)
        self.tab_widget.addTab(self.terminal_widget, "Terminal")
        
        layout.addWidget(self.tab_widget)
    
    def create_problems_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Панель инструментов для Problems
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 5, 5, 5)
        
        problems_label = QLabel("Problems")
        problems_label.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        
        self.clear_problems_btn = QPushButton("Clear")
        self.clear_problems_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.clear_problems_btn.clicked.connect(self.clear_problems)
        
        toolbar.addWidget(problems_label)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_problems_btn)
        
        # Список проблем
        self.problems_list = QListWidget()
        self.problems_list.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:hover {
                background-color: #2A2D2E;
            }
        """)
        
        layout.addLayout(toolbar)
        layout.addWidget(self.problems_list)
        
        return widget
    
    def create_output_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Панель инструментов для Output
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 5, 5, 5)
        
        output_label = QLabel("Output")
        output_label.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        
        self.clear_output_btn = QPushButton("Clear")
        self.clear_output_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.clear_output_btn.clicked.connect(self.clear_output)
        
        toolbar.addWidget(output_label)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_output_btn)
        
        # Текстовое поле для вывода
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        layout.addLayout(toolbar)
        layout.addWidget(self.output_text)
        
        return widget
    
    def add_problem(self, problem_type, file_path, line, description):
        """Добавляет проблему в список"""
        item_text = f"{file_path}:{line} - {description}"
        item = QListWidgetItem(item_text)
        
        # Цвет в зависимости от типа проблемы
        if problem_type == "error":
            item.setForeground(QColor("#F44747"))
        elif problem_type == "warning":
            item.setForeground(QColor("#FF8800"))
        else:
            item.setForeground(QColor("#CCCCCC"))
            
        self.problems_list.addItem(item)
    
    def append_output(self, text, is_error=False):
        """Добавляет текст в вывод"""
        cursor = self.output_text.textCursor()
        cursor.movePosition(cursor.End)
        
        if is_error:
            self.output_text.setTextColor(QColor("#F44747"))
        else:
            self.output_text.setTextColor(QColor("#CCCCCC"))
            
        cursor.insertText(text)
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
    
    def clear_problems(self):
        """Очищает список проблем"""
        self.problems_list.clear()
    
    def clear_output(self):
        """Очищает вывод"""
        self.output_text.clear()
    
    def get_terminal(self):
        """Возвращает терминал для внешнего использования"""
        return self.terminal_widget
    
    def set_current_tab(self, tab_name):
        """Устанавливает текущую вкладку по имени"""
        tab_names = ["Problems", "Output", "Terminal"]
        if tab_name in tab_names:
            index = tab_names.index(tab_name)
            self.tab_widget.setCurrentIndex(index)