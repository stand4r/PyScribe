"""PyScribe core application package.

Provides modularized IDE subsystems:
- application: lifecycle, settings, and bootstrap
- main_window: workbench window
- top_bar: workbench header, menu bar, and explorer chrome
- ui_manager: workbench layout and panel management
- file_manager: file operations, viewers, and tab routing
- project_handler: project opening, session, and workspace configuration
- code_runner: script execution and launch arguments
- controller: workbench orchestration and event coordination
- styling: theme loading and application-wide styles
"""
from __future__ import annotations

from app.application import ApplicationManager, main
from app.code_runner import CodeRunner
from app.controller import WorkbenchController
from app.file_manager import FileManager
from app.main_window import ModernMainWindow
from app.project_handler import ProjectHandler
from app.styling import setup_application_style, _load_design_qss
from app.top_bar import ExplorerHeader, TITLE_BAR_HEIGHT, WorkbenchTopBar
from app.ui_manager import UIManager

__all__ = [
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
    "main",
]
