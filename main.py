import asyncio
import json
import sys
import os
from pathlib import Path
from functools import partial
from typing import Dict, List, Optional, Any

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QSize, QTimer
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

from utils.FabricRunCode import FabricRunCode, RunCodeClass
from utils.programs import (
    load_settings, loadRecent, saveRecent, loadSession, 
    saveSession, clearCache, restore_backup, clear_backup, backup
)
from widgets.ProjectManager import *
from widgets.Dialog import CustomDialog
from widgets.QArgsEditor import ArgsWindow
from widgets.SettingsWidget import SettingsWidget
from widgets.WelcomeWidget import Ui_Welcome
from widgets.TabWidget import TabWidget
from widgets.PushButtons import *
from widgets.Explorer import Explorer
from widgets.ProjectDialog import *
# Импорт нового редактора
from widgets.QCodeEditor import ModernCodeEditor


class ApplicationManager:
    """Менеджер приложения для централизованного управления настройками и состоянием"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.settings = load_settings(str(self.base_path))
        self.recent_files = loadRecent()
        self.session_files = loadSession()
        
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


class ModernMainWindow(QMainWindow):
    """Главное окно приложения с современной архитектурой"""
    
    def __init__(self, app_manager: ApplicationManager):
        super().__init__()
        self.app_manager = app_manager
        self.unsaved_files_count = 0
        self.sidebar_visible = False
        self.config_path = self.app_manager.base_path / "config" / "launchArgs.json"
        
        self._setup_ui()
        self._setup_connections()
        self._initialize_application()
        
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setObjectName("MainWindow")
        self._setup_central_widget()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._apply_styles()
        
    def _setup_central_widget(self):
        """Настройка центрального виджета с редактором и проводником"""
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Основной редактор с вкладками
        self.tab_widget = TabWidget(self.central_widget, self.app_manager.settings)
        
        # Панель проводника
        self._setup_explorer_panel()
        
        # Основной layout
        main_layout = QtWidgets.QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addLayout(self.explorer_layout)
        main_layout.addWidget(self.tab_widget)
        
    def _setup_explorer_panel(self):
        """Настройка панели проводника файлов"""
        # Кнопки проводника
        self.explorer_buttons = {
            'up': UpPushButton(""),
            'copy': CopyPushButton(""),
            'paste': PastePushButton(""),
            'delete': DeletePushButton("")
        }
        
        # Layout кнопок
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)
        for button in self.explorer_buttons.values():
            buttons_layout.addWidget(button)
        
        # Дерево файлов
        self.file_explorer = Explorer()
        
        # Основной layout проводника
        self.explorer_layout = QtWidgets.QVBoxLayout()
        self.explorer_layout.setContentsMargins(0, 0, 0, 0)
        self.explorer_layout.setSpacing(0)
        self.explorer_layout.addLayout(buttons_layout)
        self.explorer_layout.addWidget(self.file_explorer)
        
        # Изначально скрываем проводник
        self._toggle_explorer_visibility(False)
        
    def _setup_menu_bar(self):
        """Настройка меню приложения"""
        self.menu_bar = self.menuBar()
        
        # Создание меню
        self.menus = {
            'file': self._create_menu("File", [
                ('New', 'Ctrl+N', self.action_new_file),
                ('Open...', 'Ctrl+O', self.action_open_file),
                ('Recent', None, None),  # Будет настроено отдельно
                ('---', None, None),
                ('Close', 'Ctrl+W', self.action_close_file),
                ('Close All', 'Ctrl+Shift+W', self.action_close_all_files),
                ('---', None, None),
                ('Save', 'Ctrl+S', self.action_save_file),
                ('Save All', 'Ctrl+Alt+S', self.action_save_all_files),
                ('Save As', 'Ctrl+Shift+S', self.action_save_as_file),
                ('---', None, None),
                ('Clear Cache', 'Ctrl+Del', self.action_clear_cache),
                ('Exit', 'Alt+F4', self.action_exit)
            ]),
            'edit': self._create_menu("Edit", [
                ('Undo', 'Ctrl+Z', self.action_undo),
                ('Redo', 'Ctrl+Y', self.action_redo),
                ('---', None, None),
                ('Cut', 'Ctrl+X', self.action_cut),
                ('Copy', 'Ctrl+C', self.action_copy),
                ('Paste', 'Ctrl+V', self.action_paste),
                ('Select All', 'Ctrl+A', self.action_select_all)
            ]),
            'run': self._create_menu("Run", [
                ('Run', 'Ctrl+Shift+X', self.action_run_code),
                ('Launch Parameters', 'Shift+F4', self.action_launch_parameters)
            ]),
            'tools': self._create_menu("Tools", [
                ('Set Shell', None, self.action_set_shell),
                ('Settings', None, self.action_open_settings)
            ]),
            'help': self._create_menu("Help", [
                ('GitHub Issues', None, self.action_github_issues)
            ])
        }
        
        self.menus['project'] = self._create_menu("Project", [
            ('Project Settings', 'Ctrl+Shift+P', self.action_project_settings),
            ('Run Project', 'F5', self.action_run_project),  # НОВОЕ
            ('Run File', 'Shift+F5', self.action_run_file),  # НОВОЕ
            ('---', None, None),
            ('Close Project', None, self.action_close_project)
        ])
        self.menus['file'] = self._create_menu("File", [
            ('New', 'Ctrl+N', self.action_new_file),
            ('Open...', 'Ctrl+O', self.action_open_file),
            ('Open Project', 'Ctrl+Shift+O', self.action_open_project),  # НОВОЕ
            ('Recent', None, None),
            ('---', None, None),
            ('Close', 'Ctrl+W', self.action_close_file),
            ('Close All', 'Ctrl+Shift+W', self.action_close_all_files),
            ('---', None, None),
            ('Save', 'Ctrl+S', self.action_save_file),
            ('Save All', 'Ctrl+Alt+S', self.action_save_all_files),
            ('Save As', 'Ctrl+Shift+S', self.action_save_as_file),
            ('---', None, None),
            ('Clear Cache', 'Ctrl+Del', self.action_clear_cache),
            ('Exit', 'Alt+F4', self.action_exit)
        ])
        # Настройка подменю Recent после создания основного меню
        self._setup_recent_files_submenu()
        
        # Добавление меню в меню бар
        for menu in self.menus.values():
            self.menu_bar.addMenu(menu)
            
    def _create_menu(self, title: str, actions: List[tuple]) -> QtWidgets.QMenu:
        """Создание меню с действиями"""
        menu = QtWidgets.QMenu(f"     {title}     ", self)
        menu.setStyleSheet("color: #ffffff")
        
        for action_text, shortcut, handler in actions:
            if action_text == "---":
                menu.addSeparator()
            elif action_text == "Recent":
                # Пропускаем - будет настроено отдельно
                continue
            else:
                action = QtWidgets.QAction(action_text, self)
                if shortcut:
                    action.setShortcut(shortcut)
                if handler:
                    action.triggered.connect(handler)
                menu.addAction(action)
                
        return menu
        
    def _setup_recent_files_submenu(self):
        """Настройка подменю недавних файлов"""
        self.recent_files_menu = self.menus['file'].addMenu("Recent")
        self.action_clear_recent = QtWidgets.QAction("Clear Recent", self)
        self.action_clear_recent.triggered.connect(self.action_clear_recent_files)
        self._update_recent_files_menu()
        
    def _setup_status_bar(self):
        """Настройка статусной панели"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
    def _setup_connections(self):
        """Настройка соединений сигналов и слотов"""
        # Вкладки
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.button_run.clicked.connect(self.action_run_code)
        self.tab_widget.button_settings.clicked.connect(self.action_open_settings)
        self.tab_widget.toggle_button.clicked.connect(self.toggle_sidebar)
        
        # Проводник
        self.file_explorer.doubleClicked.connect(self.open_file_from_explorer)
        self.explorer_buttons['up'].clicked.connect(self.file_explorer.go_up)
        
        # Таймер для автосохранения
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)  # 30 секунд
        
    def _initialize_application(self):
        """Инициализация приложения"""
        restore_backup()
        self.load_session_files()
        self.setWindowTitle("PyScribe - Modern Code Editor")
        
    def _apply_styles(self):
        """Применение стилей к интерфейсу"""
        self.setStyleSheet("background-color: #131313;")
        self.central_widget.setStyleSheet("QWidget { background-color: #25263b; }")
        
    def _toggle_explorer_visibility(self, visible: bool):
        """Переключение видимости проводника"""
        for widget in [self.file_explorer] + list(self.explorer_buttons.values()):
            widget.setVisible(visible)
        
    def _update_recent_files_menu(self):
        """Обновление меню недавних файлов"""
        self.recent_files_menu.clear()
        
        for file_path in self.app_manager.recent_files[:5]:  # Последние 5 файлов
            try:
                if Path(file_path).exists():
                    action = QtWidgets.QAction(f"   {file_path}", self)
                    action.triggered.connect(partial(self.open_recent_file, file_path))
                    self.recent_files_menu.addAction(action)
            except Exception:
                continue
                
        self.recent_files_menu.addSeparator()
        self.recent_files_menu.addAction(self.action_clear_recent)

    # Actions - File Operations
    def action_new_file(self):
        """Создание нового файла"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New File", "", "All Files (*)"
        )
        
        if file_path:
            try:
                # Создаем пустой файл
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.open_file(file_path)
                if file_path not in self.app_manager.session_files:
                    self.app_manager.session_files.append(file_path)
            except Exception as e:
                CustomDialog(f"Error creating file: {str(e)}").exec()
                
    def action_open_file(self):
        """Открытие существующего файла"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Open File", "", "All Files (*)"
        )
        
        for file_path in file_paths:
            self.open_file(file_path)
        
    def action_open_project(self):
        """Открытие проекта"""
        dialog = ProjectDialog(self)
        dialog.exec_()

    def on_project_opened(self, project_config):
        """Обработчик открытия проекта"""
        self.status_bar.showMessage(f"Project opened: {project_config.name}")
        
        # Обновляем заголовок окна
        self.setWindowTitle(f"PyScribe - {project_config.name}")
        
        # Показываем проект в проводнике
        self.file_explorer.setRootIndex(
            self.file_explorer.model.index(project_config.root_path)
        )
        self._toggle_explorer_visibility(True)
        
        # Открываем основные файлы проекта
        self.open_project_files(project_config)

    def on_folder_opened(self, folder_path):
        """Обработчик открытия папки (без создания проекта)"""
        self.file_explorer.setRootIndex(
            self.file_explorer.model.index(folder_path)
        )
        self._toggle_explorer_visibility(True)
        self.status_bar.showMessage(f"Folder opened: {Path(folder_path).name}")

    def open_project_files(self, project_config):
        """Открытие основных файлов проекта"""
        project_path = Path(project_config.root_path)
        
        # Автоматически открываем README если есть
        readme_files = list(project_path.glob("README*"))
        if readme_files:
            self.open_file(str(readme_files[0]))
        
        # Ищем основные файлы по расширениям
        main_files = []
        for pattern in ["main.py", "app.py", "index.js", "main.java", "src/main.py"]:
            found_files = list(project_path.rglob(pattern))
            main_files.extend(found_files)
        
        # Открываем первые 3 найденных файла
        for file_path in main_files[:3]:
            self.open_file(str(file_path))

    def action_run_project(self):
        """Запуск проекта"""
        if not project_manager.current_project:
            QMessageBox.information(self, "Info", "No project is currently open")
            return
        
        project = project_manager.current_project
        
        if not project.launch_command:
            # Предлагаем настроить команду запуска
            reply = QMessageBox.question(
                self, "Project Configuration",
                "No launch command configured for this project. Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.action_project_settings()
            return
        
        # Запускаем команду проекта
        try:
            import subprocess
            from utils.FabricRunCode import choice_env
            
            # Используем команду из конфигурации проекта
            command = project.launch_command
            terminal_command = choice_env(command)
            
            # Запускаем в терминале
            process = subprocess.Popen(terminal_command, shell=True, cwd=project.root_path)
            self.status_bar.showMessage(f"Project started: {command}")
            
        except Exception as e:
            CustomDialog(f"Error running project: {str(e)}").exec_()

    def action_run_file(self):
        """Запуск текущего файла (старая функциональность)"""
        self.action_run_code()  # Используем существующий метод

    def action_project_settings(self):
        """Открытие настроек проекта"""
        if not project_manager.current_project:
            QMessageBox.information(self, "Info", "No project is currently open")
            return
        
        dialog = ProjectConfigDialog(project_manager.current_project, self)
        if dialog.exec_() == QDialog.Accepted:
            project_manager.update_project_config(dialog.get_config())
            self.status_bar.showMessage("Project settings updated")

    def action_close_project(self):
        """Закрытие проекта"""
        if project_manager.current_project:
            project_name = project_manager.current_project.name
            project_manager.close_project()
            self.setWindowTitle("PyScribe - Modern Code Editor")
            self.status_bar.showMessage(f"Project closed: {project_name}")
        else:
            QMessageBox.information(self, "Info", "No project is currently open")

    # Обновите метод запуска кода для учета проекта:
    def action_run_code(self):
        """Запуск кода - с проверкой принадлежности к проекту"""
        current_editor = self.get_current_editor()
        if not current_editor:
            CustomDialog("No active editor").exec_()
            return
        
        # Проверяем, принадлежит ли файл проекту
        file_path = getattr(current_editor, 'file_path', None)
        if file_path and project_manager.current_project:
            if project_manager.is_file_in_project(str(file_path)):
                # Спрашиваем пользователя что запускать
                self.show_run_options_dialog(file_path)
                return
        
        # Запускаем файл обычным способом
        self.run_single_file(current_editor)

    def show_run_options_dialog(self, file_path):
        """Диалог выбора способа запуска"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Run Options")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Choose what to run:"))
        
        project_button = QPushButton(f"Run Project: {project_manager.current_project.name}")
        project_button.clicked.connect(lambda: self.run_project_from_dialog(dialog))
        
        file_button = QPushButton(f"Run File: {Path(file_path).name}")
        file_button.clicked.connect(lambda: self.run_file_from_dialog(dialog, file_path))
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        
        layout.addWidget(project_button)
        layout.addWidget(file_button)
        layout.addWidget(cancel_button)
        
        dialog.exec_()

    def run_project_from_dialog(self, dialog):
        """Запуск проекта из диалога"""
        dialog.accept()
        self.action_run_project()

    def run_file_from_dialog(self, dialog, file_path):
        """Запуск файла из диалога"""
        dialog.accept()
        current_editor = self.get_current_editor()
        if current_editor:
            self.run_single_file(current_editor)

    def run_single_file(self, editor):
        """Запуск одиночного файла"""
        # Сохраняем файл перед запуском
        if hasattr(editor, 'save_file'):
            editor.save_file()
        
        file_path = getattr(editor, 'file_path', None)
        if not file_path:
            CustomDialog("No file associated with current tab").exec_()
            return
        
        # Загрузка аргументов запуска
        args = self.load_launch_arguments(str(file_path))
        
        # Синхронный запуск
        try:
            file_extension = Path(file_path).suffix.lower()
            if file_extension:
                file_extension = file_extension[1:]
                
            from utils.FabricRunCode import FabricRunCode
            runner = FabricRunCode()
            
            if hasattr(runner, 'run_code_sync'):
                result = runner.run_code_sync(str(file_path), file_extension, args)
                self.status_bar.showMessage(f"File execution started: {result}")
            else:
                # Альтернативный способ запуска
                from utils.FabricRunCode import RunCodeClass
                run_code_class = RunCodeClass(str(file_path), Path(file_path).name, file_extension, args)
                if run_code_class.command:
                    import subprocess
                    process = subprocess.Popen(run_code_class.command, shell=True)
                    self.status_bar.showMessage(f"Process started with PID: {process.pid}")
                    
        except Exception as e:
            CustomDialog(f"Execution error: {str(e)}").exec_()
            
    def open_file(self, file_path: str):
        """Открытие файла в редакторе"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                CustomDialog(f"File not found: {file_path}").exec()
                return
                
            # Определяем способ чтения файла
            file_extension = file_path_obj.suffix.lower()
            if file_extension:  # Убираем точку если есть
                file_extension = file_extension[1:]
                
            languages = self.app_manager.languages
            
            if file_extension in languages['list']:
                file_type = languages['types'].get(file_extension, 1)
                if file_type == 0:  # Бинарный файл
                    content = file_path_obj.read_bytes()
                else:  # Текстовый файл
                    content = file_path_obj.read_text(encoding='utf-8')
                    backup(str(file_path_obj))
            else:
                content = file_path_obj.read_text(encoding='utf-8')
                
            self.create_editor_tab(content, str(file_path_obj))
            if str(file_path_obj) not in self.app_manager.session_files:
                self.app_manager.session_files.append(str(file_path_obj))
            
        except Exception as e:
            CustomDialog(f"Error opening file: {str(e)}").exec()
            
    def open_recent_file(self, file_path: str):
        """Открытие файла из списка недавних"""
        self.open_file(file_path)
        # Перемещаем файл в начало списка
        if file_path in self.app_manager.recent_files:
            self.app_manager.recent_files.remove(file_path)
        self.app_manager.recent_files.insert(0, file_path)
        saveRecent(self.app_manager.recent_files)
        
    def action_save_file(self):
        """Сохранение текущего файла"""
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'save_file'):
            if current_editor.save_file():
                current_index = self.tab_widget.currentIndex()
                self.remove_unsaved_marker(current_index)
                
    def action_save_all_files(self):
        """Сохранение всех открытых файлов"""
        for i in range(self.tab_widget.count()):
            editor = self.tab_widget.widget(i)
            if hasattr(editor, 'save_file'):
                if editor.save_file():
                    self.remove_unsaved_marker(i)
        self.unsaved_files_count = 0
        self.update_window_title()
        
    def action_save_as_file(self):
        """Сохранение файла как..."""
        current_editor = self.get_current_editor()
        if current_editor:
            current_index = self.tab_widget.currentIndex()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save File As", "", "All Files (*)"
            )
            if file_path:
                try:
                    # Сохраняем содержимое
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(current_editor.get_text())
                    
                    # Обновляем путь в редакторе
                    if hasattr(current_editor, 'set_file_path'):
                        current_editor.set_file_path(file_path)
                    
                    # Обновляем заголовок вкладки
                    self.update_tab_title(current_index, Path(file_path).name)
                    self.remove_unsaved_marker(current_index)
                    
                    # Обновляем session files
                    old_path = getattr(current_editor, 'file_path', None)
                    if old_path and old_path in self.app_manager.session_files:
                        self.app_manager.session_files.remove(old_path)
                    self.app_manager.session_files.append(file_path)
                    
                except Exception as e:
                    CustomDialog(f"Error saving file: {str(e)}").exec()
                    
    def action_close_file(self):
        """Закрытие текущего файла"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)
            
    def action_close_all_files(self):
        """Закрытие всех файлов"""
        # Закрываем вкладки с конца чтобы индексы не смещались
        for i in range(self.tab_widget.count() - 1, -1, -1):
            self.close_tab(i)
            
    def action_clear_cache(self):
        """Очистка кэша"""
        try:
            clearCache()
            self.action_clear_recent_files()
            self.action_close_all_files()
            self.show_welcome_screen()
            CustomDialog("Cache cleared successfully").exec()
        except Exception as e:
            CustomDialog(f"Error clearing cache: {str(e)}").exec()
            
    def action_clear_recent_files(self):
        """Очистка списка недавних файлов"""
        self.app_manager.recent_files.clear()
        saveRecent(self.app_manager.recent_files)
        self._update_recent_files_menu()

    # Actions - Edit Operations
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
            current_editor.editor.selectAll()

    # Actions - Run & Tools
    def action_run_code(self):
        """Запуск кода - синхронная версия"""
        current_editor = self.get_current_editor()
        if not current_editor:
            CustomDialog("No active editor").exec()
            return
            
        # Сохраняем файл перед запуском
        if hasattr(current_editor, 'save_file'):
            current_editor.save_file()
            
        file_path = getattr(current_editor, 'file_path', None)
        if not file_path:
            CustomDialog("No file associated with current tab").exec()
            return
            
        # Загрузка аргументов запуска
        args = self.load_launch_arguments(str(file_path))
        
        # Синхронный запуск
        try:
            file_extension = Path(file_path).suffix.lower()
            if file_extension:  # Убираем точку если есть
                file_extension = file_extension[1:]
                
            runner = FabricRunCode
            
            # Используем синхронный метод запуска
            if hasattr(FabricRunCode, 'run_code_sync'):
                result = FabricRunCode.run_code_sync(str(file_path), file_extension, args)
                print(f"Execution started: {result}")
            elif hasattr(FabricRunCode, '_run_code_sync'):
                result = FabricRunCode._run_code_sync(str(file_path), file_extension, args)
                print(f"Execution started: {result}")
            else:
                # Альтернативный синхронный вызов
                run_code_class = RunCodeClass(str(file_path), Path(file_path).name, file_extension, args)
                if run_code_class.command:
                    import subprocess
                    process = subprocess.Popen(run_code_class.command, shell=True)
                    print(f"Process started with PID: {process.pid}")
                    
        except Exception as e:
            CustomDialog(f"Execution error: {str(e)}").exec()
            
    def action_launch_parameters(self):
        """Открытие окна параметров запуска"""
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
        """Открытие настроек"""
        settings_window = SettingsWidget(
            self.app_manager.settings, 
            str(self.app_manager.base_path)
        )
        self.tab_widget.addTab(settings_window, "         Settings         ")
        
    def action_set_shell(self):
        """Настройка оболочки - перенаправляем в настройки"""
        self.action_open_settings()
        
    def action_github_issues(self):
        """Открытие страницы GitHub Issues"""
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://github.com/your-username/pyscribe/issues")
        )
        
    def action_exit(self):
        """Выход из приложения"""
        self.close()

    # Tab Management
    def create_editor_tab(self, content: str, file_path: str):
        """Создание новой вкладки с редактором"""
        try:
            # Создаем редактор с правильным parent
            editor = ModernCodeEditor(parent=self.tab_widget, language="py", settings=self.app_manager.settings)
            editor.set_code(content)
            editor.set_file_path(file_path)
            
            # Подключаем сигнал изменения текста
            if hasattr(editor, 'editor') and hasattr(editor.editor, 'textChanged'):
                editor.editor.textChanged.connect(self.on_text_changed)
            
            # Добавляем вкладку
            tab_name = f"       {Path(file_path).name}       "
            tab_index = self.tab_widget.addTab(editor, tab_name)
            self.tab_widget.setCurrentIndex(tab_index)
            
        except Exception as e:
            CustomDialog(f"Error creating editor tab: {str(e)}").exec()
            
    def close_tab(self, index: int):
        """Закрытие вкладки"""
        if index < 0 or index >= self.tab_widget.count():
            return
            
        editor = self.tab_widget.widget(index)
        if not editor:
            return
            
        # Проверяем есть ли несохраненные изменения
        if self.has_unsaved_changes(index):
            reply = self.ask_save_before_close()
            if reply == QMessageBox.Yes:
                if hasattr(editor, 'save_file'):
                    editor.save_file()
            elif reply == QMessageBox.Cancel:
                return
                
        # Удаляем из session files
        if hasattr(editor, 'file_path'):
            file_path = str(getattr(editor, 'file_path'))
            if file_path in self.app_manager.session_files:
                self.app_manager.session_files.remove(file_path)
                
        self.tab_widget.removeTab(index)
        
        # Показываем welcome screen если нет открытых вкладок
        if self.tab_widget.count() == 0:
            self.show_welcome_screen()
            
    def has_unsaved_changes(self, index: int) -> bool:
        """Проверяет есть ли несохраненные изменения во вкладке"""
        if index < 0 or index >= self.tab_widget.count():
            return False
        return "*" in self.tab_widget.tabText(index)
        
    def ask_save_before_close(self) -> int:
        """Диалог сохранения перед закрытием"""
        return QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before closing?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )

    # UI Management
    def toggle_sidebar(self):
        """Переключение видимости боковой панели"""
        self.sidebar_visible = not self.sidebar_visible
        self._toggle_explorer_visibility(self.sidebar_visible)
        
    def open_file_from_explorer(self, index):
        """Открытие файла из проводника"""
        if not self.file_explorer.model.isDir(index):
            file_path = self.file_explorer.model.filePath(index)
            self.open_file(file_path)
            
    def show_welcome_screen(self):
        """Показ welcome screen"""
        welcome_widget = Ui_Welcome(self.central_widget, self.app_manager.settings)
        welcome_widget.NewFileButton.clicked.connect(self.action_new_file)
        welcome_widget.OpenFileButton.clicked.connect(self.action_open_file)
        self.tab_widget.addTab(welcome_widget, "         Welcome         ")
        
    def load_session_files(self):
        """Загрузка файлов из сессии"""
        if self.app_manager.session_files:
            for file_path in self.app_manager.session_files:
                if Path(file_path).exists():
                    self.open_file(file_path)
        else:
            self.show_welcome_screen()
            
    def on_text_changed(self):
        """Обработчик изменения текста - добавляем маркер несохраненных изменений"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0 and not self.has_unsaved_changes(current_index):
            self.add_unsaved_marker(current_index)
            
    def add_unsaved_marker(self, index: int):
        """Добавление маркера несохраненных изменений"""
        if index < 0 or index >= self.tab_widget.count():
            return
            
        current_text = self.tab_widget.tabText(index)
        if "*" not in current_text:
            self.tab_widget.setTabText(index, current_text + " *")
            self.unsaved_files_count += 1
            self.update_window_title()
            
    def remove_unsaved_marker(self, index: int = None):
        """Удаление маркера несохраненных изменений"""
        if index is None:
            index = self.tab_widget.currentIndex()
            
        if index >= 0 and index < self.tab_widget.count():
            current_text = self.tab_widget.tabText(index)
            if "*" in current_text:
                self.tab_widget.setTabText(index, current_text.replace(" *", ""))
                self.unsaved_files_count = max(0, self.unsaved_files_count - 1)
                self.update_window_title()
                
    def update_tab_title(self, index: int, title: str):
        """Обновление заголовка вкладки"""
        if index < 0 or index >= self.tab_widget.count():
            return
            
        current_text = self.tab_widget.tabText(index)
        if "*" in current_text:
            title += " *"
        self.tab_widget.setTabText(index, f"       {title}       ")
        
    def update_window_title(self):
        """Обновление заголовка окна"""
        base_title = "PyScribe - Modern Code Editor"
        if self.unsaved_files_count > 0:
            self.setWindowTitle(f"{base_title} (*)")
        else:
            self.setWindowTitle(base_title)
            
    def get_current_editor(self):
        """Получение текущего редактора"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0 and current_index < self.tab_widget.count():
            return self.tab_widget.widget(current_index)
        return None

    # Utility Methods
    def load_launch_arguments(self, file_path: str) -> str:
        """Загрузка аргументов запуска для файла"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    args_config = json.load(f)
                return args_config.get(file_path, "")
        except Exception as e:
            print(f"Error loading launch arguments: {e}")
        return ""
        
    def auto_save(self):
        """Автосохранение открытых файлов"""
        if self.unsaved_files_count > 0:
            for i in range(self.tab_widget.count()):
                editor = self.tab_widget.widget(i)
                if (hasattr(editor, 'save_file') and 
                    hasattr(editor, 'file_path') and 
                    self.has_unsaved_changes(i)):
                    if editor.save_file():
                        self.remove_unsaved_marker(i)

    # Event Handlers
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
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
        """Финальные операции перед закрытием приложения"""
        try:
            saveSession(self.app_manager.session_files)
            saveRecent(self.app_manager.recent_files)
            clear_backup()
        except Exception as e:
            print(f"Error during application finalization: {e}")


def setup_application_style(app: QApplication):
    """Настройка стиля приложения"""
    app.setStyle("Fusion")
    
    # Темная палитра
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QtCore.Qt.black)
    palette.setColor(QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QPalette.Text, QtCore.Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QtCore.Qt.black)
    
    app.setPalette(palette)


def main():
    """Основная функция приложения"""
    try:
        app = QApplication(sys.argv)
        
        # Установка иконки
        script_dir = Path(__file__).parent
        icon_path = script_dir / "src" / "icon2.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        
        # Настройка стиля
        setup_application_style(app)
        
        # Смена рабочей директории
        os.chdir(script_dir)
        
        # Создание и запуск главного окна
        app_manager = ApplicationManager(str(script_dir))
        main_window = ModernMainWindow(app_manager)
        main_window.show()
        
        print("Application started successfully")
        
        # Простой запуск без asyncio
        result = app.exec_()
        sys.exit(result)
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()