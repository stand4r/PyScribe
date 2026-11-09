"""Run short blocking jobs away from the GUI thread.

Qt advances *every* animation from the GUI thread's event loop, so each
millisecond spent there on file-system scans or ``git`` queries is a
millisecond in which the whole workbench visibly freezes. Small one-shot jobs
(file walks, subprocess queries) are therefore pushed to the global thread pool
and their result is delivered back on the GUI thread.

Public API
----------
``run_async(fn, on_done=..., on_error=...)``   run *fn* off the GUI thread
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt5 import QtCore

__all__ = ["run_async"]

# Keep the Python wrappers alive while the pool owns the C++ runnable.
_ACTIVE: set = set()


class _TaskSignals(QtCore.QObject):
    """Lives on the GUI thread; the worker only emits through it."""

    finished = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)


class _Task(QtCore.QRunnable):
    def __init__(self, fn: Callable, signals: _TaskSignals):
        super().__init__()
        self._fn = fn
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            try:
                self._signals.failed.emit(str(exc))
            except RuntimeError:
                # The application may be shutting down already.
                pass
            return
        try:
            self._signals.finished.emit(result)
        except RuntimeError:
            pass


def run_async(fn: Callable, on_done: Optional[Callable] = None,
              on_error: Optional[Callable] = None,
              parent: Optional[QtCore.QObject] = None) -> _TaskSignals:
    """Execute *fn* on the global thread pool.

    *on_done* receives the return value, *on_error* receives an error message;
    both are called on the GUI thread.
    """
    signals = _TaskSignals(parent)
    task = _Task(fn, signals)
    _ACTIVE.add(signals)
    _ACTIVE.add(task)

    def _finish(callback, payload):
        _ACTIVE.discard(signals)
        _ACTIVE.discard(task)
        if callback is None:
            return
        try:
            callback(payload)
        except RuntimeError:
            pass

    signals.finished.connect(lambda result: _finish(on_done, result))
    signals.failed.connect(lambda message: _finish(on_error, message))
    QtCore.QThreadPool.globalInstance().start(task)
    return signals
