# widgets/TerminalWidget.py
import subprocess
import sys
import os
import codecs
from pathlib import Path

from PyQt5.QtCore import Qt, QProcess, QTimer, QByteArray, QProcessEnvironment
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QTextEdit, QLineEdit, QLabel, QPushButton, QShortcut)

class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.current_working_dir = None
        self.encoding = 'utf-8'
        self.command_history = []
        self.current_history_index = -1
        self.setup_ui()
        self.start_shell()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel("Terminal")
        self.status_label.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        
        self.dir_label = QLabel("")
        self.dir_label.setStyleSheet("color: #888888;")
        
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
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
        clear_btn.clicked.connect(self.clear_terminal)
        
        stop_btn = QPushButton("Stop")
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a1e1e;
                color: #CCCCCC;
                border: 1px solid #7a2e2e;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #6a2e2e;
            }
        """)
        stop_btn.clicked.connect(self.stop_process)
        
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.dir_label)
        header_layout.addWidget(stop_btn)
        header_layout.addWidget(clear_btn)
        
        # Terminal output
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                border: 1px solid #444444;
                border-radius: 4px;
                line-height: 1.4;
            }
        """)
        
        # Input area
        input_layout = QHBoxLayout()
        self.prompt_label = QLabel("$")
        self.prompt_label.setStyleSheet("color: #569CD6; font-weight: bold;")
        self.prompt_label.setFixedWidth(20)
        
        self.input_line = QLineEdit()
        self.input_line.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #007ACC;
            }
        """)
        self.input_line.textChanged.connect(self._highlight_input)
        self.input_line.returnPressed.connect(self.execute_command)
        
        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.input_line)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.output_text)
        layout.addLayout(input_layout)
    
    def keyPressEvent(self, event):
        """Обработка горячих клавиш для истории команд"""
        if event.key() == Qt.Key_Up and self.command_history:
            if self.current_history_index > 0:
                self.current_history_index -= 1
                self.input_line.setText(self.command_history[self.current_history_index])
        elif event.key() == Qt.Key_Down and self.command_history:
            if self.current_history_index < len(self.command_history) - 1:
                self.current_history_index += 1
                self.input_line.setText(self.command_history[self.current_history_index])
            else:
                self.current_history_index = len(self.command_history)
                self.input_line.clear()
        else:
            super().keyPressEvent(event)

    def _highlight_input(self):
        """Подсветка вводимой команды"""
        text = self.input_line.text()
        # Простая подсветка: меняем цвет если команда начинается с определенных префиксов
        if text.startswith(('python', 'py ')):
            self.input_line.setStyleSheet("color: #569CD6;")
        elif text.startswith(('npm', 'node ')):
            self.input_line.setStyleSheet("color: #4EC9B0;")
        elif text.startswith(('git ')):
            self.input_line.setStyleSheet("color: #F44747;")
        else:
            self.input_line.setStyleSheet("color: #CCCCCC;")
        
    def start_shell(self):
        """Запускает shell процесс"""
        if self.process:
            self.process.terminate()
            self.process.waitForFinished(1000)
            
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.finished.connect(self.process_finished)
        
        # Устанавливаем переменные окружения для корректной кодировки
        env = QProcessEnvironment.systemEnvironment()
        if os.name == 'nt':  # Windows
            env.insert("PYTHONIOENCODING", "utf-8")
            self.encoding = 'cp866'  # Кодировка для русской Windows
            self.prompt_label.setText(">")
            # Запускаем cmd с поддержкой расширенных команд
            self.process.start('cmd.exe', ['/K', 'echo Terminal started...'])
        else:  # Unix-like
            env.insert("LANG", "en_US.UTF-8")
            env.insert("LC_ALL", "en_US.UTF-8")
            self.encoding = 'utf-8'
            self.prompt_label.setText("$")
            self.process.start('/bin/bash', ['-i'])
        
        self.process.setProcessEnvironment(env)
        
        if self.process.waitForStarted(5000):
            self.append_output("Terminal started...\n")
        else:
            self.append_output("Failed to start terminal!\n", is_error=True)
        
    def execute_command(self):
        """Выполняет команду из input"""
        command = self.input_line.text().strip()
        if not command:
            return
            
        # Добавляем в историю
        if not self.command_history or self.command_history[-1] != command:
            self.command_history.append(command)
        self.current_history_index = len(self.command_history)
        
        self.append_output(f"$ {command}\n", is_command=True)
        self.input_line.clear()
        
        # Пишем команду в процесс с небольшой задержкой для стабильности
        if self.process and self.process.state() == QProcess.Running:
            QTimer.singleShot(10, lambda: self.process.write((command + "\r\n").encode(self.encoding)))
            
    def read_output(self):
        """Читает stdout процесса с обработкой ошибок кодировки"""
        if self.process:
            try:
                data = self.process.readAllStandardOutput().data()
                decoded_data = self.try_decode_data(data)
                if decoded_data:
                    self.append_output(decoded_data)
            except Exception as e:
                self.append_output(f"[Decode error: {str(e)}]\n", is_error=True)
                
    def read_error(self):
        """Читает stderr процесса с обработкой ошибок кодировки"""
        if self.process:
            try:
                data = self.process.readAllStandardError().data()
                decoded_data = self.try_decode_data(data)
                if decoded_data:
                    self.append_output(decoded_data, is_error=True)
            except Exception as e:
                self.append_output(f"[Decode error: {str(e)}]\n", is_error=True)
                
    def try_decode_data(self, data: QByteArray) -> str:
        """Пытается декодировать данные разными кодировками"""
        if not data:
            return ""
            
        encodings_to_try = [self.encoding, 'utf-8', 'cp1251', 'cp866', 'iso-8859-1', 'latin1']
        
        for encoding in encodings_to_try:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
                
        # Если все кодировки не подошли, используем замену ошибок
        try:
            return data.decode('utf-8', errors='replace')
        except:
            return "[Binary data]\n"
            
    def append_output(self, text, is_error=False, is_command=False):
        """Добавляет текст в вывод терминала с улучшенной подсветкой"""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        
        if is_error:
            format.setForeground(QColor("#F44747"))  # Красный для ошибок
            format.setFontWeight(QFont.Bold)
        elif is_command:
            format.setForeground(QColor("#569CD6"))  # Синий для команд
            format.setFontWeight(QFont.Bold)
        else:
            format.setForeground(QColor("#CCCCCC"))  # Стандартный цвет
            
        cursor.setCharFormat(format)
        cursor.insertText(text)
        
        # Прокрутка вниз
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
        
    def clear_terminal(self):
        """Очищает терминал"""
        self.output_text.clear()
        
    def stop_process(self):
        """Останавливает текущий процесс"""
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            self.append_output("\n[Process stopped]\n", is_error=True)
            QTimer.singleShot(1000, self.start_shell)  # Перезапускаем shell
        
    def process_finished(self):
        """Обработчик завершения процесса"""
        self.append_output("\n[Process finished]\n")
        # Автоматически перезапускаем shell
        QTimer.singleShot(100, self.start_shell)
        
    def run_code(self, file_path, args="", working_dir=None):
        """Запускает код в терминале с улучшенной обработкой"""
        # Если это команда (содержит && или |), а не файл
        if "&&" in str(file_path) or "|" in str(file_path) or not Path(file_path).exists():
            command = str(file_path)
            self._execute_complex_command(command, working_dir)
            return
            
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            self.append_output(f"Error: File not found - {file_path}\n", is_error=True)
            return
            
        # Устанавливаем рабочую директорию
        if working_dir:
            self.current_working_dir = Path(working_dir)
        else:
            self.current_working_dir = file_path_obj.parent
            
        # Определяем команду запуска по расширению
        extension = file_path_obj.suffix.lower()
        command = self.get_run_command(file_path_obj, extension, args)
        
        if command:
            self.append_output(f"Running: {command}\n", is_command=True)
            if self.process and self.process.state() == QProcess.Running:
                # Используем сложную команду для гарантированного выполнения
                full_command = f'cd /d "{self.current_working_dir}" && {command}'
                self._execute_complex_command(full_command)

    def _execute_complex_command(self, command, working_dir=None):
        """Выполняет сложные команды с улучшенной стабильностью"""
        if self.process and self.process.state() == QProcess.Running:
            # Добавляем небольшую задержку для стабильности
            if working_dir:
                cd_command = f'cd /d "{working_dir}"\r\n'
                self.process.write(cd_command.encode(self.encoding))
                QTimer.singleShot(50, lambda: self.process.write((command + "\r\n").encode(self.encoding)))
            else:
                QTimer.singleShot(10, lambda: self.process.write((command + "\r\n").encode(self.encoding)))

    def get_run_command(self, file_path, extension, args):
        """Генерирует команду запуска для разных языков"""
        file_path_str = str(file_path)
        
        commands = {
            '.py': f'python "{file_path_str}" {args}',
            '.js': f'node "{file_path_str}" {args}',
            '.java': f'javac "{file_path_str}" && java "{file_path.stem}" {args}',
            '.cpp': f'g++ "{file_path_str}" -o "{file_path.stem}" && "./{file_path.stem}" {args}',
            '.c': f'gcc "{file_path_str}" -o "{file_path.stem}" && "./{file_path.stem}" {args}',
            '.php': f'php "{file_path_str}" {args}',
            '.rb': f'ruby "{file_path_str}" {args}',
            '.pl': f'perl "{file_path_str}" {args}',
            '.sh': f'bash "{file_path_str}" {args}',
            '.asm': f'cd /d "{file_path.parent}" && ASM6X.EXE "{file_path.name}" && LNK6X.EXE "{file_path.stem}.obj" -o "{file_path.stem}.out" && SIM62X.EXE',
        }
        
        return commands.get(extension, f'"{file_path_str}" {args}')
        
    def closeEvent(self, event):
        """Останавливает процесс при закрытии"""
        if self.process:
            if self.process.state() == QProcess.Running:
                self.process.terminate()
                self.process.waitForFinished(1000)
            self.process = None
        super().closeEvent(event)