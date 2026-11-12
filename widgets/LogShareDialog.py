"""Preview and copy the local diagnostic files."""
import re
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets


class LogShareDialog(QtWidgets.QDialog):
    def __init__(self, directory: Path, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.setWindowTitle("Отправить лог")
        self.resize(760, 480)
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel(
            "Выберите журнал и проверьте его содержимое перед отправкой. "
            "Скопированный файл можно вставить в папку или приложить к сообщению."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.files = QtWidgets.QListWidget()
        self.files.setAccessibleName("Файлы журналов")
        self.files.setMaximumHeight(138)
        self.files.currentItemChanged.connect(self._preview)
        layout.addWidget(self.files)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Предпросмотр журнала")
        self.preview.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(self.preview, 1)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        self.copy_button = buttons.addButton("Скопировать файл", QtWidgets.QDialogButtonBox.ActionRole)
        self.copy_button.clicked.connect(self.copy_file)
        refresh = buttons.addButton("Обновить список", QtWidgets.QDialogButtonBox.ActionRole)
        refresh.clicked.connect(self.refresh)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self):
        current = self.files.currentItem()
        selected = current.text() if current else ""
        self.files.clear()
        try:
            paths = sorted(self.directory.iterdir())
        except OSError:
            paths = []
        for path in paths:
            if re.fullmatch(r".+\.log(?:\.\d+)?", path.name) and path.is_file() and not path.is_symlink():
                self.files.addItem(path.name)
        matches = self.files.findItems(selected, QtCore.Qt.MatchExactly)
        if matches:
            self.files.setCurrentItem(matches[0])
        elif self.files.count():
            self.files.setCurrentRow(0)
        else:
            self._preview(None)

    def _preview(self, item, previous=None):
        self.copy_button.setEnabled(False)
        self.status.clear()
        self.preview.clear()
        if item is None:
            self.status.setText("Журналы пока отсутствуют.")
            return
        path = self.directory / item.text()
        limit = 256 * 1024
        try:
            with path.open("rb") as stream:
                size = stream.seek(0, 2)
                stream.seek(max(0, size - limit))
                contents = stream.read(limit).decode("utf-8", errors="replace")
        except OSError as exc:
            self.status.setText(f"Не удалось прочитать журнал. {exc.strerror or exc}")
            return
        self.preview.setPlainText(contents)
        self.preview.moveCursor(QtGui.QTextCursor.End)
        self.copy_button.setEnabled(True)
        if size > limit:
            self.status.setText("Показаны последние 256 КБ. Копируется весь файл.")

    def copy_file(self):
        item = self.files.currentItem()
        if item is None:
            return
        path = self.directory / item.text()
        if not path.is_file() or path.is_symlink():
            self.refresh()
            self.status.setText("Журнал больше недоступен. Выберите файл из обновлённого списка.")
            return
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(path.resolve()))])
        QtWidgets.QApplication.clipboard().setMimeData(mime)
        self.status.setText(f"Файл {path.name} скопирован.")
