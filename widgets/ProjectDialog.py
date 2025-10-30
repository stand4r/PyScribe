from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFileDialog, QTextEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
                             QWidget, QFormLayout, QComboBox, QFrame, QScrollArea)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette
from pathlib import Path
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import datetime
from widgets.ProjectManager import ProjectConfig, project_manager

# Стили для современного дизайна
MODERN_STYLES = """
/* Основные стили */
QDialog {
    background-color: #2D2D30;
    color: #FFFFFF;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QLabel {
    color: #CCCCCC;
    font-size: 14px;
}

QLineEdit, QTextEdit, QComboBox {
    background-color: #3E3E42;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px;
    color: #FFFFFF;
    font-size: 14px;
    selection-background-color: #0078D4;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #0078D4;
    background-color: #46464A;
}

QPushButton {
    background-color: #0078D4;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #106EBE;
}

QPushButton:pressed {
    background-color: #005A9E;
}

QPushButton.secondary {
    background-color: #6B6B6B;
}

QPushButton.secondary:hover {
    background-color: #7B7B7B;
}

QPushButton.danger {
    background-color: #D13438;
}

QPushButton.danger:hover {
    background-color: #B02C30;
}

QTabWidget::pane {
    border: 1px solid #555555;
    background-color: #2D2D30;
}

QTabWidget::tab-bar {
    alignment: center;
}

QTabBar::tab {
    background-color: #3E3E42;
    color: #CCCCCC;
    padding: 10px 20px;
    margin: 2px;
    border-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #0078D4;
    color: white;
}

QTabBar::tab:hover:!selected {
    background-color: #505050;
}

QListWidget {
    background-color: #3E3E42;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #FFFFFF;
    font-size: 14px;
    outline: none;
}

QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #555555;
}

QListWidget::item:selected {
    background-color: #0078D4;
    color: white;
}

QListWidget::item:hover {
    background-color: #46464A;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QFrame {
    background-color: #3E3E42;
    border-radius: 6px;
    padding: 15px;
}

/* Стили для карточек проектов */
.project-card {
    background-color: #3E3E42;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 15px;
    margin: 5px;
}

.project-card:hover {
    background-color: #46464A;
    border-color: #0078D4;
}
"""

class ModernProjectCard(QFrame):
    """Современная карточка проекта"""
    
    def __init__(self, project: ProjectConfig, parent=None):
        super().__init__(parent)
        self.project = project
        self.parent_dialog = parent
        self.setup_ui()
    
    def setup_ui(self):
        self.setObjectName("project-card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # Заголовок проекта
        title_layout = QHBoxLayout()
        
        # Иконка проекта (можно заменить на реальную иконку)
        icon_label = QLabel("📁")
        icon_label.setStyleSheet("font-size: 20px;")
        title_layout.addWidget(icon_label)
        
        # Название и путь
        title_info_layout = QVBoxLayout()
        title_info_layout.setSpacing(2)
        
        name_label = QLabel(self.project.get_display_name())
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        
        path_label = QLabel(self.project.root_path)
        path_label.setStyleSheet("font-size: 12px; color: #888888;")
        path_label.setWordWrap(True)
        
        title_info_layout.addWidget(name_label)
        title_info_layout.addWidget(path_label)
        
        title_layout.addLayout(title_info_layout, 1)
        title_layout.addStretch()
        
        # Время последнего открытия
        time_label = QLabel(self.project.get_last_opened_display())
        time_label.setStyleSheet("font-size: 12px; color: #666666;")
        title_layout.addWidget(time_label)

        
        
        layout.addLayout(title_layout)
        
        # Команда запуска (если есть)
        if self.project.launch_command:
            command_frame = QFrame()
            command_frame.setStyleSheet("background-color: #2D2D30; border-radius: 4px; padding: 8px;")
            command_layout = QHBoxLayout(command_frame)
            command_layout.setContentsMargins(8, 8, 8, 8)
            
            command_icon = QLabel("🚀")
            command_icon.setStyleSheet("font-size: 14px;")
            command_layout.addWidget(command_icon)
            
            command_text = QLabel(self.project.launch_command)
            command_text.setStyleSheet("font-size: 12px; color: #CCCCCC; font-family: 'Consolas', monospace;")
            command_text.setWordWrap(True)
            command_layout.addWidget(command_text, 1)
            
            layout.addWidget(command_frame)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(separator)
        
        # Кнопки действий
        actions_layout = QHBoxLayout()
        
        actions_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open Project")
        self.open_button.setObjectName("open-button")
        self.open_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
        
        self.configure_button = QPushButton("Configure")
        self.configure_button.setObjectName("configure-button")
        self.configure_button.setStyleSheet("""
            QPushButton {
                background-color: #6B6B6B;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #7B7B7B;
            }
        """)
        
        # ДОБАВЛЯЕМ КНОПКУ УДАЛЕНИЯ
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("delete-button")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #D13438;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #B02C30;
            }
        """)
        
        actions_layout.addWidget(self.open_button)
        actions_layout.addWidget(self.configure_button)
        actions_layout.addWidget(self.delete_button)  # ДОБАВЛЯЕМ КНОПКУ УДАЛЕНИЯ
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        self.open_button.clicked.connect(self.on_open_clicked)
        self.configure_button.clicked.connect(self.on_configure_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)  # ДОБАВЛЯЕМ ОБРАБОТЧИК
        
        self.configure_button = QPushButton("Configure")
        self.configure_button.setObjectName("configure-button")
        self.configure_button.setStyleSheet("""
            QPushButton {
                background-color: #6B6B6B;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #7B7B7B;
            }
        """)
        
    def on_open_clicked(self):
        """Обработчик клика на кнопку Open"""
        print(f"DEBUG: ModernProjectCard.on_open_clicked called for project: {self.project.name}")  # ДОБАВИТЬ
        if self.parent_dialog:
            print(f"DEBUG: Calling parent_dialog.open_project")  # ДОБАВИТЬ
            self.parent_dialog.open_project(self.project)
        else:
            print(f"DEBUG: No parent_dialog found!")  # ДОБАВИТЬ
        
    def on_delete_clicked(self):
        """Обработчик клика на кнопку Delete"""
        reply = QMessageBox.question(
            self.parent_dialog,
            "Delete Project",
            f"Are you sure you want to delete project '{self.project.name}'?\n\n"
            "Note: This will only remove the project from PyScribe, not delete files from disk.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from widgets.ProjectManager import project_manager
            if project_manager.delete_project(self.project.root_path):
                QMessageBox.information(
                    self.parent_dialog,
                    "Project Deleted",
                    f"Project '{self.project.name}' has been removed from PyScribe."
                )
                # Обновляем списки в родительском диалоге
                self.parent_dialog.load_recent_projects()
                self.parent_dialog.load_all_projects()
            else:
                QMessageBox.warning(
                    self.parent_dialog,
                    "Delete Failed",
                    f"Failed to delete project '{self.project.name}'."
                )
    
    def on_configure_clicked(self):
        """Обработчик клика на кнопку Configure"""
        if self.parent_dialog:
            self.parent_dialog.configure_project(self.project)

class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Project Manager")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(MODERN_STYLES)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        #Empty Label
        self.recent_empty_label = QLabel("No recent projects found.\nCreate a new project or open an existing folder.")

        # Заголовок
        header_layout = QHBoxLayout()
        title_label = QLabel("Project Manager")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF; margin-bottom: 10px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Кнопка создания нового проекта
        new_project_btn = QPushButton("➕ New Project")
        new_project_btn.setObjectName("new-project-btn")
        new_project_btn.clicked.connect(self.show_new_project_dialog)
        header_layout.addWidget(new_project_btn)
        
        layout.addLayout(header_layout)
        
        # Вкладки
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
                border-radius: 6px;
                background-color: #2D2D30;
            }
        """)
        
        # Вкладка недавних проектов
        self.recent_tab = self.create_recent_tab()
        self.tabs.addTab(self.recent_tab, "Recent Projects")
        
        # Вкладка всех проектов
        self.all_tab = self.create_all_tab()
        self.tabs.addTab(self.all_tab, "All Projects")
        
        # Вкладка быстрого открытия
        self.quick_tab = self.create_quick_tab()
        self.tabs.addTab(self.quick_tab, "Quick Open")
        
        layout.addWidget(self.tabs)
        
        # Статус бар
        self.status_bar = QLabel("Ready to manage your projects")
        self.status_bar.setStyleSheet("color: #888888; font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_bar)

    
    def create_recent_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        recent_label = QLabel("Recently Opened Projects")
        recent_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; margin-bottom: 15px;")
        layout.addWidget(recent_label)
        
        # Область прокрутки для карточек
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        self.recent_layout = QVBoxLayout(scroll_widget)
        self.recent_layout.setSpacing(10)
        
        self.load_recent_projects()
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Сообщение если нет проектов
        
        self.recent_empty_label.setStyleSheet("color: #666666; font-size: 14px; text-align: center; padding: 40px;")
        self.recent_empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.recent_empty_label)
        
        self.update_empty_state()
        
        return widget
    
    def create_all_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Поиск
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #CCCCCC;")
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search projects by name...")
        self.search_edit.textChanged.connect(self.filter_projects)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        
        layout.addLayout(search_layout)
        
        # Область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.all_scroll_widget = QWidget()
        self.all_layout = QVBoxLayout(self.all_scroll_widget)
        self.all_layout.setSpacing(10)
        
        self.load_all_projects()
        
        scroll_area.setWidget(self.all_scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_quick_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Быстрое открытие папки
        quick_folder_frame = QFrame()
        quick_folder_frame.setStyleSheet("""
            QFrame {
                background-color: #3E3E42;
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 25px;
            }
        """)
        quick_folder_layout = QVBoxLayout(quick_folder_frame)
        
        folder_icon = QLabel("📂")
        folder_icon.setStyleSheet("font-size: 48px; text-align: center;")
        folder_icon.setAlignment(Qt.AlignCenter)
        
        folder_title = QLabel("Open Folder as Project")
        folder_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; text-align: center;")
        
        folder_desc = QLabel("Quickly open any folder and start coding.\nThe editor will automatically detect your project structure.")
        folder_desc.setStyleSheet("color: #CCCCCC; text-align: center; line-height: 1.4;")
        folder_desc.setAlignment(Qt.AlignCenter)
        folder_desc.setWordWrap(True)
        
        open_folder_btn = QPushButton("Choose Folder...")
        open_folder_btn.clicked.connect(self.quick_open_folder)
        
        quick_folder_layout.addWidget(folder_icon)
        quick_folder_layout.addWidget(folder_title)
        quick_folder_layout.addSpacing(10)
        quick_folder_layout.addWidget(folder_desc)
        quick_folder_layout.addSpacing(15)
        quick_folder_layout.addWidget(open_folder_btn)
        
        layout.addWidget(quick_folder_frame)
        layout.addStretch()
        
        return widget
    
    def load_recent_projects(self):
        """Загрузка недавних проектов"""
        # Очищаем layout
        for i in reversed(range(self.recent_layout.count())):
            widget = self.recent_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        recent_projects = project_manager.get_recent_projects(5)
        
        for project in recent_projects:
            card = ModernProjectCard(project, self)  # Передаем self как parent
            self.recent_layout.addWidget(card)
        
        self.update_empty_state()

    def load_all_projects(self):
        """Загрузка всех проектов"""
        for i in reversed(range(self.all_layout.count())):
            widget = self.all_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        all_projects = project_manager.get_sorted_projects()
        
        for project in all_projects:
            card = ModernProjectCard(project, self)  # Передаем self как parent
            self.all_layout.addWidget(card)
        
        if not all_projects:
            empty_label = QLabel("No projects found.\nClick 'New Project' to create your first project.")
            empty_label.setStyleSheet("color: #666666; font-size: 14px; text-align: center; padding: 40px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.all_layout.addWidget(empty_label)
    
    def update_empty_state(self):
        """Обновление состояния пустого списка"""
        has_recent = self.recent_layout.count() > 0
        self.recent_empty_label.setVisible(not has_recent)
    
    def filter_projects(self, text):
        """Фильтрация проектов по поисковому запросу"""
        for i in range(self.all_layout.count()):
            widget = self.all_layout.itemAt(i).widget()
            if isinstance(widget, ModernProjectCard):
                project_name = widget.project.get_display_name().lower()
                matches = text.lower() in project_name
                widget.setVisible(matches)
    
    def show_new_project_dialog(self):
        """Показать диалог создания нового проекта"""
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_recent_projects()
            self.load_all_projects()
    
    def quick_open_folder(self):
        """Быстрое открытие папки"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Project Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            # Создаем или открываем проект
            if folder in project_manager.projects:
                project = project_manager.open_project(folder)
            else:
                project = project_manager.create_project(folder)
            
            if self.parent and hasattr(self.parent, 'on_project_opened'):
                self.parent.on_project_opened(project)
            self.accept()
    
    def open_project(self, project):
        """Открытие выбранного проекта"""
        print(f"DEBUG: open_project called with project: {project.name}, path: {project.root_path}")  # ДОБАВИТЬ
        
        # Используем глобальный project_manager для открытия проекта
        opened_project = project_manager.open_project(project.root_path)
        print(f"DEBUG: project_manager.open_project returned: {opened_project}")  # ДОБАВИТЬ
        
        # Уведомляем родительское окно об открытии проекта
        if self.parent and hasattr(self.parent, 'on_project_opened'):
            print(f"DEBUG: Calling parent.on_project_opened")  # ДОБАВИТЬ
            self.parent.on_project_opened(opened_project)
        else:
            print(f"DEBUG: No parent or parent has no on_project_opened method")  # ДОБАВИТЬ
        
        print(f"DEBUG: Calling self.accept()")  # ДОБАВИТЬ
        self.accept()
    
    def configure_project(self, project):
        """Настройка проекта"""
        dialog = ProjectConfigDialog(project, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_recent_projects()
            self.load_all_projects()

class NewProjectDialog(QDialog):
    """Диалог создания нового проекта"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(MODERN_STYLES)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Заголовок
        title_label = QLabel("Create New Project")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)
        
        # Форма
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Название проекта
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Awesome Project")
        form_layout.addRow("Project Name:", self.name_edit)
        
        # Папка проекта
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select project folder...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_edit, 1)
        folder_layout.addWidget(browse_btn)
        form_layout.addRow("Project Folder:", folder_layout)
        
        # Команда запуска
        self.command_combo = QComboBox()
        self.command_combo.addItems([
            "Auto-detect",
            "python main.py",
            "npm start",
            "node index.js", 
            "cargo run",
            "go run main.go",
            "Custom command..."
        ])
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        form_layout.addRow("Launch Command:", self.command_combo)
        
        # Кастомная команда (скрыта по умолчанию)
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText("Enter custom launch command...")
        self.custom_command_edit.setVisible(False)
        form_layout.addRow("Custom Command:", self.custom_command_edit)
        
        # Описание
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Project description (optional)...")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        
        self.create_btn = QPushButton("Create Project")
        self.create_btn.setObjectName("create-btn")
        self.create_btn.clicked.connect(self.create_project)
        self.create_btn.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)
        
        # Подключаем проверку валидности
        self.name_edit.textChanged.connect(self.validate_form)
        self.folder_edit.textChanged.connect(self.validate_form)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.folder_edit.setText(folder)
            # Автозаполнение имени проекта если не заполнено
            if not self.name_edit.text():
                self.name_edit.setText(Path(folder).name)
    
    def on_command_changed(self, text):
        """Обработчик изменения команды запуска"""
        self.custom_command_edit.setVisible(text == "Custom command...")
    
    def validate_form(self):
        """Проверка валидности формы"""
        has_name = bool(self.name_edit.text().strip())
        has_folder = bool(self.folder_edit.text().strip()) and Path(self.folder_edit.text()).exists()
        self.create_btn.setEnabled(has_name and has_folder)
    
    def create_project(self):
        """Создание проекта"""
        name = self.name_edit.text().strip()
        folder = self.folder_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        # Определяем команду запуска
        command_text = self.command_combo.currentText()
        if command_text == "Auto-detect":
            launch_command = self.auto_detect_command(folder)
        elif command_text == "Custom command...":
            launch_command = self.custom_command_edit.text().strip()
        else:
            launch_command = command_text
        
        # Создаем проект
        project = project_manager.create_project(
            root_path=folder,
            name=name,
            launch_command=launch_command,
            description=description
        )
        
        # Создаем базовую структуру если папка пустая
        if not any(Path(folder).iterdir()):
            self.create_project_structure(folder)
        
        self.accept()
    
    def auto_detect_command(self, folder_path):
        """Автоматическое определение команды запуска"""
        path = Path(folder_path)
        
        if (path / "package.json").exists():
            return "npm start"
        elif (path / "main.py").exists():
            return "python main.py"
        elif (path / "index.js").exists():
            return "node index.js"
        elif (path / "Cargo.toml").exists():
            return "cargo run"
        elif (path / "go.mod").exists():
            return "go run main.go"
        elif (path / "pom.xml").exists():
            return "mvn exec:java"
        elif (path / "build.gradle").exists():
            return "./gradlew run" if (path / "gradlew").exists() else "gradle run"
        
        return ""
    
    def create_project_structure(self, folder_path):
        """Создание базовой структуры проекта"""
        try:
            path = Path(folder_path)
            
            # Создаем README
            readme_content = f"""# {self.name_edit.text()}

## Description
{self.description_edit.toPlainText() or 'Add your project description here.'}

## Getting Started
Follow these instructions to get the project up and running.

## Installation
Add installation instructions here.

## Usage
Explain how to use your project.
"""
            (path / "README.md").write_text(readme_content, encoding='utf-8')
            
            # Создаем gitignore если нет
            if not (path / ".gitignore").exists():
                gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
"""
                (path / ".gitignore").write_text(gitignore_content, encoding='utf-8')
                
        except Exception as e:
            print(f"Error creating project structure: {e}")


class ProjectConfigDialog(QDialog):
    def __init__(self, project_config, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.setWindowTitle(f"Configure Project: {project_config.name}")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(MODERN_STYLES)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Заголовок
        title_label = QLabel("Project Configuration")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)
        
        # Информация о проекте
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #3E3E42;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        
        info_title = QLabel("Project Information")
        info_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; margin-bottom: 10px;")
        info_layout.addWidget(info_title)
        
        # Путь проекта
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Location:"))
        path_label = QLabel(self.project_config.root_path)
        path_label.setStyleSheet("color: #CCCCCC; font-family: 'Consolas', monospace;")
        path_label.setWordWrap(True)
        path_layout.addWidget(path_label, 1)
        info_layout.addLayout(path_layout)
        
        # Дата создания
        created_layout = QHBoxLayout()
        created_layout.addWidget(QLabel("Created:"))
        try:
            created_date = datetime.datetime.fromisoformat(
                self.project_config.created_at.replace('Z', '+00:00')
            ).strftime("%Y-%m-%d %H:%M")
        except:
            created_date = "Unknown"
        created_label = QLabel(created_date)
        created_label.setStyleSheet("color: #CCCCCC;")
        created_layout.addWidget(created_label)
        info_layout.addLayout(created_layout)
        
        layout.addWidget(info_frame)
        
        # Форма настроек
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Название проекта
        self.name_edit = QLineEdit(self.project_config.name)
        self.name_edit.setPlaceholderText("Enter project name...")
        form_layout.addRow("Project Name:", self.name_edit)
        
        # Команда запуска
        command_layout = QVBoxLayout()
        
        self.command_combo = QComboBox()
        self.command_combo.addItems([
            "Custom command...",
            "python main.py",
            "npm start", 
            "node index.js",
            "java Main",
            "cargo run",
            "go run main.go",
            "./gradlew run",
            "mvn exec:java"
        ])
        
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText("Enter custom launch command...")
        self.custom_command_edit.setText(self.project_config.launch_command)
        
        # Устанавливаем правильный выбор в комбобоксе
        if self.project_config.launch_command in [self.command_combo.itemText(i) for i in range(1, self.command_combo.count())]:
            self.command_combo.setCurrentText(self.project_config.launch_command)
            self.custom_command_edit.setVisible(False)
        else:
            self.command_combo.setCurrentText("Custom command...")
            self.custom_command_edit.setVisible(True)
        
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        
        command_layout.addWidget(self.command_combo)
        command_layout.addWidget(self.custom_command_edit)
        form_layout.addRow("Launch Command:", command_layout)
        
        # Описание проекта
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlainText(self.project_config.description)
        self.description_edit.setPlaceholderText("Project description...")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        # Кнопка тестирования команды
        test_btn = QPushButton("Test Command")
        test_btn.setObjectName("secondary")
        test_btn.clicked.connect(self.test_command)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("save-btn")
        save_btn.clicked.connect(self.save_config)
        
        button_layout.addWidget(test_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def on_command_changed(self, text):
        """Обработчик изменения команды запуска"""
        is_custom = text == "Custom command..."
        self.custom_command_edit.setVisible(is_custom)
        
        if not is_custom and text != "Custom command...":
            self.custom_command_edit.setText(text)
    
    def test_command(self):
        """Тестирование команды запуска"""
        command = self.get_launch_command()
        if not command:
            QMessageBox.information(self, "Test Command", "No launch command specified")
            return
        
        try:
            import subprocess
            import platform
            
            # Проверяем существование команды
            if platform.system() == "Windows":
                result = subprocess.run(f"where {command.split()[0]}", 
                                      shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(f"which {command.split()[0]}", 
                                      shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                QMessageBox.information(self, "Test Command", 
                                      f"✅ Command found:\n{command}\n\nReady to run!")
            else:
                QMessageBox.warning(self, "Test Command",
                                  f"⚠️ Command not found:\n{command}\n\n"
                                  f"Make sure the command is available in your system PATH.")
                
        except Exception as e:
            QMessageBox.critical(self, "Test Command Error", 
                               f"Error testing command:\n{str(e)}")
    
    def get_launch_command(self):
        """Получение команды запуска из формы"""
        if self.command_combo.currentText() == "Custom command...":
            return self.custom_command_edit.text().strip()
        else:
            return self.command_combo.currentText()
    
    def get_config(self):
        """Получение конфигурации проекта"""
        self.project_config.name = self.name_edit.text().strip()
        self.project_config.launch_command = self.get_launch_command()
        self.project_config.description = self.description_edit.toPlainText().strip()
        return self.project_config
    
    def save_config(self):
        """Сохранение конфигурации"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Project name cannot be empty")
            return
        
        self.accept()
