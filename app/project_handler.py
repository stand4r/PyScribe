"""PyScribe project lifecycle and workspace handler."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog, QMessageBox

from core.logging_config import get_logger
from utils.programs import loadSession
from widgets.AnalysisProfilesDialog import ProjectAnalyzerDialog
from widgets.ProjectDialog import ProjectDialog

if TYPE_CHECKING:
    from app.main_window import ModernMainWindow

logger = get_logger("project_handler")


class ProjectHandler:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window

    def open_project(self):
        dialog = ProjectDialog(self.main_window)
        result = dialog.exec_()
        if result == QDialog.Accepted and dialog.selected_project is not None:
            self.on_project_opened(dialog.selected_project)

    def _choose_analyzers(self, project_config):
        current = getattr(project_config, 'analyzers', None)
        if current is None and isinstance(project_config, dict):
            current = project_config.get('analyzers')
        if current is None:
            current = ['structure', 'dependencies']
        try:
            dialog = ProjectAnalyzerDialog(project_config, current=current, parent=self.main_window)
        except Exception:
            logger.exception("Не удалось открыть выбор профилей анализа")
            return current
        if dialog.exec_() != QDialog.Accepted:
            return None
        if isinstance(project_config, dict):
            project_config['analyzers'] = dialog.selected_analyzers
        else:
            project_config.analyzers = dialog.selected_analyzers
        try:
            from widgets.ProjectManager import project_manager
            project_manager.update_project_config(project_config)
        except Exception:
            pass
        return dialog.selected_analyzers

    def _normalize_root(self, project_config) -> str:
        if hasattr(project_config, "root_path"):
            return str(Path(project_config.root_path).resolve())
        if isinstance(project_config, dict):
            return str(Path(project_config.get("root", project_config.get("root_path", "."))).resolve())
        if isinstance(project_config, (str, Path)):
            return str(Path(project_config).resolve())
        return ""

    def on_project_opened(self, project_config, choose_analyzers: bool = True):
        """Open a project.

        ``choose_analyzers=False`` is used by the command line / Explorer
        integration: the user double-clicked a folder and expects the project to
        open immediately, without the analysis-profile dialog.
        """
        norm_root = self._normalize_root(project_config)
        if not norm_root:
            return

        if hasattr(project_config, "root_path"):
            project_config.root_path = norm_root

        analyzers = self._choose_analyzers(project_config) if choose_analyzers else None
        if analyzers is None:
            analyzers = getattr(project_config, 'analyzers', None)
            if analyzers is None and isinstance(project_config, dict):
                analyzers = project_config.get('analyzers')
            if analyzers is None:
                analyzers = ['structure', 'dependencies', 'health']

        if self.main_window.current_project:
            self.main_window.save_current_session()
        self.main_window.close_all_editor_tabs()
        self.main_window.close_special_tab('welcome')
        self.main_window.close_special_tab('settings')

        self.main_window.current_project = project_config
        # Build the completion index in small batches instead of parsing the
        # whole project on the UI thread (that froze the window on big trees).
        # Even the file-list walk is deferred: it scans thousands of paths and
        # used to hold the GUI thread while the project view was appearing.
        QtCore.QTimer.singleShot(30, lambda: self._start_index(norm_root))
        name = getattr(project_config, "name", Path(norm_root).name)
        self.main_window.start_busy_indicator(f"Открытие и анализ проекта '{name}'...")
        self.main_window._analysis_failed = False
        try:
            self.main_window.intelligence_panel.set_project(norm_root, analyzers)
        except Exception:
            logger.exception("PyScribe operation failed")
        self.main_window.extension_manager.set_project_root(norm_root)
        try:
            from core.code_analysis.service import UnifiedCodeAnalysisService
            UnifiedCodeAnalysisService.get_instance().set_project_root(norm_root)
        except Exception:
            pass
        try:
            if hasattr(self.main_window, "todo_panel") and self.main_window.todo_panel:
                self.main_window.todo_panel.set_project(norm_root)
        except Exception:
            pass
        self.main_window.refresh_extensions_panel()
        self.main_window.search_panel.set_root(norm_root)
        self.main_window.git_panel.set_root(norm_root)
        self.main_window.update_window_title()

        self.main_window.project_indicator.setText(name)
        self.main_window.project_indicator.setVisible(True)
        self.main_window._set_explorer_location_title(norm_root)

        self._init_workspace_dir(norm_root)
        self._update_file_explorer_root(norm_root)

        if hasattr(self.main_window, 'activity_bar'):
            self.main_window.activity_bar.set_activity("explorer")
        if not self.main_window.sidebar_visible:
            self.main_window.toggle_sidebar()

        self._restore_project_session_files(norm_root, project_config)
        self.main_window._update_project_menu()
        self.main_window.run_panel.refresh()
        self.main_window.status_bar.showMessage(f'Проект открыт: {name} · рабочая область')
        self.main_window.update_analysis_panels()
        self._sync_ai_context()

    def _sync_ai_context(self):
        """Project context is selected automatically once a project is open."""
        panel = getattr(self.main_window, "ai_panel", None)
        if panel is None:
            return
        try:
            panel.sync_scope_with_project()
        except Exception:
            logger.exception("Не удалось синхронизировать контекст ИИ-агента")

    def _set_terminal_workspace(self, root_str: str):
        if not self.main_window.console_widget:
            return
        terminal = self.main_window.console_widget.get_terminal()
        if terminal:
            terminal.switch_session(root_str)

    def _update_file_explorer_root(self, norm_root: str):
        fe = getattr(self.main_window, 'file_explorer', None)
        if not fe or not fe.model:
            return
        try:
            root_index = fe.model.setRootPath(norm_root)
            fe.set_workspace_root(norm_root)
            fe.setRootIndex(root_index)
        except Exception:
            logger.exception("PyScribe operation failed")

    def _start_index(self, norm_root: str):
        """Walk the project tree for completion, then feed it in batches.

        The walk is a pure file-system job, so it runs on the thread pool and
        the GUI thread only receives the finished list; the parsing batches
        then run from a timer.
        """
        index = getattr(self.main_window, 'workspace_index', None)
        if index is None:
            return
        try:
            index.prepare_root(norm_root)
            from services.background import run_async
            run_async(
                index.scan_source_files,
                on_done=self._on_index_files_scanned,
                on_error=lambda message: logger.warning(
                    "Не удалось просканировать проект для индекса: %s", message),
            )
        except Exception:
            logger.exception("Не удалось построить индекс проекта")

    def _on_index_files_scanned(self, files):
        """Completion index receives the discovered files (GUI thread)."""
        try:
            self.main_window.workspace_index.set_pending_files(files or [])
            self.main_window.start_index_batching()
        except Exception:
            logger.exception("Не удалось построить индекс проекта")

    def _restore_project_session_files(self, norm_root: str, project_config: dict):
        """Reopen the project's tabs one per event-loop turn.

        Opening every restored file in one go blocked the GUI thread for the
        whole batch: each editor builds a syntax highlighter for its text, and
        while that runs every animation in the window stops. Spreading the work
        keeps the workbench painting between files.
        """
        project_session_files = loadSession(project_path=norm_root)
        valid_files = [f for f in project_session_files if Path(f).exists()]
        if not valid_files:
            self.open_project_files(project_config)
            return
        self._restore_queue = list(valid_files)
        QtCore.QTimer.singleShot(0, self._restore_next_session_file)

    def _restore_next_session_file(self):
        """Open the next restored tab, then yield to the event loop."""
        queue = getattr(self, '_restore_queue', None) or []
        if not queue:
            self._restore_queue = []
            return
        path = queue.pop(0)
        try:
            self.main_window.file_manager.open_file(path)
        except Exception:
            pass
        if queue:
            # ~2 frames of breathing room so the tab bar and the busy overlay
            # keep animating instead of freezing for the whole restore.
            QtCore.QTimer.singleShot(24, self._restore_next_session_file)

    def _init_workspace_dir(self, norm_root: str):
        project_root = Path(norm_root)
        try:
            project_root.mkdir(parents=True, exist_ok=True)
            project_root_str = str(project_root)
            self.main_window.workspace_path = project_root_str
            self._set_terminal_workspace(project_root_str)
        except Exception as exc:
            self.main_window.workspace_path = norm_root
            if hasattr(self.main_window, 'workbench'):
                self.main_window.workbench.announce(f'Workspace fallback: {exc}')

    def _find_entry_document(self, project_path: Path):
        readme_files = sorted(project_path.glob("README*"))
        if readme_files:
            return str(readme_files[0])
        for cand in ["main.py", "app.py", "index.js", "index.html", "src/main.rs", "main.go"]:
            p = project_path / cand
            if p.is_file():
                return str(p)
        return None

    def open_project_files(self, project_config):
        """Open a useful entry document (README, main.py, index.js, etc.)"""
        try:
            root = self._normalize_root(project_config)
            if not root:
                return
            entry = self._find_entry_document(Path(root))
            if entry:
                self.main_window.file_manager.open_file(entry)
        except Exception:
            logger.exception("PyScribe operation failed")

    def run_project(self):
        if not self.main_window.current_project:
            self.show_no_project_message()
            return

        project = self.main_window.current_project

        if not project.launch_command:
            reply = QMessageBox.question(
                self.main_window, "Конфигурация проекта",
                "Для этого проекта не настроена команда запуска. Настроить её сейчас?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.main_window.action_project_settings()
            return

        if self.main_window.terminal_widget:
            self.main_window.run_in_terminal(
                project.launch_command, 
                working_dir=project.root_path
            )

    def show_no_project_message(self):
        QMessageBox.information(
            self.main_window, 
            "Нет открытого проекта", 
            "Сейчас нет открытого проекта.\n\n"
            "Используйте «Открыть проект», чтобы открыть существующий проект,\n"
            "или «Управление проектами», чтобы создать новый."
        )
