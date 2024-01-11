from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QIcon
from subprocess import Popen
from os import path, system
from widgets.QCodeEditor import CodeTextEdit
from basicInterface import Ui_MainWindow
from utils.programs import *
from sys import exit, argv, executable
from widgets.QArgsEditor import ArgsWindow
from utils.FabricRunCode import *
from widgets.QTerminal import *
from widgets.HexViewer import HexViewer


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
            "css": "css",
            "bin": "bin",
            "out": "out",
            "exe": "exe"
            }


class UiMainWindow(Ui_MainWindow):
    def setupUiCustom(self):
        self.setupUi()
        self.config_path = path.dirname(path.realpath(__file__))+r"\config\launchArgs.json"
        self.settings = load_settings(path.dirname(path.realpath(__file__)))
        print(self.settings)
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.actionConfig.triggered.connect(self.actionArgsLaunch)
        self.actionNew.triggered.connect(self.actionNewFile)
        self.tabWidget.tabCloseRequested.connect(self.closeTab) 
        self.files = loadSession()
        self.loadSession(self.files)

    def loadSession(self, files):
        for file in files:
            try:
                self.createTab(open(rf"{file}", "r").readlines(), file)
            except UnicodeDecodeError:
                self.createTab(open(rf"{file}", "rb").read(), file)

    def closeTab (self, currentIndex):
        active_tab_widget: CodeTextEdit = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        if active_tab_widget.language != "bin" and active_tab_widget.language != "out" and active_tab_widget.language != "exe":
            self.actionSaveFile(currentIndex)
        if self.tabWidget.count() == 0:
            self.ResultText.setPlainText("")

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        CodeEdit: CodeTextEdit = self.tabWidget.widget(active_tab_index)
        
        self.ResultText.setPlainText("")

        with open(CodeEdit.fullfilepath, 'w') as codefile:
            codefile.write(CodeEdit.toPlainText())

        if CodeEdit.language == "python":
            if executable:
                self.ResultText.insertColorText("found interpreter", "green")
            else:
                self.ResultText.insertColorText("python interpreter not found", "red")

        elif CodeEdit.language == "c":
            self.ResultText.insertColorText(f"compiling {CodeEdit.filename}")
            exe_path = compile_program_c(CodeEdit.fullfilepath)
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
            if languages[file_path.split('/')[-1].split('.')[-1]] != "bin" and languages[file_path.split('/')[-1].split('.')[-1]] != "out" and languages[file_path.split('/')[-1].split('.')[-1]] != "exe":
                file = open(file_path, "r")
                text = "".join(file.readlines())
            else:
                file = open(file_path, "rb")            
                text = file.read()
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
        if languages[fileName.split('/')[-1].split('.')[-1]] not in ["bin", "out", "exe"]:

            self.CodeEdit = CodeTextEdit(self)
            self.CodeEdit.filename = rf"{fileName.split('/')[-1]}"
            self.CodeEdit.fullfilepath = rf"{fileName}"
            self.CodeEdit.language = languages[fileName.split('/')[-1].split('.')[-1]]
            self.CodeEdit.setObjectName("CodeEdit")
            self.tabWidget.addTab(self.CodeEdit, fileName.split('/')[-1])
        else:
            self.HexViewer = HexViewer(self) 
            self.HexViewer.filename = rf"{fileName.split('/')[-1]}"
            self.HexViewer.fullfilepath = rf"{fileName}"
            self.HexViewer.language = languages[fileName.split('/')[-1].split('.')[-1]]
            self.HexViewer.setObjectName("HewViewer")
            self.HexViewer.load_file(text)
            self.tabWidget.addTab(self.HexViewer, fileName.split('/')[-1])
            

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab: HexViewer | CodeEdit = self.tabWidget.widget(i)
            if tab.language != "bin" and tab.language != "out" and tab.language != "exe":
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
