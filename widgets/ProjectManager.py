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