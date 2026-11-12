"""PyScribe UI layout and workbench chrome management subsystem."""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QLabel

from app.top_bar import ExplorerHeader, WorkbenchTopBar
from widgets.ActivityBar import ActivityBar
from widgets.Explorer import Explorer
from widgets.GitPanel import GitPanel
from widgets.ProjectIntelligenceDashboard import ProjectIntelligenceDashboard
from widgets.RunDebugPanel import RunDebugPanel
from widgets.SearchPanel import SearchPanel
from widgets.TabWidget import TabWidget

if TYPE_CHECKING:
    from app.main_window import ModernMainWindow


class UIManager:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        self.app_manager = main_window.app_manager

    def setup_ui(self):
        self._setup_central_widget()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._apply_styles()

    def _setup_central_widget(self):
        self.main_window.central_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(self.main_window.central_widget)

        root = QtWidgets.QHBoxLayout(self.main_window.central_widget)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.main_window.activity_bar = ActivityBar(self.main_window)
        root.addWidget(self.main_window.activity_bar)

        self._setup_side_panel()
        self._setup_splitters(root)

    def _setup_side_panel(self):
        self.main_window.side_panel = QtWidgets.QFrame()
        self.main_window.side_panel.setObjectName("sidePanel")
        self.main_window.side_panel.setMinimumWidth(260)
        self.main_window.side_panel.setMaximumWidth(620)
        self.main_window.side_panel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        side_layout = QtWidgets.QVBoxLayout(self.main_window.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        # NOTE: there is deliberately no second "ПРОВОДНИК" strip here. The
        # explorer view draws its own header (ExplorerHeader + explorer actions)
        # inside _setup_explorer_panel(); adding one more produced two identical
        # labels stacked on top of each other.
        self.main_window.side_panel_title = None

        self.main_window.explorer_panel = QtWidgets.QWidget(self.main_window.side_panel)
        explorer_layout = QtWidgets.QVBoxLayout(self.main_window.explorer_panel)
        explorer_layout.setContentsMargins(0, 0, 0, 0)
        explorer_layout.setSpacing(0)
        self._setup_explorer_panel(explorer_layout)
        side_layout.addWidget(self.main_window.explorer_panel)

        self.main_window.search_panel = SearchPanel(self.main_window)
        self.main_window.search_panel.open_file_requested.connect(self.main_window.file_manager.open_file)
        self.main_window.search_panel.open_match_requested.connect(self.main_window.open_search_match)
        self.main_window.search_panel.hide()
        side_layout.addWidget(self.main_window.search_panel)

        self.main_window.run_panel = RunDebugPanel(self.main_window, self.main_window.side_panel)
        self.main_window.run_panel.hide()
        self.main_window.run_panel.run_requested.connect(self.main_window.run_target)
        self.main_window.run_panel.project_requested.connect(self.main_window.run_project_target)
        self.main_window.run_panel.run_analyze_requested.connect(self.main_window.run_and_analyze)
        side_layout.addWidget(self.main_window.run_panel)

        self.main_window.git_panel = GitPanel(self.main_window)
        self.main_window.git_panel.hide()
        side_layout.addWidget(self.main_window.git_panel)

        from widgets.TodoPanel import TodoPanel
        self.main_window.todo_panel = TodoPanel(self.main_window, self.main_window.side_panel)
        self.main_window.todo_panel.hide()
        self.main_window.todo_panel.open_location_requested.connect(self.main_window.open_analysis_location)
        side_layout.addWidget(self.main_window.todo_panel)

        self.main_window.intelligence_panel = ProjectIntelligenceDashboard(self.main_window)
        self.main_window.intelligence_panel.open_file_requested.connect(self.main_window.open_analysis_location)
        self.main_window.intelligence_panel.analysis_ready.connect(self.main_window.on_project_analysis_ready)
        self.main_window.intelligence_panel.analysis_failed.connect(self.main_window.on_project_analysis_failed)
        self.main_window.intelligence_panel.open_graph_editor_requested.connect(self.main_window.open_graph_editor)
        self.main_window.intelligence_panel.open_defense_guide_requested.connect(self.main_window.open_defense_guide)
        self.main_window.intelligence_panel.hide()
        side_layout.addWidget(self.main_window.intelligence_panel)

        # AI agent lives in the sidebar like VS Code's chat view.
        from widgets.AIAgentPanel import AIAgentPanel
        self.main_window.ai_panel = AIAgentPanel(self.main_window, self.main_window.side_panel)
        self.main_window.ai_panel.hide()
        side_layout.addWidget(self.main_window.ai_panel)

    def _setup_splitters(self, root):
        self.main_window.workspace_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.main_window.workspace_splitter.setChildrenCollapsible(False)
        self.main_window.workspace_splitter.setHandleWidth(1)
        self.main_window.workspace_splitter.setObjectName("workspaceSplitter")
        self.main_window.workspace_splitter.addWidget(self.main_window.side_panel)

        self.main_window.editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.main_window.editor_area_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.main_window.editor_area_splitter.setChildrenCollapsible(False)
        self.main_window.editor_area_splitter.setHandleWidth(1)

        self.main_window.tab_widget = TabWidget(
            self.main_window.editor_area_splitter, self.app_manager.settings
        )
        self.main_window.tab_widget.setObjectName("editorGroupPrimary")
        self.main_window.editor_area_splitter.addWidget(self.main_window.tab_widget)
        self.main_window.split_tab_widget = None
        self.main_window.active_tab_widget = self.main_window.tab_widget

        self.main_window.editor_splitter.addWidget(self.main_window.editor_area_splitter)
        self.main_window.terminal_widget = None
        self.main_window.editor_splitter.setChildrenCollapsible(False)
        self.main_window.workspace_splitter.addWidget(self.main_window.editor_splitter)
        self.main_window.workspace_splitter.setStretchFactor(0, 0)
        self.main_window.workspace_splitter.setStretchFactor(1, 1)
        self.main_window.workspace_splitter.setSizes([int(self.app_manager.settings.get('sidebar_width', 300)), 1])
        root.addWidget(self.main_window.workspace_splitter, 1)

    def _setup_explorer_panel(self, parent_layout=None):
        self.main_window.explorer_buttons = {}
        base_path = getattr(self.app_manager, "base_path", Path(__file__).resolve().parent.parent)
        from design import icons as codicons
        # VS Code explorer header actions (16px codicons in 24px hit areas).
        actions = (
            ('new_file', 'new-file', 'Новый файл'),
            ('new_folder', 'new-folder', 'Новая папка'),
            ('refresh', 'refresh', 'Обновить проводник'),
            ('collapse', 'collapse-all', 'Свернуть всё'),
        )
        for key, icon_name, tooltip in actions:
            button = QtWidgets.QToolButton()
            button.setIcon(codicons.codicon_icon(icon_name, 16, "#CCCCCC"))
            button.setIconSize(QtCore.QSize(16, 16))
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setObjectName('explorerAction')
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFixedSize(24, 24)
            self.main_window.explorer_buttons[key] = button

        header = ExplorerHeader()
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(2)
        # The single sidebar section title. It is updated by
        # ModernMainWindow._handle_activity() when another view is selected, so
        # it always matches the panel that is actually visible.
        section_label = QtWidgets.QLabel("ПРОВОДНИК")
        section_label.setObjectName("explorerSectionTitle")
        section_label.setStyleSheet("background: transparent; border: none;")
        section_label.setMinimumWidth(0)
        section_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        hl.addWidget(section_label, 1)
        for button in self.main_window.explorer_buttons.values():
            hl.addWidget(button, 0, QtCore.Qt.AlignVCenter)
        self.main_window.explorer_section_title = section_label
        # The folder being shown is reported in the tooltip instead of a second
        # text line (that was the source of the duplicated title strip).
        section_label.setToolTip("Проводник: текущий корень проекта")
        self.main_window.file_explorer = Explorer()
        self.main_window.file_explorer.setObjectName("fileExplorer")
        self.main_window.file_explorer.setHeaderHidden(True)
        self.main_window.file_explorer.root_changed.connect(
            self.main_window._set_explorer_location_title
        )
        # Connections live here only — main_window._setup_connections must not
        # connect them again (double dialogs were a real bug).
        self.main_window.explorer_buttons['new_file'].clicked.connect(
            self.main_window.file_explorer.create_new_file
        )
        self.main_window.explorer_buttons['new_folder'].clicked.connect(
            self.main_window.file_explorer.create_new_folder
        )
        self.main_window.explorer_buttons['refresh'].clicked.connect(
            self.main_window.file_explorer.refresh_model
        )
        self.main_window.explorer_buttons['collapse'].clicked.connect(
            self.main_window.file_explorer.collapseAll
        )
        if parent_layout is None:
            self.main_window.explorer_layout = QtWidgets.QVBoxLayout()
            parent_layout = self.main_window.explorer_layout
        parent_layout.addWidget(header)
        parent_layout.addWidget(self.main_window.file_explorer, 1)

    def _setup_menu_bar(self):
        self.main_window.menu_bar = None
        self.main_window.top_bar = WorkbenchTopBar(self.main_window)
        self.main_window.setMenuWidget(self.main_window.top_bar)
        self.main_window.menus = self.main_window.top_bar.menus

    def _setup_recent_files_submenu(self):
        # Recent files are intentionally not added to the top menu.
        # Empty/dynamic submenus make the workbench visually noisy.
        return

    def _setup_status_bar(self):
        # Нижний виджет строки состояний полностью скрыт по запросу пользователя.
        # Индикатор операций (busy_indicator) и статусы перенесены в центр строки редактора.
        self.main_window.status_bar = self.main_window.statusBar()
        self.main_window.status_bar.setObjectName("statusBar")
        self.main_window.status_bar.hide()
        self.main_window.status_bar.setVisible(False)
        self.main_window.status_bar.setFixedHeight(0)

        self.main_window.status_spinner = None
        self.main_window.project_indicator = QLabel("")
        self.main_window.project_indicator.setVisible(False)
        self.main_window.size_grip = None

    def _apply_styles(self):
        """Legacy hook kept for compatibility; visual styling is application-wide."""
        return

    def _toggle_explorer_visibility(self, visible: bool):
        for widget in [self.main_window.file_explorer] + list(
            self.main_window.explorer_buttons.values()
        ):
            widget.setVisible(visible)

    def _add_recent_action(self, menu, file_path: str):
        try:
            if not Path(file_path).exists():
                return
            action = QtWidgets.QAction(f"   {file_path}", self.main_window)
            action.triggered.connect(partial(self.main_window.open_recent_file, file_path))
            menu.addAction(action)
        except Exception:
            pass

    def _update_recent_files_menu(self):
        menu = getattr(self.main_window, "recent_files_menu", None)
        if menu is None:
            return
        menu.clear()

        for file_path in self.app_manager.recent_files[:5]:
            self._add_recent_action(menu, file_path)

        menu.addSeparator()
        menu.addAction(self.main_window.action_clear_recent)
