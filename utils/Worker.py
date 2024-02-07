from PyQt5.QtCore import QObject, QThread, pyqtSignal


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, func):
        super().__init__()
        self.func = func

    def run(self):
        result = self.func()
        self.finished.emit(result)


class RunInThread:
    def __init__(self, func):
        self._func = func
        self._thread = QThread()
        self._worker = _Worker(self._func)
        self._worker.moveToThread(self._thread)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_function_finished)

        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_function_finished(result):
        return result
