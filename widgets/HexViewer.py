"""Read-only hexadecimal viewer used for binary files."""
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QGridLayout, QLabel, QPlainTextEdit, QWidget, QShortcut, QHBoxLayout
)


class HexViewer(QWidget):
    """A lightweight VS Code-like binary/hex preview.

    Binary files are deliberately read-only. The original bytes are retained
    so a future editable hex mode can be added without changing file loading.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = None
        self.data = b""
        self.font_size = 12

        self.setObjectName("hexViewer")
        self.setStyleSheet("""
            QWidget#hexViewer { background: #1e1e1e; color: #cccccc; }
            QLabel { color: #858585; padding: 4px 8px; }
            QPlainTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 6px 8px;
                selection-background-color: #264f78;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12pt;
            }
        """)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        self.info_label = QLabel("Binary • read-only")
        header.addWidget(self.info_label)
        header.addStretch()
        layout.addLayout(header, 0, 0, 1, 3)

        self.address_widget = self._make_view()
        self.byte_widget = self._make_view()
        self.ascii_widget = self._make_view()

        layout.addWidget(QLabel("Offset"), 1, 0)
        layout.addWidget(QLabel("Hex"), 1, 1)
        layout.addWidget(QLabel("ASCII"), 1, 2)
        layout.addWidget(self.address_widget, 2, 0)
        layout.addWidget(self.byte_widget, 2, 1)
        layout.addWidget(self.ascii_widget, 2, 2)

        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 1)

        self.address_widget.verticalScrollBar().valueChanged.connect(self._sync_from_address)
        self.byte_widget.verticalScrollBar().valueChanged.connect(self._sync_from_bytes)
        self.ascii_widget.verticalScrollBar().valueChanged.connect(self._sync_from_ascii)

        QShortcut(QKeySequence("Ctrl+="), self, activated=self.add_font_size)
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self.pop_font_size)

    def _make_view(self):
        widget = QPlainTextEdit()
        widget.setReadOnly(True)
        widget.setLineWrapMode(QPlainTextEdit.NoWrap)
        widget.setUndoRedoEnabled(False)
        widget.setFont(QFont("Cascadia Code", self.font_size))
        return widget

    def _sync(self, source, value):
        for widget in (self.address_widget, self.byte_widget, self.ascii_widget):
            if widget is not source:
                widget.blockSignals(True)
                widget.verticalScrollBar().setValue(value)
                widget.blockSignals(False)

    def _sync_from_address(self, value): self._sync(self.address_widget, value)
    def _sync_from_bytes(self, value): self._sync(self.byte_widget, value)
    def _sync_from_ascii(self, value): self._sync(self.ascii_widget, value)

    def add_font_size(self):
        self.font_size = min(30, self.font_size + 1)
        self._apply_font()

    def pop_font_size(self):
        self.font_size = max(7, self.font_size - 1)
        self._apply_font()

    def _apply_font(self):
        font = QFont("Cascadia Code", self.font_size)
        for widget in (self.address_widget, self.byte_widget, self.ascii_widget):
            widget.setFont(font)

    # Compatibility with the original widget API.
    def addFontSize(self): self.add_font_size()
    def popFontSize(self): self.pop_font_size()

    def load_file(self, data):
        self.data = bytes(data)
        self.address_widget.clear()
        self.byte_widget.clear()
        self.ascii_widget.clear()

        # Build complete strings first; inserting one character at a time
        # becomes extremely slow on multi-megabyte binaries.
        addresses, hex_lines, ascii_lines = [], [], []
        for offset in range(0, len(self.data), 16):
            chunk = self.data[offset:offset + 16]
            addresses.append(f"{offset:08X}")
            hex_lines.append(" ".join(f"{b:02X}" for b in chunk).ljust(47))
            ascii_lines.append("".join(chr(b) if 32 <= b <= 126 else "." for b in chunk))

        self.address_widget.setPlainText("\n".join(addresses))
        self.byte_widget.setPlainText("\n".join(hex_lines))
        self.ascii_widget.setPlainText("\n".join(ascii_lines))

        name = Path(self.file_path).name if self.file_path else "Binary"
        size = len(self.data)
        self.info_label.setText(f"{name}  •  {size:,} bytes  •  read-only")
        for widget in (self.address_widget, self.byte_widget, self.ascii_widget):
            widget.moveCursor(QTextCursor.Start)
