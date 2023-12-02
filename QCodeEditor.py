from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QTextCursor, QFont


class CodeTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Times", 12))
        self.filename = ""
        self.fullfilepath = ""
        self.language = ""
        
    def addText(self, text):
        self.insertPlainText(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_QuoteDbl:
            self.insertPlainText('""')
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
            return
        if event.text() == "'":
            self.insertPlainText("''")
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
            return
        if event.text() == "(":
            self.insertPlainText("()")
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
            return
        if event.text() == "[":
            self.insertPlainText("[]")
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
            return
        if event.text() == "{":
            self.insertPlainText("{}")
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)