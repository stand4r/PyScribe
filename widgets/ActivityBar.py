"""PyScribe widgets/ActivityBar.py: VS Code-style vertical activity bar.

Metrics intentionally mirror VS Code:

* the bar is a flat 48px column (no rounded pill buttons),
* every item is a 48x48 hit-area holding a 24px monochrome codicon,
* the active item is drawn with a 2px accent stripe on the left edge,
* inactive icons are muted (#868686) and become white on hover.
"""
from PyQt5 import QtCore, QtGui, QtWidgets

from design import icons as codicons

ACTIVITY_BAR_WIDTH = 48
ITEM_SIZE = 48
ITEM_SIZE_DEFAULT = ITEM_SIZE
ICON_SIZE = 24
ICON_SIZE_DEFAULT = ICON_SIZE


class _ActivityIndicator(QtWidgets.QWidget):
    """2px accent stripe drawn on the left edge of the active item."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._accent = QtGui.QColor("#0078D4")
        self._progress = 0.0
        self._anim = None

    def set_accent(self, color: str):
        self._accent = QtGui.QColor(color)
        self.update()

    @QtCore.pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = float(value)
        self.update()

    def animate_to(self, target_rect: QtCore.QRect):
        """Slide the indicator to *target_rect* (bar-local coordinates)."""
        for motion in self.findChildren(QtCore.QParallelAnimationGroup):
            motion.stop()
        start = self.geometry()
        if start == target_rect and self.isVisible():
            return
        if not self.isVisible() and start.isEmpty():
            self.setGeometry(target_rect.left(), target_rect.top(), 2, target_rect.height())
            self._progress = 1.0
            self.show()
            self.raise_()
            self.update()
            return
        self.show()
        self.raise_()
        from widgets.animations import DURATION
        group = QtCore.QParallelAnimationGroup(self)
        for prop, a, b in ((b"geometry", start, target_rect),):
            anim = QtCore.QPropertyAnimation(self, prop, group)
            anim.setDuration(DURATION["fast"])
            anim.setStartValue(a)
            anim.setEndValue(b)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        fade = QtCore.QPropertyAnimation(self, b"progress", group)
        fade.setDuration(DURATION["fast"])
        fade.setStartValue(min(1.0, 0.55 + self._progress * 0.45))
        fade.setEndValue(1.0)
        group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def hide_indicator(self):
        self.hide()

    def paintEvent(self, event):
        if self._progress <= 0:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        color = QtGui.QColor(self._accent)
        color.setAlphaF(max(0.0, min(1.0, self._progress)))
        painter.fillRect(self.rect(), color)
        painter.end()


class ActivityBar(QtWidgets.QFrame):
    """VS Code-like vertical activity bar with independent states for panels,
    terminal and settings."""

    activity_changed = QtCore.pyqtSignal(str)
    terminal_requested = QtCore.pyqtSignal()
    browser_requested = QtCore.pyqtSignal()

    ITEMS = [
        ("explorer", "files", "Проводник (Ctrl+Shift+E)"),
        ("search", "search", "Поиск (Ctrl+Shift+F)"),
        ("git", "source-control", "Управление версиями"),
        ("todo", "circle-check", "Задачи проекта (Ctrl+Shift+T)"),
        ("run", "run", "Запуск и отладка"),
        ("intelligence", "intelligence", "Анализ проекта"),
        ("ai", "ai-agent", "ИИ-агент (Ctrl+Shift+I)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("activityBar")
        self.setFixedWidth(ACTIVITY_BAR_WIDTH)
        self.buttons = {}
        self.active_sidebar_key = None
        self.terminal_active = False
        self.settings_active = False
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for key, icon_name, tooltip in self.ITEMS:
            button = self._button(icon_name, tooltip)
            button.clicked.connect(lambda checked=False, k=key: self._activate_or_toggle(k))
            layout.addWidget(button, 0, QtCore.Qt.AlignHCenter)
            self.buttons[key] = button

        self.browser_button = self._button("browser-globe", "Браузер")
        self.browser_button.clicked.connect(self.browser_requested)
        layout.addWidget(self.browser_button, 0, QtCore.Qt.AlignHCenter)

        layout.addStretch(1)

        self.terminal_button = self._button("terminal", "Терминал (Ctrl+`)")
        self.terminal_button.clicked.connect(self.terminal_requested)
        layout.addWidget(self.terminal_button, 0, QtCore.Qt.AlignHCenter)

        self.settings_button = self._button("settings-gear", "Управление настройками")
        self.settings_button.clicked.connect(lambda: self._activate_special("settings"))
        layout.addWidget(self.settings_button, 0, QtCore.Qt.AlignHCenter)

        self._indicator = _ActivityIndicator(self)
        self._indicator.hide()
        # Signals for hover repaint needed by _set_hover are per-button.

    def _button(self, icon_name, tooltip):
        button = QtWidgets.QToolButton(self)
        button.setIcon(self._icon_for(icon_name, "#868686"))
        button.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        button.setToolTip(tooltip)
        button.setFixedSize(ITEM_SIZE, ITEM_SIZE)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setObjectName("activityAction")
        button.setProperty("iconName", icon_name)
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setFocusPolicy(QtCore.Qt.TabFocus)
        # Per-widget rule so the application QSS cannot tint the pixmap icon.
        button.setStyleSheet(
            "QToolButton#activityAction { background: transparent; border: 0; padding: 0; }"
            "QToolButton#activityAction:hover { background: transparent; border: 0; }"
            "QToolButton#activityAction:checked { background: transparent; border: 0; }"
        )
        button.installEventFilter(self)
        return button

    def eventFilter(self, watched, event):
        if isinstance(watched, QtWidgets.QToolButton) and watched.property("iconName"):
            if event.type() == QtCore.QEvent.Enter:
                self._set_hover(watched, True)
            elif event.type() == QtCore.QEvent.Leave:
                self._set_hover(watched, False)
        return super().eventFilter(watched, event)

    def _icon_for(self, name: str, color: str, size: int = None):
        """Build the right icon for an activity item (the AI item is vector)."""
        size = size or ICON_SIZE
        if name == "ai-agent":
            return codicons.ai_icon(size, color)
        if name == "circle-check":
            return codicons.line_icon(name, color)
        if name == "browser-globe":
            pixmap = QtGui.QPixmap(size * 2, size * 2)
            pixmap.setDevicePixelRatio(2)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 1.35))
            inset = size * 0.16
            circle = QtCore.QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
            painter.drawEllipse(circle)
            painter.drawEllipse(QtCore.QRectF(size * 0.36, inset, size * 0.28, circle.height()))
            painter.drawLine(QtCore.QLineF(circle.left(), size / 2, circle.right(), size / 2))
            painter.end()
            return QtGui.QIcon(pixmap)
        return codicons.codicon_icon(name, size, color)

    def _set_hover(self, button, hovering: bool):
        """VS Code behaviour: inactive icons are muted, they turn white on hover."""
        if button is None:
            return
        name = button.property("iconName")
        active = button.isChecked()
        color = "#FFFFFF" if (active or hovering) else "#868686"
        try:
            button.setIcon(self._icon_for(name, color))
        except Exception:
            pass

    def _update_button_visual(self, button, active: bool):
        if not button:
            return
        button.setChecked(active)
        icon_name = button.property("iconName")
        if not icon_name:
            return
        color = "#FFFFFF" if active else "#868686"
        button.setIcon(self._icon_for(icon_name, color))

    def _move_indicator(self, button):
        if button is None or not button.isVisible():
            self._indicator.hide_indicator()
            return
        rect = QtCore.QRect(0, button.y(), 2, button.height())
        self._indicator.animate_to(rect)

    def set_sidebar_active(self, key):
        self.active_sidebar_key = key
        for name, button in self.buttons.items():
            self._update_button_visual(button, name == key)
        if key in self.buttons:
            self._move_indicator(self.buttons[key])
        elif not self.terminal_active and not self.settings_active:
            self._indicator.hide_indicator()

    def set_terminal_active(self, active: bool):
        self.terminal_active = bool(active)
        self._update_button_visual(getattr(self, "terminal_button", None), self.terminal_active)
        self._indicator.set_accent("#0078D4")
        if self.terminal_active:
            # Terminal / settings indicators use the bottom status-edge colour.
            self._move_indicator(self.terminal_button)
        elif self.settings_active:
            self._move_indicator(self.settings_button)
        elif self.active_sidebar_key in self.buttons:
            self._move_indicator(self.buttons[self.active_sidebar_key])
        else:
            self._indicator.hide_indicator()

    def set_settings_active(self, active: bool):
        self.settings_active = bool(active)
        self._update_button_visual(getattr(self, "settings_button", None), self.settings_active)
        if self.settings_active:
            self._move_indicator(self.settings_button)
        elif self.terminal_active:
            self._move_indicator(self.terminal_button)
        elif self.active_sidebar_key in self.buttons:
            self._move_indicator(self.buttons[self.active_sidebar_key])
        else:
            self._indicator.hide_indicator()

    def set_badge(self, key: str, count: int, color: str = "#0078D4"):
        """Show or hide a badge counter on an activity bar button."""
        button = self.buttons.get(key)
        if not button:
            return
        badge = getattr(button, "_badge_label", None)
        if count <= 0:
            if badge:
                badge.hide()
            return

        if not badge:
            badge = QtWidgets.QLabel(button)
            badge.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            badge.setAlignment(QtCore.Qt.AlignCenter)
            button._badge_label = badge

        text = str(count) if count <= 99 else "99+"
        badge.setText(text)
        badge.setStyleSheet(
            f"background-color: {color}; color: #FFFFFF; font-size: 9px; font-weight: bold; "
            f"border-radius: 7px; min-width: 14px; max-height: 14px; padding: 0 3px;"
        )
        badge.adjustSize()
        w = max(14, badge.width())
        badge.setGeometry(button.width() - w - 2, 2, w, 14)
        badge.show()

    @property
    def active_key(self):
        return self.active_sidebar_key

    @active_key.setter
    def active_key(self, value):
        self.active_sidebar_key = value

    def _activate_special(self, key):
        if key == "settings":
            self.activity_changed.emit("settings")
        elif key == "terminal":
            self.terminal_requested.emit()

    def _activate_or_toggle(self, key):
        if self.active_sidebar_key == key:
            self.set_sidebar_active(None)
            self.activity_changed.emit("toggle_sidebar")
            return
        self.set_sidebar_active(key)
        self.activity_changed.emit(key)

    def set_active_visual(self, key):
        if key == "terminal":
            self.set_terminal_active(True)
        elif key == "settings":
            self.set_settings_active(True)
        else:
            self.set_sidebar_active(key)

    def sync_special_state(self, terminal_visible=False, settings_open=False, browser_open=None):
        self.set_terminal_active(terminal_visible)
        self.set_settings_active(settings_open)
        if browser_open is not None:
            self._update_button_visual(self.browser_button, browser_open)

    def set_activity(self, key):
        if key in self.buttons and self.buttons[key].isHidden():
            return
        if key == "settings":
            self._activate_special("settings")
        elif key == "terminal":
            self._activate_special("terminal")
        else:
            self.set_sidebar_active(key)
            self.activity_changed.emit(key)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_sidebar_key in self.buttons:
            self._move_indicator(self.buttons[self.active_sidebar_key])

    def on_ui_scale_changed(self, percent: int):
        """Re-render icons and resize hit areas for the global UI scale."""
        factor = max(0.5, min(2.5, percent / 100.0))
        self.setFixedWidth(max(36, int(round(ACTIVITY_BAR_WIDTH * factor))))
        item = max(32, int(round(ITEM_SIZE_DEFAULT * factor)))
        icon = max(16, int(round(ICON_SIZE_DEFAULT * factor)))
        for button in list(self.buttons.values()) + [self.browser_button, self.terminal_button, self.settings_button]:
            button.setFixedSize(item, item)
            button.setIconSize(QtCore.QSize(icon, icon))
            name = button.property("iconName")
            active = button.isChecked()
            button.setIcon(self._icon_for(name, "#FFFFFF" if active else "#868686", icon))
        if self.active_sidebar_key in self.buttons:
            self._move_indicator(self.buttons[self.active_sidebar_key])
