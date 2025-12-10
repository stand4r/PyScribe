# widgets/TerminalWidget.py
import subprocess
import sys
import os
import platform

from PyQt5.QtCore import Qt, QProcess, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QTextEdit, QLineEdit, QLabel, QPushButton, 
                            QShortcut, QTabWidget)

class TerminalTab(QWidget):
    """Один таб терминала"""
    
    output_received = pyqtSignal(str)
    
    def __init__(self, tab_id, title="Terminal", working_dir=None, parent=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self.title = title
        self.working_dir = working_dir or os.getcwd()
        self.process = None
        
        self.setup_ui()
        self.start_shell()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Terminal output
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border: none;
                padding: 8px;
            }
        """)
        
        layout.addWidget(self.output_text)
        
    def start_shell(self):
        """Запускает shell"""
        self.process = QProcess()
        self.process.setWorkingDirectory(self.working_dir)
        
        if platform.system() == 'Windows':
            self.process.start('cmd.exe')
        else:
            self.process.start('/bin/bash')
        
        # Подключаем вывод
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        
    def read_output(self):
        """Читает stdout"""
        if self.process:
            data = self.process.readAllStandardOutput().data()
            try:
                if platform.system() == 'Windows':
                    text = data.decode('cp866')
                else:
                    text = data.decode('utf-8')
                self.append_output(text)
            except:
                self.append_output("Error [Fail decode]\n")
                
    def read_error(self):
        """Читает stderr"""
        if self.process:
            data = self.process.readAllStandardError().data()
            try:
                text = data.decode('utf-8', errors='replace')
                self.append_output(text)
            except:
                self.append_output("[Error]\n")
                
    def append_output(self, text):
        """Добавляет текст в вывод"""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
        
    def write_input(self, text):
        """Отправляет команду в shell"""
        if self.process and self.process.state() == QProcess.Running:
            # Показываем команду
            self.append_output(f"> {text}\n")
            
            # Отправляем команду
            if platform.system() == 'Windows':
                self.process.write(f"{text}\r\n".encode('cp866'))
            else:
                self.process.write(f"{text}\n".encode('utf-8'))
            return True
        return False
        
    def clear(self):
        """Очищает терминал"""
        self.output_text.clear()
        
    def kill(self):
        """Завершает процесс"""
        if self.process:
            self.process.kill()


class TerminalWidget(QWidget):
    """Виджет терминала с вкладками"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = {}
        self.next_tab_id = 1
        self.current_tab = None
        self.command_history = []
        
        self.setup_ui()
        self.create_new_tab()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Панель вкладок
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)
        
        # Кнопки управления
        controls = QHBoxLayout()
        
        btn_new = QPushButton("+")
        btn_new.clicked.connect(self.create_new_tab)
        btn_new.setFixedWidth(30)
        
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.clear_current)
        
        btn_kill = QPushButton("Kill")
        btn_kill.clicked.connect(self.kill_current)
        
        controls.addWidget(btn_new)
        controls.addWidget(btn_clear)
        controls.addWidget(btn_kill)
        controls.addStretch()
        
        # Поле ввода
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Enter command...")
        self.input_line.returnPressed.connect(self.execute_command)
        
        btn_send = QPushButton("▶")
        btn_send.clicked.connect(self.execute_command)
        btn_send.setFixedWidth(40)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("$"))
        input_layout.addWidget(self.input_line)
        input_layout.addWidget(btn_send)
        
        # Собираем всё
        layout.addLayout(controls)
        layout.addWidget(self.tab_widget)
        layout.addLayout(input_layout)
        
        # Горячие клавиши
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.create_new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close_current_tab)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.clear_current)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.send_ctrl_c)
        
    def create_new_tab(self):
        """Создаёт новую вкладку"""
        tab_id = self.next_tab_id
        self.next_tab_id += 1
        
        tab = TerminalTab(tab_id, f"Terminal {tab_id}")
        self.tabs[tab_id] = tab
        self.tab_widget.addTab(tab, f"Terminal {tab_id}")
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
        
        self.current_tab = tab_id
        
    def close_tab(self, index):
        """Закрывает вкладку"""
        tab_id = list(self.tabs.keys())[index] if index < len(self.tabs) else None
        if tab_id:
            tab = self.tabs[tab_id]
            tab.kill()
            self.tab_widget.removeTab(index)
            del self.tabs[tab_id]
            
            if self.tab_widget.count() == 0:
                self.create_new_tab()
                
    def close_current_tab(self):
        """Закрывает текущую вкладку"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            self.close_tab(index)
            
    def tab_changed(self, index):
        """Обработчик смены вкладки"""
        if index >= 0:
            tab_ids = list(self.tabs.keys())
            if index < len(tab_ids):
                self.current_tab = tab_ids[index]
                
    def execute_command(self):
        """Выполняет команду"""
        command = self.input_line.text().strip()
        if not command or not self.current_tab:
            return
            
        # Добавляем в историю
        if not self.command_history or self.command_history[-1] != command:
            self.command_history.append(command)
            
        # Отправляем команду
        tab = self.tabs[self.current_tab]
        tab.write_input(command)
        
        self.input_line.clear()
        
    def clear_current(self):
        """Очищает текущий терминал"""
        if self.current_tab in self.tabs:
            self.tabs[self.current_tab].clear()
            
    def kill_current(self):
        """Завершает текущий процесс и перезапускает"""
        if self.current_tab in self.tabs:
            tab = self.tabs[self.current_tab]
            tab.kill()
            # Перезапускаем shell
            QTimer.singleShot(100, tab.start_shell)
            
    def send_ctrl_c(self):
        """Отправляет Ctrl+C"""
        if self.current_tab in self.tabs:
            tab = self.tabs[self.current_tab]
            if platform.system() == 'Windows':
                tab.write_input("\x03")
            else:
                tab.write_input("\x03")
                
    def closeEvent(self, event):
        """Завершает все процессы при закрытии"""
        for tab in self.tabs.values():
            tab.kill()
        super().closeEvent(event)