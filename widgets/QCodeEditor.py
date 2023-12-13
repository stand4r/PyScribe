from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtGui import QTextCursor, QFont, QPainter, QColor, QTextCharFormat


class CodeTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Times", 12))
        #self.highlight_text()
        self.filename = ""
        self.fullfilepath = ""
        self.language = ""
        
    def addText(self, text):
        self.insertPlainText(text)

    def keyPressEvent(self, event):
        if event.text() in  ["'", '"', "(", "{", "["]:
            if event.text() == '"':
                self.insertPlainText('""')
            elif event.text() == "'":
                self.insertPlainText("''")
            elif event.text() == "(":
                self.insertPlainText("()")
            elif event.text() == "[":
                self.insertPlainText("[]")
            elif event.text() == "{":
                self.insertPlainText("{}")
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
        else:
            super().keyPressEvent(event)
        
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        font = painter.font()
        font.setPointSize(12)  # Задаем размер шрифта для счетчика строк
        painter.setFont(font)
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # Определяем видимые блоки и рисуем номера строк
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.white)
                painter.drawText(0, int(top), self.viewport().width(), self.fontMetrics().height(), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def highlight_text(self):
        for word in ["print", "if", "else"]:
            cursor = self.document().find(word)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("red"))

            while not cursor.isNull():
                cursor.mergeCharFormat(fmt)
                cursor = self.document().find(word, cursor)