"""PyScribe workbench orchestration controller."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.main_window import ModernMainWindow


class WorkbenchController:
    """Single orchestration layer for the running PyScribe workbench.

    UI widgets stay focused on presentation; all launch/terminal/project
    hand-offs pass through this object so Run, project launch, tests and
    Project Intelligence behave as one workflow.
    """
    def __init__(self, window: 'ModernMainWindow'):
        self.window = window

    def announce(self, message: str):
        terminal = getattr(self.window, "console_widget", None)
        if not terminal:
            return
        terminal.set_current_tab("Терминал")
        tab = terminal.get_terminal()
        if not tab:
            return
        current = tab._current()
        if current:
            current.append_system_line(f"[PyScribe] {message}")

    def run_file(self, file_path):
        self.window.run_target(str(file_path), False)

    def run_project(self):
        project = self.window.current_project
        if not project:
            self.window.project_handler.show_no_project_message()
            return
        launch = (getattr(project, "launch_command", "") or "").strip()
        if launch:
            self.window.run_in_terminal_command(launch, getattr(project, "root_path", None))
            self.announce(f"Проект: {project.name}")
            self.window.status_bar.showMessage(f"Запуск проекта {project.name}")
            return
        # No explicit launch command: resolve an entry point instead of failing
        # silently. run_project_target() reports a clear message if none exists.
        self.announce(f"Команда запуска не задана — ищу точку входа проекта «{project.name}»")
        self.window.run_project_target(False)

    def run_tests(self):
        self.window.run_tests()

    def project_opened(self, project):
        if project:
            self.announce(f"Проект открыт: {project.name}")
            self.announce(f"Рабочая область: {project.root_path}")
