"""PyScribe widgets/RunDebugPanel.py: application module and reusable component."""
from pathlib import Path
from design.icons import set_line_icon
from PyQt5 import QtCore, QtWidgets


class _LazyTargetCombo(QtWidgets.QComboBox):
    """Fills the entry-point list only when the dropdown is actually opened.

    Scanning the project for run targets inside ``refresh()`` cost ~1.7 s per
    project open (a ``stat`` per file on OneDrive paths). Nobody needs that list
    until they click the combo, so the scan is deferred to the first popup.
    """

    def __init__(self, populate, parent=None):
        super().__init__(parent)
        self._populate = populate
        self._populated = False

    def showPopup(self):  # noqa: N802 - Qt naming
        if not self._populated:
            self._populated = True
            try:
                self._populate()
            except Exception:
                pass
        super().showPopup()

    def invalidate(self):
        self._populated = False


class RunDebugPanel(QtWidgets.QWidget):
    """Functional Run & Debug sidebar backed by the main window execution services."""
    run_requested = QtCore.pyqtSignal(str, bool)  # path, debug
    project_requested = QtCore.pyqtSignal(bool)  # debug
    run_analyze_requested = QtCore.pyqtSignal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setObjectName("runDebugPanel")
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("ЗАПУСК")
        title.setObjectName("sideTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self.refresh_button = QtWidgets.QToolButton()
        set_line_icon(self.refresh_button, "reload")
        self.refresh_button.setToolTip("Обновить цели запуска")
        self.refresh_button.clicked.connect(self.refresh)
        title_row.addWidget(self.refresh_button)
        layout.addLayout(title_row)

        self.target = _LazyTargetCombo(self._populate_targets)
        self.target.setObjectName("runTarget")
        self.target.currentIndexChanged.connect(self._update_state)
        layout.addWidget(self.target)

        self.run_button = QtWidgets.QPushButton("Запустить файл")
        self.run_button.clicked.connect(lambda: self._emit(False))
        layout.addWidget(self.run_button)

        self.project_button = QtWidgets.QPushButton("Запустить проект")
        self.project_button.clicked.connect(lambda: self.project_requested.emit(False))
        layout.addWidget(self.project_button)

        self.run_analyze_button = QtWidgets.QPushButton("Запуск + повторный анализ")
        self.run_analyze_button.setToolTip("Запустить цель и повторно проанализировать проект")
        self.run_analyze_button.clicked.connect(lambda: self._run_analyze())
        layout.addWidget(self.run_analyze_button)

        self.info = QtWidgets.QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("sideHint")
        layout.addWidget(self.info)
        layout.addStretch()

    def refresh(self):
        """Reset the target picker; the project scan is deferred to the popup."""
        self.target.blockSignals(True)
        self.target.clear()
        if hasattr(self.target, "invalidate"):
            self.target.invalidate()
        current = self.main_window.get_current_editor()
        if current and getattr(current, "file_path", None):
            p = Path(current.file_path)
            self.target.addItem(f"Текущий · {p.name}", str(p))
        self.target.blockSignals(False)
        self._update_state()

    def _populate_targets(self):
        """Scan the project for entry points (called on first dropdown open)."""
        self.target.blockSignals(True)
        current_label = self.target.itemText(0) if self.target.count() else ""
        current_value = self.target.itemData(0) if self.target.count() else None
        self.target.clear()
        if current_label:
            self.target.addItem(current_label, current_value)
        root = getattr(getattr(self.main_window, "current_project", None), "root_path", None)
        if root:
            from core.ignore_rules import walk_files
            entry_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs",
                                ".go", ".rs", ".php", ".rb", ".kt", ".swift", ".lua",
                                ".sh", ".pl", ".asm", ".nasm", ".fasm"}
            scan = walk_files(Path(root), extensions=entry_extensions,
                              max_files=300, max_bytes=2 * 1024 * 1024)
            labels = []
            for p in scan.files:
                try:
                    label = str(p.relative_to(root))
                except ValueError:
                    label = str(p)
                labels.append((label, str(p)))
            self.target.addItems([label for label, _ in labels])
            base = 1 if current_label else 0
            for offset, (_, value) in enumerate(labels):
                self.target.setItemData(base + offset, value, QtCore.Qt.UserRole)
        self.target.blockSignals(False)

    def _update_state(self):
        has_target = bool(self.target.currentData())
        has_project = bool(getattr(self.main_window, "current_project", None))
        self.run_button.setEnabled(has_target)
        self.project_button.setEnabled(has_project)
        self.run_analyze_button.setEnabled(has_target and has_project)
        if has_target:
            self.info.setText("Запуск выполняет выбранную цель во встроенном терминале.")
        elif has_project:
            self.info.setText("Выберите исходный файл или запустите проект целиком.")
        else:
            self.info.setText("Откройте проект или исходный файл, чтобы создать цель запуска.")

    def _run_analyze(self):
        path = self.target.currentData()
        if path:
            self.run_analyze_requested.emit(str(path))

    def _emit(self, debug):
        path = self.target.currentData()
        if path:
            self.run_requested.emit(str(path), debug)
