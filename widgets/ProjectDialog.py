from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFileDialog, QTextEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
                             QWidget, QFormLayout, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from pathlib import Path
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional



@dataclass
class ProjectConfig:
    name: str
    root_path: str
    launch_command: str = ""
    description: str = ""
    created_at: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectConfig':
        return cls(**data)
    
    def to_dict(self) -> dict:
        return asdict(self)

class ProjectManager:
    def __init__(self):
        self.current_project: Optional[ProjectConfig] = None
        self.projects_file = "projects.json"
        self.projects: Dict[str, ProjectConfig] = {}
        self.load_projects()
    
    def load_projects(self):
        """Загрузка списка проектов из файла"""
        try:
            if os.path.exists(self.projects_file):
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.projects = {k: ProjectConfig.from_dict(v) for k, v in data.items()}
        except Exception as e:
            print(f"Error loading projects: {e}")
            self.projects = {}
    
    def save_projects(self):
        """Сохранение списка проектов в файл"""
        try:
            with open(self.projects_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.projects.items()}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving projects: {e}")
    
    def create_project(self, root_path: str, name: str = None, launch_command: str = "") -> ProjectConfig:
        """Создание нового проекта"""
        if name is None:
            name = Path(root_path).name
        
        project = ProjectConfig(
            name=name,
            root_path=root_path,
            launch_command=launch_command,
            created_at=json.dumps(os.path.getctime(root_path))
        )
        
        self.projects[root_path] = project
        self.save_projects()
        return project
    
    def open_project(self, root_path: str) -> Optional[ProjectConfig]:
        """Открытие проекта"""
        if root_path in self.projects:
            self.current_project = self.projects[root_path]
        else:
            self.current_project = self.create_project(root_path)
        
        return self.current_project
    
    def close_project(self):
        """Закрытие текущего проекта"""
        self.current_project = None
    
    def update_project_config(self, config: ProjectConfig):
        """Обновление конфигурации проекта"""
        self.projects[config.root_path] = config
        if self.current_project and self.current_project.root_path == config.root_path:
            self.current_project = config
        self.save_projects()
    
    def get_project_files(self) -> List[str]:
        """Получение списка файлов проекта"""
        if not self.current_project:
            return []
        
        project_files = []
        root_path = Path(self.current_project.root_path)
        
        for ext in ['py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php', 'rb', 'go', 'rs']:
            project_files.extend(root_path.rglob(f"*.{ext}"))
        
        return [str(f) for f in project_files]
    
    def is_file_in_project(self, file_path: str) -> bool:
        """Проверка принадлежности файла к проекту"""
        if not self.current_project:
            return False
        
        try:
            file_path = Path(file_path).resolve()
            project_path = Path(self.current_project.root_path).resolve()
            return file_path.is_relative_to(project_path)
        except:
            return False

# Глобальный экземпляр
project_manager = ProjectManager()


class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Project Management")
        self.setMinimumSize(600, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Вкладки
        self.tabs = QTabWidget()
        
        # Вкладка открытия проекта
        self.open_tab = self.create_open_tab()
        self.tabs.addTab(self.open_tab, "Open Project")
        
        # Вкладка управления проектами
        self.manage_tab = self.create_manage_tab()
        self.tabs.addTab(self.manage_tab, "Manage Projects")
        
        layout.addWidget(self.tabs)
        
        # Кнопки
        button_layout = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def create_open_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Выбор папки
        folder_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Select project folder...")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_project_folder)
        
        folder_layout.addWidget(QLabel("Project Folder:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_button)
        
        # Команда запуска
        command_layout = QVBoxLayout()
        command_layout.addWidget(QLabel("Launch Command (optional):"))
        self.launch_command = QTextEdit()
        self.launch_command.setMaximumHeight(80)
        self.launch_command.setPlaceholderText("e.g.: python main.py\nOr leave empty to use file-specific commands")
        
        # Предустановленные команды
        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("Quick presets:"))
        
        self.presets_combo = QComboBox()
        self.presets_combo.addItems([
            "Select preset...",
            "python main.py",
            "npm start", 
            "node index.js",
            "java Main",
            "cargo run",
            "go run main.go"
        ])
        self.presets_combo.currentTextChanged.connect(self.apply_preset)
        
        presets_layout.addWidget(self.presets_combo)
        presets_layout.addStretch()
        
        command_layout.addLayout(presets_layout)
        command_layout.addWidget(self.launch_command)
        
        # Кнопки открытия
        open_buttons_layout = QHBoxLayout()
        self.open_project_button = QPushButton("Open as Project")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_folder_button = QPushButton("Open Folder Only")
        self.open_folder_button.clicked.connect(self.open_folder_only)
        
        open_buttons_layout.addWidget(self.open_project_button)
        open_buttons_layout.addWidget(self.open_folder_button)
        open_buttons_layout.addStretch()
        
        layout.addLayout(folder_layout)
        layout.addLayout(command_layout)
        layout.addLayout(open_buttons_layout)
        layout.addStretch()
        
        return widget
    
    def create_manage_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Recent Projects:"))
        self.projects_list = QListWidget()
        self.load_projects_list()
        layout.addWidget(self.projects_list)
        
        # Кнопки управления
        manage_buttons_layout = QHBoxLayout()
        self.open_selected_button = QPushButton("Open Selected")
        self.open_selected_button.clicked.connect(self.open_selected_project)
        self.delete_button = QPushButton("Delete Project")
        self.delete_button.clicked.connect(self.delete_project)
        self.configure_button = QPushButton("Configure")
        self.configure_button.clicked.connect(self.configure_project)
        
        manage_buttons_layout.addWidget(self.open_selected_button)
        manage_buttons_layout.addWidget(self.configure_button)
        manage_buttons_layout.addWidget(self.delete_button)
        manage_buttons_layout.addStretch()
        
        layout.addLayout(manage_buttons_layout)
        
        return widget
    
    def browse_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.folder_path.setText(folder)
            # Автоматически определяем команду запуска
            self.auto_detect_launch_command(folder)
    
    def auto_detect_launch_command(self, folder_path):
        """Автоматическое определение команды запуска на основе файлов в проекте"""
        path = Path(folder_path)
        
        # Проверяем наличие различных конфигурационных файлов
        if (path / "package.json").exists():
            self.launch_command.setPlainText("npm start")
        elif (path / "main.py").exists():
            self.launch_command.setPlainText("python main.py")
        elif (path / "index.js").exists():
            self.launch_command.setPlainText("node index.js")
        elif (path / "Cargo.toml").exists():
            self.launch_command.setPlainText("cargo run")
        elif (path / "go.mod").exists():
            self.launch_command.setPlainText("go run main.go")
        elif (path / "pom.xml").exists() or (path / "build.gradle").exists():
            self.launch_command.setPlainText("./gradlew run" if (path / "gradlew").exists() else "mvn exec:java")
    
    def apply_preset(self, preset):
        if preset != "Select preset...":
            self.launch_command.setPlainText(preset)
    
    def open_project(self):
        folder = self.folder_path.text().strip()
        if not folder:
            QMessageBox.warning(self, "Warning", "Please select a project folder")
            return
        
        if not Path(folder).exists():
            QMessageBox.warning(self, "Warning", "Selected folder does not exist")
            return
        
        launch_command = self.launch_command.toPlainText().strip()
        
        # Сохраняем проект
        project_manager.open_project(folder)
        if launch_command:
            project_manager.current_project.launch_command = launch_command
            project_manager.save_projects()
        
        if self.parent:
            self.parent.on_project_opened(project_manager.current_project)
        
        self.accept()
    
    def open_folder_only(self):
        folder = self.folder_path.text().strip()
        if not folder:
            QMessageBox.warning(self, "Warning", "Please select a folder")
            return
        
        if not Path(folder).exists():
            QMessageBox.warning(self, "Warning", "Selected folder does not exist")
            return
        
        if self.parent:
            self.parent.on_folder_opened(folder)
        
        self.accept()
    
    def load_projects_list(self):
        self.projects_list.clear()
        
        for project in project_manager.projects.values():
            item = QListWidgetItem(f"{project.name}\n{project.root_path}")
            item.setData(Qt.UserRole, project.root_path)
            self.projects_list.addItem(item)
    
    def open_selected_project(self):
        current_item = self.projects_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a project")
            return
        
        project_path = current_item.data(Qt.UserRole)
        project_manager.open_project(project_path)
        
        if self.parent:
            self.parent.on_project_opened(project_manager.current_project)
        
        self.accept()
    
    def delete_project(self):
        current_item = self.projects_list.currentItem()
        if not current_item:
            return
        
        project_path = current_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Remove project from recent list?\n(This won't delete files)",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if project_path in project_manager.projects:
                del project_manager.projects[project_path]
                project_manager.save_projects()
                self.load_projects_list()
    
    def configure_project(self):
        current_item = self.projects_list.currentItem()
        if not current_item:
            return
        
        project_path = current_item.data(Qt.UserRole)
        
        if project_path in project_manager.projects:
            project = project_manager.projects[project_path]
            dialog = ProjectConfigDialog(project, self)
            if dialog.exec_() == QDialog.Accepted:
                project_manager.update_project_config(dialog.get_config())
                self.load_projects_list()

class ProjectConfigDialog(QDialog):
    def __init__(self, project_config, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.setWindowTitle(f"Configure Project: {project_config.name}")
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(self.project_config.name)
        self.root_path_edit = QLineEdit(self.project_config.root_path)
        self.root_path_edit.setReadOnly(True)
        self.launch_command_edit = QTextEdit()
        self.launch_command_edit.setPlainText(self.project_config.launch_command)
        self.launch_command_edit.setMaximumHeight(100)
        
        layout.addRow("Project Name:", self.name_edit)
        layout.addRow("Root Path:", self.root_path_edit)
        layout.addRow("Launch Command:", self.launch_command_edit)
        
        # Кнопки
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addRow(button_layout)
    
    def get_config(self):
        self.project_config.name = self.name_edit.text()
        self.project_config.launch_command = self.launch_command_edit.toPlainText()
        return self.project_config
    
    def save_config(self):
        self.accept()