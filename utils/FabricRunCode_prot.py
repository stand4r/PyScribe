import asyncio
import subprocess
from abc import ABC, abstractmethod
from os import path
from subprocess import PIPE, Popen, check_output, CalledProcessError
from sys import platform
from concurrent.futures import ThreadPoolExecutor
import shlex
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QLineEdit, QPushButton, QLabel, QSplitter, 
                             QTabWidget, QComboBox, QMenu, QAction, QSizePolicy)
from PyQt5.QtCore import Qt, QProcess, QTimer, pyqtSignal, QByteArray, QEvent
from PyQt5.QtGui import (QFont, QTextCursor, QColor, QTextCharFormat, QKeySequence, 
                        QSyntaxHighlighter, QKeyEvent, QPalette)

def safe_path(file_path):
    """Безопасное экранирование пути для командной строки"""
    try:
        normalized = os.path.normpath(file_path)
        
        # Для Windows: всегда используем двойные кавычки для путей
        if platform == "win32":
            # Заменяем прямые слеши на обратные для Windows
            normalized = normalized.replace('/', '\\')
            return f'"{normalized}"'
        else:
            # Для Unix: используем shlex.quote
            return shlex.quote(normalized)
    except Exception as e:
        print(f"Error in safe_path: {e}")
        return f'"{file_path}"'
    
class FabricFoundTerminalClass(ABC):
    @abstractmethod
    def get_terminal_command(self, command):
        pass

class WindowsFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        # Для Windows используем двойные кавычки
        return f'cmd /c "{command}"'
    
class LinuxFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        terminals = {
            'alacritty': '-e',
            'xterm': '-e',
            'gnome-terminal': '--',
            'konsole': '-e',
            'xfce4-terminal': '-e',
            'kitty': '-e',
        }

        for terminal, param in terminals.items():
            try:
                term = check_output(['which', terminal]).decode().strip()
                if terminal == 'gnome-terminal':
                    return f'{term} {param} bash -c "{command}; exec bash"'
                else:
                    return f'{term} {param} bash -c "{command}; read -p \\"Press enter to continue...\\""'
            except (CalledProcessError, FileNotFoundError):
                continue
        return f'xterm -e bash -c "{command}; read -p \\"Press enter to continue...\\""'

class OSXFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        return f"osascript -e 'tell app \"Terminal\" to do script \"{command}\"'"

def choice_env(command):
    if platform == "win32":
        return WindowsFoundTerminalClass().get_terminal_command(command)
    elif platform == "linux" or platform == "linux2":
        return LinuxFoundTerminalClass().get_terminal_command(command)
    elif platform == "darwin":
        return OSXFoundTerminalClass().get_terminal_command(command)
    else:
        return ""

def compile_program_c(path: str) -> str:
    if platform == "win32":
        exe_path = path.rsplit(".", 1)[0] + ".exe"
    elif platform == "linux" or platform == "linux2":
        exe_path = path.rsplit(".", 1)[0] + ".out"
    
    # Используем безопасные пути
    safe_file_path = safe_path(path)
    safe_exe_path = safe_path(exe_path)
    
    command = ["gcc", safe_file_path, "-o", safe_exe_path]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return exe_path
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Compilation failed: {e.stderr}") from e

def compile_program_cpp(path: str) -> str:
    if platform == "win32":
        exe_path = path.rsplit(".", 1)[0] + ".exe"
    elif platform == "linux" or platform == "linux2":
        exe_path = path.rsplit(".", 1)[0] + ".out"
    
    # Используем безопасные пути
    safe_file_path = safe_path(path)
    safe_exe_path = safe_path(exe_path)
    
    command = ["g++", safe_file_path, "-o", safe_exe_path]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return exe_path
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Compilation failed: {e.stderr}") from e

class RunCodeClass:
    def __init__(self, pathFile, name, lang, args=""):
        self._path = path.abspath(pathFile)
        self._name = name
        self._args = args
        self.command = ""
        
        # Используем безопасный путь
        safe_file_path = safe_path(self._path)
        
        lang_commands = {
            "py": f"python {safe_file_path} {args}",
            "rb": f"ruby {safe_file_path} {args}",
            "js": f"node {safe_file_path} {args}",
            "php": f"php {safe_file_path} {args}",
            "lua": f"lua {safe_file_path} {args}",
            "pl": f"perl {safe_file_path} {args}",
            "sh": f"bash {safe_file_path} {args}",
            "ts": f"ts-node {safe_file_path} {args}",
        }
        
        if lang in lang_commands:
            self.command = choice_env(lang_commands[lang])
        elif lang == "c":
            try:
                exe = compile_program_c(self._path)
                safe_exe = safe_path(exe)
                self.command = choice_env(f"{safe_exe} {args}")
            except ValueError as e:
                raise e
        elif lang == "cpp":
            try:
                exe = compile_program_cpp(self._path)
                safe_exe = safe_path(exe)
                self.command = choice_env(f"{safe_exe} {args}")
            except ValueError as e:
                raise e
        elif lang == "java":
            # Компиляция и запуск Java
            class_dir = path.dirname(self._path)
            class_name = path.basename(self._path).replace('.java', '')
            
            # Используем безопасные пути
            safe_file_path = safe_path(self._path)
            safe_class_dir = safe_path(class_dir)
            
            compile_cmd = f"javac {safe_file_path}"
            run_cmd = f"java -cp {safe_class_dir} {class_name} {args}"
            self.command = choice_env(f"{compile_cmd} && {run_cmd}")
        else:
            self.command = None

    def process(self):
        if self.command:
            Popen(self.command, shell=True)

def safe_command(command):
    """Безопасное экранирование всей команды"""
    try:
        if platform == "win32":
            # Для Windows просто возвращаем команду как есть (пути уже экранированы)
            return command
        else:
            # Для Unix разбиваем команду на части и экранируем
            parts = command.split(' ', 1)
            if len(parts) == 2:
                return f"{parts[0]} {shlex.quote(parts[1])}"
            return command
    except Exception as e:
        print(f"Error in safe_command: {e}")
        return command

class TerminalHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса для терминала"""
    
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []
        
        # Ошибки (красный)
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#FF6B6B"))
        error_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((r'.*error.*|.*Error.*|.*ERROR.*', error_format))
        
        # Предупреждения (желтый)
        warning_format = QTextCharFormat()
        warning_format.setForeground(QColor("#FFD93D"))
        self.highlighting_rules.append((r'.*warning.*|.*Warning.*|.*WARNING.*', warning_format))
        
        # Успех (зеленый)
        success_format = QTextCharFormat()
        success_format.setForeground(QColor("#6BCF7F"))
        self.highlighting_rules.append((r'.*success.*|.*Success.*|.*SUCCESS.*', success_format))
        
        # Пути (синий)
        path_format = QTextCharFormat()
        path_format.setForeground(QColor("#4DABF7"))
        self.highlighting_rules.append((r'/[\w/\-\.]+|[\w]:\\[^\n\r]*', path_format))
        
        # Команды (бирюзовый)
        command_format = QTextCharFormat()
        command_format.setForeground(QColor("#3BC9DB"))
        self.highlighting_rules.append((r'^\$ .*', command_format))
        
        # Номера строк (серый)
        line_number_format = QTextCharFormat()
        line_number_format.setForeground(QColor("#868E96"))
        self.highlighting_rules.append((r'^\s*\d+\.', line_number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            import re
            expression = re.compile(pattern, re.IGNORECASE)
            for match in expression.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format)

class TerminalTextEdit(QTextEdit):
    """Кастомный QTextEdit для терминала с улучшенным поведением"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        
    def keyPressEvent(self, event: QKeyEvent):
        # Запрещаем редактирование кроме специальных клавиш
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Return, Qt.Key_Enter):
            super().keyPressEvent(event)
        elif event.modifiers() & Qt.ControlModifier:
            super().keyPressEvent(event)

class IntegratedTerminal(QWidget):
    """Встроенный терминал как в Linux"""
    
    commandExecuted = pyqtSignal(str)
    terminalReady = pyqtSignal()
    directoryChanged = pyqtSignal(str)  # Сигнал при смене директории
    
    def __init__(self, parent=None, working_directory=None):
        super().__init__(parent)
        self.working_directory = working_directory or os.getcwd()
        self.process = None
        self.command_history = []
        self.history_index = 0
        self.current_directory = self.working_directory
        self.setup_ui()
        self.start_shell()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Панель заголовка терминала
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)
        
        # Иконка терминала
        icon_label = QLabel("💻")
        icon_label.setStyleSheet("font-size: 14px;")
        
        title_label = QLabel("Terminal")
        title_label.setStyleSheet("""
            color: #E9ECEF; 
            font-weight: bold; 
            font-size: 13px;
        """)
        
        self.path_label = QLabel(self.format_path(self.working_directory))
        self.path_label.setStyleSheet("""
            color: #ADB5BD; 
            font-size: 11px;
            padding: 2px 6px;
            background-color: #495057;
            border-radius: 3px;
        """)
        self.path_label.setWordWrap(True)
        
        # Статус процесса
        self.status_label = QLabel("● Ready")
        self.status_label.setStyleSheet("""
            color: #51CF66;
            font-size: 11px;
            font-weight: bold;
        """)
        
        # Кнопки управления
        button_style = """
            QPushButton {
                background-color: #495057;
                color: #E9ECEF;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 40px;
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
            QPushButton:pressed {
                background-color: #3D4348;
            }
        """
        
        self.kill_button = QPushButton("Stop")
        self.kill_button.setStyleSheet(button_style + """
            QPushButton {
                background-color: #E03131;
            }
            QPushButton:hover {
                background-color: #C92A2A;
            }
            QPushButton:disabled {
                background-color: #495057;
                color: #6C757D;
            }
        """)
        self.kill_button.clicked.connect(self.kill_process)
        self.kill_button.setEnabled(False)
        
        clear_button = QPushButton("Clear")
        clear_button.setStyleSheet(button_style)
        clear_button.clicked.connect(self.clear_terminal)
        
        new_tab_button = QPushButton("+ Tab")
        new_tab_button.setStyleSheet(button_style)
        new_tab_button.clicked.connect(self.create_new_tab)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.path_label, 1)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(clear_button)
        header_layout.addWidget(self.kill_button)
        header_layout.addWidget(new_tab_button)
        
        # Область вывода терминала
        self.output = TerminalTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #0D1117;
                color: #E9ECEF;
                font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                border: none;
                padding: 12px;
                line-height: 1.4;
                selection-background-color: #1C7ED6;
            }
        """)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Подсветка синтаксиса
        self.highlighter = TerminalHighlighter(self.output.document())
        
        # Панель ввода команды
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(8)
        
        self.prompt_label = QLabel(self.get_prompt())
        self.prompt_label.setStyleSheet("""
            color: #3BC9DB; 
            font-weight: bold;
            font-family: 'Cascadia Code', monospace;
            font-size: 13px;
        """)
        self.prompt_label.setFixedWidth(60)
        
        self.input = QLineEdit()
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #161B22;
                color: #E9ECEF;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 8px 12px;
                font-family: 'Cascadia Code', monospace;
                font-size: 13px;
                selection-background-color: #1C7ED6;
            }
            QLineEdit:focus {
                border-color: #1C7ED6;
                background-color: #1C2128;
            }
            QLineEdit:hover {
                border-color: #484F58;
            }
        """)
        self.input.setPlaceholderText("Type command... (Ctrl+C to interrupt)")
        self.input.returnPressed.connect(self.execute_command)
        self.input.textChanged.connect(self.on_input_changed)
        
        # Подсказка автодополнения
        self.suggestion_label = QLabel()
        self.suggestion_label.setStyleSheet("color: #6C757D; font-family: 'Cascadia Code', monospace; font-size: 13px;")
        self.suggestion_label.setFixedWidth(200)
        
        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.suggestion_label)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.output, 1)
        layout.addLayout(input_layout)
        
        # Настройка горячих клавиш
        self.setup_shortcuts()
    
    def get_prompt(self):
        """Получение промпта в зависимости от платформы"""
        if platform == "win32":
            return "C:\\>"
        else:
            username = os.getenv('USER', 'user')
            hostname = os.getenv('HOSTNAME', 'localhost')
            return f"{username}@{hostname}:$"
    
    def format_path(self, path):
        """Форматирование пути для отображения"""
        try:
            home = os.path.expanduser("~")
            if path.startswith(home):
                return "~" + path[len(home):]
            return path
        except:
            return path
    
    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # История команд
        self.input.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """Фильтр событий для обработки горячих клавиш"""
        if obj == self.input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Up:
                self.navigate_history(-1)
                return True
            elif event.key() == Qt.Key_Down:
                self.navigate_history(1)
                return True
            elif event.key() == Qt.Key_Tab:
                self.auto_complete()
                return True
            elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
                self.interrupt_command()
                return True
            elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_L:
                self.clear_terminal()
                return True
        return super().eventFilter(obj, event)
    
    def navigate_history(self, direction):
        """Навигация по истории команд"""
        if not self.command_history:
            return
        
        self.history_index += direction
        self.history_index = max(0, min(self.history_index, len(self.command_history)))
        
        if 0 <= self.history_index < len(self.command_history):
            self.input.setText(self.command_history[self.history_index])
            self.input.deselect()
            self.input.end(False)
    
    def auto_complete(self):
        """Автодополнение команд"""
        current_text = self.input.text()
        if not current_text:
            return
        
        # Простое автодополнение для common commands
        common_commands = ['cd', 'ls', 'dir', 'python', 'node', 'git', 'npm', 'pip']
        for cmd in common_commands:
            if cmd.startswith(current_text.lower()):
                self.input.setText(cmd)
                self.input.end(False)
                break
    
    def interrupt_command(self):
        """Прерывание текущей команды (Ctrl+C)"""
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.append_output("\n^C\n", "error")
            self.update_status("Interrupted", "warning")
            QTimer.singleShot(1000, lambda: self.update_status("Ready", "success"))
    
    def on_input_changed(self, text):
        """Обработчик изменения текста ввода"""
        # Простое предложение команд
        if text.startswith('git '):
            self.suggestion_label.setText("git command...")
        elif text.startswith('npm '):
            self.suggestion_label.setText("npm command...")
        elif text.startswith('python '):
            self.suggestion_label.setText("python script...")
        else:
            self.suggestion_label.clear()
    
    def start_shell(self):
        """Запуск shell процесса"""
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.on_stdout)
        self.process.readyReadStandardError.connect(self.on_stderr)
        self.process.finished.connect(self.on_process_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        self.process.started.connect(self.on_process_started)
        
        # Настройка процесса
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        
        if platform == "win32":
            self.process.start("cmd")
        else:
            self.process.start("bash", ["-i"])  # Интерактивный режим
        
        if self.working_directory:
            self.process.setWorkingDirectory(self.working_directory)
        
        self.update_status("Starting...", "info")
    
    def on_process_started(self):
        """Обработчик запуска процесса"""
        self.kill_button.setEnabled(True)
        self.update_status("Running", "success")
        self.terminalReady.emit()
        
        # Приветственное сообщение
        welcome_msg = f"""
╔═══════════════════════════════════════════════════╗
║                PyScribe Terminal                  ║
║         Developer-friendly command line           ║
╚═══════════════════════════════════════════════════╝

Type 'help' for basic commands or start coding!
Current directory: {self.working_directory}

"""
        self.append_output(welcome_msg, "info")
    
    def execute_command(self):
        """Выполнение команды из input"""
        command = self.input.text().strip()
        if not command:
            return
        
        # Добавляем в историю
        if not self.command_history or self.command_history[-1] != command:
            self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # Отображаем команду
        self.append_output(f"{self.get_prompt()} {command}\n", "command")
        self.input.clear()
        self.suggestion_label.clear()
        
        # Обработка специальных команд
        if command.lower() in ['clear', 'cls']:
            self.clear_terminal()
            return
        elif command.lower() == 'help':
            self.show_help()
            return
        elif command.lower().startswith('cd '):
            self.change_directory(command[3:].strip())
            return
        
        # Отправляем команду в процесс
        if self.process and self.process.state() == QProcess.Running:
            # Экранируем команду перед отправкой
            safe_cmd = safe_command(command)
            self.process.write((safe_cmd + "\n").encode())
            self.commandExecuted.emit(command)
            self.update_status("Executing...", "warning")
    
    def execute_direct_command(self, command):
        """Непосредственное выполнение команды"""
        if self.process and self.process.state() == QProcess.Running:
            self.append_output(f"{self.get_prompt()} {command}\n", "command")
            # Экранируем команду перед отправкой
            safe_cmd = safe_command(command)
            self.process.write((safe_cmd + "\n").encode())
            self.commandExecuted.emit(command)
    
    def execute_python_command(self, file_path, args=""):
        """Выполнение Python команды с правильным экранированием"""
        safe_file_path = safe_path(file_path)
        command = f"python {safe_file_path} {args}".strip()
        self.execute_direct_command(command)
    
    def change_directory(self, new_dir):
        """Смена директории"""
        try:
            if not new_dir:
                new_dir = os.path.expanduser("~")
            
            # Обрабатываем относительные и абсолютные пути
            if os.path.isabs(new_dir):
                target_dir = new_dir
            else:
                target_dir = os.path.join(self.current_directory, new_dir)
            
            target_dir = os.path.abspath(os.path.normpath(target_dir))
            
            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                self.current_directory = target_dir
                self.working_directory = target_dir
                if self.process:
                    self.process.setWorkingDirectory(target_dir)
                self.path_label.setText(self.format_path(target_dir))
                self.append_output(f"Changed directory to: {target_dir}\n", "success")
                self.directoryChanged.emit(target_dir)
            else:
                self.append_output(f"Directory not found: {new_dir}\n", "error")
        except Exception as e:
            self.append_output(f"Error changing directory: {str(e)}\n", "error")
    
    def show_help(self):
        """Показать справку по командам"""
        help_text = """
Common Commands:
  cd <dir>      - Change directory
  ls/dir        - List files
  python <file> - Run Python script
  node <file>   - Run Node.js script
  clear/cls     - Clear terminal

Development:
  npm install   - Install dependencies
  pip install   - Install Python packages
  git <command> - Version control

Shortcuts:
  Ctrl+C        - Interrupt command
  Ctrl+L        - Clear terminal
  ↑/↓           - Command history
  Tab           - Auto-completion

"""
        self.append_output(help_text, "info")
    
    def on_stdout(self):
        """Чтение stdout"""
        data = self.process.readAllStandardOutput()
        text = data.data().decode('utf-8', errors='ignore')
        self.append_output(text)
    
    def on_stderr(self):
        """Чтение stderr"""
        data = self.process.readAllStandardError()
        text = data.data().decode('utf-8', errors='ignore')
        self.append_output(text, "error")
    
    def on_process_finished(self, exit_code, exit_status):
        """Обработчик завершения процесса"""
        self.append_output(f"\nProcess finished with exit code: {exit_code}\n", "info")
        self.kill_button.setEnabled(False)
        self.update_status("Finished", "info")
    
    def on_process_error(self, error):
        """Обработчик ошибки процесса"""
        self.append_output(f"\nProcess error: {error}\n", "error")
        self.kill_button.setEnabled(False)
        self.update_status("Error", "error")
    
    def append_output(self, text, message_type="normal"):
        """Добавление текста в вывод с типом сообщения"""
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Цвета для разных типов сообщений
        colors = {
            "normal": "#E9ECEF",
            "error": "#FF6B6B", 
            "success": "#51CF66",
            "warning": "#FFD93D",
            "info": "#4DABF7",
            "command": "#3BC9DB"
        }
        
        color = colors.get(message_type, "#E9ECEF")
        format = cursor.charFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        
        cursor.insertText(text)
        
        # Возвращаем обычный цвет
        format.setForeground(QColor("#E9ECEF"))
        cursor.setCharFormat(format)
        
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
    
    def update_status(self, status, status_type="normal"):
        """Обновление статуса терминала"""
        colors = {
            "success": "#51CF66",
            "error": "#FF6B6B",
            "warning": "#FFD93D", 
            "info": "#4DABF7"
        }
        
        color = colors.get(status_type, "#E9ECEF")
        self.status_label.setText(f"● {status}")
        self.status_label.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            font-weight: bold;
        """)
    
    def clear_terminal(self):
        """Очистка терминала"""
        self.output.clear()
        self.append_output("Terminal cleared\n", "info")
    
    def kill_process(self):
        """Остановка процесса"""
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.append_output("\nProcess stopped\n", "warning")
            self.update_status("Stopped", "warning")
    
    def create_new_tab(self):
        """Создание новой вкладки терминала"""
        parent = self.parent()
        if hasattr(parent, 'create_terminal'):
            parent.create_terminal(self.working_directory)
    
    def set_working_directory(self, directory):
        """Установка рабочей директории"""
        try:
            if directory and os.path.exists(directory) and os.path.isdir(directory):
                self.working_directory = directory
                self.current_directory = directory
                self.path_label.setText(self.format_path(directory))
                
                if self.process and self.process.state() == QProcess.Running:
                    self.process.setWorkingDirectory(directory)
                    # Отправляем команду смены директории в shell
                    if platform == "win32":
                        self.process.write(f"cd /d {safe_path(directory)}\n".encode())
                    else:
                        self.process.write(f"cd {safe_path(directory)}\n".encode())
                
                self.append_output(f"Working directory changed to: {directory}\n", "success")
                self.directoryChanged.emit(directory)
        except Exception as e:
            self.append_output(f"Error setting working directory: {str(e)}\n", "error")

class TerminalManager(QWidget):
    """Менеджер терминалов с вкладками"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Панель управления терминалами
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(12, 6, 12, 6)
        control_layout.setSpacing(8)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_terminal_tab)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0D1117;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #8B949E;
                padding: 8px 16px;
                margin-right: 1px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 12px;
                font-weight: normal;
            }
            QTabBar::tab:selected {
                background-color: #0D1117;
                color: #E9ECEF;
                font-weight: bold;
                border-bottom: 2px solid #1C7ED6;
            }
            QTabBar::tab:hover:!selected {
                background-color: #21262D;
                color: #C9D1D9;
            }
            QTabBar::close-button {
                image: url(none);
                subcontrol-origin: padding;
                subcontrol-position: right;
            }
        """)
        
        new_terminal_btn = QPushButton("+ New Terminal")
        new_terminal_btn.setStyleSheet("""
            QPushButton {
                background-color: #1C7ED6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1971C2;
            }
            QPushButton:pressed {
                background-color: #1864AB;
            }
        """)
        new_terminal_btn.clicked.connect(self.create_terminal)
        
        control_layout.addWidget(QLabel("🚀 Terminal"))
        control_layout.addStretch()
        control_layout.addWidget(new_terminal_btn)
        
        layout.addLayout(control_layout)
        layout.addWidget(self.tab_widget)
        
        # Создаем первый терминал по умолчанию
        self.create_terminal()
    
    def create_terminal(self, working_directory=None):
        """Создание нового терминала"""
        terminal = IntegratedTerminal(self, working_directory)
        tab_index = self.tab_widget.addTab(terminal, f"Terminal {self.tab_widget.count() + 1}")
        self.tab_widget.setCurrentIndex(tab_index)
        
        # Обновляем текст вкладки при готовности терминала
        terminal.terminalReady.connect(lambda: self.update_tab_name(terminal, f"Terminal {tab_index + 1}"))
        
        return terminal
    
    def update_tab_name(self, terminal, name):
        """Обновление имени вкладки"""
        index = self.tab_widget.indexOf(terminal)
        if index >= 0:
            self.tab_widget.setTabText(index, name)
    
    def close_terminal_tab(self, index):
        """Закрытие вкладки терминала"""
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            widget.close()
            self.tab_widget.removeTab(index)
    
    def get_current_terminal(self):
        """Получение текущего активного терминала"""
        return self.tab_widget.currentWidget()
    
    def execute_in_terminal(self, command, working_directory=None):
        """Выполнение команды в терминале"""
        terminal = self.get_current_terminal()
        if terminal:
            if working_directory:
                terminal.set_working_directory(working_directory)
            terminal.execute_direct_command(command)
    
    def execute_python_in_terminal(self, file_path, args="", working_directory=None):
        """Выполнение Python скрипта в терминале"""
        terminal = self.get_current_terminal()
        if terminal:
            if working_directory:
                terminal.set_working_directory(working_directory)
            terminal.execute_python_command(file_path, args)
    
    def set_working_directory(self, directory):
        """Установка рабочей директории для всех терминалов"""
        for i in range(self.tab_widget.count()):
            terminal = self.tab_widget.widget(i)
            if isinstance(terminal, IntegratedTerminal):
                terminal.set_working_directory(directory)

# Обновите AsyncCodeRunner для использования нового метода
class AsyncCodeRunner:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)
        self.terminal_manager = None
    
    def set_terminal_manager(self, terminal_manager):
        """Установка менеджера терминалов"""
        self.terminal_manager = terminal_manager
    
    async def run_code_async(self, file_path, language, args=""):
        """Асинхронный запуск кода"""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, self._run_code_sync, file_path, language, args
            )
            return result
        except Exception as e:
            return f"Error: {str(e)}"
        
    def run_code_sync(self, file_path, language, args=""):
        """Синхронный запуск кода"""
        return self._run_code_sync(file_path, language, args)
    
    def _run_code_sync(self, file_path, language, args=""):
        """Синхронный запуск кода (выполняется в отдельном потоке)"""
        # Если есть терминал, используем его для интерпретируемых языков
        if self.terminal_manager and language in ["py", "js", "php", "lua", "pl", "sh", "rb", "ts"]:
            return self._run_in_terminal(file_path, language, args)
        else:
            # Иначе используем старый метод для компилируемых языков
            return self._run_external(file_path, language, args)
    
    def _run_in_terminal(self, file_path, language, args=""):
        """Запуск кода во встроенном терминале"""
        try:
            working_dir = os.path.dirname(file_path)
            
            if language == "py":
                self.terminal_manager.execute_python_in_terminal(file_path, args, working_dir)
                return f"Running Python script in terminal: {os.path.basename(file_path)}"
            else:
                safe_file_path = safe_path(file_path)
                lang_commands = {
                    "js": f"node {safe_file_path} {args}",
                    "php": f"php {safe_file_path} {args}",
                    "lua": f"lua {safe_file_path} {args}",
                    "pl": f"perl {safe_file_path} {args}",
                    "sh": f"bash {safe_file_path} {args}",
                    "rb": f"ruby {safe_file_path} {args}",
                    "ts": f"ts-node {safe_file_path} {args}",
                }
                
                if language in lang_commands:
                    command = lang_commands[language]
                    self.terminal_manager.execute_in_terminal(command, working_dir)
                    return f"Running in terminal: {command}"
                else:
                    return self._run_external(file_path, language, args)
                
        except Exception as e:
            return f"Failed to run in terminal: {str(e)}"
    
    def _run_external(self, file_path, language, args=""):
        """Запуск кода внешним способом (для компилируемых языков)"""
        runner = RunCodeClass(file_path, path.basename(file_path), language, args)
        if runner.command:
            try:
                print(f"Executing command: {runner.command}")
                process = Popen(runner.command, shell=True)
                return f"Process started with PID: {process.pid}"
            except Exception as e:
                return f"Failed to start process: {str(e)}"
        return "No command generated"

# Глобальный экземпляр асинхронного раннера
FabricRunCode = AsyncCodeRunner()