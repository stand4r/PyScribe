"""Embedded web browser with a private profile and a local start page."""
from pathlib import Path

from design.icons import line_icon
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineView

from core.logging_config import get_logger
from services.browser_settings import BUILTIN_PROFILE_IDS, default_profile, profiles, search_url, user_agent

logger = get_logger("browser")

def address_url(text):
    text = text.strip()
    if not text:
        return QtCore.QUrl()
    host = text.split("/", 1)[0]
    if "://" in text or (" " not in text and ("." in host or host.split(":")[0] == "localhost")):
        return QtCore.QUrl.fromUserInput(text)
    return search_url(text)

class _WebPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        # Web content can load its own embedded resources; top-level
        # navigation is restricted to web URLs.
        return not is_main_frame or url.scheme().lower() in {"https", "http", "about"}


def _web_url(url):
    return url.isValid() and url.scheme().lower() in {"http", "https"} and bool(url.host())


def _search_icon():
    pixmap = QtGui.QPixmap(36, 36)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtGui.QPen(QtGui.QColor("#50616a"), 1.5))
    painter.drawEllipse(QtCore.QRectF(2, 2, 10, 10))
    painter.drawLine(QtCore.QPointF(10.5, 10.5), QtCore.QPointF(16, 16))
    painter.end()
    return QtGui.QIcon(pixmap)


class _StartPage(QtWidgets.QWidget):
    """Paint an offline landscape and lay shortcut tiles over it."""

    def __init__(self, browser, tab):
        super().__init__()
        self.setObjectName("browserHome")
        self.browser = browser
        self.tab = tab
        self._columns = 0
        self.tiles = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        layout.setContentsMargins(20, 12, 20, 18)
        layout.setSpacing(18)
        layout.addStretch(1)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("browserHomeSearch")
        self.search.setPlaceholderText("Поиск в Интернете или адрес сайта")
        self.search.setAccessibleName("Поиск в Интернете")
        self.search.setMaximumWidth(780)
        self.search.setClearButtonEnabled(True)
        self.search.addAction(_search_icon(), QtWidgets.QLineEdit.LeadingPosition)
        self.search.returnPressed.connect(self._search)
        search_row = QtWidgets.QHBoxLayout()
        search_row.addStretch(1)
        search_row.addWidget(self.search, 12)
        search_row.addStretch(1)
        layout.addLayout(search_row)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(8)
        layout.addLayout(self.grid)
        layout.addStretch(4)
        self.update_tiles()

    def _search(self):
        self.browser.navigate(address_url(self.search.text()), self.tab)

    def update_tiles(self):
        for tile in self.tiles:
            self.grid.removeWidget(tile)
            tile.hide()
            tile.deleteLater()
        self.tiles = []
        for index, (title, address) in enumerate(self.browser.shortcuts):
            tile = self._tile(title, title[:2].upper(), address)
            tile.clicked.connect(lambda checked=False, url=address:
                                 self.browser.navigate(QtCore.QUrl(url), self.tab))
            tile.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            tile.customContextMenuRequested.connect(
                lambda pos, button=tile, i=index: self._shortcut_menu(button, i, pos))
        add = self._tile("Добавить", "+", "Добавить ярлык")
        add.clicked.connect(lambda: self.browser.edit_shortcut())
        self._columns = 0
        self._arrange()

    def _tile(self, title, badge, hint):
        tile = QtWidgets.QToolButton(self)
        tile.setObjectName("browserShortcutTile")
        tile.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        tile.setFixedSize(88, 76)
        tile.setText(tile.fontMetrics().elidedText(title, QtCore.Qt.ElideRight, 78))
        tile.setToolTip(title + "\n" + hint if title != hint else title)
        tile.setAccessibleName(title)
        tile.setCursor(QtCore.Qt.PointingHandCursor)
        pixmap = QtGui.QPixmap(88, 88)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#385461" if badge != "+" else "#4b626d"))
        painter.drawRoundedRect(QtCore.QRectF(0, 0, 44, 44), 13, 13)
        painter.setPen(QtGui.QColor("#edf4f7"))
        font = QtGui.QFont(tile.font())
        font.setPixelSize(18)
        painter.setFont(font)
        if badge == "+":
            painter.setPen(QtGui.QPen(QtGui.QColor("#edf4f7"), 1.8,
                                      QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
            painter.drawLine(QtCore.QLineF(15, 22, 29, 22))
            painter.drawLine(QtCore.QLineF(22, 15, 22, 29))
        else:
            painter.drawText(QtCore.QRectF(0, 0, 44, 44), QtCore.Qt.AlignCenter, badge)
        painter.end()
        tile.setIcon(QtGui.QIcon(pixmap))
        tile.setIconSize(QtCore.QSize(44, 44))
        self.tiles.append(tile)
        return tile

    def _shortcut_menu(self, button, index, pos):
        menu = QtWidgets.QMenu(button)
        edit = menu.addAction("Изменить ярлык")
        remove = menu.addAction("Удалить ярлык")
        chosen = menu.exec_(button.mapToGlobal(pos))
        menu.deleteLater()
        if chosen is edit:
            self.browser.edit_shortcut(index=index)
        elif chosen is remove:
            self.browser.remove_shortcut(index)

    def _arrange(self):
        columns = min(len(self.tiles), max(1, (self.width() - 32) // 96))
        if columns == self._columns:
            return
        self._columns = columns
        for tile in self.tiles:
            self.grid.removeWidget(tile)
        for index, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, index // columns, index % columns, QtCore.Qt.AlignHCenter)
            tile.show()
        self.grid.setAlignment(QtCore.Qt.AlignHCenter)
        self.updateGeometry()

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.layout().minimumSize().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#42616b"))
        painter.scale(self.width() / 1000, self.height() / 650)
        painter.setPen(QtCore.Qt.NoPen)

        def layer(color, points):
            painter.setBrush(QtGui.QColor(color))
            painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points]))

        layer("#63838b", [(0,235),(110,202),(220,235),(336,182),(470,256),
                           (593,211),(700,258),(842,198),(1000,233),(1000,650),(0,650)])
        layer("#3b626f", [(0,144),(105,170),(225,245),(335,272),(461,339),
                           (587,363),(717,400),(850,326),(1000,278),(1000,650),(0,650)])
        layer("#294d5c", [(0,249),(110,276),(216,343),(350,389),(523,426),
                           (641,471),(779,420),(883,371),(1000,349),(1000,650),(0,650)])
        layer("#203944", [(0,364),(117,389),(214,452),(375,487),(527,522),
                           (687,520),(843,470),(1000,435),(1000,650),(0,650)])
        layer("#223e4a", [(0,536),(1000,536),(1000,650),(0,650)])
        for y, x1, x2 in [(547,326,765),(562,190,625),(580,480,955),(612,175,880)]:
            painter.setPen(QtGui.QPen(QtGui.QColor("#426571"), 1))
            painter.drawLine(QtCore.QLineF(x1, y, x2, y))
        painter.end()


class _BrowserTab(QtWidgets.QStackedWidget):
    def __init__(self, browser, profile):
        super().__init__(browser)
        self.profile_settings = profile
        self.view = None
        self.progress = 100
        self.web_error = ""
        self.home = _StartPage(browser, self)
        self.home_scroll = QtWidgets.QScrollArea()
        self.home_scroll.setObjectName("browserHomeScroll")
        self.home_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.home_scroll.setWidgetResizable(True)
        self.home_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.home_scroll.setWidget(self.home)
        self.addWidget(self.home_scroll)

    def showing_web(self):
        return self.view is not None and self.currentWidget() is self.view


class WebBrowserWidget(QtWidgets.QWidget):
    DEFAULT_SHORTCUTS = [
        ("Python", "https://docs.python.org/3/"),
        ("GitHub", "https://github.com/"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workbenchBrowser")
        self.setProperty("pyscribeSpecial", "browser")
        self.shortcuts = self._load_shortcuts()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(5)
        layout.addLayout(row)

        self.back = self._nav_button(row, "back", "Назад", lambda: self._web_action("back"))
        self.forward = self._nav_button(row, "forward", "Вперёд", lambda: self._web_action("forward"))
        self.refresh = self._nav_button(row, "reload", "Обновить", lambda: self._web_action("reload"))
        self._nav_button(row, "home", "Стартовая страница", self.show_home)
        self.address = QtWidgets.QLineEdit()
        self.address.setObjectName("browserAddress")
        self.address.setPlaceholderText("Адрес или поисковый запрос")
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(lambda: self.navigate(address_url(self.address.text())))
        row.addWidget(self.address, 1)
        self._nav_button(row, "bookmark", "Добавить текущий сайт в ярлыки", self._pin_page)
        self._nav_button(row, "external", "Открыть в системном браузере", self._open_external)
        self.profile_button = QtWidgets.QToolButton()
        self.profile_button.setObjectName("browserProfile")
        self.profile_button.setAccessibleName("Профиль браузера")
        self.profile_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.profile_button.setIconSize(QtCore.QSize(20, 20))
        self.profile_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.profile_button.setMaximumWidth(154)
        self._profile_icon_mode = None
        row.addWidget(self.profile_button)
        self.profile_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.profile_menu = QtWidgets.QMenu(self.profile_button)
        self.profile_menu.setObjectName("browserProfileMenu")
        self.profile_menu.aboutToShow.connect(self._refresh_profile_menu)
        self.profile_button.setMenu(self.profile_menu)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.web_error = QtWidgets.QLabel()
        self.web_error.setWordWrap(True)
        self.web_error.hide()
        layout.addWidget(self.web_error)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        # Pages in the stack are destroyed before the profiles owned here.
        self._profiles = {}

        footer = QtWidgets.QHBoxLayout()
        footer.setSpacing(6)
        self.tabs = QtWidgets.QTabBar()
        self.tabs.setObjectName("browserTabs")
        self.tabs.setShape(QtWidgets.QTabBar.RoundedSouth)
        self.tabs.setTabsClosable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(QtCore.Qt.ElideRight)
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._select_tab)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        footer.addWidget(self.tabs, 1)
        self._nav_button(footer, "add", "Новая вкладка (Ctrl+T)", lambda: self.new_tab())
        layout.addLayout(footer)

        for sequence, action in (("Ctrl+L", self.focus_address), ("Ctrl+T", self.new_tab)):
            shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
        self.new_tab()

    @staticmethod
    def _button(layout, text, label, callback):
        button = QtWidgets.QToolButton()
        button.setObjectName("browserAction")
        button.setText(text)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _nav_button(self, layout, icon_name, label, callback):
        button = self._button(layout, "", label, callback)
        button.setObjectName("browserNav")
        button.setIcon(line_icon(icon_name, button.palette().buttonText().color()))
        button.setIconSize(QtCore.QSize(20, 20))
        return button

    def _refresh_profile_menu(self):
        self.profile_menu.clear()
        current = self.stack.currentWidget()
        color = self.profile_button.palette().buttonText().color()
        self.profile_menu.addSection("Режим просмотра")
        has_custom_section = False
        for profile in profiles():
            built_in = profile["id"] in BUILTIN_PROFILE_IDS
            if not built_in and not has_custom_section:
                self.profile_menu.addSection("Мои профили")
                has_custom_section = True
            label = profile["name"]
            if not built_in:
                label += " · Обычный" if profile["persistent"] else " · Приватный"
            icon = line_icon("profile" if profile["persistent"] else "private", color)
            action = self.profile_menu.addAction(icon, label)
            action.setCheckable(True)
            action.setChecked(bool(current and current.profile_settings["id"] == profile["id"]))
            action.triggered.connect(lambda checked=False, value=profile: self._select_profile(value))

    def _select_profile(self, profile):
        tab = self.stack.currentWidget()
        if tab is not None and tab.profile_settings == profile:
            return
        if tab is not None and tab.view is None:
            tab.profile_settings = profile
            self._sync_navigation()
        else:
            self.new_tab(profile)

    def _profile_for_tab(self, tab):
        # An existing page keeps its storage mode and session until closed.
        settings = tab.profile_settings
        current = next((profile for profile in profiles() if profile["id"] == settings["id"]), None)
        key = (settings["id"], settings["persistent"])
        entry = self._profiles.get(key)
        if entry is None:
            if settings["persistent"]:
                profile = QWebEngineProfile(settings["id"], self)
                base = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.GenericDataLocation)
                path = Path(base) / "PyScribe" / "browser" / settings["id"]
                profile.setPersistentStoragePath(str(path / "storage"))
                profile.setCachePath(str(path / "cache"))
                profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
            else:
                profile = QWebEngineProfile(self)
            entry = profile, profile.httpUserAgent()
            self._profiles[key] = entry
        profile, native = entry
        agent = user_agent(current or settings, native)
        if profile.httpUserAgent() != agent:
            profile.setHttpUserAgent(agent)
        return profile

    @staticmethod
    def _load_shortcuts():
        from utils.settings_manager import get_settings_manager
        try:
            value = get_settings_manager().get_setting("browser_shortcuts", None)
        except RuntimeError:
            value = None
        if not isinstance(value, list):
            return list(WebBrowserWidget.DEFAULT_SHORTCUTS)
        return [(item[0], item[1]) for item in value[:60]
                if isinstance(item, (list, tuple)) and len(item) == 2
                and all(isinstance(part, str) for part in item)
                and item[0].strip() and _web_url(QtCore.QUrl(item[1]))]

    def _save_shortcuts(self):
        from utils.settings_manager import get_settings_manager
        try:
            manager = get_settings_manager()
            manager.settings["browser_shortcuts"] = self.shortcuts
            saved = manager.save_settings()
        except RuntimeError:
            saved = False
        for index in range(self.stack.count()):
            self.stack.widget(index).home.update_tiles()
        if not saved:
            QtWidgets.QMessageBox.warning(self, "Ярлыки", "Не удалось записать ярлыки в настройки.")

    def edit_shortcut(self, index=None, title="", address=""):
        if index is not None:
            title, address = self.shortcuts[index]
        elif len(self.shortcuts) >= 60:
            QtWidgets.QMessageBox.information(self, "Ярлыки", "Можно сохранить до 60 ярлыков.")
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Ярлык сайта")
        form = QtWidgets.QFormLayout(dialog)
        name = QtWidgets.QLineEdit(title)
        field = QtWidgets.QLineEdit(address)
        field.setPlaceholderText("https://example.com")
        form.addRow("Название", name)
        form.addRow("Адрес", field)
        error = QtWidgets.QLabel()
        error.setWordWrap(True)
        form.addRow(error)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Сохранить")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Отмена")
        form.addRow(buttons)

        def accept():
            raw = field.text().strip()
            url = QtCore.QUrl.fromUserInput(raw) if raw else QtCore.QUrl()
            if not _web_url(url):
                error.setText("Укажите адрес сайта HTTP или HTTPS.")
                return
            pair = (name.text().strip() or url.host(), url.toString(QtCore.QUrl.RemovePassword))
            if index is None:
                self.shortcuts.append(pair)
            else:
                self.shortcuts[index] = pair
            self._save_shortcuts()
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        dialog.resize(420, 0)
        dialog.exec_()
        dialog.deleteLater()

    def remove_shortcut(self, index):
        del self.shortcuts[index]
        self._save_shortcuts()

    def _pin_page(self):
        tab = self.stack.currentWidget()
        if tab and tab.showing_web() and _web_url(tab.view.url()):
            self.edit_shortcut(title=tab.view.title(), address=tab.view.url().toDisplayString(QtCore.QUrl.RemovePassword))
        else:
            self.edit_shortcut()

    def new_tab(self, profile=None):
        if profile is None:
            current = self.stack.currentWidget()
            key = current.profile_settings["id"] if current is not None else None
            profile = next((value for value in profiles() if value["id"] == key), None)
        tab = _BrowserTab(self, profile or default_profile())
        self.stack.addWidget(tab)
        with QtCore.QSignalBlocker(self.tabs):
            index = self.tabs.addTab("Новая вкладка")
            self.tabs.setTabData(index, tab)
            self.tabs.setCurrentIndex(index)
        self._select_tab(index)
        tab.home.search.setFocus()

    def _select_tab(self, index):
        tab = self.tabs.tabData(index)
        if tab is not None:
            self.stack.setCurrentWidget(tab)
        self._sync_navigation(force_address=True)

    def _close_tab(self, index):
        tab = self.tabs.tabData(index)
        self.tabs.removeTab(index)
        if tab is not None:
            self.stack.removeWidget(tab)
            tab.deleteLater()
        if not self.tabs.count():
            self.new_tab()

    def _tab_index(self, tab):
        return next((i for i in range(self.tabs.count()) if self.tabs.tabData(i) is tab), -1)

    def _create_view(self, tab):
        profile = self._profile_for_tab(tab)
        view = QWebEngineView(tab)
        page = _WebPage(profile, view)
        view.setPage(page)
        page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, False)
        page.featurePermissionRequested.connect(
            lambda origin, feature: page.setFeaturePermission(origin, feature, QWebEnginePage.PermissionDeniedByUser))
        tab.view = view
        tab.addWidget(view)
        view.titleChanged.connect(lambda title: self._title_changed(tab, title))
        view.iconChanged.connect(lambda icon: self.tabs.setTabIcon(self._tab_index(tab), icon)
                                 if self._tab_index(tab) >= 0 else None)
        view.urlChanged.connect(lambda _url: self._sync_navigation() if self.stack.currentWidget() is tab else None)
        view.loadStarted.connect(lambda: self._load_started(tab))
        view.loadProgress.connect(lambda value: self._set_progress(tab, value))
        view.loadFinished.connect(lambda _ok: self._set_progress(tab, 100))
        view.renderProcessTerminated.connect(lambda status, code: self._renderer_stopped(tab, status, code))

    def _load_started(self, tab):
        tab.web_error = ""
        self._set_progress(tab, 0)

    def _renderer_stopped(self, tab, status, code):
        logger.error("WebEngine renderer stopped (status=%s, exit=%s)", status, code)
        tab.web_error = "Процесс браузера остановился. Обновите страницу или откройте её в системном браузере."
        self._set_progress(tab, 100)

    def _title_changed(self, tab, title):
        index = self._tab_index(tab)
        if index >= 0 and tab.showing_web():
            self.tabs.setTabText(index, title or tab.view.url().host() or "Страница")
            self.tabs.setTabToolTip(index, title)

    def _set_progress(self, tab, value):
        tab.progress = value
        if self.stack.currentWidget() is tab:
            self._sync_navigation()

    def focus_entry(self):
        tab = self.stack.currentWidget()
        if tab and not tab.showing_web():
            tab.home.search.setFocus()
        else:
            self.focus_address()

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def show_home(self):
        tab = self.stack.currentWidget()
        if tab is None:
            return
        tab.web_error = ""
        tab.setCurrentWidget(tab.home_scroll)
        index = self._tab_index(tab)
        self.tabs.setTabText(index, "Новая вкладка")
        self.tabs.setTabToolTip(index, "")
        self.tabs.setTabIcon(index, QtGui.QIcon())
        self._sync_navigation()
        tab.home.search.setFocus()

    def navigate(self, url, tab=None):
        if _web_url(url):
            tab = tab or self.stack.currentWidget()
            try:
                if tab.view is None:
                    self._create_view(tab)
                else:
                    self._profile_for_tab(tab)
            except (OSError, RuntimeError):
                logger.exception("WebEngine page initialization failed")
                tab.web_error = "Не удалось запустить страницу. Подробности записаны в журнал PyScribe."
                self._set_progress(tab, 100)
                return
            tab.setCurrentWidget(tab.view)
            self._title_changed(tab, url.host())
            tab.view.load(url)
            if self.stack.currentWidget() is tab:
                tab.view.setFocus()
        elif not url.isEmpty():
            QtWidgets.QToolTip.showText(self.address.mapToGlobal(self.address.rect().bottomLeft()),
                                        "Введите адрес HTTP или HTTPS.")

    def _sync_navigation(self, force_address=False):
        tab = self.stack.currentWidget()
        view = tab.view if tab and tab.showing_web() else None
        self.web_error.setText(tab.web_error if tab else "")
        self.web_error.setVisible(bool(self.web_error.text()))
        self.back.setEnabled(bool(view and view.history().canGoBack()))
        self.forward.setEnabled(bool(view and view.history().canGoForward()))
        self.refresh.setEnabled(view is not None)
        if tab is not None:
            name = tab.profile_settings["name"]
            self.profile_button.setText(self.profile_button.fontMetrics().elidedText(
                name, QtCore.Qt.ElideRight, 102))
            persistent = tab.profile_settings["persistent"]
            icon_mode = "profile" if persistent else "private"
            if icon_mode != self._profile_icon_mode:
                self._profile_icon_mode = icon_mode
                self.profile_button.setIcon(line_icon(icon_mode, self.profile_button.palette().buttonText().color()))
            summary = "Данные сайтов сохраняются" if persistent else "Данные сайтов хранятся в памяти"
            self.profile_button.setToolTip(f"{name} · {summary}")
        if view is not None:
            if force_address or not self.address.hasFocus():
                self.address.setText(view.url().toDisplayString(QtCore.QUrl.RemovePassword))
            self.progress.setValue(tab.progress)
            self.progress.setVisible(tab.progress < 100)
        else:
            self.address.clear()
            self.progress.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "profile_button"):
            style = (QtCore.Qt.ToolButtonIconOnly if event.size().width() < 460
                     else QtCore.Qt.ToolButtonTextBesideIcon)
            self.profile_button.setToolButtonStyle(style)

    def _web_action(self, action):
        tab = self.stack.currentWidget()
        if tab and tab.showing_web():
            self._profile_for_tab(tab)
            getattr(tab.view, action)()

    def _open_external(self):
        tab = self.stack.currentWidget()
        if tab and tab.showing_web() and _web_url(tab.view.url()):
            QtGui.QDesktopServices.openUrl(tab.view.url())
