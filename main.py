from sys import exit, argv
from os import path, chdir, remove

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QPalette, QColor

from utils.FabricRunCode import *
from utils.programs import *
from widgets.QArgsEditor import ArgsWindow
from widgets.QCodeEditor import CodeEdit
from widgets.SettingsWidget import SettingsWidget
from widgets.Dialog import CustomDialog
from widgets.WelcomeWidget import Ui_Welcome


path_settings = path.dirname(path.realpath(__file__))
settings = load_settings(path_settings)
main_color = settings["settings"]['main_color']#013B81
text_color = settings["settings"]["text_color"]#ABB2BF
first_color = settings["settings"]['first_color']#16171D
second_color = settings["settings"]['second_color']#131313
tab_color = settings["settings"]['tab_color']#1F2228
languages = settings["languages"]
font_size = int(settings["settings"]["fontsize"])
font_size_tab = settings["settings"]["font_size_tab"]


class UiMainWindow(QtWidgets.QMainWindow):
    def setupUi(self):
        menubar = self.menuBar()
        menubar.addMenu("File")
        self.setObjectName("MainWindow")
        if name == 'nt':
            sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
            self.setFixedSize(sizeObject.width(), sizeObject.height()-20)
        else:
            self.setBaseSize(QtCore.QSize(1920,1080))
        self.setStyleSheet(f"background-color:  {first_color};\n"
                        "color: #ffffff")
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setStyleSheet(f"background-color: {first_color}")
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.right_tab_widget = QtWidgets.QWidget()
        self.right_tab_layout = QtWidgets.QHBoxLayout()

        # Убираем отступы, чтобы кнопки располагались ближе друг к другу и к краю
        self.right_tab_layout.setContentsMargins(0, 0, 0, 0)

        # Создаем кнопки
        self.button_run = QtWidgets.QPushButton("")
        self.button_run.setStyleSheet("border:none; padding-right:10px; padding-left:10px; padding-top: 2px; padding-bottom: 5px;")
        self.button_run.setIcon(QtGui.QIcon('src/iconRun.png'))
        self.button_run.clicked.connect(self.actionRunCode)
        self.button_settings = QtWidgets.QPushButton("")
        self.button_settings.setStyleSheet("border:none;padding-right:10px; padding-bottom:5px; padding-top: 2px;")
        self.button_settings.setIcon(QtGui.QIcon('src/iconSettings.png'))
        self.button_settings.clicked.connect(self.actionSettingsLaunch)

        # Добавляем кнопки в QHBoxLayout
        self.right_tab_layout.addWidget(self.button_run)
        self.right_tab_layout.addWidget(self.button_settings)

        # Применяем layout к виджету
        self.right_tab_widget.setLayout(self.right_tab_layout)

        # Помещаем виджет с кнопками в правую часть таба
        self.tabWidget.setCornerWidget(self.right_tab_widget)
        self.tabWidget.setStyleSheet(f"background-color: {main_color};\n"
                                    "color: #000000;\n"
                                    )
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setObjectName("tabWidget")
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.setStyleSheet(
            "QTabBar::close-button {image: url(src/close.png);}"
            "QTabBar {margin-left:10px;}"
            "QTabBar::tab {padding: 1px; background-color: "+tab_color+"; height: 28px; font-size:"+font_size_tab+"px; border: 1px solid"+first_color+"; border-bottom-color:"+first_color+";}"
            "QTabBar::tab:selected {background-color:"+first_color+"; color: #ffffff; border-top-color: #00FFFF; padding:1px;}"
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
        self.menuEdit = QtWidgets.QMenu(self.menubar)
        self.menuEdit.setBaseSize(QtCore.QSize(70, 0))
        self.menuEdit.setStyleSheet("color: #ffffff")
        self.menuEdit.setSeparatorsCollapsible(True)
        self.menuEdit.setObjectName("menuEdit")
        self.menuTools = QtWidgets.QMenu(self.menubar)
        self.menuTools.setBaseSize(QtCore.QSize(70, 0))
        self.menuTools.setStyleSheet("color: #ffffff")
        self.menuTools.setSeparatorsCollapsible(True)
        self.menuTools.setObjectName("menuTools")
        self.menuHelp = QtWidgets.QMenu(self.menubar)
        self.menuHelp.setBaseSize(QtCore.QSize(70, 0))
        self.menuHelp.setStyleSheet("color: #ffffff")
        self.menuHelp.setSeparatorsCollapsible(True)
        self.menuHelp.setObjectName("menuTools")
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
        self.actionRecent = QtWidgets.QAction(self)
        self.actionClose = QtWidgets.QAction(self)
        self.actionClose.setFont(font)
        self.actionClose.setObjectName("actionClose")
        self.actionCloseAll = QtWidgets.QAction(self)
        self.actionCloseAll.setFont(font)
        self.actionCloseAll.setObjectName("actionClose")
        self.actionConfig = QtWidgets.QAction(self)
        self.actionConfig.setFont(font)
        self.actionConfig.setObjectName("actionConfig")
        self.actionSave = QtWidgets.QAction(self)
        self.actionSave.setFont(font)
        self.actionSave.setObjectName("actionSave")
        self.actionSaveAll = QtWidgets.QAction(self)
        self.actionSaveAll.setFont(font)
        self.actionSaveAll.setObjectName("actionSaveAll")
        self.actionSaveAs = QtWidgets.QAction(self)
        self.actionSaveAs.setFont(font)
        self.actionSaveAs.setObjectName("actionSaveAs")
        self.actionRun = QtWidgets.QAction(self)
        self.actionRun.setFont(font)
        self.actionRun.setObjectName("actionRun")
        self.actionNew = QtWidgets.QAction(self)
        self.actionNew.setFont(font)
        self.actionNew.setObjectName("actionNewFile")
        self.actionExit = QtWidgets.QAction(self)
        self.actionExit.setFont(font)
        self.actionExit.setObjectName("actionExit")
        self.actionSettings = QtWidgets.QAction(self)
        self.actionSettings.setFont(font)
        self.actionSettings.setObjectName("actionSettings")
        #
        self.actionReturn = QtWidgets.QAction(self)
        self.actionReturn.setFont(font)
        self.actionReturn.setObjectName("actionReturn")
        self.actionRepeat = QtWidgets.QAction(self)
        self.actionRepeat.setFont(font)
        self.actionRepeat.setObjectName("actionRepeat")
        self.actionCut = QtWidgets.QAction(self)
        self.actionCut.setFont(font)
        self.actionCut.setObjectName("actionCut")
        self.actionCopy = QtWidgets.QAction(self)
        self.actionCopy.setFont(font)
        self.actionCopy.setObjectName("actionCopy")
        self.actionInsert = QtWidgets.QAction(self)
        self.actionInsert.setFont(font)
        self.actionInsert.setObjectName("actionInsert")
        self.actionHighlight = QtWidgets.QAction(self)
        self.actionHighlight.setFont(font)
        self.actionHighlight.setObjectName("actionHighlight")
        self.actionShell = QtWidgets.QAction(self)
        self.actionShell.setFont(font)
        self.actionShell.setObjectName("actionShell")
        self.actionGit = QtWidgets.QAction(self)
        self.actionGit.setFont(font)
        self.actionGit.setObjectName("actionShell")
        #
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.actionRecent)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionClose)
        self.menuFile.addAction(self.actionCloseAll)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSaveAll)
        self.menuFile.addAction(self.actionSaveAs)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuEdit.addAction(self.actionReturn)
        self.menuEdit.addAction(self.actionRepeat)
        self.menuEdit.addAction(self.actionCut)
        self.menuEdit.addAction(self.actionCopy)
        self.menuEdit.addAction(self.actionInsert)
        self.menuEdit.addAction(self.actionHighlight)
        self.menuTools.addAction(self.actionShell)
        self.menuTools.addAction(self.actionSettings)
        self.menuHelp.addAction(self.actionGit)
        self.menuRun.addAction(self.actionRun)
        self.menuRun.addAction(self.actionConfig)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuRun.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.addWidget(self.tabWidget)
        self.retranslateUi()
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(self)
        self.config_path = path.dirname(path.realpath(__file__)) + r"\config\launchArgs.json"
        self.actionRun.triggered.connect(self.actionRunCode)
        self.actionOpen.triggered.connect(self.actionOpenFile)
        self.actionSave.triggered.connect(self.actionSaveFile)
        self.actionClose.triggered.connect(self.actionCloseFile)
        self.actionCloseAll.triggered.connect(self.actionCloseAllFiles)
        self.actionSaveAs.triggered.connect(self.actionSaveAsFile)
        self.actionSaveAll.triggered.connect(self.actionSaveAllFiles)
        self.actionConfig.triggered.connect(self.actionArgsLaunch)
        self.actionNew.triggered.connect(self.actionNewFile)
        self.actionSettings.triggered.connect(self.actionSettingsLaunch)
        self.actionReturn.triggered.connect(self.actionReturnText)
        self.actionRepeat.triggered.connect(self.actionRepeatText)
        self.actionCut.triggered.connect(self.actionCutText)
        self.actionCopy.triggered.connect(self.actionCopyText)
        self.actionInsert.triggered.connect(self.actionInsertText)
        self.actionHighlight.triggered.connect(self.actionHighlightText)
        self.actionExit.triggered.connect(self.actionExitProgram)
        self.actionShell.triggered.connect(self.actionShellChoice)
        self.actionGit.triggered.connect(self.actionGitOpen)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.files = loadSession()
        self.loadSession(self.files)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "PyScribe"))
        self.menuFile.setTitle(_translate("MainWindow", "     File     "))
        self.menuRun.setTitle(_translate("MainWindow", "     Run     "))
        self.menuEdit.setTitle(_translate("MainWindow", "      Edit    "))
        self.menuTools.setTitle(_translate("MainWindow", "      Tools    "))
        self.menuHelp.setTitle(_translate("MainWindow", "      Help    "))
        self.actionConfig.setText(_translate("MainWindow", "Launch parameters"))
        self.actionConfig.setShortcut(_translate("MainWindow", "Shift+F4"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionNew.setShortcut(_translate("MainWindow", "Ctrl+N"))
        self.actionOpen.setText(_translate("MainWindow", "Open..."))
        self.actionOpen.setShortcut(_translate("MainWindow", "Ctrl+O"))
        self.actionRecent.setText(_translate("MainWindow", "Recent"))
        self.actionClose.setShortcut(_translate("MainWindow", "Ctrl+W"))
        self.actionClose.setText(_translate("MainWindow", "Close"))
        self.actionCloseAll.setShortcut(_translate("MainWindow", "Ctrl+Shift+W"))
        self.actionCloseAll.setText(_translate("MainWindow", "Close all"))
        self.actionReturn.setShortcut(_translate("MainWindow", "Ctrl+Z"))
        self.actionReturn.setText(_translate("MainWindow", "Return"))
        self.actionRepeat.setShortcut(_translate("MainWindow", "Ctrl+Y"))
        self.actionRepeat.setText(_translate("MainWindow", "Repeat"))
        self.actionCut.setShortcut(_translate("MainWindow", "Ctrl+X"))
        self.actionCut.setText(_translate("MainWindow", "Cut"))
        self.actionCopy.setShortcut(_translate("MainWindow", "Ctrl+C"))
        self.actionCopy.setText(_translate("MainWindow", "Copy"))
        self.actionInsert.setShortcut(_translate("MainWindow", "Ctrl+V"))
        self.actionInsert.setText(_translate("MainWindow", "Insert"))
        self.actionHighlight.setShortcut(_translate("MainWindow", "Ctrl+A"))
        self.actionHighlight.setText(_translate("MainWindow", "Highlight"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionSave.setShortcut(_translate("MainWindow", "Ctrl+S"))
        self.actionSaveAll.setText(_translate("MainWindow", "Save all"))
        self.actionSaveAll.setShortcut(_translate("MainWindow", "Ctrl+Alt+S"))
        self.actionSaveAs.setText(_translate("MainWindow", "Save as"))
        self.actionSaveAs.setShortcut(_translate("MainWindow", "Ctrl+Shift+S"))
        self.actionRun.setText(_translate("MainWindow", "Run"))
        self.actionRun.setShortcut(_translate("MainWindow", "Ctrl+Shift+X"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))
        self.actionExit.setShortcut(_translate("MainWindow", "Alt+F4"))
        self.actionSettings.setText(_translate("MainWindow", "Settings"))
        self.actionShell.setText(_translate("MainWindow", "Set shell"))
        self.actionGit.setText(_translate("MainWindow", "Github Issues"))

    def actionExitProgram(self):
        self.saveOpenFiles()
        saveSession(self.files)
        self.close()

    def actionCloseFile(self):
        currentIndex = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        if active_tab_widget.language != "bin" and active_tab_widget.language != "out" and active_tab_widget.language != "exe":
            self.actionSaveFile(currentIndex)
    
    def setAsterisk(self):
        index = self.tabWidget.currentIndex()
        text = self.tabWidget.tabText(index)
        if "*" not in text:
            self.tabWidget.setTabText(index, f"      {text.strip(' ')}     *    ")

    def setTabText(self, index, text):
        self.tabWidget.setTabText(index, text)

    def removeAsterisk(self, index):
        text = self.tabWidget.tabText(index)
        if "*" in text:
            text = text.replace("*", " ")
            self.tabWidget.setTabText(index, text)

    def actionCloseAllFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            self.files.remove(tab.fullfilepath)
            self.tabWidget.removeTab(i)

    def actionSaveAsFile(self):
        active_tab_widget = self.tabWidget.widget(self.tabWidget.currentIndex())
        if active_tab_widget:
            if not active_tab_widget.welcome:
                old_name = active_tab_widget.fullfilepath
                options = QtWidgets.QFileDialog.Options()
                fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save As", "", "All Files (*);;Text Files (*.txt)", options=options)
                open(fileName, "w").write(active_tab_widget.toPlainText())
                self.removeAsterisk(self.tabWidget.currentIndex())
                remove(old_name)
                self.setTabText(self.tabWidget.currentIndex(), f"       {path.basename(fileName)}       ")


    def actionGitOpen(self):
        pass

    def actionShellChoice(self):
        self.actionSettingsLaunch()

    def actionSaveAllFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            self.removeAsterisk(i)
            if tab.language != "bin" and tab.language != "out" and tab.language != "exe":
                open(tab.fullfilepath, "w").write(tab.toPlainText())
    
    def actionReturnText(self):
        pass

    def actionRepeatText(self):
        pass

    def actionCutText(self):
        pass

    def actionCopyText(self):
        pass

    def actionInsertText(self):
        pass

    def actionHighlightText(self):
        pass

    def loadSession(self, files):
        if files != []:
            for file in files:
                try:
                    if path.basename(file).split('/')[-1].split('.')[-1] not in ["bin", "exe", "out"]:
                        self.createTab(open(rf"{file}", "r").readlines(), file)
                    else:
                        self.createTab(open(rf"{file}", "rb").read(), file)
                except Exception as e:
                    print(e)
        else:
            self.welcomeWidget()

    def welcomeWidget(self):
        widget = Ui_Welcome(self.tabWidget, settings)
        widget.NewFileButton.clicked.connect(self.actionNewFile)
        widget.OpenFileButton.clicked.connect(self.actionOpenFile)
        self.tabWidget.addTab(widget, "         Welcome         ")

    def closeTab(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        try:
            self.files.remove(active_tab_widget.fullfilepath)
        except:
            pass
        self.tabWidget.removeTab(currentIndex)
        try:
            if active_tab_widget.language != "bin" and active_tab_widget.language != "out" and active_tab_widget.language != "exe":
                self.actionSaveFile(currentIndex)
        except:
            pass

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        CodeEdit = self.tabWidget.widget(active_tab_index)
        if not CodeEdit.welcome:
            with open(CodeEdit.fullfilepath, 'w') as codefile:
                codefile.write(CodeEdit.toPlainText())
            try:
                if self.CodeEdit.language == "c":
                    compile_program_c(CodeEdit.fullfilepath)
                elif self.CodeEdit.language == "cpp":
                    compile_program_cpp(CodeEdit.fullfilepath)
                try:
                    RunCodeClass(self.CodeEdit.fullfilepath, self.CodeEdit.filename, self.CodeEdit.language).process()
                except Exception as e:
                    print(e)
                    CustomDialog("Error running code").exec()
            except Exception as e:
                print(e)
                CustomDialog("Compilation error").exec()
        else:
            pass

    def actionSaveFile(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        if active_tab_widget:
            if not active_tab_widget.welcome:
                self.removeAsterisk(currentIndex)
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
            CodeEdit = active_tab_widget.findChild(CodeEdit, "CodeEdit")
            self.window = ArgsWindow(CodeEdit.filename, CodeEdit.fullfilepath, CodeEdit.language)
            self.window.show()

    def actionSettingsLaunch(self):
        window = SettingsWidget(settings, path_settings)
        self.tabWidget.addTab(window, "         Settings         ")

    def createTab(self, text, fileName):
        lang = fileName.split('/')[-1].split('.')[-1]
        self.CodeEdit = CodeEdit(self, languages[lang],[], settings)
        self.CodeEdit.filename = path.basename(fileName)
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.setObjectName("CodeEdit")
        self.CodeEdit.textedit.textChanged.connect(self.setAsterisk)
        if self.CodeEdit.language == "bin" or self.CodeEdit.language == "out" or self.CodeEdit.language == "exe":
            self.CodeEdit.addText(text)
        else:
            self.CodeEdit.setPlainText("".join(text))
        self.tabWidget.addTab(self.CodeEdit, f"       {fileName.split('/')[-1]}        ")

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            try:
                if tab.language != "bin" and tab.language != "out" and tab.language != "exe":
                    open(tab.fullfilepath, "w").write(tab.toPlainText())
            except:
                pass

    def closeEvent(self, event):
        self.saveOpenFiles()
        saveSession(self.files)
        event.accept()




if __name__ == "__main__":
    scriptDir = path.dirname(path.realpath(__file__))
    chdir(path.abspath(__file__).replace(path.basename(__file__), ""))
    app = QtWidgets.QApplication(argv)
    app.setWindowIcon(QIcon(scriptDir + path.sep + 'src/icon2.png'))
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QtCore.Qt.black)
    palette.setColor(QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QPalette.Text, QtCore.Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)
    MainWindow = UiMainWindow()
    MainWindow.setupUi()
    MainWindow.setWindowIcon(QIcon(scriptDir + path.sep + 'src/icon2.png'))
    MainWindow.show()
    exit(app.exec_())