from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize

class UpPushButton(QPushButton):
    def __init__(self, text):
        super(UpPushButton, self).__init__(text=" Up", parent=None)
        self.setIcon(QIcon("src/arrow.png"))
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            """
            QPushButton{
                background-color: #1b1c2e; border: none; font-size: 13px; padding: 10px;
            } 
            """
        )
        self.hide()
    
class DeletePushButton(QPushButton):
    def __init__(self, text):
        super(DeletePushButton, self).__init__(text=" Delete", parent=None)
        self.setIcon(QIcon("src/delete.png"))
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            """
            QPushButton{
                background-color: #1b1c2e; border: none; font-size: 13px; padding: 10px;
            } 
            """
        )
        self.hide()

class CopyPushButton(QPushButton):
    def __init__(self, text):
        super(CopyPushButton, self).__init__(text=" Copy", parent=None)
        self.setIcon(QIcon("src/copy.png"))
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            """
            QPushButton{
                background-color: #1b1c2e; border: none; font-size: 13px; padding: 10px;
            } 
            """
        )
        self.hide()

class PastePushButton(QPushButton):
    def __init__(self, text):
        super(PastePushButton, self).__init__(text=" Paste", parent=None)
        self.setIcon(QIcon("src/paste.png"))
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            """
            QPushButton{
                background-color: #1b1c2e; border: none; font-size: 13px; padding: 10px;
            } 
            """
        )
        self.hide()