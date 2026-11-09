"""PyScribe utils/settings_manager.py: application module and reusable component."""
# utils/programs/settings_manager.py
import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_SETTINGS = {
    "theme": "midnight",
    "accent_color": "#5EA6FF",
    "app_background": "#0F141A",
    "editor_background": "#121923",
    "sidebar_background": "#0F141A",
    "panel_background": "#0D1218",
    "input_background": "#1A2430",
    "hover_background": "#202C39",
    "active_background": "#263447",
    "selection_background": "#234B78",
    "border_color": "#25303C",
    "text_primary": "#E3ECF7",
    "text_secondary": "#9DAEC1",
    "editor_font": "Cascadia Code",
    "editor_font_size": 13,
    # Empty = auto: the best installed interface face is picked at startup
    # (see app/styling.py: resolve_ui_font).
    "ui_font": "",
    "ui_font_size": 13,
    # Global workbench scale in percent (accessibility / low vision support).
    "ui_scale_percent": 100,
    # AI assistant (OpenAI-compatible chat completions API).
    "ai_enabled": True,
    "ai_provider": "deepseek",
    "ai_base_url": "https://api.deepseek.com",
    "ai_model": "deepseek-flash",
    "ai_api_key": "",
    # Per-provider keys: {"deepseek": "sk-...", "gemini": "AIza..."}.
    "ai_provider_keys": {},
    "ai_temperature": 3,
    # 0 = no local output budget (the provider's own maximum applies).
    "ai_max_tokens": 0,
    # How hard the model should think: auto | none | low | medium | high.
    "ai_reasoning_effort": "auto",
    "ai_system_prompt": "",
    # What the agent attaches: project | file | none (default: no context).
    "ai_context_scope": "none",
    # Project tools for the agent: file edits, terminal, launching apps.
    "ai_allow_file_edits": True,
    "ai_access_mode": "full",
    "ai_allow_commands": True,
    # Agent behaviour: solve (full answers) | teach (Socratic tutor).
    "ai_mode": "solve",
    # Tutor strictness: soft | normal | strict.
    "ai_teach_strictness": "normal",
    # Show the model's reasoning ("размышления") while it is working.
    "ai_show_reasoning": True,
    # JSON list of MCP servers (see services/mcp_client.py).
    "ai_mcp_servers": "",
    "ai_mcp_enabled": True,
    "sidebar_width": 280,
    "bottom_panel_height": 240,
    "terminal_panel_height": 240,
    "tab_height": 36,
    "show_line_numbers": True,
    "syntax_highlighting": True,
    "word_wrap": False,
    "auto_save_interval": 30,
    "restore_session": False,
    "show_welcome": True,
    "terminal_highlighting": True,
    "terminal_font_size": 13,
    "toolchains": {},
    "run_arguments": "",
    "run_working_directory": "",
    "run_save_before_launch": True,
    "run_use_terminal": True,
    "run_confirm_unsafe": True,
    "analysis_enabled": True,
    "analysis_on_open": True,
    "analysis_on_save": True,
    "analysis_delay_ms": 350,
    "analysis_max_file_mb": 32,
    "recent_projects_limit": 10,
    "project_restore_last": False,
    "project_open_readme": True,
    "project_deduplicate_recent": True,
    "floating_terminal": True,
    "reuse_settings_tab": True,
    "reuse_welcome_tab": True,
    "focus_new_tabs": True,
    "remember_window_geometry": True,
}


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
                    loaded = json.load(f)
                self.settings = dict(DEFAULT_SETTINGS)
                if isinstance(loaded, dict):
                    self.settings.update(loaded)
            except Exception:
                self.settings = dict(DEFAULT_SETTINGS)
        else:
            self.settings = dict(DEFAULT_SETTINGS)
        # The JSON file is the source of truth at startup. Missing keys are
        # filled in memory; persistence happens only when settings are changed.
    
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

    def get(self, key: str, default: Any = None) -> Any:
        """Совместимость с dict.get()"""
        return self.get_setting(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.settings[key]

    def __setitem__(self, key: str, value: Any):
        self.settings[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.settings

    def keys(self):
        return self.settings.keys()

    def values(self):
        return self.settings.values()

    def items(self):
        return self.settings.items()
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Установить значение настройки"""
        self.settings[key] = value
        return self.save_settings()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Получить все настройки"""
        return self.settings.copy()
    
    def reset_to_default(self, default_settings: object) -> bool:
        """Сбросить настройки к значениям по умолчанию.

        Only real data is copied: iterating ``dir()`` also picked up bound
        methods (``to_dict``/``from_dict``), which made the later ``json.dump``
        fail and the reset silently do nothing.
        """
        values: Dict[str, Any] = {}
        if isinstance(default_settings, dict):
            values = dict(default_settings)
        else:
            if hasattr(default_settings, "__dict__"):
                values = {k: v for k, v in vars(default_settings).items()
                          if not k.startswith('_') and not callable(v)}
            if not values:
                # Dataclass or plain object: fall back to the known defaults.
                values = dict(DEFAULT_SETTINGS)
        for key, value in values.items():
            if callable(value):
                continue
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
