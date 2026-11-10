"""PyScribe main workbench window."""
from __future__ import annotations

import json
import sys
import shlex
import os
from pathlib import Path
from functools import partial
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QSize, QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox,
    QDialog, QVBoxLayout, QLabel, QPushButton
)

from utils.FabricRunCode import *
from utils.programs import (
    load_settings, loadRecent, saveRecent, loadSession,
    saveSession, clearCache, clear_backup, backup, restore_backup
)
from utils.settings_manager import init_settings_manager, get_settings_manager
from utils.CSharpCompiler import *
from widgets.ProjectDialog import ProjectDialog, ProjectConfigDialog
from widgets.AnalysisProfilesDialog import ProjectAnalyzerDialog
from widgets.KeyboardShortcutsDialog import KeyboardShortcutsDialog
from widgets.ExtensionsWidget import ExtensionsWidget
from widgets.ChangeCapsuleDialog import ChangeCapsuleDialog
from widgets.Dialog import CustomDialog
from widgets.QArgsEditor import ArgsWindow
from widgets.SettingsWidget import SettingsWidget
from widgets.AboutDialog import AboutDialog
from widgets.ShellIntegrationDialog import ShellIntegrationDialog
from widgets.UpdateDialog import UpdateDialog
from widgets.WelcomeWidget import Ui_Welcome
from widgets.TabWidget import TabWidget
from widgets.PushButtons import *
from widgets.Explorer import Explorer
from widgets.QCodeEditor import ModernCodeEditor
from widgets.ConsoleWidget import ConsoleWidget
from widgets.HexViewer import HexViewer
from widgets.DocumentViewerWidget import DocumentViewerWidget
from widgets.ActivityBar import ActivityBar
from widgets.SearchPanel import SearchPanel
from widgets.CommandPalette import CommandPalette
from widgets.QuickOpenDialog import QuickOpenDialog
from core.single_instance import SingleInstance
from core.logging_config import configure_logging, get_logger
from widgets.GitPanel import GitPanel
from utils.WorkspaceIndex import WorkspaceIndex
from widgets.ProjectIntelligenceDashboard import ProjectIntelligenceDashboard, ProjectGraphEditorWidget
from widgets.RunDebugPanel import RunDebugPanel
from extensions import ExtensionManager
from design.themes import THEMES, THEME_NAMES

from app.top_bar import WorkbenchTopBar, ExplorerHeader
from app.ui_manager import UIManager
from app.file_manager import FileManager
from app.project_handler import ProjectHandler
from app.code_runner import CodeRunner
from app.controller import WorkbenchController
from app.styling import _load_design_qss, setup_application_style

if TYPE_CHECKING:
    from app.application import ApplicationManager

logger = get_logger("main_window")


class ModernMainWindow(QMainWindow):
    """Класс `ModernMainWindow`. Наследует: QMainWindow.

    Инкапсулирует бизнес-логику и состояние объекта.

    Attributes:
        app_manager: Параметр app manager.
        unsaved_files_count: Параметр unsaved files count.
        sidebar_visible: Параметр sidebar visible.
        terminal_visible: Параметр terminal visible.
        config_path: Параметр config path.
        current_project: Параметр current project.
        workspace_index: Параметр workspace index.
        extension_manager: Параметр extension manager.
        _welcome_tab: Параметр welcome tab.
        _settings_tab: Параметр settings tab.
        _extensions_tab: Параметр extensions tab.
        console_widget: Параметр console widget.
        terminal_window: Параметр terminal window.
        editor_splitter: Параметр editor splitter.
        workspace_path: Параметр workspace path.
        ui_manager: Параметр ui manager.
        file_manager: Параметр file manager.
        project_handler: Параметр project handler.
        code_runner: Параметр code runner.
        csharp_compiler: Параметр csharp compiler.
        csharp_project_manager: Параметр csharp project manager.
        workbench: Параметр workbench.

    Ключевые методы: toggle_terminal, apply_application_theme, apply_interface_settings, action_compile_csharp, action_build_csharp_project, compile_csharp_file, run_csharp_program, build_csharp_project, run_in_terminal_command, run_in_terminal, add_problem, append_output, start_busy_indicator, stop_busy_indicator, show_problems_tab, show_output_tab, editor_groups, close_tab_from_group, show_command_palette, execute_command_palette, split_editor, unsplit_editor, new_terminal, toggle_sidebar, resizeEvent, keyPressEvent, load_session_files, action_new_file, action_open_file, action_open_project, action_save_file, action_save_all_files, action_save_as_file, action_close_file, action_close_all_files, action_clear_cache, action_clear_recent_files, close_all_editor_tabs, action_undo, action_redo, action_cut, action_copy, action_paste, action_select_all, action_zoom_in, action_zoom_out, action_reset_zoom, action_toggle_comment, action_duplicate_line, action_delete_line, action_toggle_word_wrap, action_run_code, action_launch_parameters, action_quick_open, action_goto_line, action_rename_symbol, action_open_settings, action_open_documentation, show_keyboard_shortcuts, action_about, action_change_capsule, action_open_extensions, action_set_shell, action_preview_markdown, action_github_issues, action_exit, action_run_project, action_run_file, action_run_selected_snippet, action_debug_file, run_target, run_project_target, run_and_analyze, run_tests, action_project_manager, action_project_settings, action_close_project, create_editor_tab, close_tab, has_unsaved_changes, ask_save_before_close, update_analysis_panels, open_graph_editor, open_defense_guide, on_project_analysis_ready, open_analysis_location, action_analyze_current_impact, open_search_match, open_file_from_explorer, close_special_tab, show_welcome_screen, is_special_widget, find_tab_for_widget, on_editor_modification_changed, on_text_changed, recalculate_unsaved_count, add_unsaved_marker, remove_unsaved_marker, get_open_file_paths, save_current_session, update_tab_title, refresh_extensions_panel, update_window_title, get_current_editor, load_launch_arguments, auto_save, show_run_options_dialog, run_project_from_dialog, run_file_from_dialog, run_single_file, closeEvent, finalize_application, on_project_opened.
    """

    def __init__(self, app_manager: ApplicationManager):
        """Инициализирует базовые компоненты соответствующий объект.

        Args:
            app_manager (ApplicationManager): Параметр app manager.
        """
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumSize(1000, 700)
        self.app_manager = app_manager
        self.unsaved_files_count = 0
        self.sidebar_visible = True
        self.terminal_visible = False
        self.config_path = self.app_manager.base_path / "config" / "launchArgs.json"
        self.current_project = None
        self.workspace_index = WorkspaceIndex()
        self.extension_manager = ExtensionManager(self.app_manager.base_path, self.app_manager.settings)
        self._welcome_tab = None
        self._settings_tab = None
        self._extensions_tab = None
        self._update_dialog = None
        self.console_widget = None
        self.terminal_window = None
        self.editor_splitter = None
        self.workspace_path = None

        self._initialize_attributes()

        self.ui_manager = UIManager(self)
        self.file_manager = FileManager(self)
        self.project_handler = ProjectHandler(self)
        self.code_runner = CodeRunner(self)
        self.csharp_compiler = CSharpCompiler()
        self.csharp_project_manager = CSharpProjectManager()

        self.project_handler.main_window = self

        self.ui_manager.setup_ui()
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage = lambda msg, timeout=0: self.stop_busy_indicator(ready_message=msg)
        self._setup_terminal()
        self.workbench = WorkbenchController(self)
        self.apply_application_theme()
        self._setup_tray_icon()
        self._setup_connections()
        self._initialize_application()
        self.apply_interface_settings()
        self._sync_special_activity()
        # The Python version goes to the status strip, not into the terminal
        # buffer: a freshly opened terminal must show only its prompt.
        QtCore.QTimer.singleShot(
            250,
            lambda: self.status_bar.showMessage(f"Среда готова · Python {sys.version.split()[0]}")
        )
        # Silent update check once a day; a newer release opens the update dialog.
        QtCore.QTimer.singleShot(3200, self._maybe_check_updates)

    def _setup_tray_icon(self):
        """Create a native Windows tray icon with a small workbench menu."""
        self.tray_icon = None
        src = self.app_manager.base_path / "src"
        # A dedicated 32px tray asset reads better than a downscaled 256px icon.
        icon_candidates = [
            src / "icon_tray.png",
            src / "PyScribe.ico",
            src / "icon_app_32.png",
            src / "icon_app.png",
        ]
        icon = QIcon()
        for path in icon_candidates:
            candidate = QIcon(str(path))
            if not candidate.pixmap(16, 16).isNull():
                icon = candidate
                break
        if icon.isNull():
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        tray = QtWidgets.QSystemTrayIcon(icon, self)
        menu = QtWidgets.QMenu(self)
        show_action = menu.addAction("Показать PyScribe")
        show_action.triggered.connect(lambda: (self.show(), self.raise_(), self.activateWindow()))
        menu.addAction("Открыть проект…", self.action_open_project)
        menu.addAction("Настройки", self.action_open_settings)
        menu.addSeparator()
        menu.addAction("Выход", self.action_exit)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: (self.show(), self.raise_(), self.activateWindow()) if reason == QtWidgets.QSystemTrayIcon.Trigger else None)
        tray.setToolTip("PyScribe")
        self.tray_icon = tray
        QtCore.QTimer.singleShot(0, tray.show)

    def _initialize_attributes(self):
        """Выполняет операцию  initialize attributes.
        """
        # Editor group state must exist before any startup action/callback can
        # query the current editor. UIManager replaces these with the real
        # widgets during setup_ui().
        self.tab_widget = None
        self.split_tab_widget = None
        self.active_tab_widget = None
        self.file_explorer = None
        self.explorer_buttons = {}
        self.explorer_layout = None
        self.central_widget = None
        self.menu_bar = None
        self.menus = {}
        self.status_bar = None
        self.auto_save_timer = None
        self.recent_files_menu = None
        self.action_clear_recent = None
        self.project_indicator = None
        self.git_panel = None
        self.top_bar = None
        self._current_status_message = "Готово"
        self._is_busy = False
        self.analysis_refresh_timer = QTimer(self)
        self.analysis_refresh_timer.setSingleShot(True)
        self.analysis_refresh_timer.timeout.connect(self._on_typing_settled)

    def _setup_terminal(self):
        """Create the terminal as an integrated bottom workbench panel."""
        self.console_widget = ConsoleWidget(self.editor_splitter)
        self.console_widget.setObjectName("consoleWidget")
        self.editor_splitter.addWidget(self.console_widget)
        self.editor_splitter.setStretchFactor(0, 1)
        self.editor_splitter.setStretchFactor(1, 0)
        self.editor_splitter.setSizes([self.editor_splitter.height() or 700, 0])
        self.terminal_window = None
        self.terminal_visible = False
        self.console_widget.hide()

    def _terminal_visibility_changed(self, visible):
        """Выполняет операцию  terminal visibility changed.

        Args:
            visible: Флаг активации или отображения соответствующего режима.
        """
        self.terminal_visible = bool(visible)
        if hasattr(self, "activity_bar"):
            self.activity_bar.sync_special_state(
                terminal_visible=self.terminal_visible,
                settings_open=self._settings_tab is not None and self._settings_tab.isVisible()
            )

    def toggle_terminal(self):
        """Show/hide the integrated bottom terminal panel with smooth animation."""
        if not self.console_widget or not self.editor_splitter:
            return

        if hasattr(self, '_terminal_anim') and self._terminal_anim is not None:
            try:
                self._terminal_anim.stop()
            except Exception:
                pass

        # Use the splitter's own measured size; before the first layout pass the
        # widget height can be tiny, which would collapse the panel.
        sizes_now = self.editor_splitter.sizes()
        measured = sum(sizes_now) if sizes_now and sum(sizes_now) > 0 else self.editor_splitter.height()
        total = max(320, measured)
        sm = get_settings_manager()
        s = sm.get_all_settings()
        cfg_h = int(s.get('terminal_panel_height', s.get('bottom_panel_height', 240)))
        min_panel = self._terminal_min_height()
        max_panel = max(min_panel, total - 140)
        target_height = max(min_panel, min(max(cfg_h, min_panel), max_panel))

        if self.terminal_visible:
            current_sizes = self.editor_splitter.sizes()
            start_height = current_sizes[1] if len(current_sizes) > 1 and current_sizes[1] > 0 else target_height

            anim = QtCore.QVariantAnimation(self)
            anim.setDuration(160)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            anim.setStartValue(start_height)
            anim.setEndValue(0)

            def _step(val):
                """Выполняет операцию  step.

                Args:
                    val: Параметр val.
                """
                h = int(val)
                self.editor_splitter.setSizes([max(1, total - h), h])

            anim.valueChanged.connect(_step)
            anim.finished.connect(self._on_terminal_hide_finished)
            self._terminal_anim = anim
            anim.start()
        else:
            self.console_widget.show()
            self.console_widget.raise_()
            self.console_widget.set_current_tab("Терминал")

            anim = QtCore.QVariantAnimation(self)
            anim.setDuration(160)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            anim.setStartValue(0)
            anim.setEndValue(target_height)

            def _step(val):
                """Выполняет операцию  step.

                Args:
                    val: Параметр val.
                """
                h = int(val)
                self.editor_splitter.setSizes([max(1, total - h), h])

            anim.valueChanged.connect(_step)
            anim.finished.connect(self._on_terminal_show_finished)
            self._terminal_anim = anim
            anim.start()
            # Content fades in alongside the height tween for a polished reveal.
            try:
                from widgets.animations import fade_in
                fade_in(self.console_widget, duration=220)
            except Exception:
                pass

    def _terminal_min_height(self) -> int:
        """Smallest panel height that keeps the terminal tab bar + prompt visible."""
        needed = 168
        try:
            bar = self.console_widget.tab_widget.tabBar()
            needed += max(0, bar.height())
            term = self.console_widget.get_terminal()
            if term is not None and getattr(term, "tab_widget", None) is not None:
                needed += max(0, term.tab_widget.tabBar().height()) + 12
        except Exception:
            pass
        return needed

    def _is_settings_tab_open(self) -> bool:
        """Проверяет, является ли settings tab open.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        return self._settings_tab is not None and self._settings_tab.isVisible()

    def _on_terminal_hide_finished(self):
        """Обработчик события для terminal hide finished.
        """
        self.console_widget.hide()
        self.terminal_visible = False
        self._terminal_anim = None
        self.activity_bar.sync_special_state(
            terminal_visible=False,
            settings_open=self._is_settings_tab_open()
        )

    def _on_terminal_show_finished(self):
        """Обработчик события для terminal show finished.
        """
        self.terminal_visible = True
        self._terminal_anim = None
        terminal = self.console_widget.get_terminal()
        if terminal:
            terminal.setFocus()
        self.activity_bar.sync_special_state(
            terminal_visible=True,
            settings_open=self._is_settings_tab_open()
        )

    def _apply_design_system(self):
        """Remove legacy per-widget styles so the centralized QSS is authoritative."""
        self.setStyleSheet("")
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.setStyleSheet("")
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setStyleSheet(_load_design_qss(self.app_manager.base_path))

    def apply_application_theme(self):
        """Reapply the centralized design system plus user appearance overrides."""
        # NOTE: per-widget stylesheets are deliberately NOT cleared here. Doing
        # so stripped the styling of widgets that set their own QSS in their
        # constructors (find bar, code lens, status strip) and they never got it
        # back. The application-level stylesheet is the single source of truth.
        app = QtWidgets.QApplication.instance()
        if app is not None:
            sm = get_settings_manager()
            s = sm.get_all_settings()
            preset = THEMES.get(str(s.get("theme", "midnight")), THEMES.get("dark", {}))
            colors = {k: s.get(k, v) for k, v in preset.items()}
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(colors.get("app_background", "#181818")))
            palette.setColor(QPalette.WindowText, QColor(colors.get("text_primary", "#D4D4D4")))
            palette.setColor(QPalette.Base, QColor(colors.get("editor_background", "#1E1E1E")))
            palette.setColor(QPalette.AlternateBase, QColor(colors.get("panel_background", "#181818")))
            palette.setColor(QPalette.ToolTipBase, QColor(colors.get("input_background", "#242424")))
            palette.setColor(QPalette.ToolTipText, QColor(colors.get("text_primary", "#D4D4D4")))
            palette.setColor(QPalette.Text, QColor(colors.get("text_primary", "#D4D4D4")))
            palette.setColor(QPalette.Button, QColor(colors.get("input_background", "#242424")))
            palette.setColor(QPalette.ButtonText, QColor(colors.get("text_primary", "#D4D4D4")))
            palette.setColor(QPalette.Highlight, QColor(colors.get("selection_background", "#264F78")))
            palette.setColor(QPalette.HighlightedText, QColor(colors.get("text_primary", "#D4D4D4")))
            app.setPalette(palette)
            self.app_manager.settings = s

            qss = _load_design_qss(self.app_manager.base_path)
            from app.styling import resolve_ui_font, user_appearance_qss
            # An empty setting means "auto": pick the best installed face.
            ui_font = str(s.get('ui_font') or '').strip() or resolve_ui_font()
            ui_font_size = max(12, min(15, int(s.get('ui_font_size', 13))))
            # Only *user-configurable* values are appended here. All structure
            # (radii, paddings, row heights) lives in design/theme.qss so the
            # chrome stays uniform; overriding it here caused the "mismatched
            # widget sizes" look this block used to produce.
            qss += "\n/* User appearance overrides */\n"
            qss += user_appearance_qss(s, ui_font_size)
            # Accessibility: apply the global workbench scale to every metric.
            from app.ui_scale import apply_ui_scale, normalize_scale
            scale = normalize_scale(s.get('ui_scale_percent', 100))
            self._current_ui_scale = scale
            apply_ui_scale(app, scale, stylesheet_provider=lambda: qss)
            # Keep native dialogs and popups on the same face as the stylesheet.
            from app.styling import ui_qfont
            app.setFont(ui_qfont(9))
        self.apply_interface_settings()
        self.apply_accessibility_scale()

    def _is_ai_view_active(self) -> bool:
        """True when the sidebar currently shows the AI agent chat."""
        panel = getattr(self, "ai_panel", None)
        return bool(panel is not None and not panel.isHidden())

    def _watch_ai_view_width(self):
        """Give the chat column the room its layout needs (DSH uses ~380-460px)."""
        from app.ui_scale import scale_px
        try:
            panel = getattr(self, "ai_panel", None)
            active = self._is_ai_view_active()
            wanted_max = scale_px(720) if active else scale_px(620)
            self.side_panel.setMaximumWidth(wanted_max)
            if not active or not hasattr(self, "workspace_splitter"):
                return
            target = max(scale_px(300), int(get_settings_manager().get_setting('sidebar_width', 300)))
            chat_min = scale_px(400)
            if target < chat_min:
                sizes = self.workspace_splitter.sizes()
                total = sum(sizes) if sizes else self.workspace_splitter.width()
                new_w = min(chat_min, wanted_max)
                self.workspace_splitter.setSizes([new_w, max(1, total - new_w)])
        except Exception:
            logger.exception("Не удалось настроить ширину панели ИИ")

    def start_index_batching(self, batch_size: int = 40, interval_ms: int = 24):
        """Feed the completion index in small slices so the UI stays responsive.

        Indexing a large project synchronously used to freeze the window right
        after opening it. Files are now reserved in small batches and parsed on
        the thread pool, so even a 3k-line module (≈60 ms of ``ast.parse``) no
        longer stops the event loop that drives every animation.
        """
        timer = getattr(self, "_index_timer", None)
        if timer is not None:
            timer.stop()
        else:
            self._index_timer = QtCore.QTimer(self)
            self._index_timer.timeout.connect(self._index_batch)
            timer = self._index_timer
        self._index_timer.setInterval(max(0, int(interval_ms)))
        self._index_batch_size = max(1, int(batch_size))
        self._index_worker_busy = False
        self._index_timer.start()

    def _index_batch(self):
        timer = getattr(self, "_index_timer", None)
        index = getattr(self, "workspace_index", None)
        if index is None:
            if timer is not None:
                timer.stop()
            return
        if getattr(self, "_index_worker_busy", False):
            # The previous slice is still being parsed off the GUI thread.
            return
        try:
            paths = index.take_batch_paths(getattr(self, "_index_batch_size", 40))
        except Exception:
            logger.exception("Не удалось построить индекс автодополнения")
            if timer is not None:
                timer.stop()
            return
        if not paths:
            if timer is not None:
                timer.stop()
            return
        from services.background import run_async
        generation = index.generation
        self._index_worker_busy = True
        run_async(
            lambda: index.parse_files(paths),
            on_done=lambda parsed: self._on_index_batch_parsed(parsed, generation),
            on_error=self._on_index_batch_failed,
        )

    def _on_index_batch_parsed(self, parsed, generation=None):
        """Merge a parsed slice back into the index (GUI thread)."""
        self._index_worker_busy = False
        index = getattr(self, "workspace_index", None)
        if index is None or generation != index.generation:
            # Another project replaced the index while this slice was parsed.
            return
        try:
            index.apply_parsed(parsed or [])
        except Exception:
            logger.exception("Не удалось применить результаты индексации")

    def _on_index_batch_failed(self, message):
        self._index_worker_busy = False
        logger.warning("Индексация автодополнения прервана: %s", message)

    def _ensure_intelligence_width(self):
        """Widen the sidebar enough that the analysis tabs are readable.

        The analysis view has five tabs plus a header of its own; at the default
        sidebar width they were clipped into each other.
        """
        from app.ui_scale import scale_px
        try:
            if not hasattr(self, "workspace_splitter"):
                return
            sizes = self.workspace_splitter.sizes()
            if not sizes:
                return
            wanted = scale_px(460)
            total = sum(sizes)
            if sizes[0] >= wanted or total - wanted < scale_px(320):
                return
            self.workspace_splitter.setSizes([wanted, total - wanted])
        except Exception:
            logger.exception("Не удалось расширить панель анализа")

    def apply_accessibility_scale(self):
        """Resize fixed-size chrome (activity bar, icons, sidebar) to the UI scale."""
        from app.ui_scale import current_scale, scale_px
        scale = current_scale()
        factor = scale / 100.0
        try:
            if hasattr(self, 'activity_bar') and self.activity_bar is not None:
                self.activity_bar.on_ui_scale_changed(scale)
        except Exception:
            logger.exception("Не удалось масштабировать activity bar")
        try:
            if hasattr(self, 'explorer_buttons'):
                for button in self.explorer_buttons.values():
                    button.setFixedSize(scale_px(24), scale_px(24))
                    button.setIconSize(QtCore.QSize(scale_px(16), scale_px(16)))
        except Exception:
            logger.exception("Не удалось масштабировать кнопки проводника")
        try:
            if hasattr(self, 'top_bar') and self.top_bar is not None:
                self.top_bar.on_ui_scale_changed(scale)
        except Exception:
            logger.exception("Не удалось масштабировать верхнюю панель")
        try:
            if getattr(self, 'console_widget', None) is not None:
                self.console_widget.on_ui_scale_changed(scale)
        except Exception:
            pass
        # Side panels and the terminal panel keep their configured pixel width /
        # height at 100%; scale them so text never gets clipped.
        try:
            if getattr(self, 'side_panel', None) is not None:
                self.side_panel.setMinimumWidth(scale_px(260))
                self.side_panel.setMaximumWidth(scale_px(620))
            if getattr(self, 'workspace_splitter', None) is not None:
                width = scale_px(int(get_settings_manager().get_setting('sidebar_width', 300)))
                total = max(width + scale_px(400), self.workspace_splitter.width())
                self.workspace_splitter.setSizes([width, max(1, total - width)])
        except Exception:
            pass
        if getattr(self, 'terminal_visible', False) and getattr(self, 'console_widget', None):
            QtCore.QTimer.singleShot(0, self._adjust_terminal_size)
        self.status_bar.showMessage(f"Масштаб интерфейса: {int(factor * 100)}%")

    def action_zoom_interface_in(self):
        """Increase the whole workbench scale by one step (accessibility)."""
        self._step_interface_scale(+1)

    def action_zoom_interface_out(self):
        """Decrease the whole workbench scale by one step (accessibility)."""
        self._step_interface_scale(-1)

    def action_reset_interface_zoom(self):
        """Reset the workbench scale to 100%."""
        self._set_interface_scale(100)

    def _step_interface_scale(self, direction: int):
        from app.ui_scale import available_scales, current_scale
        presets = available_scales()
        now = current_scale()
        if direction > 0:
            nxt = next((p for p in presets if p > now), presets[-1])
        else:
            nxt = next((p for p in reversed(presets) if p < now), presets[0])
        self._set_interface_scale(nxt)

    def _set_interface_scale(self, percent: int):
        from app.ui_scale import normalize_scale
        percent = normalize_scale(percent)
        sm = get_settings_manager()
        sm.settings['ui_scale_percent'] = percent
        sm.save_settings()
        self.app_manager.settings = sm.get_all_settings()
        self.apply_application_theme()

    def apply_interface_settings(self):
        """Apply dimensions and editor/terminal presentation settings immediately."""
        sm = get_settings_manager()
        s = sm.get_all_settings()
        if hasattr(self, 'workspace_splitter') and self.workspace_splitter:
            width = int(s.get('sidebar_width', 280))
            total = max(width + 500, self.workspace_splitter.width())
            self.workspace_splitter.setSizes([width, max(1, total - width)])
        # Update tab height
        tab_h = int(s.get('tab_height', 36))
        for group in self.editor_groups():
            if hasattr(group, 'tabBar') and group.tabBar():
                group.tabBar().setMinimumHeight(tab_h)
                group.tabBar().setMaximumHeight(tab_h)
        # Terminal presentation update
        if hasattr(self, 'console_widget') and self.console_widget and hasattr(self.console_widget, 'apply_terminal_settings'):
            self.console_widget.apply_terminal_settings()
        # Auto-save timer interval update
        interval = max(0, int(s.get('auto_save_interval', 30)))
        if getattr(self, 'auto_save_timer', None) is not None:
            if interval > 0:
                self.auto_save_timer.setInterval(interval * 1000)
                if not self.auto_save_timer.isActive():
                    self.auto_save_timer.start()
            else:
                self.auto_save_timer.stop()
        # Update editor widgets without forcing a destructive document reload.
        editor_font = str(s.get('editor_font', 'Cascadia Code'))
        editor_size = int(s.get('editor_font_size', 13))
        word_wrap = bool(s.get('word_wrap', False))
        show_ln = bool(s.get('show_line_numbers', True))
        syntax_hl = bool(s.get('syntax_highlighting', True))
        for group in self.editor_groups():
            for i in range(group.count()):
                self._apply_editor_preferences_to_widget(
                    group.widget(i), editor_font, editor_size, word_wrap, show_ln, syntax_hl
                )

    def _apply_editor_preferences_to_widget(
        self, w, font_family: str, font_size: int,
        word_wrap: bool, show_ln: bool, syntax_hl: bool
    ):
        """Применяет настройки или изменения editor preferences to widget.

        Args:
            w: Параметр w.
            font_family (str): Параметр font family.
            font_size (int): Параметр font size.
            word_wrap (bool): Параметр word wrap.
            show_ln (bool): Параметр show ln.
            syntax_hl (bool): Параметр syntax hl.
        """
        ed = getattr(w, 'editor', None)
        if ed is None:
            return
        f = ed.font()
        f.setFamily(font_family)
        f.setPointSize(font_size)
        ed.setFont(f)
        if hasattr(ed, 'setLineWrapMode'):
            wrap_mode = QtWidgets.QPlainTextEdit.WidgetWidth if word_wrap else QtWidgets.QPlainTextEdit.NoWrap
            ed.setLineWrapMode(wrap_mode)
        if hasattr(ed, 'set_line_numbers_visible'):
            ed.set_line_numbers_visible(show_ln)
        if hasattr(ed, 'set_syntax_highlighting_enabled'):
            ed.set_syntax_highlighting_enabled(syntax_hl)

    def action_compile_csharp(self):
        """Compile current C# file"""
        current_editor = self.get_current_editor()
        if not current_editor or not hasattr(current_editor, 'file_path'):
            CustomDialog("Файл C# не открыт").exec()
            return
        file_path = getattr(current_editor, 'file_path')
        if file_path and str(file_path).endswith('.cs'):
            self.compile_csharp_file(str(file_path))
        else:
            CustomDialog("Текущий файл не является файлом C#").exec()

    def action_build_csharp_project(self):
        """Build C# project"""
        if hasattr(self, 'current_project') and self.current_project:
            self.build_csharp_project(self.current_project.root_path)
            return
        directory = QFileDialog.getExistingDirectory(self, "Выберите папку проекта C#")
        if directory:
            self.build_csharp_project(directory)

    def _prompt_run_csharp(self, output_path: str):
        """Выполняет операцию  prompt run csharp.

        Args:
            output_path (str): Параметр output path.
        """
        msg = f"Компиляция успешно завершена!\nВыходной файл: {output_path}\n\nЗапустить программу?"
        reply = QMessageBox.question(
            self, "Компиляция успешна", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.run_csharp_program(output_path)

    def compile_csharp_file(self, file_path: str):
        """Compile and run C# file"""
        if not file_path.endswith('.cs'):
            CustomDialog("Выбранный файл не является файлом C#").exec()
            return

        self.status_bar.showMessage("Компиляция файла C#...")
        if self.csharp_compiler.dotnet_path:
            success, output_path, message = self.csharp_compiler.compile_with_dotnet(file_path)
        else:
            success, output_path, message = self.csharp_compiler.compile_single_file(file_path)

        if success:
            self.status_bar.showMessage("Компиляция успешно завершена!")
            self._prompt_run_csharp(output_path)
        else:
            self.status_bar.showMessage("Ошибка компиляции!")
            self.show_problems_tab()
            self.add_problem("error", file_path, 0, f"Ошибка компиляции: {message}")

    def run_csharp_program(self, exe_path: str, args: str = ""):
        """Run C# program in terminal"""
        working_dir = Path(exe_path).parent
        if not self.terminal_visible:
            self.toggle_terminal()

        self.console_widget.set_current_tab("Terminal")
        terminal = self.console_widget.get_terminal()
        if terminal:
            terminal.run_code(f'"{exe_path}" {args}', "", str(working_dir))

    def build_csharp_project(self, project_path: str):
        """Build C# project or solution"""
        project_type = self.csharp_project_manager.detect_project_type(project_path)
        self.status_bar.showMessage(f"Сборка {project_type}...")

        if project_type == "solution":
            success, output, error = self.csharp_compiler.build_solution(project_path)
        elif project_type == "project":
            csproj_files = list(Path(project_path).glob("*.csproj"))
            if csproj_files:
                success, output, error = self.csharp_compiler.compile_with_dotnet(str(csproj_files[0]))
            else:
                success, output, error = False, "", "Файл .csproj не найден"
        else:
            success, output, error = False, "", "Не является корректной папкой проекта C#"

        if success:
            self.status_bar.showMessage("Сборка успешно завершена!")
            self.append_output(output)
        else:
            self.status_bar.showMessage("Ошибка сборки!")
            self.show_problems_tab()
            self.append_output(error, is_error=True)

    def run_in_terminal_command(self, command, working_dir=None):
        """Выполняет запуск рабочего процесса in terminal command.

        Args:
            command: Параметр command.
            working_dir: Параметр working dir.
        """
        if not self.terminal_visible:
            self.toggle_terminal()
        else:
            self.console_widget.set_current_tab("Terminal")
        terminal = self.console_widget.get_terminal()
        if terminal:
            terminal.run_command(command, working_dir)

    def run_in_terminal(self, file_path, args="", working_dir=None):
        """Запуск кода в терминале"""
        if not self.terminal_visible:
            self.toggle_terminal()

        self.console_widget.set_current_tab("Terminal")
        terminal = self.console_widget.get_terminal()
        if terminal:
            terminal.run_code(file_path, args, working_dir)

    def add_problem(self, problem_type, file_path, line, description):
        """Добавляет проблему в консоль"""
        if hasattr(self, 'console_widget') and self.console_widget:
            self.console_widget.add_problem(problem_type, file_path, line, description)

    def append_output(self, text, is_error=False):
        """Добавляет текст в вывод"""
        if hasattr(self, 'console_widget') and self.console_widget:
            self.console_widget.append_output(text, is_error)

    def start_busy_indicator(self, message: str = "Выполняется операция..."):
        """Запускает процесс или таймер busy indicator.

        Args:
            message (str): Параметр message.
        """
        self._current_status_message = message
        self._is_busy = True
        if hasattr(self, "status_spinner") and self.status_spinner:
            self.status_spinner.start()
        self._propagate_status_to_editors(busy=True, message=message)

    def stop_busy_indicator(self, ready_message: str = "Готово"):
        """Останавливает выполнение busy indicator.

        Args:
            ready_message (str): Параметр ready message.
        """
        self._current_status_message = ready_message
        self._is_busy = False
        if hasattr(self, "status_spinner") and self.status_spinner:
            self.status_spinner.stop()
        self._propagate_status_to_editors(busy=False, message=ready_message)

    def _propagate_status_to_editors(self, busy: bool, message: str):
        """Выполняет операцию  propagate status to editors.

        Args:
            busy (bool): Параметр busy.
            message (str): Параметр message.
        """
        for tw in [getattr(self, 'tab_widget', None), getattr(self, 'split_tab_widget', None)]:
            if not tw:
                continue
            for i in range(tw.count()):
                w = tw.widget(i)
                if hasattr(w, 'start_busy_indicator') and hasattr(w, 'stop_busy_indicator'):
                    if busy:
                        w.start_busy_indicator(message)
                    else:
                        w.stop_busy_indicator(ready_message=message)

    def show_problems_tab(self):
        """Показывает вкладку Problems"""
        if not self.terminal_visible:
            self.toggle_terminal()
        self.console_widget.set_current_tab("Проблемы")

    def show_output_tab(self):
        """Показывает вкладку Output"""
        if not self.terminal_visible:
            self.toggle_terminal()
        self.console_widget.set_current_tab("Вывод")

    def _setup_connections(self):
        """Выполняет операцию  setup connections.
        """
        self._connect_tab_group(self.tab_widget)
        self.tab_widget.currentChanged.connect(lambda _: self._set_active_group(self.tab_widget))

        self.file_explorer.doubleClicked.connect(self.open_file_from_explorer)
        self.file_explorer.open_file_requested.connect(self.file_manager.open_file)
        if hasattr(self.file_explorer, 'preview_markdown_requested'):
            self.file_explorer.preview_markdown_requested.connect(self.file_manager.open_markdown_file)
        if hasattr(self.file_explorer, 'open_text_requested'):
            self.file_explorer.open_text_requested.connect(self.file_manager.open_text_editor)
        # Explorer header buttons are connected exactly once in UIManager
        # (_setup_explorer_panel); connecting them here again opened two dialogs.

        self.activity_bar.activity_changed.connect(self._handle_activity)
        self.activity_bar.terminal_requested.connect(self.toggle_terminal)
        self.activity_bar.browser_requested.connect(self.action_open_browser)

        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(max(0, int(get_settings_manager().get_setting('auto_save_interval', 30))) * 1000)

        self._global_shortcuts = []
        self._install_global_shortcuts()

    def _install_global_shortcuts(self):
        """Install robust application-level keyboard shortcuts across the workbench.

        Keep editor and viewer shortcuts in their own widgets. Qt treats
        overlapping shortcuts as ambiguous even when their contexts differ.
        """
        shortcuts = [
            ("Ctrl+N", self.action_new_file),
            ("Ctrl+O", self.action_open_file),
            ("Ctrl+Shift+O", self.action_open_project),
            ("Ctrl+S", self.action_save_file),
            ("Ctrl+Shift+S", self.action_save_as_file),
            ("Ctrl+W", self.action_close_file),
            ("Ctrl+P", self.action_quick_open),
            ("Ctrl+Shift+P", self.show_command_palette),
            ("F1", self.action_open_documentation),
            ("Ctrl+Shift+V", self.action_preview_markdown),
            ("F5", self.action_run_file),
            ("Ctrl+F5", self.action_run_project),
            ("Ctrl+`", self.toggle_terminal),
            ("Ctrl+\\", self.toggle_sidebar),
            ("Ctrl+G", self.action_goto_line),
            ("Ctrl+Z", self.action_undo),
            ("Ctrl+Y", self.action_redo),
            ("Ctrl+Shift+Z", self.action_redo),
            ("Ctrl+Shift+F", self._focus_search),
            ("Ctrl+A", self.action_select_all),
            ("Ctrl+X", self.action_cut),
            ("Ctrl+C", self.action_copy),
            ("Ctrl+V", self.action_paste),
            ("F2", self.action_rename_symbol),
            # Accessibility: whole-workbench scaling.
            ("Ctrl+Alt+=", self.action_zoom_interface_in),
            ("Ctrl+Alt++", self.action_zoom_interface_in),
            ("Ctrl+Alt+-", self.action_zoom_interface_out),
            ("Ctrl+Alt+0", self.action_reset_interface_zoom),
            # AI agent.
            ("Ctrl+Shift+I", self.show_ai_agent),
            ("Ctrl+Alt+E", self.action_ai_explain_selection),
            ("Ctrl+Alt+Shift+I", self.action_ai_apply_code),
        ]
        self._global_shortcuts = []
        for key_seq, handler in shortcuts:
            sc = QtWidgets.QShortcut(QtGui.QKeySequence(key_seq), self)
            sc.setContext(QtCore.Qt.ApplicationShortcut)
            sc.activated.connect(handler)
            self._global_shortcuts.append(sc)

    def _connect_tab_group(self, group):
        """Устанавливает соединение tab group.

        Args:
            group: Параметр group.
        """
        group.tabCloseRequested.connect(lambda index, g=group: self.close_tab_from_group(g, index))
        group.currentChanged.connect(lambda index, g=group: (self._set_active_group(g), self.update_analysis_panels(), self._sync_special_activity()))
        group.groupActivated.connect(self._set_active_group)

    def _set_active_group(self, group):
        """Устанавливает новое значение для active group.

        Args:
            group: Параметр group.
        """
        self.active_tab_widget = group

    def editor_groups(self):
        """Выполняет операцию editor groups.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        groups = [self.tab_widget]
        if self.split_tab_widget is not None:
            groups.append(self.split_tab_widget)
        return groups

    def close_tab_from_group(self, group, index):
        """Закрывает и освобождает системные ресурсы tab from group.

        Args:
            group: Параметр group.
            index: Смещение или индекс начального элемента для выборки.
        """
        if group is self.active_tab_widget:
            self.close_tab(index)
        else:
            old = self.active_tab_widget
            self.active_tab_widget = group
            self.close_tab(index)
            self.active_tab_widget = old

    def show_ai_agent(self):
        """Open the AI agent sidebar view (and focus its input)."""
        try:
            self.activity_bar.set_activity("ai")
        except Exception:
            self._handle_activity("ai")
        panel = getattr(self, "ai_panel", None)
        if panel is not None:
            panel.refresh_status()
            QtCore.QTimer.singleShot(80, panel.input.setFocus)
        self.status_bar.showMessage("ИИ-агент: задайте вопрос о коде")

    def action_ai_explain_selection(self):
        """Ask the AI agent to explain the current selection/line."""
        editor = self.get_current_editor()
        if editor is None:
            CustomDialog("Нет активного редактора").exec_()
            return
        self.show_ai_agent()
        panel = getattr(self, "ai_panel", None)
        if panel is None:
            return
        text_editor = getattr(editor, "editor", None)
        cursor = text_editor.textCursor() if text_editor is not None else None
        has_selection = bool(cursor and cursor.hasSelection())
        panel.include_selection.setChecked(has_selection)
        panel.include_file.setChecked(True)
        panel.send_with_context("Объясни, что делает этот код, и подскажи, как его улучшить.")

    def action_ai_apply_code(self):
        """Apply the first code block of the AI answer to the editor."""
        panel = getattr(self, "ai_panel", None)
        applied = bool(panel is not None and panel.apply_last_code())
        if applied:
            self.status_bar.showMessage("Код из ответа ИИ вставлен в редактор")
        else:
            self.status_bar.showMessage("В ответе ИИ нет блока кода для применения")
        return applied

    def action_ai_copy_answer(self):
        """Copy the last AI answer to the clipboard."""
        panel = getattr(self, "ai_panel", None)
        copied = bool(panel is not None and panel.copy_last_answer())
        if not copied:
            self.status_bar.showMessage("Нет ответа ИИ для копирования")
        return copied

    def _handle_activity(self, key):
        """Обрабатывает событие или входящие данные activity.

        Args:
            key: Ключ доступа или идентификатор параметра.
        """
        panels = {
            "explorer": self.explorer_panel,
            "search": self.search_panel,
            "run": self.run_panel,
            "extensions": self.extensions_panel,
            "git": self.git_panel,
            "intelligence": self.intelligence_panel,
            "ai": getattr(self, "ai_panel", None),
        }
        if key == "settings":
            self.action_open_settings()
            return
        if key == "extensions":
            self.action_open_extensions()
            return
        if key == "toggle_sidebar":
            self.toggle_sidebar()
            return
        for panel in panels.values():
            if panel is not None:
                panel.hide()
        # Leaving the AI view restores the normal sidebar width ceiling.
        if key != "ai":
            QtCore.QTimer.singleShot(0, self._watch_ai_view_width)
        title_label = getattr(self, 'explorer_section_title', None)
        if title_label is not None:
            title_label.setText({
                "explorer": "ПРОВОДНИК",
                "search": "ПОИСК",
                "run": "ЗАПУСК",
                "extensions": "РАСШИРЕНИЯ",
                "git": "УПРАВЛЕНИЕ ВЕРСИЯМИ",
                "intelligence": "АНАЛИЗ ПРОЕКТА",
                "ai": "ИИ-АГЕНТ",
            }.get(key, "ПРОВОДНИК"))
        panel = panels.get(key)
        if panel:
            panel.show()
            self._fade_in_panel(panel)
            if key == "intelligence":
                self._ensure_intelligence_panel_project()
            if key == "ai" and hasattr(panel, "refresh_status"):
                panel.refresh_status()
                QtCore.QTimer.singleShot(0, self._watch_ai_view_width)
        if not self.sidebar_visible:
            self.toggle_sidebar()
        else:
            self.sidebar_visible = True
            self.side_panel.show()
        if key == "search" and self.search_panel.query.text():
            self.search_panel.search()

    def _fade_in_panel(self, panel):
        """Cross-fade the side panel content when switching activity views."""
        if panel is None:
            return
        try:
            from widgets.animations import fade_in
            fade_in(panel, duration=160)
        except Exception:
            pass

    def _ensure_intelligence_panel_project(self):
        """Выполняет операцию  ensure intelligence panel project.
        """
        if not hasattr(self, "intelligence_panel"):
            return
        panel = self.intelligence_panel
        engine = getattr(panel, 'engine', None)
        if not engine or not getattr(engine, 'root', None):
            detected = panel._resolve_root_path()
            if detected:
                panel.set_project(detected)

    def show_command_palette(self):
        """Выполняет операцию show command palette.
        """
        commands = [
            ("Файл: Новый файл", "new"),
            ("Файл: Открыть файл", "open"),
            ("Файл: Сохранить", "save"),
            ("Файл: Сохранить всё", "save_all"),
            ("Файл: Открыть в HEX-просмотрщике…", "open_hex"),
            ("Файл: Открыть как таблицу…", "open_table"),
            ("Файл: Открыть PDF…", "open_pdf"),
            ("Вид: Переключить терминал", "terminal"),
            ("Вид: Разделить редактор", "split"),
            ("Вид: Проводник", "explorer"),
            ("Вид: Поиск", "search"),
            ("Вид: Архитектурный граф", "graph"),
            ("Вид: Предпросмотр Markdown", "preview_markdown"),
            ("Запуск: Запустить текущий файл", "run"),
            ("Проект: Открыть проект", "project"),
            ("Настройки: Параметры", "settings"),
            ("Окно: Закрыть активный редактор", "close"),
            ("Перейти к файлу (Быстрое открытие)", "quick_open"),
            ("Перейти к строке", "goto_line"),
            ("Переименовать символ", "rename"),
            ("Проект: Анализ проекта", "intelligence"),
            ("Проект: Анализ влияния текущего файла", "impact"),
            ("Проект: Изменить капсулу", "capsule"),
            ("Справка: Руководство пользователя (Документация)", "documentation"),
            ("Справка: Горячие клавиши", "shortcuts"),
            ("Справка: Проверить обновления…", "updates"),
            ("Справка: Интеграция с проводником…", "shell"),
            ("Справка: О программе", "about"),
        ]
        dialog = CommandPalette(commands, self)
        dialog.command_triggered.connect(self.execute_command_palette)
        dialog.exec_()

    def execute_command_palette(self, command):
        """Исполняет команду или алгоритм command palette.

        Args:
            command: Параметр command.
        """
        actions = {
            "new": self.action_new_file, "open": self.action_open_file,
            "open_hex": self.action_open_hex_file, "open_table": self.action_open_table_file,
            "open_pdf": self.action_open_pdf_file,
            "save": self.action_save_file, "save_all": self.action_save_all_files,
            "terminal": self.toggle_terminal, "split": self.split_editor,
            "explorer": lambda: self.activity_bar.set_activity("explorer"),
            "search": lambda: self.activity_bar.set_activity("search"),
            "graph": lambda: self.open_graph_editor(self.intelligence_panel.engine, 'modules') if getattr(self.intelligence_panel, 'engine', None) else CustomDialog("Сначала откройте проект для просмотра графа").exec_(),
            "preview_markdown": self.action_preview_markdown,
            "run": self.action_run_file, "project": self.action_open_project,
            "settings": self.action_open_settings, "close": self.action_close_file,
            "quick_open": self.action_quick_open, "goto_line": self.action_goto_line,
            "rename": self.action_rename_symbol,
            "intelligence": lambda: self.activity_bar.set_activity("intelligence"),
            "impact": self.action_analyze_current_impact,
            "adversary": self.action_adversary_test,
            "capsule": self.action_change_capsule,
            "documentation": self.action_open_documentation,
            "shortcuts": self.show_keyboard_shortcuts,
            "updates": self.action_check_updates,
            "shell": self.action_shell_integration,
            "about": self.action_about,
        }
        handler = actions.get(command)
        if handler:
            handler()

    def _move_active_tab_to_split(self):
        """Выполняет операцию  move active tab to split.
        """
        current_group = self.active_tab_widget or self.tab_widget
        index = current_group.currentIndex()
        if index < 0:
            return
        widget = current_group.widget(index)
        title = current_group.tabText(index)
        if widget and not isinstance(widget, Ui_Welcome):
            current_group.removeTab(index)
            new_index = self.split_tab_widget.addTab(widget, title)
            self.split_tab_widget.setCurrentIndex(new_index)

    def split_editor(self, *, orientation=None):
        """Выполняет операцию split editor.
        """
        if self.split_tab_widget is not None:
            if orientation is None:
                self.unsplit_editor()
            else:
                self.editor_area_splitter.setOrientation(orientation)
                self.editor_area_splitter.setSizes([1, 1])
            return
        self.editor_area_splitter.setOrientation(orientation or QtCore.Qt.Horizontal)
        self.split_tab_widget = TabWidget(self.editor_area_splitter, self.app_manager.settings)
        self.split_tab_widget.setObjectName("editorGroupSecondary")
        self.editor_area_splitter.addWidget(self.split_tab_widget)
        self._connect_tab_group(self.split_tab_widget)
        self._move_active_tab_to_split()
        self._set_active_group(self.split_tab_widget)
        # Always start a split as a true 50/50 editor layout.
        QtCore.QTimer.singleShot(0, lambda: self.editor_area_splitter.setSizes([1, 1]))

    def unsplit_editor(self):
        """Remove the secondary editor group and keep its tabs in the primary group."""
        secondary = self.split_tab_widget
        if secondary is None:
            return
        primary = self.tab_widget
        widgets = []
        while secondary.count():
            widget = secondary.widget(0)
            title = secondary.tabText(0)
            icon = secondary.tabIcon(0)
            tip = secondary.tabToolTip(0)
            secondary.removeTab(0)
            widgets.append((widget, title, icon, tip))
        for widget, title, icon, tip in widgets:
            idx = primary.addTab(widget, icon, title)
            primary.setTabToolTip(idx, tip)
            primary.setCurrentIndex(idx)
        secondary.deleteLater()
        self.split_tab_widget = None
        self.editor_area_splitter.setSizes([1, 0])
        self._set_active_group(primary)

    def new_terminal(self):
        """Выполняет операцию new terminal.
        """
        if not self.terminal_visible:
            self.toggle_terminal()
        if hasattr(self.console_widget, 'new_terminal'):
            self.console_widget.new_terminal()
        else:
            self.console_widget.get_terminal().setFocus()

    def _restore_last_project(self, settings) -> bool:
        """Выполняет операцию  restore last project.

        Args:
            settings: Словарь или объект параметров конфигурации.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        if not settings.get("project_restore_last", False):
            return False
        recent_projects = loadRecent()
        if not recent_projects:
            return False
        last_project = recent_projects[0]
        if not Path(last_project).exists():
            return False
        try:
            self.project_handler.open_project(last_project)
            return True
        except Exception:
            logger.exception("Failed to restore last project")
            return False

    def _restore_previous_session(self, settings) -> bool:
        """Выполняет операцию  restore previous session.

        Args:
            settings: Словарь или объект параметров конфигурации.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        if not settings.get("restore_session", False):
            return False
        session_files = [p for p in self.app_manager.session_files if Path(p).exists()]
        if not session_files:
            return False
        restored = False
        for f in session_files:
            try:
                self.file_manager.open_file(f)
                restored = True
            except Exception:
                logger.exception("Failed to restore session file")
        return restored

    def _initialize_application(self):
        """Выполняет операцию  initialize application.
        """
        restore_backup()
        self.setWindowTitle("PyScribe")
        if hasattr(self, "top_bar"):
            self.top_bar.set_project("")
        sm = get_settings_manager()
        s = sm.get_all_settings()

        restored_project = self._restore_last_project(s)
        restored_session = False
        if not restored_project:
            restored_session = self._restore_previous_session(s)

        if s.get("show_welcome", True) or (not restored_project and not restored_session):
            if self.active_tab_widget.count() == 0:
                self.show_welcome_screen()

        if not restored_project and hasattr(self, 'intelligence_panel'):
            try:
                init_root = str(Path.cwd().resolve())
                self.intelligence_panel.set_project(init_root)
            except Exception:
                pass

    def _set_explorer_location_title(self, path):
        """Report the current project/root folder as the Explorer header tooltip.

        The header keeps the section title ("ПРОВОДНИК" / "ПОИСК" / …) which is
        owned by _handle_activity(); writing the folder name into the same label
        produced the duplicated title strip.
        """
        label = getattr(self, 'explorer_section_title', None)
        if label is None:
            return
        folder = ""
        if self.current_project is not None:
            folder = str(getattr(self.current_project, 'name', '') or "")
        if not folder:
            try:
                p = Path(str(path))
                folder = p.name or p.anchor.replace('\\', '/') or str(path)
            except Exception:
                folder = str(path)
        label.setToolTip(f"Проводник: {folder}" if folder else "Проводник")

    def _on_sidebar_hide_finished(self):
        """Обработчик события для sidebar hide finished.
        """
        self.sidebar_visible = False
        self.side_panel.hide()
        self.activity_bar.set_active_visual(None)
        self._sidebar_anim = None

    def _on_sidebar_show_finished(self):
        """Обработчик события для sidebar show finished.
        """
        self.sidebar_visible = True
        self._sidebar_anim = None

    def _activate_first_visible_panel(self):
        """Выполняет операцию  activate first visible panel.
        """
        panels = (
            ("explorer", self.explorer_panel),
            ("search", self.search_panel),
            ("run", self.run_panel),
            ("extensions", self.extensions_panel),
            ("git", self.git_panel),
            ("intelligence", self.intelligence_panel)
        )
        for key, p in panels:
            if p.isVisible():
                self.activity_bar.set_active_visual(key)
                return
        self.explorer_panel.show()
        self.activity_bar.set_active_visual("explorer")

    def toggle_sidebar(self):
        """Выполняет операцию toggle sidebar.
        """
        if not hasattr(self, 'workspace_splitter') or not self.workspace_splitter:
            return

        if hasattr(self, '_sidebar_anim') and self._sidebar_anim is not None:
            try:
                self._sidebar_anim.stop()
            except Exception:
                pass

        sm = get_settings_manager()
        target_width = int(sm.get('sidebar_width', 280))
        total_width = max(target_width + 400, self.workspace_splitter.width())

        if self.sidebar_visible:
            current_sizes = self.workspace_splitter.sizes()
            start_width = current_sizes[0] if current_sizes and current_sizes[0] > 0 else target_width

            anim = QtCore.QVariantAnimation(self)
            anim.setDuration(160)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            anim.setStartValue(start_width)
            anim.setEndValue(0)

            def _step_hide(val):
                """Выполняет операцию  step hide.

                Args:
                    val: Параметр val.
                """
                w = int(val)
                self.workspace_splitter.setSizes([w, max(1, total_width - w)])

            anim.valueChanged.connect(_step_hide)
            anim.finished.connect(self._on_sidebar_hide_finished)
            self._sidebar_anim = anim
            anim.start()
        else:
            self.side_panel.show()
            self._activate_first_visible_panel()

            anim = QtCore.QVariantAnimation(self)
            anim.setDuration(160)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            anim.setStartValue(0)
            anim.setEndValue(target_width)

            def _step_show(val):
                """Выполняет операцию  step show.

                Args:
                    val: Параметр val.
                """
                w = int(val)
                self.workspace_splitter.setSizes([w, max(1, total_width - w)])

            anim.valueChanged.connect(_step_show)
            anim.finished.connect(self._on_sidebar_show_finished)
            self._sidebar_anim = anim
            anim.start()

    def _adjust_terminal_size(self):
        """Keep the integrated bottom panel at a sensible height after resize."""
        if self.terminal_visible and self.console_widget and self.editor_splitter:
            total = max(300, self.editor_splitter.height())
            current = self.editor_splitter.sizes()
            panel_height = current[1] if len(current) > 1 and current[1] > 0 else min(300, max(220, total // 3))
            self.editor_splitter.setSizes([max(200, total - panel_height), panel_height])

    def resizeEvent(self, event):
        """Выполняет операцию resizeEvent.

        Args:
            event: Параметр event.
        """
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._adjust_terminal_size)

    def keyPressEvent(self, event):
        """Выполняет операцию keyPressEvent.

        Args:
            event: Параметр event.
        """
        ctrl = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        shift = bool(event.modifiers() & QtCore.Qt.ShiftModifier)
        key = event.key()

        if ctrl and not shift and key == QtCore.Qt.Key_S:
            self.action_save_file()
            return
        if ctrl and shift and key == QtCore.Qt.Key_S:
            self.action_save_as_file()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_O:
            self.action_open_file()
            return
        if ctrl and shift and key == QtCore.Qt.Key_O:
            self.action_open_project()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_N:
            self.action_new_file()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_W:
            self.action_close_file()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_P:
            self.action_quick_open()
            return
        if (ctrl and shift and key == QtCore.Qt.Key_P) or key == QtCore.Qt.Key_F1:
            self.show_command_palette()
            return
        if key == QtCore.Qt.Key_F5:
            if ctrl: self.action_run_project()
            else: self.action_run_file()
            return
        if ctrl and key == QtCore.Qt.Key_G:
            self.action_goto_line()
            return
        if ctrl and (key in (QtCore.Qt.Key_QuoteLeft, QtCore.Qt.Key_AsciiTilde) or event.text() == '`'):
            self.toggle_terminal()
            return
        if ctrl and (key == QtCore.Qt.Key_Backslash or event.text() == '\\'):
            self.toggle_sidebar()
            return
        if ctrl and shift and key == QtCore.Qt.Key_F:
            self._focus_search()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_F:
            self._trigger_find()
            return
        if ctrl and not shift and key == QtCore.Qt.Key_H:
            self._trigger_replace()
            return
        super().keyPressEvent(event)

    def load_session_files(self):
        """Restore standalone session files only if no project is active."""
        if self.current_project:
            return
        existing = loadSession(project_path=None)
        if not existing:
            if self.active_tab_widget.count() == 0:
                self.show_welcome_screen()
            return
        for f in existing:
            try:
                self.file_manager.open_file(f)
            except Exception:
                pass

    def action_new_file(self):
        """Выполняет операцию action new file.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Создать новый файл", "", "Все файлы (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("")
            self.file_manager.open_file(file_path)
            if file_path not in self.app_manager.session_files:
                self.app_manager.session_files.append(file_path)
        except Exception as e:
            CustomDialog(f"Ошибка создания файла: {str(e)}").exec()

    def action_open_file(self):
        """Выполняет операцию action open file.
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Открыть файл", "", "Все файлы (*)"
        )
        for file_path in file_paths:
            self.file_manager.open_file(file_path)

    def action_open_hex_file(self):
        """Открыть любой файл в HEX-просмотрщике."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть в HEX-просмотрщике", "", "Все файлы (*)"
        )
        if file_path:
            self.file_manager.open_binary_file(file_path)

    def action_open_table_file(self):
        """Открыть табличный файл в просмотрщике таблиц."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть таблицу", "", "Таблицы (*.csv *.tsv *.tab *.xlsx *.xlsm);;Все файлы (*)"
        )
        if file_path:
            self.file_manager.open_table_file(file_path)

    def action_open_pdf_file(self):
        """Открыть PDF файл в просмотрщике документов."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть PDF", "", "PDF документы (*.pdf);;Все файлы (*)"
        )
        if file_path:
            self.file_manager.open_pdf_file(file_path)

    def action_open_project(self):
        """Выполняет операцию action open project.
        """
        self.project_handler.open_project()

    def _refresh_intelligence_panel_if_visible(self):
        """Выполняет операцию  refresh intelligence panel if visible.
        """
        if self.intelligence_panel and self.intelligence_panel.isVisible():
            self.intelligence_panel.refresh()

    def action_save_file(self):
        """Выполняет операцию action save file.
        """
        current_editor = self.get_current_editor()
        if not current_editor or self.is_special_widget(current_editor):
            return
        if self.file_manager.save_file(current_editor):
            if hasattr(current_editor, "editor") and hasattr(current_editor.editor, "document"):
                current_editor.editor.document().setModified(False)
            if getattr(current_editor, "file_path", None) and self.workspace_index.root:
                self.workspace_index.update_file(Path(current_editor.file_path), current_editor.get_code())
                self._refresh_intelligence_panel_if_visible()
            current_index = self.active_tab_widget.currentIndex()
            self.remove_unsaved_marker(current_index)
            self.recalculate_unsaved_count()

    def action_save_all_files(self):
        """Выполняет операцию action save all files.
        """
        self.file_manager.save_all_files()

    def action_save_as_file(self):
        """Выполняет операцию action save as file.

        Raises:
            IOError: При возникновении ошибки в процессе выполнения.
        """
        current_editor = self.get_current_editor()
        if not current_editor or self.is_special_widget(current_editor):
            return

        old_path = getattr(current_editor, "file_path", None)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить файл как", str(old_path) if old_path else "", "Все файлы (*)"
        )
        if not file_path:
            return

        try:
            if isinstance(current_editor, HexViewer):
                CustomDialog("Двоичные файлы доступны только для чтения.").exec_()
                return

            if not current_editor.save_file_as(file_path):
                raise IOError("Не удалось сохранить файл")
            if hasattr(current_editor, "editor") and hasattr(current_editor.editor, "document"):
                current_editor.editor.document().setModified(False)
            if self.workspace_index.root:
                self.workspace_index.update_file(Path(file_path), current_editor.get_code())

            if old_path and str(old_path) in self.app_manager.session_files:
                self.app_manager.session_files.remove(str(old_path))

            new_path = str(Path(file_path).resolve())
            if new_path not in self.app_manager.session_files:
                self.app_manager.session_files.append(new_path)
            self.save_current_session()

            index = self.active_tab_widget.currentIndex()
            self.update_tab_title(index, Path(file_path).name)
            self.remove_unsaved_marker(index)
            self.recalculate_unsaved_count()
        except Exception as e:
            CustomDialog(f"Ошибка сохранения файла: {str(e)}").exec_()

    def action_close_file(self):
        """Выполняет операцию action close file.
        """
        current_index = self.active_tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def action_close_all_files(self):
        """Выполняет операцию action close all files.
        """
        for i in range(self.active_tab_widget.count() - 1, -1, -1):
            self.close_tab(i)

    def action_clear_cache(self):
        """Выполняет операцию action clear cache.
        """
        try:
            clearCache()
            self.action_clear_recent_files()
            self.app_manager.session_files.clear()
            saveSession(self.app_manager.session_files)
            self.action_close_all_files()
            self.show_welcome_screen()
            CustomDialog("Кэш успешно очищен").exec()
        except Exception as e:
            CustomDialog(f"Ошибка очистки кэша: {str(e)}").exec()

    def action_clear_recent_files(self):
        """Выполняет операцию action clear recent files.
        """
        self.app_manager.recent_files.clear()
        saveRecent(self.app_manager.recent_files)
        if self.recent_files_menu is not None:
            self.ui_manager._update_recent_files_menu()
        if self._welcome_tab is not None:
            self._welcome_tab.set_recent_files([])

    def _close_group_editor_tabs(self, group):
        """Закрывает и освобождает системные ресурсы group editor tabs.

        Args:
            group: Параметр group.
        """
        for i in range(group.count() - 1, -1, -1):
            widget = group.widget(i)
            if widget.property("pyscribeSpecial") not in {"welcome", "settings", "extensions"}:
                self.close_tab(i)

    def close_all_editor_tabs(self):
        """Закрывает все вкладки редактора"""
        for group in self.editor_groups():
            old = self.active_tab_widget
            self.active_tab_widget = group
            self._close_group_editor_tabs(group)
            self.active_tab_widget = old

    def action_undo(self):
        """Выполняет операцию action undo.
        """
        current_editor = self.get_current_editor()
        if current_editor:
            target = getattr(current_editor, 'editor', current_editor)
            if hasattr(target, 'undo'):
                target.undo()

    def action_redo(self):
        """Выполняет операцию action redo.
        """
        current_editor = self.get_current_editor()
        if current_editor:
            target = getattr(current_editor, 'editor', current_editor)
            if hasattr(target, 'redo'):
                target.redo()

    def action_cut(self):
        """Выполняет операцию action cut.
        """
        current_editor = self.get_current_editor()
        if current_editor:
            target = getattr(current_editor, 'editor', current_editor)
            if hasattr(target, 'cut'):
                target.cut()

    def action_copy(self):
        """Выполняет операцию action copy.
        """
        current_editor = self.get_current_editor()
        if current_editor:
            target = getattr(current_editor, 'editor', current_editor)
            if hasattr(target, 'copy'):
                target.copy()

    def action_paste(self):
        """Выполняет операцию action paste.
        """
        current_editor = self.get_current_editor()
        if current_editor:
            target = getattr(current_editor, 'editor', current_editor)
            if hasattr(target, 'paste'):
                target.paste()

    def action_select_all(self):
        """Выполняет операцию action select all.
        """
        current_editor = self.get_current_editor()
        if not current_editor:
            return
        target = getattr(current_editor, 'editor', current_editor)
        if hasattr(target, 'selectAll'):
            target.selectAll()
        elif hasattr(target, 'select_all'):
            target.select_all()

    def _focus_search(self):
        """Focus the workspace search panel in the sidebar."""
        self.activity_bar.set_activity("search")
        if hasattr(self, 'search_panel') and hasattr(self.search_panel, 'query'):
            self.search_panel.query.setFocus()
            self.search_panel.query.selectAll()

    def _trigger_find(self):
        """Trigger find in the active code editor or open workspace search."""
        ed = self.get_current_editor()
        if ed and hasattr(ed, 'show_find_bar'):
            ed.show_find_bar()
        else:
            self._focus_search()

    def _trigger_replace(self):
        """Trigger replace in the active code editor."""
        ed = self.get_current_editor()
        if ed and hasattr(ed, 'show_replace_bar'):
            ed.show_replace_bar()
        else:
            self._focus_search()

    def action_zoom_in(self):
        """Выполняет операцию action zoom in.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_zoom_in'):
            ed._zoom_in()
        elif ed and hasattr(ed, 'editor') and hasattr(ed.editor, '_zoom_in'):
            ed.editor._zoom_in()

    def action_zoom_out(self):
        """Выполняет операцию action zoom out.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_zoom_out'):
            ed._zoom_out()
        elif ed and hasattr(ed, 'editor') and hasattr(ed.editor, '_zoom_out'):
            ed.editor._zoom_out()

    def action_reset_zoom(self):
        """Выполняет операцию action reset zoom.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_reset_zoom'):
            ed._reset_zoom()
        elif ed and hasattr(ed, 'editor') and hasattr(ed.editor, '_reset_zoom'):
            ed.editor._reset_zoom()

    def action_toggle_comment(self):
        """Выполняет операцию action toggle comment.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_toggle_comment'):
            ed._toggle_comment()

    def action_duplicate_line(self):
        """Выполняет операцию action duplicate line.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_duplicate_line'):
            ed._duplicate_line()

    def action_delete_line(self):
        """Выполняет операцию action delete line.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, '_delete_line'):
            ed._delete_line()

    def action_toggle_word_wrap(self):
        """Выполняет операцию action toggle word wrap.
        """
        ed = self.get_current_editor()
        if ed and hasattr(ed, 'toggle_word_wrap'):
            ed.toggle_word_wrap()

    def action_run_code(self):
        """Выполняет операцию action run code.
        """
        self.code_runner.run_code()

    def action_launch_parameters(self):
        """Выполняет операцию action launch parameters.
        """
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, 'file_path'):
            file_path = getattr(current_editor, 'file_path')
            language = getattr(current_editor, 'language', 'txt')
            args_window = ArgsWindow(Path(file_path).name, str(file_path), language)
            args_window.show()

    def action_open_browser(self):
        existing = self._find_special_tab("browser")
        if existing:
            group, index = existing
            self._set_active_group(group)
            group.setCurrentIndex(index)
            group.widget(index).focus_entry()
            self._sync_special_activity()
            return
        try:
            from widgets.WebBrowserWidget import WebBrowserWidget
            browser = WebBrowserWidget(self)
        except ImportError:
            CustomDialog("Для встроенного браузера установите PyQtWebEngine.").exec_()
            return
        group = self.active_tab_widget
        index = group.addTab(browser, "Браузер")
        group.setCurrentIndex(index)
        browser.focus_entry()
        self._sync_special_activity()

    def _find_special_tab(self, kind: str):
        """Выполняет поиск и возвращает special tab.

        Args:
            kind (str): Параметр kind.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        for group in self.editor_groups():
            match = next((i for i in range(group.count()) if group.widget(i).property("pyscribeSpecial") == kind), None)
            if match is not None:
                return group, match
        return None

    def action_quick_open(self):
        """Выполняет операцию action quick open.
        """
        root = self.workspace_index.root or (self.current_project.root_path if self.current_project else None)
        dialog = QuickOpenDialog(root, self.app_manager.recent_files, self)
        dialog.file_selected.connect(self.file_manager.open_file)
        dialog.exec_()

    def action_goto_line(self):
        """Выполняет операцию action goto line.
        """
        editor = self.get_current_editor()
        if not editor or not hasattr(editor, "editor"):
            return
        line, ok = QtWidgets.QInputDialog.getInt(self, "Перейти к строке", "Номер строки:", 1, 1, 1000000)
        if ok:
            cursor = editor.editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.Start)
            cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, line - 1)
            editor.editor.setTextCursor(cursor)
            editor.editor.centerCursor()
            editor.editor.setFocus()

    def action_rename_symbol(self):
        """Выполняет операцию action rename symbol.
        """
        editor = self.get_current_editor()
        if not editor or not hasattr(editor, "editor"):
            return
        text_editor = editor.editor
        cursor = text_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QtGui.QTextCursor.WordUnderCursor)
        old = cursor.selectedText()
        if not old or not old.replace("_", "a").isalnum():
            return
        new, ok = QtWidgets.QInputDialog.getText(self, "Переименовать символ", f"Переименовать '{old}' в:", text=old)
        if not ok or not new or new == old:
            return
        if not (new[0].isalpha() or new[0] == "_") or not all(ch.isalnum() or ch == "_" for ch in new):
            QMessageBox.warning(self, "Переименовать символ", "Используйте корректный идентификатор.")
            return
        code = editor.get_code()
        import re
        updated = re.sub(r"\b" + re.escape(old) + r"\b", new, code)
        if updated != code:
            editor.set_code(updated)
            self.on_text_changed()

    def action_open_settings(self):
        """Open Settings as a unique editor tab."""
        found = self._find_special_tab("settings")
        if found:
            group, idx = found
            self._set_active_group(group)
            group.setCurrentIndex(idx)
            self._sync_special_activity()
            return
        settings_window = SettingsWidget(
            self.app_manager.settings, str(self.app_manager.base_path), self
        )
        settings_window.setProperty("pyscribeSpecial", "settings")
        index = self.active_tab_widget.addTab(settings_window, "Настройки")
        self.active_tab_widget.setCurrentIndex(index)
        self._settings_tab = settings_window
        self._sync_special_activity()

    def action_open_documentation(self):
        """Open the complete PyScribe user guide in an interactive Markdown tab."""
        found = self._find_special_tab("documentation")
        if found:
            group, idx = found
            self._set_active_group(group)
            group.setCurrentIndex(idx)
            return

        from widgets.MarkdownViewerWidget import MarkdownViewerWidget
        doc_path = Path(self.app_manager.base_path) / "USER_GUIDE.md"
        content = ""
        if doc_path.is_file():
            try:
                content = doc_path.read_text(encoding="utf-8")
            except Exception:
                pass

        viewer = MarkdownViewerWidget(file_path=str(doc_path), content=content, parent=self)
        viewer.setProperty("pyscribeSpecial", "documentation")
        index = self.active_tab_widget.addTab(viewer, "📖 Руководство пользователя.md")
        self.active_tab_widget.setCurrentIndex(index)
        self.status_bar.showMessage("Руководство пользователя PyScribe открыто")

    def show_keyboard_shortcuts(self):
        """Выполняет операцию show keyboard shortcuts.
        """
        KeyboardShortcutsDialog(self).exec_()

    def action_about(self):
        """Показать диалог 'О программе'"""
        AboutDialog(self).exec_()

    # ------------------------------------------------------------------
    # Updates and Windows Explorer integration
    # ------------------------------------------------------------------
    def action_check_updates(self):
        """«Справка → Проверить обновления…» (manual check, no throttle)."""
        self._open_update_dialog(auto=False)

    def action_shell_integration(self):
        """Register/unregister «Открыть в PyScribe» and «Открыть с помощью»."""
        ShellIntegrationDialog(self).exec_()

    def _maybe_check_updates(self):
        """Automatic daily check; skipped entirely when disabled in settings."""
        if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
            return          # tests and headless runs must not touch the network
        try:
            from datetime import datetime, timedelta
            from utils.settings_manager import get_settings_manager
            manager = get_settings_manager()
            if not bool(manager.get_setting("update_auto_check", True)):
                return
            last = str(manager.get_setting("update_last_check", "") or "")
            if last:
                try:
                    previous = datetime.fromisoformat(last.replace("Z", "+00:00"))
                except ValueError:
                    previous = None
                if previous is not None:
                    now = datetime.now(previous.tzinfo) if previous.tzinfo else datetime.now()
                    if now - previous < timedelta(hours=20):
                        return
        except Exception:  # noqa: BLE001 - an update check must never break startup
            return
        self._open_update_dialog(auto=True)

    def _open_update_dialog(self, auto: bool = False):
        dialog = getattr(self, "_update_dialog", None)
        if dialog is not None:
            try:
                # Reuse the window and restart the check: never delete a dialog
                # while its QThread is still running.
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                dialog._start_check()
                return
            except RuntimeError:
                self._update_dialog = None
        dialog = UpdateDialog(self, auto=auto)
        dialog.finished.connect(lambda *_: setattr(self, "_update_dialog", None))
        self._update_dialog = dialog
        if auto:
            # Stay hidden while checking: the dialog shows itself only when a
            # newer release exists, so a daily check never flashes a window.
            dialog.hide()
        else:
            dialog.exec_()

    def action_change_capsule(self):
        """Выполняет операцию action change capsule.
        """
        ChangeCapsuleDialog(self, self).exec_()

    def action_open_extensions(self):
        """Open the extension manager as a unique editor tab, like Settings."""
        found = self._find_special_tab("extensions")
        if found:
            group, idx = found
            self._set_active_group(group)
            group.setCurrentIndex(idx)
            return
        widget = ExtensionsWidget(self.extension_manager, self.app_manager.base_path, self)
        widget.setProperty("pyscribeSpecial", "extensions")
        index = self.active_tab_widget.addTab(widget, "Расширения")
        self.active_tab_widget.setCurrentIndex(index)
        self._extensions_tab = widget

    def action_set_shell(self):
        """Выполняет операцию action set shell.
        """
        self.action_open_settings()

    def action_preview_markdown(self):
        """Открыть rich-предпросмотр Markdown для текущего файла или содержимого редактора."""
        editor = self.get_current_editor()
        if editor:
            file_path = getattr(editor, 'file_path', None)
            if file_path and Path(file_path).suffix.lower() in {'.md', '.markdown'}:
                source = getattr(editor, "editor", editor)
                if not isinstance(source, (QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
                    source = None
                self.file_manager.open_markdown_file(str(file_path), source=source)
                return
            content = ""
            if hasattr(editor, "get_code"):
                content = editor.get_code()
            elif hasattr(editor, "toPlainText"):
                content = editor.toPlainText()
            elif hasattr(editor, "editor") and hasattr(editor.editor, "toPlainText"):
                content = editor.editor.toPlainText()
            if content:
                from widgets.MarkdownViewerWidget import MarkdownViewerWidget
                viewer = MarkdownViewerWidget(content=content, parent=self)
                source = getattr(editor, "editor", editor)
                if isinstance(source, (QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
                    viewer.bind_source(source)
                index = self.active_tab_widget.addTab(viewer, "Предпросмотр Markdown")
                self.active_tab_widget.setCurrentIndex(index)
                return
        self.status_bar.showMessage("Откройте Markdown (.md) файл для предпросмотра")

    def action_github_issues(self):
        """Выполняет операцию action github issues.
        """
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://github.com/stand4r/PyScribe/issues")
        )

    def action_exit(self):
        """Выполняет операцию action exit.
        """
        if getattr(self, 'tray_icon', None):
            self.tray_icon.hide()
        self.close()

    def action_run_project(self):
        """Выполняет операцию action run project.
        """
        self.workbench.run_project()

    def action_run_file(self):
        """Выполняет операцию action run file.
        """
        current_editor = self.get_current_editor()
        if not current_editor:
            CustomDialog("Нет активного редактора").exec_()
            return
        file_path = getattr(current_editor, 'file_path', None)
        if file_path:
            self.workbench.run_file(str(file_path))

    def action_run_selected_snippet(self):
        """Выполняет операцию action run selected snippet.
        """
        editor = self.get_current_editor()
        if not editor:
            CustomDialog("Нет активного редактора").exec_()
            return
        ed = getattr(editor, 'editor', editor)
        if hasattr(ed, 'run_selected_code'):
            ed.run_selected_code()

    def action_debug_file(self):
        """Выполняет операцию action debug file.
        """
        current_editor = self.get_current_editor()
        if current_editor and getattr(current_editor, 'file_path', None):
            self.run_target(str(current_editor.file_path), True)
        else:
            CustomDialog("Нет активного исходного файла для отладки").exec_()

    def run_target(self, file_path, debug=False):
        """Run/debug one source file in the integrated terminal.

        All launches go through the terminal's dedicated run channel, which
        streams stdout/stderr live, reports the exit code and supports stdin.
        """
        path = Path(str(file_path)).resolve()
        if not path.exists():
            CustomDialog(f"Файл не найден: {path}").exec_(); return
        editor = self.get_current_editor()
        if editor and str(getattr(editor, 'file_path', '')) == str(path) and hasattr(editor, 'save_file'):
            if not editor.save_file():
                CustomDialog("Не удалось сохранить файл перед выполнением").exec_(); return
        lang = path.suffix.lower().lstrip('.')
        args = self.load_launch_arguments(str(path))

        project_root = None
        if self.current_project:
            project_root = getattr(self.current_project, 'root_path', None)
        cwd = Path(project_root) if project_root and Path(project_root).is_dir() else path.parent

        def q(value):
            return '"' + str(value).replace('"', '') + '"'

        args = (args or "").strip()
        stem = path.stem
        command = None
        self.workbench.announce(f"Запуск: {path.name} · cwd={cwd}")

        # Build a single command string; the terminal runs it as its own
        # process (compile-then-run chains are still executed by the shell).
        if lang in {'py', 'pyw'}:
            command = f'{q(sys.executable)}{" -m pdb" if debug else ""} {q(path)} {args}'.strip()
        elif lang in {'js', 'mjs', 'cjs'}:
            command = f'node {"--inspect-brk " if debug else ""}{q(path)} {args}'.strip()
        elif lang == 'ts':
            command = f'ts-node {q(path)} {args}'.strip()
        elif lang in {'sh', 'bash', 'zsh'}:
            command = f'bash {q(path)} {args}'.strip()
        elif lang == 'go':
            command = f'go run {q(path)} {args}'.strip()
        elif lang == 'rs':
            command = f'rustc {q(path)} -o {q(path.with_suffix(""))} && {q(path.with_suffix(""))} {args}'.strip()
        elif lang in {'c', 'h'}:
            out = path.with_suffix('.pyscribe_run.exe' if os.name == 'nt' else '.pyscribe_run')
            command = f'gcc {q(path)} -o {q(out)} && {q(out)} {args}'.strip()
        elif lang in {'cpp', 'cc', 'cxx', 'hpp'}:
            out = path.with_suffix('.pyscribe_run.exe' if os.name == 'nt' else '.pyscribe_run')
            command = f'g++ {q(path)} -std=c++17 -o {q(out)} && {q(out)} {args}'.strip()
        elif lang == 'java':
            command = f'javac {q(path)} && java -cp {q(path.parent)} {stem} {args}'.strip()
        elif lang == 'cs':
            proj_file = next(iter(Path(cwd).glob('*.csproj')), None)
            command = f'dotnet run --project {q(proj_file or path)}'.strip()
        elif lang == 'php':
            command = f'php {q(path)} {args}'.strip()
        elif lang == 'rb':
            command = f'ruby {q(path)} {args}'.strip()
        elif lang == 'kt':
            command = (f'kotlinc {q(path)} -include-runtime -d {q(path.with_suffix(".jar"))} '
                       f'&& java -jar {q(path.with_suffix(".jar"))}').strip()
        elif lang == 'swift':
            command = f'swift {q(path)} {args}'.strip()
        elif lang == 'lua':
            command = f'lua {q(path)} {args}'.strip()
        else:
            # Unknown type: open it with the OS default handler.
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
            except Exception:
                logger.exception("Не удалось открыть файл")
            self.status_bar.showMessage(f"Файл открыт системным приложением: {path.name}")
            return

        self.run_in_terminal_command(command, cwd)
        self.status_bar.showMessage(("Отладка " if debug else "Запуск ") + path.name)

    _ENTRY_CANDIDATES = (
        'main.py', 'app.py', 'run.py', '__main__.py', 'manage.py',
        'index.js', 'main.js', 'server.js', 'index.ts', 'main.ts',
        'main.go', 'main.rs',
    )

    def run_project_target(self, debug=False):
        """Запустить проект: явная команда запуска, точка входа или активный файл."""
        if not self.current_project:
            CustomDialog("Сначала откройте проект.").exec_()
            return
        root = Path(str(self.current_project.root_path))
        if not root.is_dir():
            CustomDialog(f"Папка проекта не найдена:\n{root}").exec_()
            return
        candidates = []
        for name in self._ENTRY_CANDIDATES:
            p = root / name
            if p.is_file():
                candidates.append(p)
        # A package layout (src/main.py, app/main.py, ...) is common too.
        if not candidates:
            for sub in ("src", "app", "package", "backend"):
                base = root / sub
                if not base.is_dir():
                    continue
                for name in self._ENTRY_CANDIDATES:
                    p = base / name
                    if p.is_file():
                        candidates.append(p)
                        break
                if candidates:
                    break
        if candidates:
            self.workbench.announce(f"Точка входа в проект: {candidates[0].name}")
            self.run_target(str(candidates[0]), debug)
            return
        # Prefer the current editor if it belongs to this workspace.
        editor = self.get_current_editor()
        if editor and getattr(editor, 'file_path', None) and str(Path(editor.file_path).resolve()).startswith(str(root.resolve()) + os.sep):
            self.run_target(str(editor.file_path), debug)
            return
        CustomDialog("Точка входа в проект не найдена. Откройте файл, который хотите запустить.").exec_()

    def run_and_analyze(self, file_path):
        """PyScribe-specific workflow: execute a target, then refresh the structural model."""
        self.run_target(file_path, False)
        if self.current_project:
            self.activity_bar.set_activity("intelligence")
            QtCore.QTimer.singleShot(1200, self.intelligence_panel.refresh)

    def run_tests(self):
        """Выполняет запуск рабочего процесса tests.
        """
        if not self.current_project:
            return
        root = Path(self.current_project.root_path)
        if (root / 'pytest.ini').exists() or (root / 'pyproject.toml').exists() or (root / 'tests').exists():
            self.workbench.announce(f"Тесты: pytest · cwd={root}")
            self.run_in_terminal('pytest', '', root)
        elif (root / 'package.json').exists():
            self.workbench.announce(f"Тесты: npm test · cwd={root}")
            self.run_in_terminal('npm', 'test', root)
        else:
            CustomDialog("Конфигурация тестов не обнаружена.").exec_()

    def action_project_manager(self):
        """Выполняет операцию action project manager.
        """
        self.action_open_project()

    def action_project_settings(self):
        """Выполняет операцию action project settings.
        """
        if not self.current_project:
            self.project_handler.show_no_project_message()
            return

        try:
            dialog = ProjectConfigDialog(self.current_project, self)
            if dialog.exec_() == QDialog.Accepted:
                self.current_project = dialog.get_config()
                self.status_bar.showMessage("Параметры проекта обновлены")
                self.project_indicator.setText(self.current_project.name)
                self.update_window_title()
        except Exception as e:
            CustomDialog(f"Ошибка открытия параметров проекта: {str(e)}").exec_()

    def action_close_project(self):
        """Выполняет операцию action close project.
        """
        if not self.current_project:
            self.project_handler.show_no_project_message()
            return

        project_name = self.current_project.name

        reply = QMessageBox.question(
            self, "Закрыть проект",
            f"Закрыть проект '{project_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.save_current_session()
            self.close_all_editor_tabs()
            self.current_project = None
            self.workspace_index.set_root(None)
            self.intelligence_panel.set_project(None)
            self.extension_manager.set_project_root(None)
            self.refresh_extensions_panel()
            self.git_panel.set_root(None)
            self.top_bar.set_project("")
            self.setWindowTitle("PyScribe")
            self.project_indicator.setVisible(False)
            self.status_bar.showMessage(f"Проект закрыт: {project_name}")
            self._update_project_menu()
            # No project → the agent falls back to "без контекста".
            ai_panel = getattr(self, "ai_panel", None)
            if ai_panel is not None:
                try:
                    ai_panel.sync_scope_with_project()
                except Exception:
                    logger.exception("Не удалось сбросить контекст ИИ-агента")
            self.show_welcome_screen()

    def _configure_editor_instance(self, editor, s):
        """Выполняет операцию  configure editor instance.

        Args:
            editor: Параметр editor.
            s: Параметр s.
        """
        ed = getattr(editor, 'editor', None)
        if not ed:
            return
        f = ed.font()
        f.setFamily(str(s.get('editor_font', 'Cascadia Code')))
        f.setPointSize(int(s.get('editor_font_size', 13)))
        ed.setFont(f)
        if hasattr(ed, 'setLineWrapMode'):
            wrap = QtWidgets.QPlainTextEdit.WidgetWidth if s.get('word_wrap', False) else QtWidgets.QPlainTextEdit.NoWrap
            ed.setLineWrapMode(wrap)
        if hasattr(ed, 'set_line_numbers_visible'):
            ed.set_line_numbers_visible(bool(s.get('show_line_numbers', True)))
        if hasattr(ed, 'set_syntax_highlighting_enabled'):
            ed.set_syntax_highlighting_enabled(bool(s.get('syntax_highlighting', True)))
        if hasattr(ed, 'document') and ed.document():
            ed.document().modificationChanged.connect(
                lambda mod, w=editor: self.on_editor_modification_changed(w, mod)
            )
        if hasattr(ed, 'textChanged'):
            ed.textChanged.connect(self.on_text_changed)

    def create_editor_tab(self, content: str, file_path: str):
        """Создает и инициализирует новый экземпляр editor tab.

        Args:
            content (str): Полезная нагрузка или входные данные для обработки.
            file_path (str): Путь к целевому файлу или директории в файловой системе.
        """
        try:
            sm = get_settings_manager()
            s = sm.get_all_settings()
            suffix = Path(file_path).suffix.lower().lstrip(".") or "txt"
            editor = ModernCodeEditor(
                parent=self.active_tab_widget,
                language=suffix,
                settings=s,
                workspace_index=self.workspace_index,
                extension_manager=self.extension_manager
            )
            editor.set_code(content)
            editor.set_file_path(file_path)
            self._configure_editor_instance(editor, s)
            if hasattr(self, '_current_status_message') and self._current_status_message:
                if getattr(self, '_is_busy', False):
                    editor.start_busy_indicator(self._current_status_message)
                else:
                    editor.stop_busy_indicator(self._current_status_message)

            tab_name = Path(file_path).name
            tab_index = self.active_tab_widget.addTab(editor, tab_name)
            self.active_tab_widget.setCurrentIndex(tab_index)
            self.save_current_session()
            if hasattr(self, "run_panel"):
                self.run_panel.refresh()
        except Exception as e:
            CustomDialog(f"Ошибка создания вкладки редактора: {str(e)}").exec()

    def close_tab(self, index: int):
        """Закрывает и освобождает системные ресурсы tab.

        Args:
            index (int): Смещение или индекс начального элемента для выборки.
        """
        if index < 0 or index >= self.active_tab_widget.count():
            return

        editor = self.active_tab_widget.widget(index)
        if not editor:
            return

        if self.has_unsaved_changes(index):
            reply = self.ask_save_before_close()
            if reply == QMessageBox.Yes and hasattr(editor, 'save_file'):
                editor.save_file()
            elif reply == QMessageBox.Cancel:
                return

        if hasattr(editor, 'file_path') and editor.file_path:
            file_path = str(getattr(editor, 'file_path'))
            if file_path in self.app_manager.session_files:
                self.app_manager.session_files.remove(file_path)

        if editor is getattr(self, "_settings_tab", None) or editor.property("pyscribeSpecial") == "settings":
            self._settings_tab = None
        if editor is getattr(self, "_welcome_tab", None) or editor.property("pyscribeSpecial") == "welcome":
            self._welcome_tab = None
        if editor is getattr(self, "_extensions_tab", None) or editor.property("pyscribeSpecial") == "extensions":
            self._extensions_tab = None

        self.active_tab_widget.removeTab(index)
        if isinstance(editor, DocumentViewerWidget) or editor.property("pyscribeSpecial") == "browser":
            editor.deleteLater()
        self.recalculate_unsaved_count()
        self.save_current_session()
        self._sync_special_activity()

        if self.active_tab_widget.count() == 0 and self.split_tab_widget is None:
            self.show_welcome_screen()

    def has_unsaved_changes(self, index: int) -> bool:
        """Проверяет наличие unsaved changes.

        Args:
            index (int): Смещение или индекс начального элемента для выборки.

        Returns:
            bool: True, если проверка пройдена успешно; иначе False.
        """
        if index < 0 or index >= self.active_tab_widget.count():
            return False
        w = self.active_tab_widget.widget(index)
        if self.is_special_widget(w):
            return False
        if hasattr(w, "is_modified"):
            return w.is_modified()
        if hasattr(w, "editor") and hasattr(w.editor, "document"):
            return w.editor.document().isModified()
        return "*" in self.active_tab_widget.tabText(index)

    def ask_save_before_close(self) -> int:
        """Выполняет операцию ask save before close.

        Returns:
            int: Результат выполнения операции или результирующий объект.
        """
        return QMessageBox.question(
            self,
            "Несохранённые изменения",
            "Сохранить изменения перед закрытием?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )

    def update_analysis_panels(self):
        """Refresh Problems/Output for the active editor file, never the whole project."""
        if not getattr(self, "console_widget", None):
            return
        editor = self.get_current_editor()
        file_path = getattr(editor, "file_path", None) if editor else None
        engine = getattr(self.intelligence_panel, "engine", None)
        if file_path and engine:
            content = editor.get_code() if hasattr(editor, "get_code") else None
            self.console_widget.set_file_context(str(file_path), engine=engine, content=content)
        elif file_path:
            self.console_widget.set_file_context(str(file_path))
        else:
            self.console_widget.set_file_context(None)

    def _resolve_intelligence_root(self, engine) -> str:
        """Выполняет операцию  resolve intelligence root.

        Args:
            engine: Параметр engine.

        Returns:
            str: Результат выполнения операции или результирующий объект.
        """
        if engine and getattr(engine, 'root', None):
            return engine.root
        if getattr(self, 'current_project', None) and getattr(self.current_project, 'root_path', None):
            return self.current_project.root_path
        editor = self.get_current_editor()
        fp = getattr(editor, 'file_path', None) if editor else None
        if fp and Path(fp).exists():
            return str(Path(fp).parent)
        return os.getcwd()

    @staticmethod
    def _analysis_ready(engine) -> bool:
        """True when *engine* holds a *completed* analysis.

        A fresh engine exposes an empty placeholder analysis, so only a real run
        (it records its duration and the files it saw) counts as finished.
        """
        analysis = getattr(engine, 'analysis', None)
        if analysis is None:
            return False
        if getattr(analysis, 'duration_ms', 0):
            return True
        return bool(getattr(analysis, 'files', None))

    @staticmethod
    def _analysis_disabled(engine) -> bool:
        """True when the project is configured without any analyzer."""
        try:
            return not set(getattr(engine, 'enabled_analyzers', ()) or ())
        except TypeError:
            return False

    def _ensure_engine_analysis(self, engine, root: str):
        """Make sure an analysis is *running* for the project — never run it inline.

        Analysing a project synchronously took seconds and blocked the GUI
        thread, which froze every animation in the window (Qt drives them all
        from that same event loop). The dashboard already runs the analysis on a
        worker thread; here we only kick it off. Callers that need the result
        should check :meth:`_analysis_ready` and schedule themselves with
        :meth:`_defer_until_analysis`.

        Args:
            engine: Engine of the analysis panel (may be ``None``).
            root (str): Project root the analysis should belong to.

        Returns:
            The engine that is (or will be) analysed.
        """
        if not root or self._analysis_ready(engine):
            return engine
        if getattr(self, '_analysis_failed', False):
            # Do not restart a failing analysis in a loop.
            return engine
        panel = getattr(self, 'intelligence_panel', None)
        if panel is None:
            return engine
        panel_root = getattr(getattr(panel, 'engine', None), 'root', None)
        try:
            same_project = bool(panel_root) and str(panel_root) == str(root)
        except (TypeError, ValueError):
            same_project = False
        if same_project:
            panel.refresh()          # starts the worker thread if it is idle
        else:
            panel.set_project(root)  # new engine, analysis starts in the worker
        return getattr(panel, 'engine', None) or engine

    def _defer_until_analysis(self, action):
        """Queue *action* to run once Project Intelligence finishes analysing."""
        if action is None:
            return
        if getattr(self, '_analysis_failed', False):
            self.status_bar.showMessage(
                "Анализ проекта не удался — действие отменено", 5000)
            return
        pending = getattr(self, '_analysis_pending_actions', None)
        if pending is None:
            pending = []
            self._analysis_pending_actions = pending
        if len(pending) < 8:
            pending.append(action)

    def _drain_analysis_actions(self):
        """Run everything that was waiting for the analysis to finish."""
        pending = getattr(self, '_analysis_pending_actions', None) or []
        self._analysis_pending_actions = []
        for action in pending:
            try:
                action()
            except Exception:
                logger.exception("Не удалось выполнить отложенное действие анализа")

    def _find_graph_in_group(self, group):
        """Выполняет поиск и возвращает graph in group.

        Args:
            group: Параметр group.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        for i in range(group.count()):
            w = group.widget(i)
            if isinstance(w, ProjectGraphEditorWidget):
                return i, w
        return None

    def _find_graph_widget(self):
        """Выполняет поиск и возвращает graph widget.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        for group in self.editor_groups():
            res = self._find_graph_in_group(group)
            if res is not None:
                i, w = res
                return group, i, w
        return None

    def _refresh_graph_widget(self, found, engine, mode: str, title: str):
        """Выполняет операцию  refresh graph widget.

        Args:
            found: Параметр found.
            engine: Параметр engine.
            mode (str): Параметр mode.
            title (str): Параметр title.
        """
        group, idx, w = found
        group.setCurrentIndex(idx)
        if engine:
            w.engine = engine
            w.analysis = getattr(engine, 'analysis', None)
        w.set_mode(mode)
        w.refresh()
        self.status_bar.showMessage(f"Граф проекта '{title}' обновлён")

    def open_graph_editor(self, engine=None, mode='modules'):
        """Open architecture graph in an editor tab (or focus and refresh if already open)."""
        try:
            if engine is None:
                engine = getattr(self.intelligence_panel, 'engine', None)
            root = self._resolve_intelligence_root(engine)
            engine = self._ensure_engine_analysis(engine, root)
            if not self._analysis_ready(engine) and not self._analysis_disabled(engine):
                # The analysis is running on the worker thread; waiting for it
                # here would freeze the whole window, so finish the job later.
                self._defer_until_analysis(lambda: self.open_graph_editor(None, mode))
                self.status_bar.showMessage(
                    "Анализ проекта выполняется — граф откроется после него", 5000)
                return
            title = Path(root).name if root else 'Проект'

            found = self._find_graph_widget()
            if found:
                self._refresh_graph_widget(found, engine, mode, title)
                return

            graph = ProjectGraphEditorWidget(engine, mode, None)
            graph.open_file_requested.connect(self.open_analysis_location)
            index = self.active_tab_widget.addTab(graph, f"Граф: {title}")
            self.active_tab_widget.setCurrentIndex(index)
            self.status_bar.showMessage(f"Открыт архитектурный граф проекта: {title}")
        except Exception as exc:
            CustomDialog(f"Ошибка открытия графа проекта: {exc}").exec_()

    def _save_and_open_passport(self, guide_md: str, root: str) -> bool:
        """Сохраняет состояние в постоянное хранилище and open passport.

        Args:
            guide_md (str): Параметр guide md.
            root (str): Параметр root.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        if not root or not Path(root).exists():
            return False
        guide_path = Path(root) / 'PROJECT_REPORT.md'
        try:
            guide_path.write_text(guide_md, encoding='utf-8')
            self.file_manager.open_markdown_file(str(guide_path))
            self.status_bar.showMessage(f"Архитектурный паспорт сформирован: {guide_path.name}")
            return True
        except Exception:
            return False

    def open_defense_guide(self):
        """Generate and open the Architecture Passport in an editor tab."""
        try:
            from services.code_intelligence_service import CodeIntelligenceService
            engine = getattr(self.intelligence_panel, 'engine', None)
            root = self._resolve_intelligence_root(engine)
            engine = self._ensure_engine_analysis(engine, root)
            if not self._analysis_ready(engine) and not self._analysis_disabled(engine):
                self._defer_until_analysis(self.open_defense_guide)
                self.status_bar.showMessage(
                    "Анализ проекта выполняется — паспорт сформируется после него", 5000)
                return

            analysis = getattr(engine, 'analysis', None)
            project_title = Path(root).name if root else 'Проект'
            guide_md = CodeIntelligenceService.generate_architecture_passport(analysis, project_title, root or '.')

            if self._save_and_open_passport(guide_md, root):
                return

            from widgets.MarkdownViewerWidget import MarkdownViewerWidget
            viewer = MarkdownViewerWidget(content=guide_md, parent=self)
            curr_idx = self.active_tab_widget.addTab(viewer, "Паспорт проекта.md")
            self.active_tab_widget.setCurrentIndex(curr_idx)
            self.status_bar.showMessage("Архитектурный паспорт проекта успешно сформирован")
        except Exception as exc:
            CustomDialog(f"Ошибка формирования паспорта проекта: {exc}").exec_()

    def _apply_analysis_to_editor(self, editor, analysis):
        """Применяет настройки или изменения analysis to editor.

        Args:
            editor: Параметр editor.
            analysis: Параметр analysis.
        """
        if hasattr(editor, "set_completion_context"):
            editor.set_completion_context(self.workspace_index, self.extension_manager)
        if isinstance(editor, ProjectGraphEditorWidget) and getattr(self.intelligence_panel, "engine", None):
            editor.engine = self.intelligence_panel.engine
            editor.analysis = analysis
            editor.refresh()

    def _propagate_analysis_to_editors(self, analysis):
        """Выполняет операцию  propagate analysis to editors.

        Args:
            analysis: Параметр analysis.
        """
        for group in self.editor_groups():
            for i in range(group.count()):
                self._apply_analysis_to_editor(group.widget(i), analysis)

    def on_project_analysis_ready(self, analysis):
        """Use Project Intelligence's canonical tree as the completion source."""
        self._analysis_failed = False
        try:
            self.workspace_index.apply_analysis(analysis)
            self._propagate_analysis_to_editors(analysis)
            self.update_analysis_panels()
            self.stop_busy_indicator(f"✓ Анализ завершён")
        except Exception as exc:
            logger.exception("Ошибка анализа")
        finally:
            # Graph/passport actions wait for exactly this moment instead of
            # running the analysis inline (which froze the workbench).
            self._drain_analysis_actions()

    def on_project_analysis_failed(self, message=""):
        """The analysis failed: queued actions must not wait forever."""
        self._analysis_failed = True
        self._analysis_pending_actions = []
        logger.warning("Анализ проекта не удался: %s", message)

    def _scroll_editor_to_line(self, text_editor, line_number: int):
        """Выполняет операцию  scroll editor to line.

        Args:
            text_editor: Параметр text editor.
            line_number (int): Параметр line number.
        """
        cursor = text_editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        for _ in range(max(0, int(line_number) - 1)):
            if not cursor.movePosition(QtGui.QTextCursor.Down):
                break
        text_editor.setTextCursor(cursor)
        text_editor.centerCursor()
        text_editor.setFocus()

    def open_analysis_location(self, file_path, line_number=1):
        """Open a location reported by Project Intelligence and focus its line."""
        self.file_manager.open_file(file_path)
        editor = self.get_current_editor()
        if editor and hasattr(editor, "editor"):
            self._scroll_editor_to_line(editor.editor, line_number)

    def action_analyze_current_impact(self):
        """Выполняет операцию action analyze current impact.
        """
        if not self.current_project:
            CustomDialog("Сначала откройте проект.").exec_()
            return
        self.activity_bar.set_activity("intelligence")
        editor = self.get_current_editor()
        path = getattr(editor, "file_path", None) if editor else None
        if path:
            self.intelligence_panel.set_impact_file(path)

    def action_adversary_test(self):
        """«Адвокат дьявола»: испытать текущий файл граничными входами."""
        editor = self.get_current_editor()
        path = getattr(editor, "file_path", None) if editor else None
        if not path:
            CustomDialog("Сначала откройте файл Python, который нужно испытать.").exec_()
            return
        self.activity_bar.set_activity("intelligence")
        self.intelligence_panel.set_adversary_file(path)
        self.intelligence_panel._run_adversary()

    def open_search_match(self, file_path, line_number):
        """Открывает ресурс или дескриптор search match.

        Args:
            file_path: Путь к целевому файлу или директории в файловой системе.
            line_number: Параметр line number.
        """
        self.file_manager.open_file(file_path)
        editor = self.get_current_editor()
        if editor and hasattr(editor, "editor"):
            self._scroll_editor_to_line(editor.editor, line_number)

    def open_file_from_explorer(self, index):
        """Открывает ресурс или дескриптор file from explorer.

        Args:
            index: Смещение или индекс начального элемента для выборки.
        """
        if not self.file_explorer.model.isDir(index):
            file_path = self.file_explorer.model.filePath(index)
            self.file_manager.open_file(file_path)

    def _sync_special_activity(self):
        """Синхронизирует состояние между компонентами special activity.
        """
        settings_open = any(
            group.currentWidget() is not None and (
                group.currentWidget().property("pyscribeSpecial") == "settings"
                or (getattr(self, "_settings_tab", None) is not None and group.currentWidget() is self._settings_tab)
            )
            for group in self.editor_groups()
        )
        if not settings_open and getattr(self, "_settings_tab", None) is not None:
            still_exists = any(
                any(group.widget(i) is self._settings_tab for i in range(group.count()))
                for group in self.editor_groups()
            )
            if not still_exists:
                self._settings_tab = None
        if hasattr(self, "activity_bar"):
            self.activity_bar.sync_special_state(
                terminal_visible=self.terminal_visible,
                settings_open=settings_open,
                browser_open=any(group.currentWidget() is not None and
                                 group.currentWidget().property("pyscribeSpecial") == "browser"
                                 for group in self.editor_groups()),
            )

    def _remove_special_tab_from_group(self, group, kind: str):
        """Удаляет из коллекции special tab from group.

        Args:
            group: Параметр group.
            kind (str): Параметр kind.
        """
        for i in range(group.count() - 1, -1, -1):
            widget = group.widget(i)
            if widget.property("pyscribeSpecial") == kind:
                group.removeTab(i)

    def close_special_tab(self, kind: str):
        """Закрывает и освобождает системные ресурсы special tab.

        Args:
            kind (str): Параметр kind.
        """
        for group in self.editor_groups():
            self._remove_special_tab_from_group(group, kind)
        if kind == "welcome":
            self._welcome_tab = None
        elif kind == "settings":
            self._settings_tab = None
        elif kind == "extensions":
            self._extensions_tab = None
        self._sync_special_activity()

    def show_welcome_screen(self):
        """Выполняет операцию show welcome screen.
        """
        found = self._find_special_tab("welcome")
        if found:
            group, idx = found
            self._set_active_group(group)
            group.setCurrentIndex(idx)
            widget = group.widget(idx)
            widget.set_recent_files(self.app_manager.recent_files)
            if hasattr(widget, 'refresh_recent_projects'):
                widget.refresh_recent_projects()
            return
        welcome_widget = Ui_Welcome(
            self.central_widget, self.app_manager.settings, self.app_manager.recent_files
        )
        welcome_widget.setProperty("pyscribeSpecial", "welcome")
        welcome_widget.new_file_card.clicked.connect(self.action_new_file)
        welcome_widget.open_file_card.clicked.connect(self.action_open_file)
        welcome_widget.open_project_card.clicked.connect(self.project_handler.open_project)
        welcome_widget.recent_project_requested.connect(self.project_handler.on_project_opened)
        welcome_widget.recent_file_requested.connect(self.file_manager.open_file)
        index = self.active_tab_widget.addTab(welcome_widget, "Начало работы")
        self.active_tab_widget.setCurrentIndex(index)
        self._welcome_tab = welcome_widget

    def is_special_widget(self, widget) -> bool:
        """Check if widget is a special pane (Welcome, Settings, etc.) that should not be tracked as an editable file."""
        if widget is None:
            return True
        prop = getattr(widget, "property", None)
        if prop and prop("pyscribeSpecial") in {"welcome", "settings", "extensions", "browser"}:
            return True
        cname = widget.__class__.__name__
        if cname in {"Ui_Welcome", "SettingsWidget", "DocumentViewerWidget", "HexViewer", "MarkdownViewerWidget", "DiagramViewerWidget", "PDFViewerWidget", "TableViewerWidget"}:
            return True
        fp = getattr(widget, "file_path", None)
        if not fp:
            return True
        return False

    def _find_tab_in_group_widget(self, group, widget):
        """Выполняет поиск и возвращает tab in group widget.

        Args:
            group: Параметр group.
            widget: Параметр widget.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        for i in range(group.count()):
            w = group.widget(i)
            if w is widget or (hasattr(w, 'editor') and w.editor is widget):
                return i
        return -1

    def find_tab_for_widget(self, widget):
        """Find the QTabWidget group and index containing the given widget or inner editor."""
        if widget is None:
            return None, -1
        for group in self.editor_groups():
            idx = self._find_tab_in_group_widget(group, widget)
            if idx >= 0:
                return group, idx
        return None, -1

    def on_editor_modification_changed(self, editor, modified: bool):
        """Handle document modification signal: add/remove '*' marker on the exact matching tab."""
        if self.is_special_widget(editor):
            return
        group, index = self.find_tab_for_widget(editor)
        if group is None or index < 0:
            return
        current_text = group.tabText(index)
        if modified and "*" not in current_text:
            group.setTabText(index, current_text + " *")
        elif not modified and "*" in current_text:
            clean_title = current_text.replace(" *", "").replace("*", "").strip()
            group.setTabText(index, clean_title)
        self.recalculate_unsaved_count()

    def _update_editor_index(self, editor):
        """Обновляет параметры editor index.

        Args:
            editor: Параметр editor.
        """
        if not editor or self.is_special_widget(editor) or not self.workspace_index.root:
            return
        fp = getattr(editor, "file_path", None)
        if fp:
            try:
                self.workspace_index.update_file(Path(fp), editor.get_code())
            except Exception:
                pass

    def on_text_changed(self):
        """Debounced live index and analysis update for genuine files without modifying tab titles.

        Re-indexing the file on every keystroke re-parsed the whole module (tens
        of milliseconds each time), so the index update waits for a short typing
        pause together with the diagnostics refresh.
        """
        if getattr(self, "analysis_refresh_timer", None):
            self.analysis_refresh_timer.start(500)
        else:
            self._on_typing_settled()

    def _on_typing_settled(self):
        """Typing stopped: refresh the completion index and the diagnostics."""
        self._update_editor_index(self.get_current_editor())
        self.update_analysis_panels()

    def _count_group_unsaved(self, group) -> int:
        """Подсчитывает количество group unsaved.

        Args:
            group: Параметр group.

        Returns:
            int: Результат выполнения операции или результирующий объект.
        """
        count = 0
        for i in range(group.count()):
            w = group.widget(i)
            if not self.is_special_widget(w) and "*" in group.tabText(i):
                count += 1
        return count

    def recalculate_unsaved_count(self):
        """Count only real open files with unsaved markers."""
        self.unsaved_files_count = sum(self._count_group_unsaved(g) for g in self.editor_groups())
        self.update_window_title()

    def add_unsaved_marker(self, index: int, group=None):
        """Выполняет операцию add unsaved marker.

        Args:
            index (int): Смещение или индекс начального элемента для выборки.
            group: Параметр group.
        """
        if group is None:
            group = self.active_tab_widget or self.tab_widget
        if group is None or index < 0 or index >= group.count():
            return
        w = group.widget(index)
        if self.is_special_widget(w):
            return
        current_text = group.tabText(index)
        if "*" not in current_text:
            group.setTabText(index, current_text + " *")
            self.recalculate_unsaved_count()

    def remove_unsaved_marker(self, index: int = None, group=None):
        """Удаляет из коллекции unsaved marker.

        Args:
            index (int): Смещение или индекс начального элемента для выборки.
            group: Параметр group.
        """
        if group is None:
            group = self.active_tab_widget or self.tab_widget
        if group is None:
            return
        if index is None:
            index = group.currentIndex()
        if 0 <= index < group.count():
            current_text = group.tabText(index)
            if "*" in current_text:
                clean_title = current_text.replace(" *", "").replace("*", "").strip()
                group.setTabText(index, clean_title)
                self.recalculate_unsaved_count()

    def _extract_open_paths_from_group(self, group, seen: set, paths: list):
        """Выполняет операцию  extract open paths from group.

        Args:
            group: Параметр group.
            seen (set): Параметр seen.
            paths (list): Параметр paths.
        """
        for i in range(group.count()):
            w = group.widget(i)
            if self.is_special_widget(w):
                continue
            fp = getattr(w, "file_path", None)
            if not fp:
                continue
            p = Path(fp)
            if not p.exists():
                continue
            p_str = str(p.resolve())
            if p_str not in seen:
                seen.add(p_str)
                paths.append(p_str)

    def get_open_file_paths(self) -> list:
        """Collect paths of all genuine files open across all editor tab groups."""
        paths = []
        seen = set()
        for group in self.editor_groups():
            self._extract_open_paths_from_group(group, seen, paths)
        return paths

    def save_current_session(self):
        """Persist open files scoped to current project, or standalone if no project is active."""
        current_files = self.get_open_file_paths()
        self.app_manager.session_files = current_files
        if self.current_project and getattr(self.current_project, "root_path", None):
            saveSession(current_files, project_path=self.current_project.root_path)
        else:
            saveSession(current_files, project_path=None)

    def update_tab_title(self, index: int, title: str):
        """Обновляет параметры tab title.

        Args:
            index (int): Смещение или индекс начального элемента для выборки.
            title (str): Параметр title.
        """
        if index < 0 or index >= self.active_tab_widget.count():
            return

        current_text = self.active_tab_widget.tabText(index)
        if "*" in current_text:
            title += " *"
        self.active_tab_widget.setTabText(index, title)

    def refresh_extensions_panel(self):
        """Выполняет операцию refresh extensions panel.
        """
        if not hasattr(self, "extensions_list"):
            return
        self.extensions_list.clear()
        extensions = self.extension_manager.list_extensions()
        if not extensions:
            item = QtWidgets.QListWidgetItem("Нет установленных расширений")
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.extensions_list.addItem(item)
            return
        for ext in extensions:
            name = ext.get("name", ext.get("id", "Расширение"))
            version = ext.get("version", "")
            item = QtWidgets.QListWidgetItem(f"{name}  {version}".strip())
            item.setToolTip(ext.get("id", ""))
            self.extensions_list.addItem(item)
        for ext_id, error in self.extension_manager.errors.items():
            item = QtWidgets.QListWidgetItem(f"{ext_id}  • ошибка загрузки")
            item.setToolTip(error)
            self.extensions_list.addItem(item)

    def update_window_title(self):
        """Обновляет параметры window title.
        """
        base_title = "PyScribe"
        if hasattr(self, 'current_project') and self.current_project:
            base_title += f" - {self.current_project.name}"
        if self.unsaved_files_count > 0:
            base_title += " (*)"
        self.setWindowTitle(base_title)
        if hasattr(self, 'top_bar'):
            self.top_bar.set_project(self.current_project.name if self.current_project else "")

    def get_current_editor(self):
        """Возвращает current editor.

        Returns:
            Результат выполнения операции или результирующий объект.
        """
        # During startup some actions/signals can fire before UIManager has
        # assigned active_tab_widget. Fall back to the primary editor group.
        group = self.active_tab_widget or self.tab_widget
        if group is None:
            return None

        current_index = group.currentIndex()
        if 0 <= current_index < group.count():
            editor = group.widget(current_index)
            if hasattr(editor, 'get_code') and hasattr(editor, 'set_code'):
                return editor
        return None

    def load_launch_arguments(self, file_path: str) -> str:
        """Загружает и десериализует launch arguments.

        Args:
            file_path (str): Путь к целевому файлу или директории в файловой системе.

        Returns:
            str: Результат выполнения операции или результирующий объект.
        """
        if not self.config_path.exists():
            return ""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                args_config = json.load(f)
            return args_config.get(file_path, "")
        except Exception:
            logger.exception("PyScribe operation failed")
            return ""

    def _tab_is_dirty(self, group, index: int, editor) -> bool:
        """Выполняет операцию  tab is dirty.

        Args:
            group: Параметр group.
            index (int): Смещение или индекс начального элемента для выборки.
            editor: Параметр editor.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        if hasattr(editor, "is_modified") and editor.is_modified():
            return True
        if hasattr(editor, "editor") and hasattr(editor.editor, "document"):
            if editor.editor.document().isModified():
                return True
        return "*" in group.tabText(index)

    def _perform_tab_save(self, group, index: int, editor, file_path: str) -> bool:
        """Выполняет операцию  perform tab save.

        Args:
            group: Параметр group.
            index (int): Смещение или индекс начального элемента для выборки.
            editor: Параметр editor.
            file_path (str): Путь к целевому файлу или директории в файловой системе.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        try:
            if not editor.save_file():
                return False
            if hasattr(editor, "editor") and hasattr(editor.editor, "document"):
                editor.editor.document().setModified(False)
            self.remove_unsaved_marker(index, group=group)
            if self.workspace_index.root:
                self.workspace_index.update_file(Path(file_path), editor.get_code())
            return True
        except Exception as e:
            logger.warning("Auto-save failed for %s: %s", file_path, e)
            return False

    def _save_modified_tab(self, group, index: int) -> bool:
        """Сохраняет состояние в постоянное хранилище modified tab.

        Args:
            group: Параметр group.
            index (int): Смещение или индекс начального элемента для выборки.

        Returns:
            bool: Результат выполнения операции или результирующий объект.
        """
        editor = group.widget(index)
        if self.is_special_widget(editor):
            return False
        file_path = getattr(editor, "file_path", None)
        if not file_path or not hasattr(editor, "save_file"):
            return False
        if not self._tab_is_dirty(group, index, editor):
            return False
        return self._perform_tab_save(group, index, editor, file_path)

    def auto_save(self):
        """Выполняет операцию auto save.
        """
        saved_any = any(
            self._save_modified_tab(group, i)
            for group in self.editor_groups()
            for i in range(group.count())
        )
        if saved_any:
            self.recalculate_unsaved_count()
            if getattr(self, "status_bar", None):
                self.status_bar.showMessage("Автосохранение выполнено", 2000)

    def show_run_options_dialog(self, file_path):
        """Выполняет операцию show run options dialog.

        Args:
            file_path: Путь к целевому файлу или директории в файловой системе.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Параметры запуска")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Выберите вариант запуска:")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            f"Текущий проект: <b>{self.current_project.name}</b>\n"
            f"Текущий файл: {Path(file_path).name}"
        )
        desc_label.setStyleSheet("color: #CCCCCC; line-height: 1.4;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        project_button = QPushButton("Запустить проект")
        project_button.setStyleSheet("font-size: 14px; padding: 12px;")
        project_button.clicked.connect(lambda: self.run_project_from_dialog(dialog))

        file_button = QPushButton("Запустить текущий файл")
        file_button.setStyleSheet("font-size: 14px; padding: 12px;")
        file_button.clicked.connect(lambda: self.run_file_from_dialog(dialog, file_path))

        cancel_button = QPushButton("Отмена")
        cancel_button.setObjectName("secondary")
        cancel_button.clicked.connect(dialog.reject)

        layout.addWidget(project_button)
        layout.addWidget(file_button)
        layout.addWidget(cancel_button)

        dialog.exec_()

    def run_project_from_dialog(self, dialog):
        """Выполняет запуск рабочего процесса project from dialog.

        Args:
            dialog: Параметр dialog.
        """
        dialog.accept()
        self.action_run_project()

    def run_file_from_dialog(self, dialog, file_path):
        """Выполняет запуск рабочего процесса file from dialog.

        Args:
            dialog: Параметр dialog.
            file_path: Путь к целевому файлу или директории в файловой системе.
        """
        dialog.accept()
        current_editor = self.get_current_editor()
        if current_editor:
            self.run_single_file(current_editor)

    def run_single_file(self, editor):
        """Выполняет запуск рабочего процесса single file.

        Args:
            editor: Параметр editor.
        """
        if hasattr(editor, 'save_file'):
            if not editor.save_file():
                CustomDialog("Не удалось сохранить файл перед выполнением").exec_()
                return

        file_path = getattr(editor, 'file_path', None)
        if not file_path:
            CustomDialog("Нет связанного файла для текущей вкладки").exec_()
            return

        args = self.load_launch_arguments(str(file_path))

        working_dir = None
        if hasattr(self, 'current_project') and self.current_project:
            working_dir = self.current_project.root_path

        self.run_in_terminal(str(file_path), args, working_dir)

    def _update_project_menu(self):
        """Обновляет параметры project menu.
        """
        has_project = hasattr(self, 'current_project') and self.current_project is not None
        if hasattr(self, 'project_indicator') and self.project_indicator:
            self.project_indicator.setText(self.current_project.name if has_project else "")
            self.project_indicator.setVisible(False)
        if hasattr(self, 'top_bar'):
            self.top_bar.set_project(self.current_project.name if has_project else "")

    def closeEvent(self, event):
        """Закрывает и освобождает системные ресурсы event.

        Args:
            event: Параметр event.
        """
        if self.unsaved_files_count > 0:
            reply = QMessageBox.question(
                self,
                "Несохранённые изменения",
                "Сохранить все изменения перед выходом?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.action_save_all_files()
                self.finalize_application()
                event.accept()
            elif reply == QMessageBox.No:
                self.finalize_application()
                event.accept()
            else:
                event.ignore()
                return
        else:
            self.finalize_application()
            event.accept()

    def finalize_application(self):
        """Выполняет операцию finalize application.
        """
        try:
            if hasattr(self, 'console_widget') and hasattr(self.console_widget, 'shutdown'):
                self.console_widget.shutdown()
            # Stop the AI worker and terminate any MCP servers it spawned.
            ai_panel = getattr(self, 'ai_panel', None)
            if ai_panel is not None and hasattr(ai_panel, 'shutdown'):
                try:
                    ai_panel.shutdown()
                except Exception:
                    logger.exception("Не удалось остановить ИИ-агента")
            # Stop analysis/index threads so no worker outlives the window.
            panel = getattr(self, 'intelligence_panel', None)
            if panel is not None and hasattr(panel, 'shutdown'):
                try:
                    panel.shutdown()
                except Exception:
                    logger.exception("Не удалось остановить анализ проекта")
            timer = getattr(self, '_index_timer', None)
            if timer is not None:
                timer.stop()
            self.save_current_session()
            saveRecent(self.app_manager.recent_files)
            clear_backup()
        except Exception:
            logger.exception("PyScribe operation failed")

    def on_project_opened(self, project_config):
        """Обработчик события для project opened.

        Args:
            project_config: Параметр project config.
        """
        self.project_handler.on_project_opened(project_config)
