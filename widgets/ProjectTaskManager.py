"""Process and thread usage for launches belonging to the active project."""
import time

import psutil
from PyQt5 import QtCore, QtWidgets


class ProcessSnapshot(QtCore.QThread):
    ready = QtCore.pyqtSignal(object)

    def __init__(self, roots, previous, parent=None):
        super().__init__(parent)
        self.roots = roots
        self.previous = previous

    def run(self):
        now = time.monotonic()
        rows, samples, processes = [], {}, {}
        for pid in self.roots:
            try:
                root = psutil.Process(pid)
                processes[pid] = root
                for child in root.children(recursive=True):
                    processes[child.pid] = child
            except (psutil.Error, OSError):
                continue
        cores = psutil.cpu_count() or 1

        def usage(key, seconds):
            samples[key] = (now, seconds)
            before = self.previous.get(key)
            if before is None or now <= before[0]:
                return None
            return max(0.0, (seconds - before[1]) / (now - before[0]) * 100 / cores)

        for pid, process in processes.items():
            try:
                with process.oneshot():
                    born = process.create_time()
                    key = (pid, born)
                    cpu = process.cpu_times()
                    row = dict(key=key, pid=pid, parent=process.ppid(), name=process.name(),
                               status=process.status(), memory=process.memory_info().rss,
                               cpu=usage(key, cpu.user + cpu.system), threads=[])
                for thread in process.threads():
                    row["threads"].append((thread.id, usage(
                        (pid, born, thread.id), thread.user_time + thread.system_time)))
                rows.append(row)
            except (psutil.Error, OSError):
                continue
        self.ready.emit((rows, samples))


class ProjectTaskManager(QtWidgets.QWidget):
    def __init__(self, terminal, parent=None):
        super().__init__(parent)
        self.terminal = terminal
        self.worker = None
        self.previous = {}
        self.session = None
        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Процесс / поток", "PID / TID", "CPU", "RAM", "Потоки", "Состояние"])
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 270)
        self.tree.setToolTip("CPU — доля общей мощности компьютера. RAM — рабочая память процесса. "
                             "Потоки используют общую память процесса.")
        layout.addWidget(self.tree)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self):
        session = self.terminal._session_key
        if session != self.session:
            self.session = session
            self.previous = {}
            self.tree.clear()
        if not session:
            self.summary.setText("Откройте проект, чтобы видеть его процессы.")
            self.tree.clear()
            return
        if self.worker is not None:
            return
        roots = []
        for tab in self.terminal.tabs.values():
            for process in (tab.process, getattr(tab, "_run_process", None)):
                if process is not None and process.state() != QtCore.QProcess.NotRunning:
                    pid = int(process.processId())
                    if pid:
                        roots.append(pid)
        self.summary.setText("Процессы терминалов и запусков проекта · " + session)
        # The application owns an in-flight query so closing the panel cannot destroy a running thread.
        worker = ProcessSnapshot(roots, self.previous, QtWidgets.QApplication.instance())
        worker.project_session = session
        self.worker = worker
        worker.ready.connect(self.accept_snapshot)
        worker.finished.connect(self.query_finished)
        worker.finished.connect(worker.deleteLater)
        QtWidgets.QApplication.instance().aboutToQuit.connect(worker.wait)
        worker.start()

    def query_finished(self):
        self.worker = None

    @staticmethod
    def cpu_text(value):
        return "…" if value is None else f"{value:.1f}%"

    def accept_snapshot(self, result):
        session = self.sender().project_session
        if session != self.terminal._session_key:
            return
        rows, self.previous = result
        expanded = set()
        selected = self.tree.currentItem()
        selected_key = selected.data(0, QtCore.Qt.UserRole) if selected else None
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                expanded.add(item.data(0, QtCore.Qt.UserRole))
            iterator += 1
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        items = {}
        for row in rows:
            item = QtWidgets.QTreeWidgetItem([
                row["name"], str(row["pid"]), self.cpu_text(row["cpu"]),
                f'{row["memory"] / 1048576:.1f} МБ', str(len(row["threads"])), row["status"]])
            item.setData(0, QtCore.Qt.UserRole, row["key"])
            items[row["pid"]] = item
        for row in rows:
            item = items[row["pid"]]
            parent = items.get(row["parent"])
            if parent is not None and parent is not item:
                parent.addChild(item)
            else:
                self.tree.addTopLevelItem(item)
            for tid, cpu in row["threads"]:
                thread = QtWidgets.QTreeWidgetItem(
                    [f"Поток {tid}", str(tid), self.cpu_text(cpu), "Общая", "", ""])
                key = (*row["key"], tid)
                thread.setData(0, QtCore.Qt.UserRole, key)
                item.addChild(thread)
                if key == selected_key:
                    self.tree.setCurrentItem(thread)
            item.setExpanded(row["key"] in expanded)
            if row["key"] == selected_key:
                self.tree.setCurrentItem(item)
        self.tree.setUpdatesEnabled(True)
        memory = sum(row["memory"] for row in rows) / 1048576
        self.summary.setText(f"{len(rows)} процессов · {sum(len(r['threads']) for r in rows)} потоков · "
                             f"RAM {memory:.1f} МБ · {session}")
