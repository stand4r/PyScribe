"""PyScribe utils/programs.py: application module and reusable component."""
from core.logging_config import get_logger
import shutil
from os import path, getlogin, name, environ, remove, makedirs, listdir
from dataclasses import dataclass, asdict
from typing import Dict, Any
import json
from pathlib import Path

try:
    from os import getuid
except ImportError:
    pass
from json import load, dumps


import hashlib


def _state_dir() -> Path:
    """Stable per-user state directory, independent of current working directory."""
    import tempfile
    root = Path(tempfile.gettempdir()) / "PyScribe"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_file(filename: str) -> Path:
    return _state_dir() / filename


def _project_session_file(project_path: str) -> Path:
    sessions_dir = _state_dir() / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    norm = str(Path(project_path).resolve()).lower()
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return sessions_dir / f"proj_{h}.json"


def saveSession(files_array: list, project_path: str = None):
    """Save session files. If project_path is provided, files are stored strictly for that project."""
    clean_files = [str(x) for x in files_array if str(x) and not str(x).startswith("<") and Path(str(x)).exists()]
    clean_files = list(dict.fromkeys(clean_files))

    if project_path:
        target = _project_session_file(project_path)
        payload = {
            "project_path": str(Path(project_path).resolve()),
            "files": clean_files
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        target = _state_file("session_standalone.json")
        target.write_text(json.dumps(clean_files, ensure_ascii=False, indent=2), encoding="utf-8")
        _state_file("session.json").write_text(json.dumps(clean_files, ensure_ascii=False, indent=2), encoding="utf-8")


def loadSession(project_path: str = None) -> list:
    """Load session files. If project_path is provided, only files belonging to that project are returned."""
    try:
        if project_path:
            target = _project_session_file(project_path)
            if not target.exists():
                return []
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                files = data.get("files", [])
            elif isinstance(data, list):
                files = data
            else:
                files = []
            return [str(x) for x in files if Path(str(x)).exists()]
        else:
            target = _state_file("session_standalone.json")
            if not target.exists():
                target = _state_file("session.json")
            if not target.exists():
                return []
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data if Path(str(x)).exists()]
            return []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def saveRecent(recent_files: list):
    unique = list(dict.fromkeys(str(x) for x in recent_files))
    _state_file("recent.json").write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8")


def removeRecentFile():
    try:
        _state_file("recent.json").unlink()
    except FileNotFoundError:
        pass


def clearCache():
    for filename in ("recent.json", "session.json", "session_standalone.json", "recent.pkl", "session.pkl"):
        try:
            _state_file(filename).unlink()
        except FileNotFoundError:
            pass
    sessions_dir = _state_dir() / "sessions"
    if sessions_dir.exists():
        try:
            shutil.rmtree(sessions_dir, ignore_errors=True)
        except Exception:
            pass


def loadRecent() -> list:
    try:
        data = json.loads(_state_file("recent.json").read_text(encoding="utf-8"))
        return list(dict.fromkeys(str(x) for x in data)) if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        saveRecent([])
        return []


def exist_config(file_path):
    return path.exists(file_path)


def create_config(file_path):
    open(file_path, "w").write("{\n}")


def get_username():
    if name == 'nt':
        username = getlogin()
    else:
        import pwd
        username = pwd.getpwuid(getuid())[0]
    return username


def get_scriptdir():
    return path.dirname(path.realpath(__file__))


def loadConfigFromJson(file_path, need_dict):
    if not path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)[need_dict]
    except Exception:
        return None


def dumpJsonFile(file_path, json_data):
    try:
        with open(file_path, 'r+') as f:
            f.seek(0)
            f.write(dumps(json_data))
            f.truncate()
    except Exception:
        return None


def loadJsonFile(file_path):
    if not path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)
    except Exception:
        return None


def load_settings(scriptPath):
    configPath = scriptPath + r"/config/settings.json"
    return load(open(configPath, "r"))


def update_settings(scriptPath, data):
    with open(scriptPath + r"/config/settings.json", 'r+') as f:
        f.seek(0)
        f.write(dumps(data))
        f.truncate()


def backup(file):
    """Создание backup с правильной кодировкой"""
    backup_folder = 'backups'
    backup_name = Path(file).name.split('.')[0] + '_backup.txt'
    
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = Path(temp_dir) / backup_folder
    else:
        file_path = Path(backup_folder)
    
    if not file_path.exists():
        file_path.mkdir(parents=True, exist_ok=True)
    
    backup_file = file_path / backup_name
    
    try:
        # Читаем оригинальный файл с определением кодировки
        encodings = ['utf-8', 'cp1251', 'latin1', 'iso-8859-1', 'cp866']
        content = None
        original_encoding = 'utf-8'
        
        for encoding in encodings:
            try:
                with open(file, "r", encoding=encoding) as f:
                    content = f.read()
                original_encoding = encoding
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            # Если не удалось прочитать как текст, читаем как бинарный
            with open(file, "rb") as f:
                binary_content = f.read()
                content = binary_content.decode('utf-8', errors='ignore')
                original_encoding = 'binary'
        
        # Сохраняем backup в UTF-8
        with open(backup_file, "w", encoding='utf-8') as f:
            f.write(content)
            f.write(f"\n# Original file: {file}\n")
            f.write(f"# Encoding: {original_encoding}\n")
            
    except Exception as e:
        logger.exception("Error creating backup for {file}: ")


def clear_backup():
    file_path = _state_dir() / 'backups'
    if file_path.exists():
        for child in file_path.iterdir():
            if child.is_file():
                try:
                    child.unlink()
                except OSError:
                    pass


def check_backups():
    file_path = _state_dir() / 'backups'
    if file_path.exists():
        return [str(p) for p in file_path.iterdir() if p.is_file()]
    return []


def restore_backup():
    """Восстановление из backup с обработкой кодировок"""
    files = check_backups()
    for file in files:
        try:
            # Пробуем разные кодировки
            encodings = ['utf-8', 'cp1251', 'latin1', 'iso-8859-1', 'cp866']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file, "r", encoding=encoding) as f:
                        content = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # Если ни одна кодировка не подошла, читаем как бинарный и пробуем декодировать
                with open(file, "rb") as f:
                    binary_content = f.read()
                    # Пробуем декодировать с игнорированием ошибок
                    try:
                        text = binary_content.decode('utf-8', errors='ignore')
                        content = text.splitlines(True)
                    except Exception:
                        # Если всё равно ошибка, пропускаем файл
                        logger.info(f"Could not decode backup file: {file}")
                        continue
            
            if content and len(content) > 1:
                original_file = content[-1].strip()
                # Проверяем существование оригинального файла
                if Path(original_file).exists():
                    # Записываем содержимое (все строки кроме последней)
                    with open(original_file, "w", encoding='utf-8') as f:
                        f.write("".join(content[0:-1]))
                    logger.info(f"Restored backup for: {original_file}")
                else:
                    logger.info(f"Original file not found: {original_file}")
                    
        except Exception as e:
            logger.exception("Error restoring backup {file}: ")
            continue
    
    # Очищаем backup после восстановления
    clear_backup()

@dataclass
class EditorSettings:
    main_color: str = "#013B81"
    text_color: str = "#ABB2BF"
    first_color: str = "#16171D"
    second_color: str = "#131313"
    tab_color: str = "#1F2228"
    fontsize: str = "12"
    font_size_tab: str = "10"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EditorSettings':
        valid_data = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid_data)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class SettingsManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.settings_path = None
            self.settings = None
    
    def initialize(self, script_path: str):
        self.settings_path = script_path + r"/config/settings.json"
        self.settings = self._load_settings()
    
    def _load_settings(self) -> EditorSettings:
        try:
            with open(self.settings_path, "r") as f:
                data = json.load(f)
            return EditorSettings.from_dict(data.get("settings", {}))
        except Exception as e:
            logger.exception("Error loading settings: ")
            return EditorSettings()
    
    def save_settings(self):
        if self.settings and self.settings_path:
            try:
                with open(self.settings_path, "r+") as f:
                    data = json.load(f)
                    data["settings"] = self.settings.to_dict()
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()
            except Exception as e:
                logger.exception("Error saving settings: ")
    
    def get_setting(self, key: str):
        return getattr(self.settings, key, None)
    
    def set_setting(self, key: str, value: Any):
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            self.save_settings()

# Глобальный экземпляр
settings_manager = SettingsManager()

logger = get_logger("programs")
