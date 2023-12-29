from PyQt5.QtWidgets import QTextEdit, QShortcut
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QFont, QKeySequence

class QTerminal(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.fontSize = 14
        self.setFont(QFont("Console", self.fontSize))
        self.shortcutAdd = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self.shortcutAdd.activated.connect(self.addFontSize)
        self.shortcutPop = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcutPop.activated.connect(self.popFontSize)

    @pyqtSlot()
    def addFontSize(self):
        self.fontSize+=1
        self.setFont(QFont("Console", self.fontSize))

    @pyqtSlot()
    def popFontSize(self):
        self.fontSize-=1
        self.setFont(QFont("Console", self.fontSize))

    def insertColorText(self, text, color=None):
        if color:
            self.insertHtml(f"<font color={color}>{text}</font><br>\n")
        else:
            self.insertPlainText(text+"\n")