"""PyScribe entry point.

Initializes the PyScribe IDE environment and launches the main application window.
All core subsystems are modularized under the `app` package:
- `app.application`: ApplicationManager, lifecycle, bootstrap
- `app.main_window`: ModernMainWindow
- `app.controller`: WorkbenchController
- `app.top_bar`: WorkbenchTopBar, ExplorerHeader
- `app.ui_manager`: UIManager
- `app.file_manager`: FileManager
- `app.project_handler`: ProjectHandler
- `app.code_runner`: CodeRunner
- `app.styling`: theme loading and design tokens
"""
from __future__ import annotations

import sys
from app.application import ApplicationManager, main
from app.code_runner import CodeRunner
from app.controller import WorkbenchController
from app.file_manager import FileManager
from app.main_window import ModernMainWindow
from app.project_handler import ProjectHandler
from app.styling import (
    _DesignSystemEventFilter,
    _load_design_qss,
    _set_windows_app_identity,
    setup_application_style,
)
from app.top_bar import TITLE_BAR_HEIGHT, ExplorerHeader, WorkbenchTopBar
from app.ui_manager import UIManager

__all__ = [
    "main",
    "ApplicationManager",
    "ModernMainWindow",
    "WorkbenchController",
    "WorkbenchTopBar",
    "ExplorerHeader",
    "TITLE_BAR_HEIGHT",
    "UIManager",
    "FileManager",
    "ProjectHandler",
    "CodeRunner",
    "setup_application_style",
    "_load_design_qss",
    "_DesignSystemEventFilter",
    "_set_windows_app_identity",
]


if __name__ == "__main__":
    main()
