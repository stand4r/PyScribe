import json
import sys
import os
from pathlib import Path
from functools import partial
from typing import Dict, List, Optional, Any

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QSize, QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, 
    QDialog, QVBoxLayout, QLabel, QPushButton, QShortcut
)

from utils.FabricRunCode import *
from utils.programs import (
    load_settings, loadRecent, saveRecent, loadSession, 
    saveSession, clearCache, clear_backup, backup, restore_backup
)
from utils.settings_manager import init_settings_manager, get_settings_manager
from widgets.ProjectDialog import ProjectDialog, ProjectConfigDialog
from widgets.Dialog import CustomDialog
from widgets.QArgsEditor import ArgsWindow
from widgets.SettingsWidget import SettingsWidget
from widgets.WelcomeWidget import Ui_Welcome
from widgets.TabWidget import TabWidget
from widgets.PushButtons import *
from widgets.Explorer import Explorer
from widgets.QCodeEditor import ModernCodeEditor
from widgets.ConsoleWidget import ConsoleWidget


class ApplicationManager:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        
        config_path = self.base_path / "config" / "settings.json"
        init_settings_manager(str(config_path))
        
        self.settings = self._load_settings()
        self.recent_files = loadRecent()
        self.session_files = loadSession()
        
    def _load_settings(self):
        """Загрузить настройки через менеджер"""
        settings_manager = get_settings_manager()
        
        # Если настроек нет, создаем дефолтные
        if not settings_manager.settings:
            from utils.programs import EditorSettings
            default_settings = EditorSettings()
            settings_manager.reset_to_default(default_settings)
        
        return settings_manager.get_all_settings()

    @property
    def colors(self) -> Dict[str, str]:
        return {
            'main': self.settings["settings"]["main_color"],
            'text': self.settings["settings"]["text_color"],
            'first': self.settings["settings"]["first_color"],
            'second': self.settings["settings"]["second_color"],
            'tab': self.settings["settings"]["tab_color"]
        }
    
    @property
    def fonts(self) -> Dict[str, int]:
        return {
            'size': int(self.settings["settings"]["fontsize"]),
            'tab_size': self.settings["settings"]["font_size_tab"]
        }
    
    @property
    def languages(self) -> Dict[str, Any]:
        return {
            'list': self.settings["languages"],
            'types': self.settings["languages_type"]
        }

    @property
    def supported_formats(self) -> Dict[str, List[str]]:
        return {
            'pdf': ['.pdf'],
            'images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp'],
            'text': ['.txt', '.py', '.js', '.html', '.css', '.json', '.xml']
        }

class UIManager:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        self.app_manager = main_window.app_manager
        
    def setup_ui(self):
        self._setup_central_widget()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._apply_styles()
        
    def _setup_central_widget(self):
        self.main_window.central_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(self.main_window.central_widget)
        
        # Основной вертикальный layout
        main_layout = QtWidgets.QVBoxLayout(self.main_window.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Горизонтальный layout для explorer и редактора
        horizontal_layout = QtWidgets.QHBoxLayout()
        horizontal_layout.setContentsMargins(0, 20, 12, 15)
        horizontal_layout.setSpacing(0)
        
        # Настройка explorer
        self._setup_explorer_panel()
        
        # Создаем splitter для редактора и терминала
        self.main_window.editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # Tab widget (редактор)
        self.main_window.tab_widget = TabWidget(
            self.main_window.editor_splitter,
            self.app_manager.settings
        )
        
        # Терминал (будет добавлен позже)
        self.main_window.terminal_widget = None
        
        # Добавляем splitter в горизонтальный layout
        horizontal_layout.addLayout(self.main_window.explorer_layout)
        horizontal_layout.addWidget(self.main_window.editor_splitter)
        
        # Добавляем горизонтальный layout в основной
        main_layout.addLayout(horizontal_layout)
        
    def _setup_explorer_panel(self):
        self.main_window.explorer_buttons = {
            'up': UpPushButton(""),
            'copy': CopyPushButton(""),
            'paste': PastePushButton(""),
            'delete': DeletePushButton("")
        }
        
        # Стилизуем кнопки в стиле YouTube
        button_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 18px;
                padding: 8px 16px;
                color: rgba(255, 255, 255, 0.95);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 500;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
        """
        
        for button in self.main_window.explorer_buttons.values():
            button.setStyleSheet(button_style)
            button.setCursor(Qt.PointingHandCursor)
        
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 8, 4)  # Добавьте отступы
        buttons_layout.setSpacing(4)
        
        for button in self.main_window.explorer_buttons.values():
            buttons_layout.addWidget(button)
        
        # ИСПОЛЬЗУЙТЕ ModernExplorer вместо старого Explorer
        self.main_window.file_explorer = Explorer()
        
        self.main_window.explorer_layout = QtWidgets.QVBoxLayout()
        self.main_window.explorer_layout.setContentsMargins(0, 0, 5, 5)  # Добавьте отступы
        self.main_window.explorer_layout.setSpacing(0)
        self.main_window.explorer_layout.addLayout(buttons_layout)
        self.main_window.explorer_layout.addWidget(self.main_window.file_explorer)
        
        self._toggle_explorer_visibility(False)
        
    def _setup_menu_bar(self):
        self.main_window.menu_bar = self.main_window.menuBar()
        self.main_window.menus = {}
        
        self._create_main_menus()
        self._setup_recent_files_submenu()
        
        for menu in self.main_window.menus.values():
            self.main_window.menu_bar.addMenu(menu)
            
    def _create_main_menus(self):
        menu_definitions = {
            'file': [
                ('New', 'Ctrl+N', self.main_window.action_new_file),
                ('Open...', 'Ctrl+O', self.main_window.action_open_file),
                ('Open Project', 'Ctrl+Shift+O', self.main_window.action_open_project),
                ('Recent', None, None),
                ('---', None, None),
                ('Close', 'Ctrl+W', self.main_window.action_close_file),
                ('Close All', 'Ctrl+Shift+W', self.main_window.action_close_all_files),
                ('---', None, None),
                ('Save', 'Ctrl+S', self.main_window.action_save_file),
                ('Save All', 'Ctrl+Alt+S', self.main_window.action_save_all_files),
                ('Save As', 'Ctrl+Shift+S', self.main_window.action_save_as_file),
                ('---', None, None),
                ('Clear Cache', 'Ctrl+Del', self.main_window.action_clear_cache),
                ('Exit', 'Alt+F4', self.main_window.action_exit)
            ],
            'edit': [
                ('Undo', 'Ctrl+Z', self.main_window.action_undo),
                ('Redo', 'Ctrl+Y', self.main_window.action_redo),
                ('---', None, None),
                ('Cut', 'Ctrl+X', self.main_window.action_cut),
                ('Copy', 'Ctrl+C', self.main_window.action_copy),
                ('Paste', 'Ctrl+V', self.main_window.action_paste),
                ('Select All', 'Ctrl+A', self.main_window.action_select_all)
            ],
            'run': [
                ('Run', 'Ctrl+R', self.main_window.action_run_code),  # Изменено с Ctrl+Shift+X
            ],
            'project': [
                ('Project Manager', 'Ctrl+Shift+P', self.main_window.action_project_manager),
                ('---', None, None),
                ('Run Project', 'F5', self.main_window.action_run_project),
                ('Run File', 'Ctrl+F5', self.main_window.action_run_file),
                ('---', None, None),
                ('Project Settings', None, self.main_window.action_project_settings),
            ],
            'tools': [
                ('Terminal', 'ctrl+`', self.main_window.toggle_terminal),  # Изменено с Ctrl+`
                ('Settings', None, self.main_window.action_open_settings)
            ],
            'help': [
                ('GitHub Issues', None, self.main_window.action_github_issues)
            ]
        }

        for menu_name, actions in menu_definitions.items():
            self.main_window.menus[menu_name] = self._create_menu(
                menu_name.capitalize(), 
                actions
            )
            
    def _create_menu(self, title: str, actions: List[tuple]) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(f"     {title}     ", self.main_window)
        menu.setStyleSheet("color: #ffffff")
        
        for action_text, shortcut, handler in actions:
            if action_text == "---":
                menu.addSeparator()
            elif action_text == "Recent":
                continue
            else:
                action = QtWidgets.QAction(action_text, self.main_window)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))  # Явное создание QKeySequence
                if handler:
                    action.triggered.connect(handler)
                menu.addAction(action)
                
        return menu
        
    def _setup_recent_files_submenu(self):
        self.main_window.recent_files_menu = self.main_window.menus['file'].addMenu("Recent")
        self.main_window.action_clear_recent = QtWidgets.QAction("Clear Recent", self.main_window)
        self.main_window.action_clear_recent.triggered.connect(
            self.main_window.action_clear_recent_files
        )
        self._update_recent_files_menu()
        
    def _setup_status_bar(self):
        self.main_window.status_bar = self.main_window.statusBar()
        self.main_window.status_bar.showMessage("Ready")
        
        self.main_window.project_indicator = QLabel("No Project")
        self.main_window.project_indicator.setStyleSheet("""
            QLabel {
                background-color: #0078D4;
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.main_window.project_indicator.setVisible(False)
        self.main_window.status_bar.addPermanentWidget(self.main_window.project_indicator)
        
    def _apply_styles(self):
        self.main_window.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(20, 20, 20, 0.95),
                    stop:1 rgba(30, 30, 30, 0.95));
            }
            QWidget {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.95);
            }""")
        self.main_window.central_widget.setStyleSheet("QWidget { background-color: #25263b; }")
        
    def _toggle_explorer_visibility(self, visible: bool):
        for widget in [self.main_window.file_explorer] + list(
            self.main_window.explorer_buttons.values()
        ):
            widget.setVisible(visible)
            
    def _update_recent_files_menu(self):
        self.main_window.recent_files_menu.clear()
        
        for file_path in self.app_manager.recent_files[:5]:
            try:
                if Path(file_path).exists():
                    action = QtWidgets.QAction(f"   {file_path}", self.main_window)
                    action.triggered.connect(
                        partial(self.main_window.open_recent_file, file_path)
                    )
                    self.main_window.recent_files_menu.addAction(action)
            except Exception:
                continue
                
        self.main_window.recent_files_menu.addSeparator()
        self.main_window.recent_files_menu.addAction(self.main_window.action_clear_recent)


class FileManager:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        self.app_manager = main_window.app_manager
        
    def open_file(self, file_path: str):
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                CustomDialog(f"File not found: {file_path}").exec()
                return
                
            file_extension = file_path_obj.suffix.lower()
            
            # Проверяем PDF файлы
            if file_extension == '.pdf':
                self.open_pdf_file(file_path)
                return
                
            languages = self.app_manager.languages
            
            if file_extension in languages['list']:
                file_type = languages['types'].get(file_extension, 1)
                if file_type == 0:
                    content = file_path_obj.read_bytes()
                else:
                    content = file_path_obj.read_text(encoding='utf-8')
                    backup(str(file_path_obj))
            else:
                content = file_path_obj.read_text(encoding='utf-8')
                
            self.main_window.create_editor_tab(content, str(file_path_obj))
            if str(file_path_obj) not in self.app_manager.session_files:
                self.app_manager.session_files.append(str(file_path_obj))
            
        except Exception as e:
            CustomDialog(f"Error opening file: {str(e)}").exec()
            
    def open_recent_file(self, file_path: str):
        self.open_file(file_path)
        if file_path in self.app_manager.recent_files:
            self.app_manager.recent_files.remove(file_path)
        self.app_manager.recent_files.insert(0, file_path)
        saveRecent(self.app_manager.recent_files)
        
    def save_file(self, editor) -> bool:
        if hasattr(editor, 'save_file'):
            return editor.save_file()
        return False
        
    def save_all_files(self):
        for i in range(self.main_window.tab_widget.count()):
            editor = self.main_window.tab_widget.widget(i)
            if self.save_file(editor):
                self.main_window.remove_unsaved_marker(i)
        self.main_window.unsaved_files_count = 0
        self.main_window.update_window_title()
    
    def open_pdf_file(self, file_path: str):
        """Открыть PDF файл в специальном viewer"""
        try:
            from widgets.PDFViewerWidget import PDFViewerWidget
            
            pdf_viewer = PDFViewerWidget(self.main_window)
            pdf_viewer.open_pdf(file_path)
            
            # Добавляем как новую вкладку
            file_name = Path(file_path).name
            tab_index = self.main_window.tab_widget.addTab(pdf_viewer, f"       {file_name}       ")
            self.main_window.tab_widget.setCurrentIndex(tab_index)
            
            # Добавляем в сессию
            if file_path not in self.app_manager.session_files:
                self.app_manager.session_files.append(file_path)
                
        except Exception as e:
            CustomDialog(f"Error opening PDF: {str(e)}").exec()


class ProjectHandler:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        
    def open_project(self):
        dialog = ProjectDialog(self.main_window)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            print("DEBUG: ProjectDialog accepted")

    def on_project_opened(self, project_config):
            print(f"DEBUG: Project opened: {project_config.name}")
            
            # Закрываем все открытые файлы перед открытием проекта
            self.main_window.close_all_editor_tabs()
            
            self.main_window.current_project = project_config
            self.main_window.update_window_title()
            
            self.main_window.project_indicator.setText(project_config.name)
            self.main_window.project_indicator.setVisible(True)
            
            if hasattr(self.main_window, 'file_explorer') and self.main_window.file_explorer:
                try:
                    model = self.main_window.file_explorer.model
                    if model:
                        root_index = model.index(project_config.root_path)
                        self.main_window.file_explorer.setRootIndex(root_index)
                        self.main_window.file_explorer.expandAll()
                except Exception as e:
                    print(f"DEBUG: Error setting file explorer root: {e}")
            
            if not self.main_window.sidebar_visible:
                self.main_window.toggle_sidebar()
            
            self.open_project_files(project_config)
            self.main_window._update_project_menu()
            
            self.main_window.status_bar.showMessage(f"Project opened: {project_config.name}")

    def open_project_files(self, project_config):
        try:
            project_path = Path(project_config.root_path)
            
            readme_files = list(project_path.glob("README*"))
            if readme_files:
                self.main_window.file_manager.open_file(str(readme_files[0]))
            
            main_files = []
            patterns = [
                "main.py", "app.py", "index.js", "main.java", 
                "src/main.py", "src/app.py", "src/index.js"
            ]
            
            for pattern in patterns:
                found_files = list(project_path.rglob(pattern))
                main_files.extend(found_files)
            
            for file_path in main_files[:3]:
                self.main_window.file_manager.open_file(str(file_path))
                
        except Exception as e:
            print(f"Error opening project files: {e}")

    def run_project(self):
        if not self.main_window.current_project:
            self.show_no_project_message()
            return
        
        project = self.main_window.current_project
        
        if not project.launch_command:
            reply = QMessageBox.question(
                self.main_window, "Project Configuration",
                "No launch command configured for this project. Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.main_window.action_project_settings()
            return
        
        # Используем команду из проекта как единую команду
        if self.main_window.terminal_widget:
            self.main_window.run_in_terminal(
                project.launch_command, 
                working_dir=project.root_path
            )

    def show_no_project_message(self):
        QMessageBox.information(
            self.main_window, 
            "No Project", 
            "No project is currently open.\n\n"
            "Use 'Open Project' (Ctrl+Shift+O) to open an existing project\n"
            "or 'Project Manager' to create a new one."
        )


class CodeRunner:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        
    def run_code(self):
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            CustomDialog("No active editor").exec()
            return
            
        if hasattr(current_editor, 'save_file'):
            if not current_editor.save_file():
                CustomDialog("Failed to save file before execution").exec_()
                return
            
        file_path = getattr(current_editor, 'file_path', None)
        if not file_path:
            CustomDialog("No file associated with current tab").exec()
            return
            
        args = self.main_window.load_launch_arguments(str(file_path))
        
        working_dir = None
        if hasattr(self.main_window, 'current_project') and self.main_window.current_project:
            working_dir = self.main_window.current_project.root_path
            
        self.main_window.run_in_terminal(str(file_path), args, working_dir)


class ModernMainWindow(QMainWindow):
    def __init__(self, app_manager: ApplicationManager):
        super().__init__()
        self.app_manager = app_manager
        self.unsaved_files_count = 0
        self.sidebar_visible = False
        self.terminal_visible = True
        self.config_path = self.app_manager.base_path / "config" / "launchArgs.json"
        self.current_project = None
        self.console_widget = None
        self.editor_splitter = None
        
        self._initialize_attributes()
        
        self.ui_manager = UIManager(self)
        self.file_manager = FileManager(self)
        self.project_handler = ProjectHandler(self)
        self.code_runner = CodeRunner(self)

        self.project_handler.main_window = self
        
        self.ui_manager.setup_ui()
        self._setup_terminal()
        self._setup_connections()
        self._initialize_application()
        
    def _initialize_attributes(self):
        self.tab_widget = None
        self.file_explorer = None
        self.explorer_buttons = {}
        self.explorer_layout = None
        self.central_widget = None
        self.menu_bar = None
        self.menus = {}
        self.status_bar = None
        self.auto_save_timer = None
        self.recent_files_menu = None
        self.action_clear_recent = None
        self.project_indicator = None
        
    def _setup_terminal(self):
        """Настройка консоли с вкладками под редактором"""
        self.console_widget = ConsoleWidget(self)
        self.console_widget.setVisible(False)
        
        # Добавляем консоль в splitter под редактором
        if hasattr(self, 'editor_splitter') and self.editor_splitter:
            self.editor_splitter.addWidget(self.console_widget)
            # Устанавливаем начальные размеры (консоль скрыта)
            self.editor_splitter.setSizes([1000, 0])
            
            # Настраиваем splitter для возможности изменения размеров
            self.editor_splitter.setChildrenCollapsible(False)
            self.editor_splitter.setHandleWidth(4)
            self.editor_splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: #3C3C3C;
                    height: 4px;
                }
                QSplitter::handle:hover {
                    background-color: #0078D4;
                }
            """)

    def toggle_terminal(self):
        """Переключение видимости консоли с адаптацией размеров"""
        self.terminal_visible = not self.terminal_visible
        
        if self.console_widget and hasattr(self, 'editor_splitter'):
            self.console_widget.setVisible(self.terminal_visible)
            
            if self.terminal_visible:
                # Показываем консоль (30% высоты)
                total_height = self.editor_splitter.height()
                editor_height = int(total_height * 0.7)
                console_height = int(total_height * 0.3)
                self.editor_splitter.setSizes([editor_height, console_height])
            else:
                # Скрываем консоль
                self.editor_splitter.setSizes([self.editor_splitter.height(), 0])
    
    def apply_application_theme(self):
        """Применить тему ко всему приложению"""
        colors = self.app_manager.colors
        
        # Обновляем стиль главного окна
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {colors['first']};
                color: {colors['text']};
            }}
            QMenuBar {{
                background-color: {colors['main']};
                color: {colors['text']};
                border: none;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 5px 10px;
            }}
            QMenuBar::item:selected {{
                background-color: {colors['second']};
            }}
            QMenu {{
                background-color: {colors['main']};
                color: {colors['text']};
                border: 1px solid {colors['second']};
            }}
            QMenu::item {{
                padding: 5px 20px;
            }}
            QMenu::item:selected {{
                background-color: {colors['second']};
            }}
        """)
        
        # Обновляем статус бар
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {colors['main']};
                color: {colors['text']};
                border-top: 1px solid {colors['second']};
            }}
        """)
        
        # Обновляем центральный виджет
        if hasattr(self, 'central_widget'):
            self.central_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {colors['first']};
                    color: {colors['text']};
                }}
            """)
    
    def action_open_settings(self):
        """Открыть настройки в отдельном окне"""
        settings_window = SettingsWidget(
            self.app_manager.settings, 
            str(self.app_manager.base_path),
            self  # Передаем родительское окно для обновления темы
        )
        
        # Создаем диалоговое окно для настроек
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setMinimumSize(600, 700)
        
        # Применяем текущую тему к диалогу
        colors = self.app_manager.colors
        dialog.setStyleSheet(f"background-color: {colors['first']}; color: {colors['text']};")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(settings_window)
        
        # Кнопка закрытия
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.reject)
        button_box.setStyleSheet(f"background-color: {colors['main']};")
        layout.addWidget(button_box)
        
        dialog.exec_()
    
    def run_in_terminal(self, file_path, args="", working_dir=None):
        """Запуск кода в терминале"""
        if not self.terminal_visible:
            self.toggle_terminal()
            
        # Переключаемся на вкладку Terminal
        self.console_widget.set_current_tab("Terminal")
        
        # Получаем терминал из консольного виджета
        terminal = self.console_widget.get_terminal()
        if terminal:
            # Если это команда (содержит &&), а не путь к файлу
            if "&&" in str(file_path):
                # Передаем команду как есть
                terminal.run_code(file_path, args, working_dir)
            else:
                # Стандартный запуск файла
                terminal.run_code(file_path, args, working_dir)

    def add_problem(self, problem_type, file_path, line, description):
        """Добавляет проблему в консоль"""
        if hasattr(self, 'console_widget') and self.console_widget:
            self.console_widget.add_problem(problem_type, file_path, line, description)
    
    def append_output(self, text, is_error=False):
        """Добавляет текст в вывод"""
        if hasattr(self, 'console_widget') and self.console_widget:
            self.console_widget.append_output(text, is_error)
    
    def show_problems_tab(self):
        """Показывает вкладку Problems"""
        if not self.terminal_visible:
            self.toggle_terminal()
        self.console_widget.set_current_tab("Problems")
    
    def show_output_tab(self):
        """Показывает вкладку Output"""
        if not self.terminal_visible:
            self.toggle_terminal()
        self.console_widget.set_current_tab("Output")

    def _setup_connections(self):
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.button_run.clicked.connect(self.action_run_code)
        self.tab_widget.button_settings.clicked.connect(self.action_open_settings)
        self.tab_widget.toggle_button.clicked.connect(self.toggle_sidebar)
        
        self.file_explorer.doubleClicked.connect(self.open_file_from_explorer)
        self.explorer_buttons['up'].clicked.connect(self.file_explorer.go_up)
        
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)

        self.terminal_shortcut = QShortcut(QKeySequence("Ctrl+`"), self)
        self.terminal_shortcut.activated.connect(self.toggle_terminal)
        
    def _initialize_application(self):
        restore_backup()
        self.load_session_files()
        self.setWindowTitle("PyScribe - Modern Code Editor")

    def toggle_sidebar(self):
        """Переключение sidebar с адаптацией терминала"""
        old_sidebar_visible = self.sidebar_visible
        self.sidebar_visible = not self.sidebar_visible
        self.ui_manager._toggle_explorer_visibility(self.sidebar_visible)
        
        # Если sidebar изменил видимость, обновляем размеры
        if old_sidebar_visible != self.sidebar_visible and self.terminal_visible:
            # Небольшая задержка для обновления layout
            QtCore.QTimer.singleShot(50, self._adjust_terminal_size)
    
    def _adjust_terminal_size(self):
        """Автоматическая регулировка размера терминала при изменении layout"""
        if self.terminal_visible and hasattr(self, 'editor_splitter'):
            total_height = self.editor_splitter.height()
            editor_height = int(total_height * 0.7)
            terminal_height = int(total_height * 0.3)
            self.editor_splitter.setSizes([editor_height, terminal_height])
        
    def load_session_files(self):
        if self.app_manager.session_files:
            for file_path in self.app_manager.session_files:
                if Path(file_path).exists():
                    self.file_manager.open_file(file_path)
        else:
            self.show_welcome_screen()

    # Остальные методы остаются без изменений...
    def action_new_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New File", "", "All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.file_manager.open_file(file_path)
                if file_path not in self.app_manager.session_files:
                    self.app_manager.session_files.append(file_path)
            except Exception as e:
                CustomDialog(f"Error creating file: {str(e)}").exec()
                
    def action_open_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Open File", "", "All Files (*)"
        )
        
        for file_path in file_paths:
            self.file_manager.open_file(file_path)
        
    def action_open_project(self):
        self.project_handler.open_project()

    def action_save_file(self):
        current_editor = self.get_current_editor()
        if current_editor and self.file_manager.save_file(current_editor):
            current_index = self.tab_widget.currentIndex()
            self.remove_unsaved_marker(current_index)
            
    def action_save_all_files(self):
        self.file_manager.save_all_files()
        
    def action_save_as_file(self):
        current_editor = self.get_current_editor()
        if current_editor:
            current_index = self.tab_widget.currentIndex()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save File As", "", "All Files (*)"
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(current_editor.get_text())
                    
                    if hasattr(current_editor, 'set_file_path'):
                        current_editor.set_file_path(file_path)
                    
                    self.update_tab_title(current_index, Path(file_path).name)
                    self.remove_unsaved_marker(current_index)
                    
                    old_path = getattr(current_editor, 'file_path', None)
                    if old_path and old_path in self.app_manager.session_files:
                        self.app_manager.session_files.remove(old_path)
                    self.app_manager.session_files.append(file_path)
                    
                except Exception as e:
                    CustomDialog(f"Error saving file: {str(e)}").exec()
                    
    def action_close_file(self):
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)
            
    def action_close_all_files(self):
        for i in range(self.tab_widget.count() - 1, -1, -1):
            self.close_tab(i)
            
    def action_clear_cache(self):
        try:
            clearCache()
            self.action_clear_recent_files()
            # Очищаем сессионные файлы
            self.app_manager.session_files.clear()
            saveSession(self.app_manager.session_files)
            self.action_close_all_files()
            self.show_welcome_screen()
            CustomDialog("Cache cleared successfully").exec()
        except Exception as e:
            CustomDialog(f"Error clearing cache: {str(e)}").exec()
            
    def action_clear_recent_files(self):
        self.app_manager.recent_files.clear()
        saveRecent(self.app_manager.recent_files)
        self.ui_manager._update_recent_files_menu()

    def close_all_editor_tabs(self):
        """Закрывает все вкладки редактора"""
        for i in range(self.tab_widget.count() - 1, -1, -1):
            widget = self.tab_widget.widget(i)
            if not isinstance(widget, (Ui_Welcome, SettingsWidget)):
                self.close_tab(i)

    def action_undo(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.undo()
            
    def action_redo(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.redo()
            
    def action_cut(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.cut()
            
    def action_copy(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.copy()
            
    def action_paste(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.paste()
            
    def action_select_all(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'editor'):
            current_editor.editor.select_all()

    def action_run_code(self):
        self.code_runner.run_code()
            
    def action_launch_parameters(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'file_path'):
            file_path = getattr(current_editor, 'file_path')
            language = getattr(current_editor, 'language', 'txt')
            args_window = ArgsWindow(
                Path(file_path).name,
                str(file_path),
                language
            )
            args_window.show()
            
    def action_open_settings(self):
        settings_window = SettingsWidget(
            self.app_manager.settings, 
            str(self.app_manager.base_path)
        )
        self.tab_widget.addTab(settings_window, "         Settings         ")
        
    def action_set_shell(self):
        self.action_open_settings()
        
    def action_github_issues(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://github.com/stand4r/PyScribe/issues")
        )
        
    def action_exit(self):
        self.close()

    def action_run_project(self):
        self.project_handler.run_project()

    def action_run_file(self):
        current_editor = self.get_current_editor()
        if not current_editor:
            CustomDialog("No active editor").exec_()
            return
        
        file_path = getattr(current_editor, 'file_path', None)
        if file_path and self.current_project:
            self.show_run_options_dialog(file_path)
            return
        
        self.run_single_file(current_editor)

    def action_project_manager(self):
        self.action_open_project()

    def action_project_settings(self):
        if not self.current_project:
            self.project_handler.show_no_project_message()
            return
        
        try:
            dialog = ProjectConfigDialog(self.current_project, self)
            if dialog.exec_() == QDialog.Accepted:
                self.current_project = dialog.get_config()
                self.status_bar.showMessage("Project settings updated")
                self.project_indicator.setText(self.current_project.name)
                self.update_window_title()
        except Exception as e:
            CustomDialog(f"Error opening project settings: {str(e)}").exec_()

    def action_close_project(self):
        if not self.current_project:
            self.project_handler.show_no_project_message()
            return
        
        project_name = self.current_project.name
        
        reply = QMessageBox.question(
            self, "Close Project",
            f"Close project '{project_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.current_project = None
            self.setWindowTitle("PyScribe - Modern Code Editor")
            self.project_indicator.setVisible(False)
            self.status_bar.showMessage(f"Project closed: {project_name}")
            self._update_project_menu()

    def create_editor_tab(self, content: str, file_path: str):
        try:
            editor = ModernCodeEditor(
                parent=self.tab_widget, 
                language="py", 
                settings=self.app_manager.settings
            )
            editor.set_code(content)
            editor.set_file_path(file_path)
            
            if hasattr(editor, 'editor') and hasattr(editor.editor, 'textChanged'):
                editor.editor.textChanged.connect(self.on_text_changed)
            
            tab_name = f"       {Path(file_path).name}       "
            tab_index = self.tab_widget.addTab(editor, tab_name)
            self.tab_widget.setCurrentIndex(tab_index)
            
        except Exception as e:
            CustomDialog(f"Error creating editor tab: {str(e)}").exec()
            
    def close_tab(self, index: int):
        if index < 0 or index >= self.tab_widget.count():
            return
            
        editor = self.tab_widget.widget(index)
        if not editor:
            return
            
        if self.has_unsaved_changes(index):
            reply = self.ask_save_before_close()
            if reply == QMessageBox.Yes:
                if hasattr(editor, 'save_file'):
                    editor.save_file()
            elif reply == QMessageBox.Cancel:
                return
                
        if hasattr(editor, 'file_path'):
            file_path = str(getattr(editor, 'file_path'))
            if file_path in self.app_manager.session_files:
                self.app_manager.session_files.remove(file_path)
                
        self.tab_widget.removeTab(index)
        
        if self.tab_widget.count() == 0:
            self.show_welcome_screen()
            
    def has_unsaved_changes(self, index: int) -> bool:
        if index < 0 or index >= self.tab_widget.count():
            return False
        return "*" in self.tab_widget.tabText(index)
        
    def ask_save_before_close(self) -> int:
        return QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before closing?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )

    def open_file_from_explorer(self, index):
        if not self.file_explorer.model.isDir(index):
            file_path = self.file_explorer.model.filePath(index)
            self.file_manager.open_file(file_path)
            
    def show_welcome_screen(self):
        welcome_widget = Ui_Welcome(self.central_widget, self.app_manager.settings)
        welcome_widget.new_file_card.clicked.connect(self.action_new_file)
        welcome_widget.open_file_card.clicked.connect(self.action_open_file)
        self.tab_widget.addTab(welcome_widget, "         Welcome         ")
            
    def on_text_changed(self):
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0 and not self.has_unsaved_changes(current_index):
            self.add_unsaved_marker(current_index)
            
    def add_unsaved_marker(self, index: int):
        if index < 0 or index >= self.tab_widget.count():
            return
            
        current_text = self.tab_widget.tabText(index)
        if "*" not in current_text:
            self.tab_widget.setTabText(index, current_text + " *")
            self.unsaved_files_count += 1
            self.update_window_title()
            
    def remove_unsaved_marker(self, index: int = None):
        if index is None:
            index = self.tab_widget.currentIndex()
            
        if index >= 0 and index < self.tab_widget.count():
            current_text = self.tab_widget.tabText(index)
            if "*" in current_text:
                self.tab_widget.setTabText(index, current_text.replace(" *", ""))
                self.unsaved_files_count = max(0, self.unsaved_files_count - 1)
                self.update_window_title()
                
    def update_tab_title(self, index: int, title: str):
        if index < 0 or index >= self.tab_widget.count():
            return
            
        current_text = self.tab_widget.tabText(index)
        if "*" in current_text:
            title += " *"
        self.tab_widget.setTabText(index, f"       {title}       ")
        
    def update_window_title(self):
        base_title = "PyScribe"
        if hasattr(self, 'current_project') and self.current_project:
            base_title += f" - {self.current_project.name}"
        else:
            base_title += " - Modern Code Editor"
        
        if self.unsaved_files_count > 0:
            base_title += " (*)"
        
        self.setWindowTitle(base_title)
            
    def get_current_editor(self):
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0 and current_index < self.tab_widget.count():
            editor = self.tab_widget.widget(current_index)
            if hasattr(editor, 'get_code') and hasattr(editor, 'set_code'):
                return editor
        return None

    def load_launch_arguments(self, file_path: str) -> str:
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    args_config = json.load(f)
                return args_config.get(file_path, "")
        except Exception as e:
            print(f"Error loading launch arguments: {e}")
        return ""
        
    def auto_save(self):
        if self.unsaved_files_count > 0:
            for i in range(self.tab_widget.count()):
                editor = self.tab_widget.widget(i)
                if (hasattr(editor, 'save_file') and 
                    hasattr(editor, 'file_path') and 
                    self.has_unsaved_changes(i)):
                    if editor.save_file():
                        self.remove_unsaved_marker(i)

    def show_run_options_dialog(self, file_path):
        dialog = QDialog(self)
        dialog.setWindowTitle("Run Options")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_label = QLabel("Choose what to run:")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)
        
        desc_label = QLabel(
            f"You're working in project: <b>{self.current_project.name}</b>\n"
            f"Current file: {Path(file_path).name}"
        )
        desc_label.setStyleSheet("color: #CCCCCC; line-height: 1.4;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        project_button = QPushButton(f"🚀 Run Project")
        project_button.setStyleSheet("font-size: 14px; padding: 12px;")
        project_button.clicked.connect(lambda: self.run_project_from_dialog(dialog))
        
        file_button = QPushButton(f"📄 Run Current File")
        file_button.setStyleSheet("font-size: 14px; padding: 12px;")
        file_button.clicked.connect(lambda: self.run_file_from_dialog(dialog, file_path))
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondary")
        cancel_button.clicked.connect(dialog.reject)
        
        layout.addWidget(project_button)
        layout.addWidget(file_button)
        layout.addWidget(cancel_button)
        
        dialog.exec_()

    def run_project_from_dialog(self, dialog):
        dialog.accept()
        self.action_run_project()

    def run_file_from_dialog(self, dialog, file_path):
        dialog.accept()
        current_editor = self.get_current_editor()
        if current_editor:
            self.run_single_file(current_editor)

    def run_single_file(self, editor):
        if hasattr(editor, 'save_file'):
            if not editor.save_file():
                CustomDialog("Failed to save file before execution").exec_()
                return
        
        file_path = getattr(editor, 'file_path', None)
        if not file_path:
            CustomDialog("No file associated with current tab").exec_()
            return
        
        args = self.load_launch_arguments(str(file_path))
        
        working_dir = None
        if hasattr(self, 'current_project') and self.current_project:
            working_dir = self.current_project.root_path
            
        self.run_in_terminal(str(file_path), args, working_dir)

    def _update_project_menu(self):
        has_project = hasattr(self, 'current_project') and self.current_project is not None
        
        if 'project' in self.menus:
            project_menu = self.menus['project']
            for action in project_menu.actions():
                text = action.text()
                if text in ["Run Project", "Run File", "Project Settings", "Close Project"]:
                    action.setEnabled(has_project)
        
        if hasattr(self, 'project_indicator'):
            if has_project:
                self.project_indicator.setText(self.current_project.name)
                self.project_indicator.setVisible(True)
            else:
                self.project_indicator.setVisible(False)

    def closeEvent(self, event):
        if self.unsaved_files_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save all changes before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.action_save_all_files()
                self.finalize_application()
                event.accept()
            elif reply == QMessageBox.No:
                self.finalize_application()
                event.accept()
            else:
                event.ignore()
                return
        else:
            self.finalize_application()
            event.accept()
            
    def finalize_application(self):
        try:
            saveSession(self.app_manager.session_files)
            saveRecent(self.app_manager.recent_files)
            clear_backup()
        except Exception as e:
            print(f"Error during application finalization: {e}")
    
    def on_project_opened(self, project_config):
        self.project_handler.on_project_opened(project_config)


def setup_application_style(app: QApplication):
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    
    app.setPalette(palette)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "icon.png")))


def main():
    app = QApplication(sys.argv)
    
    base_path = Path(__file__).parent
    app_manager = ApplicationManager(str(base_path))
    
    setup_application_style(app)
    
    window = ModernMainWindow(app_manager)
    window.showMaximized()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()