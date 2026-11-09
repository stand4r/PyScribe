"""PyScribe top title bar, menu strip, and explorer header components."""
from __future__ import annotations

from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon, QPainter

from design.themes import THEMES
from design import icons as codicons
from utils.settings_manager import get_settings_manager

# VS Code-like custom title bar. The menu strip inside it uses 24px hit areas
# and 13px text, matching the rest of the chrome typography.
TITLE_BAR_HEIGHT = 40
MENU_BUTTON_HEIGHT = 24
WINDOW_CONTROL_SIZE = QSize(46, 30)


class OmniSearchPill(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal()

    def __init__(self, base_path: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("omniSearchPill")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(26)
        self.setFixedWidth(420)
        # Flat box with a hairline border — the same treatment as an input field.
        self.setStyleSheet("""
            QFrame#omniSearchPill {
                background: #313131;
                border: 1px solid #313131;
                border-radius: 2px;
            }
            QFrame#omniSearchPill:hover { border: 1px solid #454545; }
        """)
        pill_layout = QtWidgets.QHBoxLayout(self)
        pill_layout.setContentsMargins(6, 0, 8, 0)
        pill_layout.setSpacing(6)

        lens_icon = QtWidgets.QLabel()
        lens_icon.setPixmap(codicons.codicon_icon("search", 16, "#9D9D9D").pixmap(16, 16))
        lens_icon.setFixedSize(16, 16)
        lens_icon.setStyleSheet("background: transparent; border: none;")
        pill_layout.addWidget(lens_icon, 0, QtCore.Qt.AlignVCenter)

        prompt = QtWidgets.QLabel("Поиск файлов и команд")
        prompt.setStyleSheet("background: transparent; border: none; color: #9D9D9D; font-size: 13px;")
        pill_layout.addWidget(prompt, 0, QtCore.Qt.AlignVCenter)
        pill_layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class WorkbenchTopBar(QtWidgets.QFrame):
    """VS Code-inspired application/title/menu strip."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("workbenchTopBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(2)

        base_path = getattr(getattr(window, "app_manager", None), "base_path", Path(__file__).resolve().parent.parent)
        self._base_path = Path(base_path)

        # Brand mark sits to the left of the "PyScribe" wordmark. A dedicated
        # monochrome glyph is used so it stays crisp at 16 px on any background
        # (the coloured app icon turns to mush at that size).
        brand = QtWidgets.QLabel()
        brand.setObjectName("appBrandIcon")
        brand.setStyleSheet("background: transparent; border: none;")
        brand.setFixedSize(20, 20)
        brand.setAlignment(QtCore.Qt.AlignCenter)
        glyph = self._base_path / "src" / "icon_titlebar_2x.png"
        if not glyph.exists():
            glyph = self._base_path / "src" / "icon_titlebar.png"
        pixmap = QtGui.QPixmap(str(glyph))
        if not pixmap.isNull():
            brand.setPixmap(pixmap.scaled(16, 16, QtCore.Qt.KeepAspectRatio,
                                          QtCore.Qt.SmoothTransformation))
        else:
            icon = self._base_path / "src" / "icon_app_32.png"
            brand.setPixmap(QtGui.QIcon(str(icon)).pixmap(16, 16))
        layout.addWidget(brand, 0, QtCore.Qt.AlignVCenter)

        title = QtWidgets.QLabel("PyScribe")
        title.setObjectName("appTitle")
        title.setStyleSheet("background: transparent; border: none; color: #CCCCCC; font-size: 13px;")
        layout.addWidget(title, 0, QtCore.Qt.AlignVCenter)
        layout.addSpacing(10)

        self.menus = {}
        for name, definitions in self._definitions().items():
            button = QtWidgets.QToolButton()
            button.setText(name)
            button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            button.setMenu(self._make_menu(definitions))
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setStyleSheet(
                "QToolButton { border-radius: 3px; padding: 0 8px; font-size: 13px; "
                "color: #CCCCCC; background: transparent; border: none; }"
                "QToolButton:hover { background: #2A2D2E; color: #FFFFFF; }"
                "QToolButton::menu-indicator { image: none; width: 0; }"
            )
            self.menus[name.lower()] = button.menu()
            layout.addWidget(button, 0, QtCore.Qt.AlignVCenter)

        layout.addStretch(1)

        # Command palette entry point, styled like VS Code's centre search box.
        self.search_pill = OmniSearchPill(self._base_path, self)
        self.search_pill.clicked.connect(getattr(self.window, "action_quick_open", lambda: None))
        layout.addWidget(self.search_pill, 0, QtCore.Qt.AlignVCenter)
        layout.addSpacing(12)

        layout.addStretch(1)

        # Retain self.project so external callers do not error, but omit from layout
        self.project = QtWidgets.QLabel("")
        self.project.setObjectName("topProject")

        # Native title-bar replacement, right-aligned like VS Code on Windows.
        self.window_controls = QtWidgets.QWidget(self)
        self.window_controls.setObjectName("windowControls")
        self.window_controls.setStyleSheet("background: transparent; border: none;")
        controls = QtWidgets.QHBoxLayout(self.window_controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(0)

        self.minimize_button = self._window_button("chrome-minimize", "Свернуть", self.window.showMinimized, "windowControl")
        self.maximize_button = self._window_button("chrome-maximize", "Развернуть", self._toggle_maximize, "windowControl")
        self.close_button = self._window_button("chrome-close", "Закрыть", self.window.close, "windowClose")
        for b in (self.minimize_button, self.maximize_button, self.close_button):
            controls.addWidget(b)
        layout.addWidget(self.window_controls, 0, QtCore.Qt.AlignVCenter)
        self._drag_pos = None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        sm = get_settings_manager()
        preset = THEMES.get(str(sm.get("theme", "midnight")), THEMES.get("dark", {}))
        border_hex = sm.get("border_color", preset.get("border_color", "#25303C"))
        painter.setPen(QtGui.QColor(border_hex))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def _window_button(self, icon_name, tooltip, handler, object_name):
        button = QtWidgets.QToolButton(self)
        button.setIcon(codicons.codicon_icon(icon_name, 16, "#CCCCCC"))
        button.setIconSize(QtCore.QSize(16, 16))
        button.setToolTip(tooltip)
        button.setObjectName(object_name)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setAutoRaise(True)
        button.setFixedSize(WINDOW_CONTROL_SIZE)
        button.setStyleSheet(
            "QToolButton { border-radius: 0; border: none; background: transparent; }"
            "QToolButton#windowControl:hover { background: #2A2D2E; }"
            "QToolButton#windowClose:hover { background: #E81123; }"
        )
        button.clicked.connect(handler)
        return button

    def _toggle_maximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
            self.maximize_button.setIcon(codicons.codicon_icon("chrome-maximize", 16, "#CCCCCC"))
        else:
            self.window.showMaximized()
            self.maximize_button.setIcon(codicons.codicon_icon("chrome-restore", 16, "#CCCCCC"))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is None or child not in self.findChildren(QtWidgets.QToolButton):
                self._drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton and not self.window.isMaximized():
            self.window.move(event.globalPos() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._toggle_maximize()
            event.accept()
        super().mouseDoubleClickEvent(event)

    def _definitions(self):
        w = self.window
        return {
            "Файл": [
                ("Новый файл", None, w.action_new_file),
                ("Открыть файл…", None, w.action_open_file),
                ("Открыть проект…", None, w.action_open_project),
                ("---", None, None),
                ("Открыть как таблицу…", None, w.action_open_table_file),
                ("Открыть в HEX-просмотрщике…", None, w.action_open_hex_file),
                ("Открыть PDF…", None, w.action_open_pdf_file),
                ("---", None, None),
                ("Сохранить", None, w.action_save_file),
                ("Сохранить как…", None, w.action_save_as_file),
                ("Закрыть редактор", None, w.action_close_file),
                ("Выход", None, w.action_exit),
            ],
            "Правка": [
                ("Отменить", None, w.action_undo),
                ("Повторить", None, w.action_redo),
                ("Вырезать", None, w.action_cut),
                ("Копировать", None, w.action_copy),
                ("Вставить", None, w.action_paste),
                ("Выделить всё", None, w.action_select_all),
            ],
            "Вид": [
                ("Проводник", None, lambda: w.activity_bar.set_activity("explorer")),
                ("Поиск", None, lambda: w.activity_bar.set_activity("search")),
                ("Управление версиями", None, lambda: w.activity_bar.set_activity("git")),
                ("Анализ проекта", None, lambda: w.activity_bar.set_activity("intelligence")),
                ("ИИ-агент", "Ctrl+Shift+I", w.show_ai_agent),
                ("---", None, None),
                ("Архитектурный граф", None, lambda: w.open_graph_editor(None, 'modules')),
                ("Архитектурный паспорт проекта", None, w.open_defense_guide),
                ("Предпросмотр Markdown", "Ctrl+Shift+V", w.action_preview_markdown),
                ("Боковая панель", None, w.toggle_sidebar),
                ("Терминал", "Ctrl+`", w.toggle_terminal),
                ("Разделить редактор", None, w.split_editor),
                ("---", None, None),
                ("Увеличить масштаб интерфейса", "Ctrl+Alt+=", w.action_zoom_interface_in),
                ("Уменьшить масштаб интерфейса", "Ctrl+Alt+-", w.action_zoom_interface_out),
                ("Сбросить масштаб интерфейса (100%)", "Ctrl+Alt+0", w.action_reset_interface_zoom),
            ],
            "Запуск": [
                ("Запустить текущий файл", "F5", w.action_run_file),
                ("Запустить проект", "Ctrl+F5", w.action_run_project),
                ("Запустить выделенный фрагмент кода", "Ctrl+Enter", w.action_run_selected_snippet),
                ("---", None, None),
                ("Объяснить код с помощью ИИ", "Ctrl+Alt+E", w.action_ai_explain_selection),
                ("Применить код из ответа ИИ", None, w.action_ai_apply_code),
            ],
            "Терминал": [
                ("Новый терминал", None, w.new_terminal),
                ("Показать/скрыть терминал", None, w.toggle_terminal),
            ],
            "Git": [
                ("Панель контроля версий", None, lambda: w.activity_bar.set_activity("git")),
                ("Синхронизировать проект (Sync)", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.git_sync())),
                ("Зафиксировать (Commit)…", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.message.setFocus())),
                ("---", None, None),
                ("Отправить изменения (Push)", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.git_push())),
                ("Получить изменения (Pull)", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.git_pull())),
                ("Индексировать все файлы (Stage All)", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.stage_all())),
                ("Снять индексацию (Unstage All)", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel.unstage_all())),
                ("---", None, None),
                ("Создать новую ветку…", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel._create_branch_dialog())),
                ("Капсула изменений (История)", None, w.action_change_capsule),
                ("---", None, None),
                ("Клонировать с GitHub…", None, lambda: getattr(w, "git_panel", None) and w.git_panel.show_clone_dialog()),
                ("Опубликовать проект на GitHub 🚀", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel._publish_to_github())),
                ("Мои репозитории GitHub…", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel._open_user_repos())),
                ("Аккаунт GitHub (Авторизация PAT)…", None, lambda: (w.activity_bar.set_activity("git"), getattr(w, "git_panel", None) and w.git_panel._handle_auth_action())),
                ("Открыть репозиторий на GitHub ↗", None, lambda: getattr(w, "git_panel", None) and w.git_panel.open_github_repo()),
            ],
            "Справка": [
                ("Руководство пользователя (Документация)", None, w.action_open_documentation),
                ("---", None, None),
                ("Палитра команд", None, w.show_command_palette),
                ("Горячие клавиши", None, w.show_keyboard_shortcuts),
                ("GitHub Issues", None, w.action_github_issues),
                ("---", None, None),
                ("Проверить обновления…", None, w.action_check_updates),
                ("Интеграция с проводником…", None, w.action_shell_integration),
                ("---", None, None),
                ("О программе", None, w.action_about),
            ],
        }

    def _make_menu(self, definitions):
        menu = QtWidgets.QMenu(self)
        for item in definitions:
            if item is None or (isinstance(item, (list, tuple)) and item[0] in ("---", "separator")):
                menu.addSeparator()
                continue
            text, shortcut, handler = item
            # Shortcuts are dispatched centrally by ModernMainWindow. Keeping
            # them off popup QMenus avoids the classic PyQt bug where bindings
            # work only while the menu is open.
            action = QtWidgets.QAction(text, menu)
            if handler:
                action.triggered.connect(handler)
            menu.addAction(action)
        return menu

    def set_project(self, name):
        self.project.setText(name or "")

    def on_ui_scale_changed(self, percent: int):
        """Resize the title bar and its fixed-size controls for the UI scale."""
        from app.ui_scale import scale_px
        self.setFixedHeight(scale_px(TITLE_BAR_HEIGHT))
        try:
            self.search_pill.setFixedHeight(scale_px(26))
            self.search_pill.setFixedWidth(scale_px(420))
        except Exception:
            pass
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            button.setFixedSize(scale_px(46), scale_px(30))
            button.setIconSize(QtCore.QSize(scale_px(16), scale_px(16)))


class ExplorerHeader(QtWidgets.QFrame):
    """Header frame with guaranteed continuous 1px bottom border."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("explorerHeader")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        sm = get_settings_manager()
        preset = THEMES.get(str(sm.get("theme", "midnight")), THEMES.get("dark", {}))
        border_hex = sm.get("border_color", preset.get("border_color", "#25303C"))
        painter.setPen(QtGui.QColor(border_hex))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
