"""Local audit log of user interactions, without recording input content."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5 import QtCore, QtWidgets

_logger = logging.getLogger("pyscribe-user-actions")
_logger.propagate = False


def record_action(action: str):
    """Record a fixed action name without user data."""
    if _logger.handlers:
        _logger.info("%s", action)


class _InteractionLog(QtCore.QObject):
    _discrete = {
        QtCore.QEvent.MouseButtonRelease: "mouse_click",
        QtCore.QEvent.MouseButtonDblClick: "mouse_double_click",
        QtCore.QEvent.Shortcut: "shortcut",
        QtCore.QEvent.Drop: "drop",
        QtCore.QEvent.TouchEnd: "touch_end",
    }
    _batched = {
        QtCore.QEvent.KeyPress: "keyboard_input",
        QtCore.QEvent.InputMethod: "input_method",
        QtCore.QEvent.Wheel: "scroll",
    }

    def __init__(self, app):
        super().__init__(app)
        self.pending = {}
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(750)
        self.timer.timeout.connect(self.flush)

    def flush(self):
        self.timer.stop()
        for (action, target), count in self.pending.items():
            _logger.info("%s | widget=%s | count=%d", action, target, count)
        self.pending.clear()

    def eventFilter(self, watched, event):
        kind = event.type()
        action = self._discrete.get(kind) or self._batched.get(kind)
        if action is None or not isinstance(watched, (QtWidgets.QWidget, QtWidgets.QShortcut)):
            return False
        if not event.spontaneous() and kind != QtCore.QEvent.Shortcut:
            return False
        target = type(watched).__name__
        if kind in self._batched:
            key = (action, target)
            self.pending[key] = self.pending.get(key, 0) + 1
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.flush()
            _logger.info("%s | widget=%s", action, target)
        return False

    def close(self):
        self.flush()
        record_action("session_end")


def install_activity_log(app, base_path: Path):
    """Write a rotating log in the project or the installed user's data folder."""
    from core.logging_config import log_directory

    path = log_directory(base_path) / "user-actions.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    except OSError:
        from core.logging_config import get_logger

        get_logger("activity").exception("Не удалось открыть журнал действий")
        return
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    audit = _InteractionLog(app)
    app.installEventFilter(audit)
    app._pyscribe_activity_log = audit
    app.aboutToQuit.connect(audit.close)
    record_action("session_start")
