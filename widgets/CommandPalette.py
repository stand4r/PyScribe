"""PyScribe widgets/CommandPalette.py: application module and reusable component."""
from PyQt5 import QtCore, QtGui, QtWidgets


class CommandPalette(QtWidgets.QDialog):
    """Compact command launcher inspired by VS Code's Command Palette."""
    command_triggered = QtCore.pyqtSignal(str)

    def __init__(self, commands=None, parent=None):
        super().__init__(parent)
        self.commands = commands or []
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setModal(True)
        self.resize(720, 420)
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Введите команду для поиска…")
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._activate)
        root.addWidget(self.input)
        self.list = QtWidgets.QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._activate())
        root.addWidget(self.list)
        self.setStyleSheet("""
            QDialog { background: #252526; border: 1px solid #454545; border-radius: 10px; }
            QLineEdit { background: #3c3c3c; color: #f0f0f0; border: 1px solid #007acc; border-radius: 6px; padding: 9px 12px; font-size: 13px; }
            QListWidget { background: #252526; color: #cccccc; border: none; outline: none; border-radius: 6px; }
            QListWidget::item { padding: 8px 12px; border-radius: 4px; margin: 1px 2px; }
            QListWidget::item:selected { background: #094771; color: #ffffff; }
        """)
        self._filter("")

    def _filter(self, text):
        self.list.clear()
        query = text.lower().strip()
        for label, command in self.commands:
            if query in label.lower():
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, command)
                self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _activate(self):
        item = self.list.currentItem()
        if item:
            self.command_triggered.emit(item.data(QtCore.Qt.UserRole))
            self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.input.setFocus()
        self.input.selectAll()
        # Smooth fade-in animation
        self._anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.start()
