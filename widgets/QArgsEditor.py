"""PyScribe launch arguments editor widget."""
from os import path
from json import dumps, load
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets


class ArgsWindow(QtWidgets.QWidget):
    def __init__(self, filename: str, scriptDir: str, filepath: str, lang: str):
        super().__init__()
        self.filename = filename
        self.scriptDir = scriptDir
        self.filepath = filepath
        self.lang = lang
        self.config_path = str(Path(self.scriptDir) / "config" / "launchArgs.json")
        self.exist_args = self.load_args(self.config_path, self.filepath)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("ArgsWindow")
        self.setWindowTitle("Параметры запуска файла")
        self.setFixedSize(580, 200)
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #d4d4d4; , sans-serif; font-size: 12px; }
            QLineEdit { background-color: #252526; border: 1px solid #3c3c3c; border-radius: 4px; padding: 6px; color: #ffffff; }
            QLineEdit:focus { border: 1px solid #007acc; }
            QPushButton { background-color: #0e639c; color: white; border: none; border-radius: 4px; padding: 6px 16px; font-weight: 600; }
            QPushButton:hover { background-color: #1177bb; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addLayout(self._create_header_info())
        layout.addLayout(self._create_args_input())
        layout.addLayout(self._create_button_row())

    def _create_header_info(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(16)

        f_lbl = QtWidgets.QLabel("Файл:")
        f_lbl.setStyleSheet("color: #888888; font-weight: 600;")
        self.file_label = QtWidgets.QLabel(self.filename)
        self.file_label.setStyleSheet("color: #58a6ff; font-weight: bold;")
        row.addWidget(f_lbl)
        row.addWidget(self.file_label)
        row.addSpacing(20)

        l_lbl = QtWidgets.QLabel("Язык:")
        l_lbl.setStyleSheet("color: #888888; font-weight: 600;")
        self.language_label = QtWidgets.QLabel(self.lang.capitalize())
        self.language_label.setStyleSheet("color: #4ec9b0; font-weight: bold;")
        row.addWidget(l_lbl)
        row.addWidget(self.language_label)
        row.addStretch()
        return row

    def _create_args_input(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        label = QtWidgets.QLabel("Аргументы:")
        label.setStyleSheet("color: #cccccc;")
        self.args_edit = QtWidgets.QLineEdit()
        self.args_edit.setPlaceholderText("Например: --debug --port 8080 -v")
        self.args_edit.setText(self.exist_args)
        row.addWidget(label)
        row.addWidget(self.args_edit, 1)
        return row

    def _create_button_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.addStretch()

        self.pushButton = QtWidgets.QPushButton("Сохранить")
        self.pushButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.pushButton.clicked.connect(self.saveSettings)
        row.addWidget(self.pushButton)

        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.setStyleSheet("background-color: #333333; color: #cccccc;")
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.close)
        row.addWidget(cancel_btn)
        return row

    def saveSettings(self):
        flags = self.args_edit.text()
        if not self.exist_config(self.config_path) or self.clear_file(self.config_path):
            self.create_config(self.config_path)
        self.dump_args(self.config_path, self.filepath, flags)
        self.close()

    def exist_config(self, config):
        return path.exists(config)

    def create_config(self, config):
        Path(config).parent.mkdir(parents=True, exist_ok=True)
        Path(config).write_text("{\n\n}", encoding="utf-8")

    def clear_file(self, config):
        try:
            return Path(config).read_text(encoding="utf-8").strip() == ""
        except Exception:
            return True

    def dump_args(self, config, filepath, args):
        try:
            p = Path(config)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = load(open(config, "r", encoding="utf-8")) if p.exists() else {}
        except Exception:
            data = {}
        data[filepath] = args
        Path(config).write_text(dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_args(self, config, filepath) -> str:
        try:
            p = Path(config)
            if not p.exists():
                return ""
            data = load(open(config, "r", encoding="utf-8"))
            return str(data.get(filepath, ""))
        except Exception:
            return ""

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.saveSettings()
        else:
            super().keyPressEvent(event)
