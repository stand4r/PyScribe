"""PyScribe widgets/ProjectManager.py: application module and reusable component."""
from core.logging_config import get_logger
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import datetime

@dataclass
class ProjectConfig:
    name: str
    root_path: str
    launch_command: str = ""
    description: str = ""
    created_at: str = ""
    last_opened: str = ""
    analyzers: List[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectConfig':
        values = {k: v for k, v in data.items() if k in cls.__annotations__}
        if values.get('analyzers') is None:
            values['analyzers'] = ['structure', 'dependencies']
        return cls(**values)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def get_display_name(self) -> str:
        """Получить отображаемое имя проекта"""
        return self.name if self.name else Path(self.root_path).name
    
    def get_folder_name(self) -> str:
        """Получить имя папки проекта"""
        return Path(self.root_path).name
    
    def get_last_opened_display(self) -> str:
        """Получить отформатированное время последнего открытия"""
        if not self.last_opened:
            return "Никогда"
        try:
            last_opened = datetime.datetime.fromisoformat(self.last_opened.replace('Z', '+00:00'))
            now = datetime.datetime.now()
            diff = now - last_opened
            
            if diff.days == 0:
                return "Сегодня"
            elif diff.days == 1:
                return "Вчера"
            elif diff.days < 7:
                return f"{diff.days} дн. назад"
            elif diff.days < 30:
                weeks = max(1, diff.days // 7)
                return f"{weeks} нед. назад"
            else:
                return last_opened.strftime("%d.%m.%Y")
        except Exception:
            return "Неизвестно"

class ProjectManager:
    def __init__(self):
        self.current_project: Optional[ProjectConfig] = None
        self.projects_file = self._resolve_projects_file()
        self.projects: Dict[str, ProjectConfig] = {}
        self.load_projects()

    @staticmethod
    def _app_data_dir() -> Path:
        """Writable per-user directory for PyScribe state files."""
        if os.name == "nt":
            root = os.environ.get("APPDATA") or str(Path.home())
        else:
            root = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(root) / "PyScribe"

    @classmethod
    def _resolve_projects_file(cls) -> Path:
        """Absolute path for projects.json.

        The file used to be opened as the bare relative name ``projects.json``,
        which resolved against the process working directory — that made saving
        fail with ``PermissionError: [Errno 13]`` whenever the app was started
        from a protected folder (Program Files, another user's directory, the
        PyInstaller bundle, ...).
        """
        target_dir = cls._app_data_dir()
        target = target_dir / "projects.json"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Fall back to the user's home directory if APPDATA is unavailable.
            target = Path.home() / ".pyscribe-projects.json"
        # One-time migration of a legacy relative file next to the executable.
        if not target.exists():
            legacy = Path.cwd() / "projects.json"
            try:
                if legacy.exists() and legacy.is_file():
                    target.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                    logger.info("Migrated legacy projects.json to %s", target)
            except OSError:
                pass
        return target
    
    @staticmethod
    def _canonical_path(root_path: str) -> str:
        """Return one stable identity for a project path, including Windows case."""
        resolved = str(Path(root_path).expanduser().resolve())
        return os.path.normcase(os.path.normpath(resolved)).casefold()

    def _deduplicate(self) -> None:
        """Merge legacy duplicate project records by canonical filesystem path."""
        merged = {}
        for config in self.projects.values():
            try:
                config.root_path = str(Path(config.root_path).expanduser().resolve())
                key = self._canonical_path(config.root_path)
            except (OSError, ValueError):
                continue
            old = merged.get(key)
            if old is None:
                merged[key] = config
                continue
            old_time = old.last_opened or ""
            new_time = config.last_opened or ""
            if new_time > old_time:
                merged[key] = config
        self.projects = merged

    def load_projects(self):
        """Загрузка и нормализация списка проектов без дублей."""
        try:
            if os.path.exists(self.projects_file):
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.projects = {k: ProjectConfig.from_dict(v) for k, v in data.items()}
            else:
                self.projects = {}
            self._deduplicate()
            self.save_projects()
        except Exception:
            logger.exception("Error loading projects")
            self.projects = {}
    
    def save_projects(self) -> bool:
        """Persist the project list atomically. Returns True on success."""
        path = Path(self.projects_file)
        payload = json.dumps({k: v.to_dict() for k, v in self.projects.items()},
                             indent=2, ensure_ascii=False)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write to a sibling temp file first so a crash cannot truncate the
            # real file, then replace it in one step.
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
            return True
        except PermissionError:
            logger.error(
                "Error saving projects: нет прав на запись в %s. "
                "Файл проектов должен лежать в пользовательском каталоге.",
                path)
            self._last_save_error = "Нет прав на запись в " + str(path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error saving projects: ")
            self._last_save_error = str(exc)
        return False
    
    def create_project(self, root_path: str, name: str = None, launch_command: str = "", description: str = "") -> ProjectConfig:
        """Создание нового проекта"""
        root_path = str(Path(root_path).expanduser().resolve())
        canonical = self._canonical_path(root_path)
        existing = next((p for p in self.projects.values() if self._canonical_path(p.root_path) == canonical), None)
        if existing:
            existing.last_opened = datetime.datetime.now().isoformat()
            self.current_project = existing
            self.save_projects()
            return existing
        if name is None:
            name = Path(root_path).name
        
        project = ProjectConfig(
            name=name,
            root_path=root_path,
            launch_command=launch_command,
            description=description,
            created_at=datetime.datetime.now().isoformat(),
            last_opened=datetime.datetime.now().isoformat(),
            analyzers=['structure', 'dependencies', 'health']
        )
        
        self.projects[self._canonical_path(root_path)] = project
        self._deduplicate()
        self.save_projects()
        return project
    
    def open_project(self, root_path: str) -> Optional[ProjectConfig]:
        """Открытие проекта"""
        root_path = str(Path(root_path).expanduser().resolve())
        canonical = self._canonical_path(root_path)
        match = next((p for p in self.projects.values() if self._canonical_path(p.root_path) == canonical), None)
        if match is not None:
            self.current_project = match
            # Обновляем время последнего открытия
            self.current_project.last_opened = datetime.datetime.now().isoformat()
            self.save_projects()
        else:
            self.current_project = self.create_project(root_path)
        
        return self.current_project
    
    def close_project(self):
        """Закрытие текущего проекта"""
        self.current_project = None
    
    def update_project_config(self, config: ProjectConfig):
        """Обновление конфигурации проекта"""
        config.root_path = str(Path(config.root_path).resolve())
        self.projects[self._canonical_path(config.root_path)] = config
        self._deduplicate()
        if self.current_project and str(Path(self.current_project.root_path).resolve()) == config.root_path:
            self.current_project = config
        self.save_projects()
    
    def get_recent_projects(self, limit: int = 10) -> List[ProjectConfig]:
        """Получение списка недавних проектов"""
        self._deduplicate()
        projects = list(self.projects.values())
        seen = set()
        unique = []
        for project in sorted(projects, key=lambda x: x.last_opened or "", reverse=True):
            key = self._canonical_path(project.root_path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(project)
        return unique[:limit]
    
    def get_sorted_projects(self) -> List[ProjectConfig]:
        """Получение отсортированного списка проектов"""
        projects = list(self.projects.values())
        projects.sort(key=lambda x: x.get_display_name().lower())
        return projects
    
    def get_project_files(self) -> List[str]:
        """Получение списка файлов проекта"""
        if not self.current_project:
            return []
        
        project_files = []
        root_path = Path(self.current_project.root_path)

        from core.ignore_rules import walk_files
        # One pruned pass instead of eleven full rglob walks over the project.
        extensions = {f".{ext}" for ext in
                      ('py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php', 'rb',
                       'go', 'rs')}
        scan = walk_files(root_path, extensions=extensions, max_files=5000)
        project_files.extend(scan.files)

        return [str(f) for f in project_files]
    
    def is_file_in_project(self, file_path: str) -> bool:
        """Проверка принадлежности файла к проекту"""
        if not self.current_project:
            return False
        
        try:
            file_path = Path(file_path).resolve()
            project_path = Path(self.current_project.root_path).resolve()
            return file_path.is_relative_to(project_path)
        except Exception:
            return False
    
    def delete_project(self, root_path: str) -> bool:
        """Удаляет проект из менеджера по каноническому или исходному пути."""
        try:
            if not root_path:
                return False
            canonical = self._canonical_path(root_path)
            keys_to_remove = []
            for key, config in list(self.projects.items()):
                if key == root_path or key == canonical:
                    keys_to_remove.append(key)
                elif hasattr(config, "root_path") and self._canonical_path(config.root_path) == canonical:
                    keys_to_remove.append(key)
                elif self._canonical_path(key) == canonical:
                    keys_to_remove.append(key)

            if keys_to_remove:
                for k in set(keys_to_remove):
                    self.projects.pop(k, None)
                if self.current_project and self._canonical_path(self.current_project.root_path) == canonical:
                    self.current_project = None
                self.save_projects()
                return True
            return False
        except Exception:
            logger.exception("Error deleting project: ")
            return False


logger = get_logger("ProjectManager")

# Глобальный экземпляр
project_manager = ProjectManager()
