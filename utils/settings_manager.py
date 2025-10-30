# utils/programs/settings_manager.py
import json
import os
from pathlib import Path
from typing import Any, Dict

class SettingsManager:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.settings = {}
        self.load_settings()
    
    def load_settings(self):
        """Загрузить настройки из файла"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            except Exception:
                self.settings = {}
        else:
            self.settings = {}
            self.save_settings()
    
    def save_settings(self):
        """Сохранить настройки в файл"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки"""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Установить значение настройки"""
        self.settings[key] = value
        return self.save_settings()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Получить все настройки"""
        return self.settings.copy()
    
    def reset_to_default(self, default_settings: object) -> bool:
        """Сбросить настройки к значениям по умолчанию"""
        for key in dir(default_settings):
            if not key.startswith('_'):
                value = getattr(default_settings, key)
                self.settings[key] = value
        return self.save_settings()

# Глобальный экземпляр менеджера настроек
_settings_manager = None

def init_settings_manager(config_path: str):
    global _settings_manager
    _settings_manager = SettingsManager(config_path)

def get_settings_manager() -> SettingsManager:
    global _settings_manager
    if _settings_manager is None:
        raise RuntimeError("Settings manager not initialized")
    return _settings_manager