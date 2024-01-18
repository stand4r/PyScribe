from PyQt5.QtWidgets import QGridLayout, QLabel, QPlainTextEdit, QWidget, QShortcut 
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QKeySequence, QFont



class HexViewer(QWidget):
    def __init__(self, parent=None):
        super(HexViewer, self).__init__(parent)
        self.layout = QGridLayout(self)
        self.language = ""
        self.filename = ""
        self.fullfilepeth = ""
        self.address_widget = QPlainTextEdit(self)
        self.byte_widget = QPlainTextEdit(self)
        self.ascii_widget = QPlainTextEdit(self)
        self.address_widget.setStyleSheet("width: 0px;\n")
        self.address_widget.setFixedWidth(250)
        self.address_widget
        self.byte_widget.setStyleSheet("width: 0px;\n")
        self.ascii_widget.setStyleSheet("width: 0px;\n")
        self.fontSize = 14
        self.setStyleSheet(
            "background-color:#131313;\n"
            "color: #ffffff;\n"
            "letter-spacing:1px;\n"
        )
        self.layout.addWidget(QLabel("Адреса"), 0, 0)
        self.layout.addWidget(QLabel("Байты"), 0, 1)
        self.layout.addWidget(QLabel("ASCII-расшифровка"), 0, 2)
        self.layout.addWidget(self.address_widget, 1, 0)
        self.layout.addWidget(self.byte_widget, 1, 1)
        self.layout.addWidget(self.ascii_widget, 1, 2)
        self.shortcutAdd = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self.shortcutAdd.activated.connect(self.addFontSize)
        self.shortcutPop = QShortcut(QKeySequence("Ctrl+-"), self)
        self.setFont(QFont("Courier New", self.fontSize))
        self.ascii_widget.setFont(QFont("Courier New", self.fontSize))
        self.address_widget.setFont(QFont("Courier New", self.fontSize))
        self.byte_widget.setFont(QFont("Courier New", self.fontSize))
        self.address_widget.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.byte_widget.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.ascii_widget.verticalScrollBar().valueChanged.connect(self.sync_scroll)

    def sync_scroll(self, value):
        self.address_widget.verticalScrollBar().setValue(value)
        self.byte_widget.verticalScrollBar().setValue(value)
        self.ascii_widget.verticalScrollBar().setValue(value)
 
    @pyqtSlot()
    def addFontSize(self):
        self.fontSize+=1
        self.setFont(QFont("Courier New", self.fontSize))

    @pyqtSlot()
    def popFontSize(self):
        self.fontSize-=1
        self.setFont(QFont("Courier New", self.fontSize))

    def load_file(self, data):
        self.address_widget.clear()
        self.byte_widget.clear()
        self.ascii_widget.clear()
    
        for i, byte in enumerate(data):
            if i % 8 == 0 or i == 0:
                self.address_widget.insertPlainText("{:08X}\n".format(i)) 
                self.byte_widget.insertPlainText("\n")
                self.ascii_widget.insertPlainText("\n")
    
            self.byte_widget.insertPlainText("{:02X} ".format(byte))
    
            if byte >= 32 and byte <= 126:
                self.ascii_widget.insertPlainText(chr(byte)+" ")
            else:
                self.ascii_widget.insertPlainText(".")
