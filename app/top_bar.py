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
MENU_SEARCH_SPACING = 16
WINDOW_CONTROL_SIZE = QSize(46, 30)


class OmniSearchPill(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal()

    def __init__(self, base_path: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("omniSearchPill")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(26)
        self.setMinimumWidth(36)
        self.setMaximumWidth(420)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setToolTip("Поиск файлов и команд (Ctrl+P)")
        pill_layout = QtWidgets.QHBoxLayout(self)
        pill_layout.setContentsMargins(6, 0, 8, 0)
        pill_layout.setSpacing(6)

        lens_icon = QtWidgets.QLabel()
        lens_icon.setPixmap(codicons.codicon_icon("search", 16, "#9D9D9D").pixmap(16, 16))
        lens_icon.setFixedSize(16, 16)
        lens_icon.setStyleSheet("background: transparent; border: none;")
        pill_layout.addWidget(lens_icon, 0, QtCore.Qt.AlignVCenter)

        prompt = QtWidgets.QLabel("Поиск файлов и команд")
        prompt.setObjectName("omniSearchPrompt")
        prompt.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        pill_layout.addWidget(prompt, 1, QtCore.Qt.AlignVCenter)
        self._prompt = prompt

    def sizeHint(self):
        return QSize(self.maximumWidth(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._prompt.setVisible(event.size().width() > 150)

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
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(2)
        self.menu_group = QtWidgets.QWidget(self)
        self.menu_group.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        menu_layout = QtWidgets.QHBoxLayout(self.menu_group)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(2)
        layout.addWidget(self.menu_group)

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
        menu_layout.addWidget(brand, 0, QtCore.Qt.AlignVCenter)

        title = QtWidgets.QLabel("PyScribe")
        title.setObjectName("appTitle")
        title.setStyleSheet("background: transparent; border: none; color: #CCCCCC; font-size: 13px;")
        menu_layout.addWidget(title, 0, QtCore.Qt.AlignVCenter)
        menu_layout.addSpacing(10)

        self.menus = {}
        self.menu_strip = QtWidgets.QWidget()
        self.menu_strip.setObjectName("workbenchMenuStrip")
        strip = QtWidgets.QHBoxLayout(self.menu_strip)
        strip.setContentsMargins(0, 0, 0, 0)
        strip.setSpacing(1)
        self.compact_menu = self._menu_button("Меню")
        overflow = QtWidgets.QMenu(self.compact_menu)
        overflow.setObjectName("workbenchPopup")
        self.compact_menu.setMenu(overflow)
        for name, sections in self._definitions().items():
            button = self._menu_button(name)
            menu = self._make_menu(sections)
            menu.setTitle(name)
            button.setMenu(menu)
            self.menus[name.lower()] = menu
            strip.addWidget(button)
            overflow.addMenu(menu)
        menu_layout.addWidget(self.menu_strip)
        menu_layout.addWidget(self.compact_menu)
        self.compact_menu.hide()
        layout.addSpacing(MENU_SEARCH_SPACING)

        self.search_pill = OmniSearchPill(self._base_path, self)
        self.search_pill.clicked.connect(self.window.action_quick_open)
        layout.addStretch()
        layout.addWidget(self.search_pill, 0, QtCore.Qt.AlignVCenter)
        layout.addStretch()
        self.search_balance = QtWidgets.QSpacerItem(0, 0)
        layout.addItem(self.search_balance)
        layout.addSpacing(6)

        # Retain self.project so external callers do not error, but omit from layout
        self.project = QtWidgets.QLabel("")
        self.project.setObjectName("topProject")

        # Native title-bar replacement, right-aligned like VS Code on Windows.
        self.window_controls = QtWidgets.QWidget(self)
        self.window_controls.setObjectName("windowControls")
        self.window_controls.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
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

    @staticmethod
    def _menu_button(label):
        button = QtWidgets.QToolButton()
        button.setObjectName("workbenchMenuButton")
        button.setText(label)
        button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _definitions(self):
        w = self.window

        def activity(key):
            return lambda: w.activity_bar.set_activity(key)

        def git(method):
            def invoke():
                panel = getattr(w, "git_panel", None)
                if panel is None or not w.extension_enabled("git"):
                    return
                w.activity_bar.set_activity("git")
                if method == "commit":
                    panel.message.setFocus()
                else:
                    getattr(panel, method)()
            return invoke

        version_control = (
            ("Рабочая копия", (
                ("Панель Git", None, activity("git")),
                ("Подготовить коммит…", None, git("commit")),
                ("Добавить все файлы в индекс", None, git("stage_all")),
                ("Снять индексацию всех файлов", None, git("unstage_all")),
                ("Создать ветку…", None, git("_create_branch_dialog")),
                ("Капсула изменений", None, w.action_change_capsule),
            )),
            ("Удалённый репозиторий", (
                ("Получить изменения · Pull", None, git("git_pull")),
                ("Отправить изменения · Push", None, git("git_push")),
                ("Синхронизировать проект", None, git("git_sync")),
            )),
            ("GitHub", (
                ("Клонировать репозиторий…", None, git("show_clone_dialog")),
                ("Опубликовать проект…", None, git("_publish_to_github")),
                ("Мои репозитории…", None, git("_open_user_repos")),
                ("Аккаунт GitHub…", None, git("_handle_auth_action")),
                ("Открыть репозиторий на GitHub", None, git("open_github_repo")),
            )),
        )
        return {
            "Файл": (
                ("Создание и открытие", (
                    ("Новый файл", "Ctrl+N", w.action_new_file),
                    ("Открыть файл…", "Ctrl+O", w.action_open_file),
                    ("Быстрый переход к файлу", "Ctrl+P", w.action_quick_open),
                )),
                ("Сохранение и закрытие", (
                    ("Сохранить", "Ctrl+S", w.action_save_file),
                    ("Сохранить как…", "Ctrl+Shift+S", w.action_save_as_file),
                    ("Сохранить все файлы", None, w.action_save_all_files),
                    ("Закрыть вкладку", "Ctrl+W", w.action_close_file),
                    ("Выход", None, w.action_exit),
                )),
            ),
            "Правка": (
                ("История правок", (
                    ("Отменить", "Ctrl+Z", w.action_undo),
                    ("Повторить", "Ctrl+Y", w.action_redo),
                )),
                ("Буфер обмена", (
                    ("Вырезать", "Ctrl+X", w.action_cut),
                    ("Копировать", "Ctrl+C", w.action_copy),
                    ("Вставить", "Ctrl+V", w.action_paste),
                    ("Выделить всё", "Ctrl+A", w.action_select_all),
                )),
                ("Поиск и навигация", (
                    ("Найти в файле", "Ctrl+F", w._trigger_find),
                    ("Заменить в файле", "Ctrl+H", w._trigger_replace),
                    ("Перейти к строке…", "Ctrl+G", w.action_goto_line),
                )),
            ),
            "Проект": (
                ("Рабочая папка", (
                    ("Открыть проект…", "Ctrl+Shift+O", w.action_open_project),
                    ("Настройки проекта…", None, w.action_project_settings),
                    ("Закрыть проект", None, w.action_close_project),
                )),
                ("Анализ и версии", (
                    ("Анализ проекта", None, activity("intelligence")),
                    ("Архитектурный граф", None, lambda: w.open_graph_editor(None, "modules")),
                    ("Архитектурный паспорт", None, w.open_defense_guide),
                    ("Git и GitHub", None, version_control),
                )),
            ),
            "Вид": (
                ("Панели", (
                    ("Проводник", None, activity("explorer")),
                    ("Поиск по проекту", "Ctrl+Shift+F", w._focus_search),
                    ("Показать или скрыть боковую панель", None, w.toggle_sidebar),
                    ("Показать или скрыть терминал", "Ctrl+`", w.toggle_terminal),
                )),
                ("Редактор", (
                    ("Разделить редактор", None, w.split_editor),
                    ("Предпросмотр Markdown", "Ctrl+Shift+V", w.action_preview_markdown),
                )),
                ("Масштаб интерфейса", (
                    ("Увеличить", "Ctrl+Alt+=", w.action_zoom_interface_in),
                    ("Уменьшить", "Ctrl+Alt+−", w.action_zoom_interface_out),
                    ("Сбросить до 100%", "Ctrl+Alt+0", w.action_reset_interface_zoom),
                )),
            ),
            "Запуск": (
                ("Выполнение кода", (
                    ("Запустить текущий файл", "F5", w.action_run_file),
                    ("Запустить проект", "Ctrl+F5", w.action_run_project),
                    ("Запустить выделенный фрагмент", None, w.action_run_selected_snippet),
                )),
                ("Терминал", (("Новый терминал", None, w.new_terminal),)),
            ),
            "Инструменты": (
                ("Рабочая среда", (
                    ("Настройки", None, w.action_open_settings),
                    ("Браузер", None, w.action_open_browser),
                    ("Интеграция с проводником…", None, w.action_shell_integration),
                )),
                ("ИИ-агент", (
                    ("Открыть ИИ-агента", "Ctrl+Shift+I", w.show_ai_agent),
                    ("Объяснить код", "Ctrl+Alt+E", w.action_ai_explain_selection),
                    ("Применить код из ответа", None, w.action_ai_apply_code),
                )),
            ),
            "Справка": (
                ("Документация", (
                    ("Руководство пользователя", "F1", w.action_open_documentation),
                    ("Горячие клавиши", None, w.show_keyboard_shortcuts),
                    ("Палитра команд", "Ctrl+Shift+P", w.show_command_palette),
                )),
                ("О PyScribe", (
                    ("О программе", None, w.action_about),
                    ("Проверить обновления…", None, w.action_check_updates),
                    ("Сообщить о проблеме на GitHub", None, w.action_github_issues),
                    ("Отправить лог…", None, lambda: w.action_send_log()),
                )),
            ),
        }

    def _make_menu(self, sections):
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("workbenchPopup")
        for index, (heading, items) in enumerate(sections):
            if index:
                menu.addSeparator()
            label = QtWidgets.QLabel(heading.upper())
            label.setObjectName("workbenchMenuSection")
            label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            section = QtWidgets.QWidgetAction(menu)
            section.setDefaultWidget(label)
            menu.addAction(section)
            for text, shortcut, handler in items:
                if isinstance(handler, tuple):
                    submenu = self._make_menu(handler)
                    submenu.setTitle(text)
                    menu.addMenu(submenu)
                    continue
                # The suffix is presentation only; bindings live in the
                # workbench and its focused widgets.
                action = QtWidgets.QAction(f"{text}\t{shortcut}" if shortcut else text, menu)
                action.triggered.connect(handler)
                menu.addAction(action)
        return menu

    def _fit_menu_strip(self):
        if not hasattr(self, "window_controls"):
            return
        chrome = self.window_controls.sizeHint().width() + 165 + MENU_SEARCH_SPACING
        compact = self.width() < self.menu_strip.sizeHint().width() + chrome
        self.menu_strip.setVisible(not compact)
        self.compact_menu.setVisible(compact)
        self._center_search()

    def _center_search(self):
        layout = self.layout()
        margins = layout.contentsMargins()
        left = margins.left() + self.menu_group.layout().sizeHint().width() + MENU_SEARCH_SPACING
        right = margins.right() + self.window_controls.sizeHint().width() + 6
        # Balance the unequal side groups only when there is room for the full search field.
        spare = self.width() - left - right - self.search_pill.maximumWidth() - 2 * layout.spacing()
        balance = max(0, min(left - right, spare))
        if balance != self.search_balance.sizeHint().width():
            self.search_balance.changeSize(balance, 0, QtWidgets.QSizePolicy.Fixed)
            layout.invalidate()

    def event(self, event):
        if event.type() == QtCore.QEvent.LayoutRequest and hasattr(self, "window_controls"):
            self._center_search()
        return super().event(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_menu_strip()

    def set_project(self, name):
        self.project.setText(name or "")

    def on_ui_scale_changed(self, percent: int):
        """Resize the title bar and its fixed-size controls for the UI scale."""
        from app.ui_scale import scale_px
        self.setFixedHeight(scale_px(TITLE_BAR_HEIGHT))
        try:
            self.search_pill.setFixedHeight(scale_px(26))
            self.search_pill.setMaximumWidth(scale_px(420))
        except Exception:
            pass
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            button.setFixedSize(scale_px(46), scale_px(30))
            button.setIconSize(QtCore.QSize(scale_px(16), scale_px(16)))
        self._fit_menu_strip()


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
