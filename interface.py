# -*- coding: cp1251 -*-

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QIcon
from subprocess import PIPE, Popen
from os import path
from QCodeEditor import CodeTextEdit
from basicInterface import Ui_MainWindow
from QReadOnlyTextEditor import QReadOnlyTextEdit



files = []
fileNames = []
languages = {"py": "python",
             "c": "c",
             "cpp": "cpp",
             "js": "javascript",
             "xml": "xml",
             "kt": "kotlin",
             "rss": "rss",
             "rb": "ruby",
             "html": "html",
             "htm": "html",
             "xhtml": "html",
             "css": "css"
             }


class UiMainWindow(Ui_MainWindow):
    def setupUiCustom(self, MainWindow):
        self.setupUi(MainWindow)
        self.MainWindow = MainWindow
        scriptDir = path.dirname(path.realpath(__file__))
        MainWindow.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png')) 
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.actionNew.triggered.connect(self.actionNewFile)
        
    def closeTab (self, currentIndex):
        self.tabWidget.removeTab(currentIndex)       

    def actionRunCode(self):
        self.ResultText.setPlainText("")
        self.ResultText.insertPlainText(f"~> run {self.CodeEdit.filename}\n")
        open(self.CodeEdit.fullfilepath, "w").write(self.CodeEdit.toPlainText())
        process = Popen([sys.executable, self.CodeEdit.fullfilepath], shell=True, stderr=PIPE, stdout=PIPE, text=True)
        while True:
            output = process.stdout.readline()
            error = process.stderr.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                self.ResultText.insertPlainText(output.encode('cp1251').decode('cp866'))
            if error:
                self.ResultText.insertPlainText(error.encode('cp1251').decode('cp866'))

    def actionOpenFile(self):
        fileDialog = QtWidgets.QFileDialog()
        fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        fileDialog.setNameFilter("All files(*.*)")  
        if fileDialog.exec_():
            files.clear()
            files.append(fileDialog.selectedFiles())
            self.openFilesForTabs()
            
    def actionNewFile(self):
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self.MainWindow, "Save File", "", "All Files (*);", options=options)
        if fileName:
            files.clear()
            files.append(fileName)
            self.openFilesForTabs()
            
    def actionSaveFile(self):
        open(self.CodeEdit.fullfilepath, "w").write(self.CodeEdit.toPlainText())
            
    def openFilesForTabs(self):
        fileNames.clear()
        for file in files:
            fileNames.append(file[0].split("/")[-1])
            text = open(file[0], "r").readlines()
            self.createTab(text, file[0])

    def createTab(self, text, fileName):
        self.tab = QtWidgets.QWidget()
        self.tab.setObjectName("tab")
        self.CodeEdit = CodeTextEdit(self.tab)
        self.CodeEdit.setGeometry(QtCore.QRect(-7, -4, 950, 791))
        self.CodeEdit.setMinimumSize(QtCore.QSize(950, 0))
        self.CodeEdit.setMaximumSize(QtCore.QSize(950, 16777215))
        self.CodeEdit.filename = rf"{fileName.split('/')[-1]}"
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.language = languages[fileName.split('/')[-1].split('.')[-1]]
        print(self.CodeEdit.language)
        font = QtGui.QFont()
        font.setPointSize(12)
        self.CodeEdit.setFont(font)
        self.CodeEdit.setStyleSheet("background-color:#0A1F32;\n"
"color: #ffffff;\n"
"padding: 12px; padding-bottom: 100px;padding-left: 20px;padding-right:20px")
        self.CodeEdit.setObjectName("CodeEdit")
        txt = "".join(text)
        self.CodeEdit.addText(txt.encode('cp1251').decode('cp866'))
        self.ResultText = QReadOnlyTextEdit(self.tab)
        self.ResultText.setGeometry(QtCore.QRect(939, -10, 601, 757))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ResultText.sizePolicy().hasHeightForWidth())
        self.ResultText.setSizePolicy(sizePolicy)
        self.ResultText.setMinimumSize(QtCore.QSize(601, 757))
        self.ResultText.setMaximumSize(QtCore.QSize(601, 757))
        font = QtGui.QFont()
        font.setFamily("MS Shell Dlg 2")
        font.setPointSize(12)
        self.ResultText.setFont(font)
        self.ResultText.setStyleSheet("background-color: #0A1F32;\n"
"color: #ffffff;\n"
"padding: 12px; padding-bottom: 100px; padding-right:100px;")
        self.ResultText.setObjectName("ResultText")
        self.tabWidget.addTab(self.tab, fileName.split('/')[-1])



if __name__ == "__main__":
    import sys
    scriptDir = path.dirname(path.realpath(__file__))
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png'))
    MainWindow = QtWidgets.QMainWindow()
    ui = UiMainWindow()
    ui.setupUiCustom(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_()) 