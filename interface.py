from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QTextCursor, QFont
from subprocess import PIPE, Popen



class ReadOnlyTextEdit(QtWidgets.QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event):
        if not self.textCursor().hasSelection():
            return
        else:
            if event.key() == QtCore.Key_Backspace or event.key() == QtCore.Key_Delete:
                return
        super().keyPressEvent(event)
        

class CodeTextEdit(QtWidgets.QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Times", 12))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_QuoteDbl:
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


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1500, 850)
        MainWindow.setStyleSheet("#MainWindow{background-color: #121212;}") 
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        MainWindow.setMinimumSize(QtCore.QSize(1500, 850))
        MainWindow.setMaximumSize(QtCore.QSize(1500, 850))
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.TreeFiles = QtWidgets.QTreeView(self.centralwidget)
        self.TreeFiles.setEnabled(True)
        self.TreeFiles.setMaximumSize(QtCore.QSize(220, 16777215))
        self.TreeFiles.setObjectName("TreeFiles")
        self.TreeFiles.setStyleSheet("#TreeFiles{background-color:#002137; border-radius:10px}")
        self.horizontalLayout.addWidget(self.TreeFiles)
        self.CodeText = CodeTextEdit(self.centralwidget)
        self.CodeText.setMinimumSize(QtCore.QSize(850, 0))
        self.CodeText.setMaximumSize(QtCore.QSize(850, 16777215))
        self.CodeText.setObjectName("CodeText")
        self.CodeText.setStyleSheet("#CodeText{background-color:#332f2c; border-radius:10px; color: #ffffff; padding: 10px}")
        self.horizontalLayout.addWidget(self.CodeText)
        self.ResultText = ReadOnlyTextEdit(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ResultText.sizePolicy().hasHeightForWidth())
        self.ResultText.setSizePolicy(sizePolicy)
        self.ResultText.setMinimumSize(QtCore.QSize(3, 0))
        self.ResultText.setMaximumSize(QtCore.QSize(500, 16777215))
        self.ResultText.setObjectName("ResultText")
        self.ResultText.setStyleSheet("#ResultText{background-color:#332f2c; border-radius:10px; color:#fbfbfb; \
            font: 12pt 'Times New Roman'; padding: 15px}")
        self.horizontalLayout.addWidget(self.ResultText)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.frame_2 = QtWidgets.QFrame(self.centralwidget)
        self.frame_2.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_2.setObjectName("frame_2")
        self.verticalLayout.addWidget(self.frame_2)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1500, 26))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuFile.setStyleSheet("#menuFile{background-color: #332f2c; color: #ffffff}")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        self.statusbar.setStyleSheet("#statusbar{background-color:#332f2c; color: #ffffff}")
        MainWindow.setStatusBar(self.statusbar)
        self.actionOpen = QtWidgets.QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionSave = QtWidgets.QAction(MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionRun = QtWidgets.QAction(MainWindow)
        self.actionRun.setObjectName("actionRun")
        self.actionRun.setShortcut('Ctrl+Shift+x')
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen_Directory = QtWidgets.QAction(MainWindow)
        self.actionOpen_Directory.setObjectName("actionOpen_Directory")
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionRun)
        self.menuFile.addAction(self.actionOpen_Directory)
        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        
        

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "IDE Python"))
        self.ResultText.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'MS Shell Dlg 2\'; font-size:7.8pt; font-weight:400; font-style:normal;\">\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>"))
        self.menuFile.setTitle(_translate("MainWindow", "File   "))
        self.actionOpen.setText(_translate("MainWindow", "Open             Shift+F5"))
        self.actionSave.setText(_translate("MainWindow", "Save             Ctrl+S"))
        self.actionRun.setText(_translate("MainWindow", "Run              Ctrl+Shift+X"))
        self.actionOpen_Directory.setText(_translate("MainWindow", "Open Directory   Shift+F6"))
        
    def actionRunCode(self):
        open("output.py", "w").write(self.CodeText.toPlainText())
        process = Popen("python output.py", shell=True, stderr=PIPE, stdout=PIPE, text=True)
        while True:
            output = process.stdout.readline()
            error = process.stderr.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                self.ResultText.setPlainText(self.ResultText.toPlainText()+output)
            if error:
                self.ResultText.setPlainText(self.ResultText.toPlainText()+error)
        
        

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
