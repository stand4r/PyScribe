from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QIcon
from subprocess import PIPE, Popen
from os import path
from widgets.QCodeEditor import CodeTextEdit
from basicInterface import Ui_MainWindow
from time import perf_counter
from utils.programs import *
from sys import exit, argv, executable

try:
    from PyQt5.QtWinExtras import QtWin
    myappid = 'stand4r.PyScribe.pyscribe.1'
    QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

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
    def setupUiCustom(self):
        self.setupUi()
        self.files = loadSession()
        scriptDir = path.dirname(path.realpath(__file__))
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.actionNew.triggered.connect(self.actionNewFile)
        self.loadSession(self.files)

    def loadSession(self, files):
        for file in files:
            self.createTab(open(rf"{file}", "r").readlines(), file)

    def closeTab (self, currentIndex):
        active_tab_index = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(active_tab_index)
        self.files.remove(active_tab_widget.findChild(CodeTextEdit, "CodeEdit").fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        self.actionSaveFile()
        if self.tabWidget.count() == 0:
            self.ResultText.setGeometry(QtCore.QRect(939, 12, 599, 757))
            self.ResultText.setMinimumSize(QtCore.QSize(599, 791))
            self.ResultText.setMaximumSize(QtCore.QSize(599, 791))
            self.ResultText.setPlainText("")

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(active_tab_index)
        if active_tab_widget:
            CodeEdit = active_tab_widget.findChild(CodeTextEdit, "CodeEdit")
        
        self.ResultText.setPlainText("")

        with open(CodeEdit.fullfilepath, 'w') as codefile:
            codefile.write(CodeEdit.toPlainText())

        if CodeEdit.language == "python":
            if executable:
                self.ResultText.insertHtml(f"> <font color=green>found interpreter</font><br>")
            else:
                self.ResultText.insertPlainText(f"> <font color=red>ERROR</font>: python interpreter not found<br>")
            command = [executable, '"' + CodeEdit.fullfilepath + '"']

        elif CodeEdit.language == "c":
            self.ResultText.insertPlainText(f"> compiling {CodeEdit.filename}...\n")
            exe_path = compile_program_c(CodeEdit.fullfilepath)
            command = [f'"{exe_path}"']
            self.ResultText.insertHtml(f"> <font color=green>compilation completed</font><br>")
        elif self.CodeEdit.language == "cpp":
            self.ResultText.insertPlainText(f"> compiling {CodeEdit.filename}...\n")
            exe_path = compile_program_cpp(CodeEdit.fullfilepath)
            command = [f'"{exe_path}"']
            self.ResultText.insertHtml(f"> <font color=green>compilation completed</font><br>")
        self.ResultText.insertPlainText(f"> run {CodeEdit.filename}\n")
        
        tac = perf_counter()
        Popen(f'start cmd /k {" ".join(command)}', shell=True)
        tic = perf_counter()
        
        self.ResultText.insertPlainText(f"\nCode executed in {tic-tac:0.4f} seconds")

    def actionSaveFile(self):
        active_tab_index = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(active_tab_index)
        if active_tab_widget:
            CodeEdit = active_tab_widget.findChild(CodeTextEdit, "CodeEdit")
            open(CodeEdit.fullfilepath, "w").write(CodeEdit.toPlainText())

    def actionOpenFile(self):
        fileDialog = QtWidgets.QFileDialog()
        fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        fileDialog.setNameFilter("All files(*.*)") 
        if fileDialog.exec_():
            file_path = fileDialog.selectedFiles()[0]
            with open(file_path, "r") as file:
                text = file.readlines()
                self.files.append(file_path)
                self.createTab(text, file_path)

    def actionNewFile(self):
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*);", options=options)
        if fileName:
            with open(fileName, "w") as file:
                file.write('')
                with open(fileName, "r") as file_read:
                    text = file_read.readlines()
                    self.createTab(text, fileName)

    def createTab(self, text, fileName):
        self.ResultText.setGeometry(QtCore.QRect(939, 43, 599, 757))
        self.ResultText.setMinimumSize(QtCore.QSize(599, 791))
        self.ResultText.setMaximumSize(QtCore.QSize(599, 791))
        self.tab = QtWidgets.QWidget()
        self.tab.setObjectName("tab")
        self.CodeEdit = CodeTextEdit(self.tab)
        self.CodeEdit.setGeometry(QtCore.QRect(-7, -3, 950, 791))
        self.CodeEdit.setMinimumSize(QtCore.QSize(950, 790))
        self.CodeEdit.setMaximumSize(QtCore.QSize(950, 790))
        self.CodeEdit.filename = rf"{fileName.split('/')[-1]}"
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.language = languages[fileName.split('/')[-1].split('.')[-1]]
        font = QtGui.QFont()
        font.setPointSize(12)
        self.CodeEdit.setFont(font)
        self.CodeEdit.setStyleSheet("background-color:#1e1f1e;\n"
            "color: #ffffff;\n"
            "padding: 12px;\n"
            "padding-bottom: 100px;\n"
            "padding-left: 20px;\n"
            "padding-right:20px;\n"
            "letter-spacing:2px;"
            )
        self.CodeEdit.setObjectName("CodeEdit")
        txt = "".join(text)
        self.CodeEdit.addText(txt)
        self.tabWidget.addTab(self.tab, fileName.split('/')[-1])

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            CodeEdit = tab.findChild(CodeTextEdit, "CodeEdit")
            open(CodeEdit.fullfilepath, "w").write(CodeEdit.toPlainText())

    def closeEvent(self, event):
        self.saveOpenFiles()
        saveSession(self.files)
        event.accept()




if __name__ == "__main__":
    scriptDir = path.dirname(path.realpath(__file__))
    app = QtWidgets.QApplication(argv)
    app.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png'))
    MainWindow = UiMainWindow()
    MainWindow.setupUiCustom()
    MainWindow.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png'))
    MainWindow.show()
    exit(app.exec_())