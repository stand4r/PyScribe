"""PyScribe application lifecycle, settings management, and bootstrap."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

from app.styling import _set_windows_app_identity, setup_application_style
from core.logging_config import configure_logging, get_logger
from core.single_instance import SingleInstance
from utils.programs import loadRecent, loadSession
from utils.settings_manager import get_settings_manager, init_settings_manager

logger = get_logger("application")


class ApplicationManager:
    """
    Класс `ApplicationManager`.
    Отвечает за инкапсуляцию бизнес-логики и управление состоянием объекта.
    Ключевые методы: colors, fonts, languages, supported_formats.
    """

    def __init__(self, base_path: str):
        """
        Назначение и краткое описание функции `__init__`.

        Args:
            base_path (str): Назначение и ожидаемые данные аргумента.
        """
        self.base_path = Path(base_path)
        self.logger = configure_logging(self.base_path)

        config_path = self._resolve_config_path(self.base_path)
        init_settings_manager(str(config_path))
        self.settings = self._load_settings()
        self.recent_files = loadRecent()
        self.session_files = loadSession()

    @staticmethod

    def _resolve_config_path(base_path: Path) -> Path:
        """
        Назначение и краткое описание функции `_resolve_config_path`.

        Args:
            base_path (Path): Назначение и ожидаемые данные аргумента.

        Returns:
             (Path)
        """
        bundled = base_path / "config" / "settings.default.json"
        if getattr(sys, "frozen", False):
            user_root = (
                Path(os.environ.get("APPDATA", Path.home())) / "PyScribe"
                if os.name == "nt"
                else Path.home() / ".config" / "PyScribe"
            )
            config_path = user_root / "settings.json"
        else:
            config_path = base_path / "config" / "settings.json"
        if not config_path.exists() and bundled.exists():
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
        return config_path

    def _load_settings(self):
        """Загрузить настройки через менеджер"""
        settings_manager = get_settings_manager()

        if not settings_manager.settings:
            from utils.programs import EditorSettings
            default_settings = EditorSettings()
            settings_manager.reset_to_default(default_settings)

        return settings_manager.get_all_settings()

    @property

    def colors(self) -> Dict[str, str]:
        """
        Назначение и краткое описание функции `colors`.

        Returns:
             (Dict[str, str])
        """
        return {
            'main': self.settings["settings"]["main_color"],
            'text': self.settings["settings"]["text_color"],
            'first': self.settings["settings"]["first_color"],
            'second': self.settings["settings"]["second_color"],
            'tab': self.settings["settings"]["tab_color"]
        }

    @property

    def fonts(self) -> Dict[str, int]:
        """
        Назначение и краткое описание функции `fonts`.

        Returns:
             (Dict[str, int])
        """
        return {
            'size': int(self.settings["settings"]["fontsize"]),
            'tab_size': self.settings["settings"]["font_size_tab"]
        }

    @property

    def languages(self) -> Dict[str, Any]:
        """
        Назначение и краткое описание функции `languages`.

        Returns:
             (Dict[str, Any])
        """
        return {
            'list': self.settings["languages"],
            'types': self.settings["languages_type"]
        }

    @property

    def supported_formats(self) -> Dict[str, List[str]]:
        """
        Назначение и краткое описание функции `supported_formats`.

        Returns:
             (Dict[str, List[str]])
        """
        return {
            'pdf': ['.pdf'],
            'images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp'],
            'text': ['.txt', '.py', '.js', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.php', '.rb', '.kt', '.swift', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.md', '.sql'],
            'office': ['.xlsx', '.docx']
        }


def open_external_target(window, argument) -> str:
    """Open one Explorer/CLI target. Returns ``file``, ``folder`` or ``missing``.

    A directory becomes the current project without the analysis-profile
    dialog, because «Открыть с помощью» must feel instant. Split from
    :func:`main` so the behaviour is unit-testable with a stub window.
    """
    path = Path(argument)
    if path.is_file():
        window.file_manager.open_file(str(path))
        return "file"
    if path.is_dir():
        from widgets.ProjectManager import ProjectConfig
        config = ProjectConfig(
            name=path.name,
            root_path=str(path),
            analyzers=["structure", "dependencies"],
        )
        window.project_handler.on_project_opened(config, choose_analyzers=False)
        return "folder"
    if path.exists():
        window.file_manager.open_file(str(path))
        return "file"
    return "missing"


def main():
    """PyScribe main entry function."""
    _set_windows_app_identity()
    QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)

    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        # Resolve to project root (parent directory of app/)
        base_path = Path(__file__).resolve().parent.parent

    instance = SingleInstance("PyScribe")
    if not instance.acquire(sys.argv[1:]):
        return
    app._pyscribe_instance = instance

    app_manager = ApplicationManager(str(base_path))
    setup_application_style(app, base_path)

    from app.main_window import ModernMainWindow
    window = ModernMainWindow(app_manager)

    def handle_external(arguments):
        """Open files/folders passed by Explorer ("Открыть с помощью" / CLI).

        The window is brought to the front first, then every target is opened:
        a file in the editor, a directory as a project (without the analyzer
        dialog — the context menu must open instantly).
        """
        window.showNormal()
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        for argument in arguments:
            try:
                open_external_target(window, argument)
            except Exception:  # noqa: BLE001 - never break the launch
                logger.exception("Не удалось открыть %s", argument)

    instance.message_received.connect(handle_external)
    app.aboutToQuit.connect(window.finalize_application)
    window.showMaximized()
    if len(sys.argv) > 1:
        # Explorer passes the clicked path as an argument; open it once the
        # window is actually on screen (the layout is not ready before that).
        QtCore.QTimer.singleShot(60, lambda: handle_external(sys.argv[1:]))
    sys.exit(app.exec_())
