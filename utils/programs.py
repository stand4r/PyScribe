import pickle
import shutil
from os import path, getlogin, name, environ, remove, makedirs, listdir
from dataclasses import dataclass, asdict
from typing import Dict, Any
import json
from pathlib import Path

try:
    from os import getuid
except:
    pass
from json import load, dumps


def saveSession(files_array: list):
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)

        if temp_dir:
            file_path = path.join(temp_dir, "session.pkl")
    else:
        file_path = "session.pkl"
    with open(file_path, 'wb') as f:
        pickle.dump((files_array), f)


def loadSession() -> list:
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "session.pkl")
    else:
        file_path = "session.pkl"
    try:
        with open(file_path, 'rb') as f:
            files_array = pickle.load(f)
    except FileNotFoundError:
        with open(file_path, 'wb') as f:
            pickle.dump([], f)
        files_array = []
    return files_array


def saveRecent(recent_files: list):
    recent_files = list(set(recent_files))
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    with open(file_path, 'wb') as f:
        pickle.dump((recent_files), f)


def removeRecentFile():
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    remove(file_path)


def clearCache():
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path_recent = path.join(temp_dir, "recent.pkl")
            file_path_session = path.join(temp_dir, "session.pkl")
    else:
        file_path_recent = "recent.pkl"
        file_path_session = "session.pkl"
    remove(file_path_recent)
    remove(file_path_session)


def loadRecent() -> list:
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    try:
        with open(file_path, 'rb') as f:
            files_array = pickle.load(f)
            files_array = list(set(files_array))
            return files_array
    except FileNotFoundError:
        with open(file_path, 'wb') as f:
            pickle.dump([], f)
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
    except:
        return None


def dumpJsonFile(file_path, json_data):
    try:
        with open(file_path, 'r+') as f:
            f.seek(0)
            f.write(dumps(json_data))
            f.truncate()
    except:
        return None


def loadJsonFile(file_path):
    if not path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)
    except:
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
        print(f"Error creating backup for {file}: {e}")


def clear_backup():
    backup_folder = 'backups'
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, backup_folder)
    else:
        file_path = backup_folder
    if path.exists(file_path):
        for name_file in listdir(file_path):
            remove(path.join(file_path, name_file))


def check_backups():
    files = list()
    backup_folder = 'backups'
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, backup_folder)
    else:
        file_path = backup_folder
    if path.exists(file_path):
        for name_file in listdir(file_path):
            files.append(path.join(file_path, name_file))
        return files
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
                    except:
                        # Если всё равно ошибка, пропускаем файл
                        print(f"Could not decode backup file: {file}")
                        continue
            
            if content and len(content) > 1:
                original_file = content[-1].strip()
                # Проверяем существование оригинального файла
                if Path(original_file).exists():
                    # Записываем содержимое (все строки кроме последней)
                    with open(original_file, "w", encoding='utf-8') as f:
                        f.write("".join(content[0:-1]))
                    print(f"Restored backup for: {original_file}")
                else:
                    print(f"Original file not found: {original_file}")
                    
        except Exception as e:
            print(f"Error restoring backup {file}: {e}")
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
            print(f"Error loading settings: {e}")
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
                print(f"Error saving settings: {e}")
    
    def get_setting(self, key: str):
        return getattr(self.settings, key, None)
    
    def set_setting(self, key: str, value: Any):
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            self.save_settings()

# Глобальный экземпляр
settings_manager = SettingsManager()