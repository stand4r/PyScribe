from PyQt5 import QtCore, QtWidgets

class QReadOnlyTextEdit(QtWidgets.QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event):
        if not self.textCursor().hasSelection():
            return
        else:
            if event.key() == QtCore.Qt.Key_Backspace or event.key() == QtCore.Qt.Key_Delete:
                return
        super().keyPressEvent(event)