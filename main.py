from sys import exit, argv, executable

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon

from utils.FabricRunCode import *
from utils.programs import *
from widgets.QArgsEditor import ArgsWindow
from widgets.QCodeEditor import CodeTextEdit
from widgets.SettingsWidget import SettingsWidget
from widgets.QTerminal import QTerminal



path_settings = path.dirname(path.realpath(__file__))
settings = load_settings(path_settings)
main_color = settings["settings"]['main_color']#1e1f1e
first_color = settings["settings"]['first_color']#191819
second_color = settings["settings"]['second_color']#131313
languages = settings["languages"]


class UiMainWindow(QtWidgets.QMainWindow):

    def setupUi(self):
        menubar = self.menuBar()
        fmenu = menubar.addMenu("File")
        self.setObjectName("MainWindow")
        self.setMinimumSize(QtCore.QSize(1080, 720))
        self.setMaximumSize(QtCore.QSize(4050, 4050))
        self.setStyleSheet(f"background-color:  {first_color};\n"
                           "color: #ffffff")
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setStyleSheet(f"background-color: {first_color}")
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setStyleSheet(f"background-color: {main_color};\n"
                                     "color: #000000\n")
        self.tabWidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setObjectName("tabWidget")
        self.tabWidget.setStyleSheet(
            "QTabBar::tab {background-color: #1e1f1e; width: 150px; height: 30px; border-width: 1px; padding-right: 20px; font-size: 16px; letter-spacing: 1px; border: 1px solid blue; border-top-right-radius: 8px; border-top-left-radius: 8px;}"
            "QTabBar::tab:selected {background-color: #131313; border: 1px solid #3b3b3b; color: #d4d4d4;border-bottom-color: #131313;}"
            "QTabBar::tab:!selected {background-color: #1e1f1e; border: 1px solid #4f4843;color: #d4d4d4; border-bottom-color: #3b3b3b;}"
        )
        self.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(self)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1500, 30))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setBaseSize(QtCore.QSize(70, 0))
        self.menuFile.setStyleSheet("color: #ffffff")
        self.menuFile.setSeparatorsCollapsible(True)
        self.menuFile.setObjectName("menuFile")
        self.menuRun = QtWidgets.QMenu(self.menubar)
        self.menuRun.setBaseSize(QtCore.QSize(70, 0))
        self.menuRun.setStyleSheet("color: #ffffff")
        self.menuRun.setSeparatorsCollapsible(True)
        self.menuRun.setObjectName("menuRun")
        self.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        self.actionOpen = QtWidgets.QAction(self)
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(10)
        self.actionOpen.setFont(font)
        self.actionOpen.setObjectName("actionOpen")
        self.actionConfig = QtWidgets.QAction(self)
        self.actionConfig.setFont(font)
        self.actionConfig.setObjectName("actionConfig")
        self.actionSave = QtWidgets.QAction(self)
        self.actionSave.setFont(font)
        self.actionSave.setObjectName("actionSave")
        self.actionRun = QtWidgets.QAction(self)
        self.actionRun.setFont(font)
        self.actionRun.setObjectName("actionRun")
        self.actionNew = QtWidgets.QAction(self)
        self.actionNew.setFont(font)
        self.actionNew.setObjectName("actionNewFile")
        self.actionSettings = QtWidgets.QAction(self)
        self.actionSettings.setFont(font)
        self.actionSettings.setObjectName("actionSettings")
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionRun)
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionSettings)
        self.menuRun.addAction(self.actionConfig)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuRun.menuAction())
        self.ResultText = QTerminal(self.centralwidget)
        self.ResultText.setStyleSheet(f"background-color: {second_color};\n"
                                      "color: #ffffff;\n"
                                      "padding: 7px; letter-spacing: 1px; padding-top: 40px;border-radius: 10px; border: 1px solid #3b3b3b;")
        self.ResultText.setObjectName("ResultText")
        self.verticalLayout.addWidget(self.tabWidget, 5)
        self.verticalLayout.addWidget(self.ResultText, 2)
        self.retranslateUi()
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(self)
        self.config_path = path.dirname(path.realpath(__file__)) + r"\config\launchArgs.json"
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.actionConfig.triggered.connect(self.actionArgsLaunch)
        self.actionNew.triggered.connect(self.actionNewFile)
        self.actionSettings.triggered.connect(self.actionSettingsLaunch)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.files = loadSession()
        self.loadSession(self.files)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "PyScribe"))
        self.menuFile.setTitle(_translate("MainWindow", "     File     "))
        self.menuRun.setTitle(_translate("MainWindow", "     Run     "))
        self.actionConfig.setText(_translate("MainWindow", "Launch parameters"))
        self.actionConfig.setShortcut(_translate("MainWindow", "Shift+F4"))
        self.actionOpen.setText(_translate("MainWindow", "Open"))
        self.actionOpen.setShortcut(_translate("MainWindow", "Shift+F5"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionSave.setShortcut(_translate("MainWindow", "Ctrl+S"))
        self.actionRun.setText(_translate("MainWindow", "Run"))
        self.actionRun.setShortcut(_translate("MainWindow", "Ctrl+Shift+X"))
        self.actionNew.setText(_translate("MainWindow", "New File"))
        self.actionNew.setShortcut(_translate("MainWindow", "Shift+F6"))
        self.actionSettings.setText(_translate("MainWindow", "Settings"))

    def setupUiCustom(self):
        self.setupUi()

        '''sett = SettingsWidget()
        sett.show()'''

    def loadSession(self, files):
        for file in files:
            try:
                self.createTab(open(rf"{file}", "r").readlines(), file)
            except UnicodeDecodeError:
                self.createTab(open(rf"{file}", "rb").read(), file)

    def closeTab(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        if active_tab_widget.language != "bin" and active_tab_widget.language != "out" and active_tab_widget.language != "exe":
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
            if languages[file_path.split('/')[-1].split('.')[-1]] != "bin" and languages[
                file_path.split('/')[-1].split('.')[-1]] != "out" and languages[
                file_path.split('/')[-1].split('.')[-1]] != "exe":
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

    def actionSettingsLaunch(self):
        window = SettingsWidget(settings, path_settings)
        window.show()

    def createTab(self, text, fileName):
        self.CodeEdit = CodeTextEdit(self)
        self.CodeEdit.filename = rf"{fileName.split('/')[-1]}"
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.language = languages[fileName.split('/')[-1].split('.')[-1]]
        self.CodeEdit.setPlainText("".join(text))
        self.CodeEdit.setObjectName("CodeEdit")
        if self.CodeEdit.language == "bin" or self.CodeEdit.language == "out" or self.CodeEdit.language == "exe":
            self.CodeEdit.addText(text)
        self.tabWidget.addTab(self.CodeEdit, fileName.split('/')[-1])

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            if tab.language != "bin" and tab.language != "out" and tab.language != "exe":
                open(tab.fullfilepath, "w").write(tab.toPlainText())

    def closeEvent(self, event):
        self.saveOpenFiles()
        saveSession(self.files)
        event.accept()


if __name__ == "__main__":
    scriptDir = path.dirname(path.realpath(__file__))
    app = QtWidgets.QApplication(argv)
    app.setWindowIcon(QIcon(scriptDir + path.sep + 'src/icon2.png'))
    MainWindow = UiMainWindow()
    MainWindow.setupUiCustom()
    MainWindow.setWindowIcon(QIcon(scriptDir + path.sep + 'src/icon2.png'))
    MainWindow.show()
    exit(app.exec_())
