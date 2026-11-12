"""Reading and folding controls for a terminal's output."""
from contextlib import contextmanager

from PyQt5 import QtCore, QtGui, QtWidgets


class TerminalOutputControls(QtWidgets.QWidget):
    def __init__(self, screen, parent=None):
        super().__init__(parent)
        self.screen = screen
        self.unread = 0
        self.errors = 0
        self.groups = []
        self.last_block = None
        self.next_block = 0
        self.updating = False
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        self.resume = QtWidgets.QPushButton()
        self.resume.clicked.connect(self.follow)
        layout.addWidget(self.resume)
        self.expand = QtWidgets.QPushButton()
        self.expand.setCheckable(True)
        self.expand.toggled.connect(self.set_expanded)
        layout.addWidget(self.expand)
        self.resume.hide()
        self.expand.hide()
        screen.verticalScrollBar().valueChanged.connect(self.scrolled)

    def scrolled(self):
        bar = self.screen.verticalScrollBar()
        if not self.updating and bar.value() >= bar.maximum() - 2:
            self.unread = self.errors = 0
            self.resume.hide()

    def follow(self):
        bar = self.screen.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.scrolled()

    @contextmanager
    def append(self, text="", error=False):
        bar = self.screen.verticalScrollBar()
        position = bar.value()
        paused = position < bar.maximum() - 2
        selection = QtGui.QTextCursor(self.screen.textCursor())
        self.updating = True
        try:
            yield
        finally:
            if paused:
                self.screen.setTextCursor(selection)
                bar.setValue(position)
                self.unread += text.count("\n")
                self.errors += int(error)
                self.resume.setText(f"К новым строкам · {self.unread} · ошибок {self.errors}")
                self.resume.setVisible(bool(self.unread))
            self.updating = False

    def fold_output(self, start_position):
        document = self.screen.document()
        before = len(self.groups)
        block = document.findBlock(max(start_position, self.next_block))
        while block.isValid() and block.next().isValid():
            previous = self.last_block
            if (block.text() and previous is not None and previous.isValid()
                    and previous.next() == block and previous.text() == block.text()):
                self.groups.append(block)
                if not self.expand.isChecked():
                    block.setVisible(False)
                    block.setLineCount(0)
            self.last_block = block
            self.next_block = block.next().position()
            block = block.next()
        if len(self.groups) != before:
            self.expand.setText(f"Повторы · {len(self.groups)}")
            self.expand.show()
            document.markContentsDirty(start_position, document.characterCount() - start_position)
            self.screen.viewport().update()

    def set_expanded(self, expanded):
        for block in self.groups:
            if block.isValid():
                block.setVisible(expanded)
                block.setLineCount(1 if expanded else 0)
        document = self.screen.document()
        document.markContentsDirty(0, document.characterCount())
        self.screen.viewport().update()

    def reset(self):
        self.groups.clear()
        self.last_block = None
        self.next_block = 0
        self.unread = self.errors = 0
        self.resume.hide()
        self.expand.hide()
