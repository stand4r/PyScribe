from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QIcon
from subprocess import Popen, check_output
from os import path, system
from widgets.QCodeEditor import CodeTextEdit
from basicInterface import Ui_MainWindow
from time import perf_counter
from utils.programs import *
from sys import exit, argv, executable
from widgets.QArgsEditor import ArgsWindow
from utils.FabricRunCode import *
from widgets.QTerminal import *

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
        self.config_path = path.dirname(path.realpath(__file__))+r"\config\launchArgs.json"
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.actionConfig.triggered.connect(self.actionArgsLaunch)
        self.actionNew.triggered.connect(self.actionNewFile)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.loadSession(self.files)

    def loadSession(self, files):
        for file in files:
            self.createTab(open(rf"{file}", "r").readlines(), file)

    def closeTab (self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        self.actionSaveFile(currentIndex)
        if self.tabWidget.count() == 0:
            self.ResultText.setPlainText("")

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        CodeEdit = self.tabWidget.widget(active_tab_index)
        
        self.ResultText.setPlainText("")

        with open(CodeEdit.fullfilepath, 'w') as codefile:
            codefile.write(CodeEdit.toPlainText())

        if CodeEdit.language == "python":
            if executable:
                self.ResultText.insertColorText("found interpreter", "green")
            else:
                self.ResultText.insertColorText("python interpreter not found", "red")
            command = [executable, '"' + CodeEdit.fullfilepath + '"']

        elif CodeEdit.language == "c":
            self.ResultText.insertColorText(f"compiling {CodeEdit.filename}")
            exe_path = compile_program_c(CodeEdit.fullfilepath)
            command = [f'"{exe_path}"']
            self.ResultText.insertColorText("compilation completed", "green")
        elif self.CodeEdit.language == "cpp":
            self.ResultText.insertColorText(f"compiling {CodeEdit.filename}")
            exe_path = compile_program_cpp(CodeEdit.fullfilepath)
            command = [f'"{exe_path}"']
            self.ResultText.insertColorText("compilation completed", "green")
        self.ResultText.insertColorText(f"run {CodeEdit.filename}")

        RunCodeClass(self.CodeEdit.fullfilepath, self.CodeEdit.filename, self.CodeEdit.language).process()

    def actionSaveFile(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        if active_tab_widget:
            open(active_tab_widget.fullfilepath, "w").write(active_tab_widget.toPlainText())

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

    def actionArgsLaunch(self):
        active_tab_index = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(active_tab_index)
        if active_tab_widget:
            CodeEdit = active_tab_widget.findChild(CodeTextEdit, "CodeEdit")
            self.window = ArgsWindow(CodeEdit.filename, CodeEdit.fullfilepath, CodeEdit.language)
            self.window.show()

    def createTab(self, text, fileName):
        self.CodeEdit = CodeTextEdit(self)
        self.CodeEdit.filename = rf"{fileName.split('/')[-1]}"
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.language = languages[fileName.split('/')[-1].split('.')[-1]]
        self.CodeEdit.setObjectName("CodeEdit")
        txt = "".join(text)
        self.CodeEdit.addText(txt)
        self.tabWidget.addTab(self.CodeEdit, fileName.split('/')[-1])

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            open(tab.fullfilepath, "w").write(tab.toPlainText())

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