"""PyScribe widgets/QuickOpenDialog.py: application module and reusable component."""
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets


class QuickOpenDialog(QtWidgets.QDialog):
    file_selected = QtCore.pyqtSignal(str)

    def __init__(self, root: Path | None, recent_files=None, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve() if root else None
        self.setWindowTitle("Быстрое открытие файлов")
        self.setModal(True)
        self.resize(720, 520)
        self.setObjectName("quickOpenDialog")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Поиск файлов по имени…")
        self.query.setClearButtonEnabled(True)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("quickOpenList")
        layout.addWidget(self.query)
        layout.addWidget(self.list, 1)
        self.setStyleSheet("""
            QDialog#quickOpenDialog { background: #252526; border: 1px solid #454545; border-radius: 10px; }
            QLineEdit { background: #3c3c3c; color: #f0f0f0; border: 1px solid #007acc; border-radius: 6px; padding: 9px 12px; font-size: 13px; }
            QListWidget#quickOpenList { background: #252526; color: #cccccc; border: none; outline: none; border-radius: 6px; }
            QListWidget#quickOpenList::item { padding: 6px 10px; border-radius: 4px; margin: 1px 2px; }
            QListWidget#quickOpenList::item:selected { background: #094771; color: #ffffff; }
        """)
        self.paths = []
        self.query.textChanged.connect(self._filter)
        self.list.itemActivated.connect(self._open_current)
        self.query.returnPressed.connect(self._open_current)
        self._build_paths(recent_files or [])
        self._filter("")
        self.query.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self._anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.start()

    def _build_paths(self, recent):
        seen = set()
        for value in recent:
            p = Path(value)
            if p.is_file() and str(p.resolve()) not in seen:
                seen.add(str(p.resolve()))
                self.paths.append((p.resolve(), "Недавние"))
        if self.root and self.root.exists():
            from core.ignore_rules import walk_files
            # Pruned walk: rglob used to descend into node_modules/.git before
            # the filter ran, which made quick open crawl on large projects.
            scan = walk_files(self.root, extensions=None, max_files=3000,
                              max_bytes=4 * 1024 * 1024)
            for p in scan.files:
                if str(p.resolve()) in seen:
                    continue
                seen.add(str(p.resolve()))
                try:
                    group = str(p.parent.relative_to(self.root))
                except ValueError:
                    group = ""
                self.paths.append((p.resolve(), group))
                if len(self.paths) >= 3000:
                    break

    def _filter(self, text):
        query = text.strip().lower()
        self.list.clear()
        for path, group in self.paths:
            hay = f"{path.name} {path}".lower()
            if not query or query in hay:
                item = QtWidgets.QListWidgetItem(path.name)
                item.setToolTip(str(path))
                item.setData(QtCore.Qt.UserRole, str(path))
                if group:
                    item.setStatusTip(group)
                self.list.addItem(item)
                if self.list.count() >= 100:
                    break
        if self.list.count():
            self.list.setCurrentRow(0)

    def _open_current(self):
        item = self.list.currentItem()
        if not item:
            return
        self.file_selected.emit(item.data(QtCore.Qt.UserRole))
        self.accept()
