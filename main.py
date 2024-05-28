from functools import partial
from os import chdir, system, name, path
from sys import exit, argv

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QPalette, QColor

from utils.FabricRunCode import *
from utils.programs import *
from widgets.Dialog import CustomDialog
from widgets.QArgsEditor import ArgsWindow
from widgets.QCodeEditor import CodeEdit
from widgets.SettingsWidget import SettingsWidget
from widgets.WelcomeWidget import Ui_Welcome
from widgets.TabWidget import TabWidget
from widgets.PushButtons import *
from widgets.Explorer import Explorer


path_settings = path.dirname(path.realpath(__file__))
settings = load_settings(path_settings)
list_recent_files = loadRecent()
main_color = settings["settings"]["main_color"]  # 013B81
text_color = settings["settings"]["text_color"]  # ABB2BF
first_color = settings["settings"]["first_color"]  # 16171D
second_color = settings["settings"]["second_color"]  # 131313
tab_color = settings["settings"]["tab_color"]  # 1F2228
languages = settings["languages"]
languages_type = settings["languages_type"]
font_size = int(settings["settings"]["fontsize"])
font_size_tab = settings["settings"]["font_size_tab"]


class UiMainWindow(QtWidgets.QMainWindow):
    def setupUi(self):
        self.setObjectName("MainWindow")
        QtCore.QMetaObject.connectSlotsByName(self)
        
        #настройки дисплея
        if name == "nt":
            sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
            self.setFixedSize(sizeObject.width(), sizeObject.height() - 20)
        else:
            self.setBaseSize(QtCore.QSize(1920, 1080))
            
        #базовые переменные
        self.unsavedfiles = 0
        self.sidebar_visible = False
        self.files = loadSession()
        self.config_path = (
            path.dirname(path.realpath(__file__)) + r"\config\launchArgs.json"
        )
        
        #объявление объектов интерфейса
        #---интерфейс---
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.setCentralWidget(self.centralwidget)
        self.tabWidget = TabWidget(self.centralwidget, settings)
        self.up_button = UpPushButton("")
        self.delete_button = DeletePushButton("")
        self.copy_button = CopyPushButton("")
        self.paste_button = PastePushButton("")
        self.buttons_explorer_layout = QtWidgets.QHBoxLayout()
        self.buttons_explorer_layout.setSpacing(0)
        self.buttons_explorer_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_explorer_layout.addWidget(self.up_button)
        self.buttons_explorer_layout.addWidget(self.copy_button)
        self.buttons_explorer_layout.addWidget(self.paste_button)
        self.buttons_explorer_layout.addWidget(self.delete_button)
        
        self.tree = Explorer()
        
        self.explorer_layout = QtWidgets.QVBoxLayout()
        self.explorer_layout.setSpacing(0)
        self.explorer_layout.setContentsMargins(0, 0, 0, 0)
        self.explorer_layout.addLayout(self.buttons_explorer_layout)
        self.explorer_layout.addWidget(self.tree)
        
        self.horLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horLayout.setObjectName("horLayout")
        self.horLayout.setSpacing(0)
        self.horLayout.setContentsMargins(0, 0, 0, 0)
        self.horLayout.addLayout(self.explorer_layout)
        self.horLayout.addWidget(self.tabWidget)
        
        #---меню---
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(10)

        self.menubar = self.menuBar()
        self.menubar.addMenu("File")
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
        self.actionOpen.setFont(font)
        self.actionOpen.setObjectName("actionOpen")
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
        self.actionCache = QtWidgets.QAction(self)
        self.actionCache.setFont(font)
        self.actionCache.setObjectName("actionExit")
        self.actionSettings = QtWidgets.QAction(self)
        self.actionSettings.setFont(font)
        self.actionSettings.setObjectName("actionSettings")
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
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionOpen)
        self.actionRecent = self.menuFile.addMenu("Recent")
        self.actionClearRecent = QtWidgets.QAction("   Clear", self)
        self.actionRecent.addAction(self.actionClearRecent)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionClose)
        self.menuFile.addAction(self.actionCloseAll)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSaveAll)
        self.menuFile.addAction(self.actionSaveAs)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionCache)
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
        self.actionRecent_0 = None
        self.actionRecent_1 = None
        self.actionRecent_2 = None
        self.actionRecent_3 = None
        self.actionRecent_4 = None
        
        
        #---привязки---
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
        self.actionCache.triggered.connect(self.actionClearCache)
        self.actionRepeat.triggered.connect(self.actionRepeatText)
        self.actionCut.triggered.connect(self.actionCutText)
        self.actionCopy.triggered.connect(self.actionCopyText)
        self.actionInsert.triggered.connect(self.actionInsertText)
        self.actionHighlight.triggered.connect(self.actionHighlightText)
        self.actionExit.triggered.connect(self.actionExitProgram)
        self.actionShell.triggered.connect(self.actionShellChoice)
        self.actionGit.triggered.connect(self.actionGitOpen)
        self.actionClearRecent.triggered.connect(self.clearMenuRecent)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        self.tabWidget.button_run.clicked.connect(self.actionRunCode)
        self.tabWidget.button_settings.clicked.connect(self.actionSettingsLaunch)
        self.tabWidget.toggle_button.clicked.connect(self.toggle_sidebar)
        self.tree.doubleClicked.connect(self.open_file_explorer)
        self.up_button.clicked.connect(self.tree.go_up)
        
        #---стили---
        self.setStyleSheet(f"background-color: #131313;")
        self.centralwidget.setStyleSheet("QWidget#centralwidget {background-color: #25263b;}")
        #---вызовы локальных функций
        self.actionLoadRecent()
        restore_backup()
        self.loadSession(self.files)
        self.retranslateUi()
        
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
        self.actionRecent.setTitle(_translate("MainWindow", "Recent"))
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
        self.actionCache.setText(_translate("MainWindow", "Clear cache"))
        self.actionCache.setShortcut(_translate("MainWindow", "Ctrl+Del"))
        self.actionExit.setShortcut(_translate("MainWindow", "Alt+F4"))
        self.actionSettings.setText(_translate("MainWindow", "Settings"))
        self.actionShell.setText(_translate("MainWindow", "Set shell"))
        self.actionGit.setText(_translate("MainWindow", "Github Issues"))

    def open_file_explorer(self, index):
        if not self.tree.model.isDir(index):
            file_path = self.tree.model.filePath(index)
            if file_path.split("/")[-1].split(".")[-1] in settings["languages"]:
                if (
                    settings["languages_type"][file_path.split("/")[-1].split(".")[-1]]
                    == 0
                ):
                    file = open(file_path, "rb")
                    text = file.read()
                else:
                    file = open(file_path, "r", encoding="utf-8")
                    text = "".join(file.readlines())
            else:
                file = open(file_path, "r", encoding="utf-8")
                text = "".join(file.readlines())
                backup(file_path)
                self.files.append(file_path)
            self.tree.setRootIndex(
                self.tree.model.index(QtCore.QFileInfo(file_path).absolutePath())
            )
            self.createTab(text, file_path)
        else:
            self.tree.setRootIndex(index)

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.tree.hide()
            self.up_button.hide()
            self.delete_button.hide()
            self.copy_button.hide()
            self.paste_button.hide()
        else:
            self.tree.show()
            self.up_button.show()
            self.delete_button.show()
            self.copy_button.show() 
            self.paste_button.show()
        self.sidebar_visible = not self.sidebar_visible

    def go_up(self):
        current_index = self.tree.currentIndex()
        parent_index = self.tree.model.parent(current_index)
        if parent_index.isValid():
            self.tree.setRootIndex(parent_index)

    def actionLoadRecent(self):
        list_recent_files = loadRecent()
        if len(list_recent_files) != 0:
            self.actionRecent.clear()
            for i in range(len(list_recent_files)):
                try:
                    lang = path.basename(list_recent_files[i]).split("/")[-1].split(".")[-1]
                    if lang in languages:
                        if settings["languages_type"][lang] != 0:
                            text = "".join(
                                open(
                                    rf"{list_recent_files[i]}", "r", encoding="utf-8"
                                ).readlines()
                            )
                        else:
                            text = open(rf"{list_recent_files[i]}", "rb").read()
                    else:
                        text = "".join(
                            open(
                                rf"{list_recent_files[i]}", "r", encoding="utf-8"
                            ).readlines()
                        )
                    locals()["self.actionRecent_" + str(i)] = QtWidgets.QAction(
                        "   " + list_recent_files[i], self
                    )
                    locals()["self.actionRecent_" + str(i)].triggered.connect(
                        partial(
                            self.createTabRecent, text=text, fileName=list_recent_files[i]
                        )
                    )
                    self.actionRecent.addAction(locals()["self.actionRecent_" + str(i)])
                except:
                    pass
        self.actionRecent.addSeparator()
        self.actionRecent.addAction(self.actionClearRecent)

    def clearMenuRecent(self):
        self.actionRecent.clear()
        self.actionRecent.addAction(self.actionClearRecent)
        removeRecentFile()
        self.actionLoadRecent()

    def createTabRecent(self, text, fileName):
        self.popRecentFile(fileName)
        self.createTab(text, fileName)

    def actionExitProgram(self):
        self.saveOpenFiles()
        saveSession(self.files)
        self.close()

    def actionCloseFile(self):
        currentIndex = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        if active_tab_widget.mode != 0:
            self.actionSaveFile(currentIndex)

    def setAsterisk(self):
        index = self.tabWidget.currentIndex()
        text = self.tabWidget.tabText(index)
        widget = self.tabWidget.widget(index)
        if "*" not in text and not widget.welcome:
            self.unsavedfiles += 1
            self.tabWidget.setTabText(index, f"      {text.strip(' ')}     *    ")

    def setTabText(self, index, text):
        self.tabWidget.setTabText(index, text)

    def removeAsterisk(self, index):
        index_tab = self.tabWidget.currentIndex()
        text = self.tabWidget.tabText(index_tab)
        if "*" in text:
            self.unsavedfiles -= 1
            text = text.replace("*", " ")
            self.tabWidget.setTabText(index_tab, text)

    def actionCloseAllFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            self.files.remove(tab.fullfilepath)
            self.tabWidget.removeTab(i)

    def actionClearCache(self):
        try:
            CustomDialog("Cache is cleared")
            clearCache()
            self.actionClearRecent()
            self.actionCloseAllFiles()
            self.welcomeWidget()
        except:
            CustomDialog("Cache is not cleared")

    def actionSaveAsFile(self):
        active_tab_widget = self.tabWidget.widget(self.tabWidget.currentIndex())
        if active_tab_widget:
            if not active_tab_widget.welcome and active_tab_widget.mode != 0:
                old_name = active_tab_widget.fullfilepath
                options = QtWidgets.QFileDialog.Options()
                fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self,
                    "Save As",
                    "",
                    "All Files (*);;Text Files (*.txt)",
                    options=options,
                )
                open(fileName, "w", encoding="utf-8").write(
                    active_tab_widget.toPlainText()
                )
                self.removeAsterisk(self.tabWidget.currentIndex())
                remove(old_name)
                self.setTabText(
                    self.tabWidget.currentIndex(),
                    f"       {path.basename(fileName)}       ",
                )

    def actionGitOpen(self):
        pass

    def actionShellChoice(self):
        self.actionSettingsLaunch()

    def actionSaveAllFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            self.removeAsterisk(i)
            if tab.mode != 0:
                open(tab.fullfilepath, "w", encoding="utf-8").write(tab.toPlainText())

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
        if len(files) > 0:
            for file in files:
                try:
                    if (
                        path.basename(file).split("/")[-1].split(".")[-1]
                        not in settings["languages"]
                    ):
                        self.createTab(open(rf"{file}", "r").readlines(), file)
                    else:
                        if (
                            settings["languages_type"][
                                path.basename(file).split("/")[-1].split(".")[-1]
                            ]
                            == 1
                        ):
                            self.createTab(open(rf"{file}", "r").readlines(), file)
                        else:
                            self.createTab(open(rf"{file}", "rb").read(), file)
                except Exception as e:
                    print(e)
        else:
            self.welcomeWidget()

    def welcomeWidget(self):
        widget = Ui_Welcome(self.centralwidget, settings)
        widget.NewFileButton.clicked.connect(self.actionNewFile)
        widget.OpenFileButton.clicked.connect(self.actionOpenFile)
        self.tabWidget.addTab(widget, "         Welcome         ")

    def closeTab(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        try:
            path = active_tab_widget.fullfilepath
            self.files.remove(path)
        except:
            pass
        try:
            if "*" in self.tabWidget.tabText(currentIndex):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "",
                    "Сохранить файл перед закрытием?",
                    QtWidgets.QMessageBox.Yes
                    | QtWidgets.QMessageBox.No
                    | QtWidgets.QMessageBox.Cancel,
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    if active_tab_widget.mode != 0:
                        self.actionSaveFile(currentIndex)
                    self.addRecentFile(path)
                elif reply == QtWidgets.QMessageBox.No:
                    self.addRecentFile(path)
                    self.tabWidget.removeTab(currentIndex)
                elif reply == QtWidgets.QMessageBox.Cancel:
                    pass
            else:
                self.addRecentFile(path)
                self.tabWidget.removeTab(currentIndex)
        except Exception as e:
            print(e)
            CustomDialog("Tab closing error").exec()

    def addRecentFile(self, pathfile: str):
        if pathfile not in list_recent_files:
            list_recent_files.append(pathfile)
            saveRecent(list_recent_files)
            self.actionLoadRecent()

    def popRecentFile(self, pathfile: str):
        if pathfile in list_recent_files:
            list_recent_files.append(pathfile)
            saveRecent(list_recent_files)
            self.actionLoadRecent()

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        CodeEdit = self.tabWidget.widget(active_tab_index)
        if CodeEdit.mode == 1:
            if not CodeEdit.welcome:
                with open(CodeEdit.fullfilepath, "w", encoding="utf-8") as codefile:
                    codefile.write(CodeEdit.toPlainText())
                try:
                    if self.CodeEdit.language == "c":
                        compile_program_c(CodeEdit.fullfilepath)
                    elif self.CodeEdit.language == "cpp":
                        compile_program_cpp(CodeEdit.fullfilepath)
                    try:
                        proc = RunCodeClass(
                            self.CodeEdit.fullfilepath,
                            self.CodeEdit.filename,
                            self.CodeEdit.language,
                        )
                        if proc.command is None:
                            CustomDialog("Launch error").exec()
                        else:
                            proc.process()
                    except Exception as e:
                        print(e)
                        CustomDialog("Error running code").exec()
                except Exception as e:
                    print(e)
                    CustomDialog("Compilation error").exec()
            else:
                print("Welcome widget not supported for launch")

    def actionSaveFile(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        if active_tab_widget:
            if not active_tab_widget.welcome:
                self.removeAsterisk(currentIndex)
                open(active_tab_widget.fullfilepath, "w", encoding="UTF-8").write(
                    active_tab_widget.toPlainText()
                )

    def actionOpenFile(self):
        fileDialog = QtWidgets.QFileDialog()
        fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        fileDialog.setNameFilter("All files(*.*)")
        if fileDialog.exec_():
            file_path = fileDialog.selectedFiles()[0]
            if file_path.split("/")[-1].split(".")[-1] in settings["languages"]:
                if (
                    settings["languages_type"][file_path.split("/")[-1].split(".")[-1]]
                    == 0
                ):
                    file = open(file_path, "rb")
                    text = file.read()
                else:
                    backup(file_path)
                    file = open(file_path, "r", encoding="utf-8")
                    text = "".join(file.readlines())
            else:
                file = open(file_path, "r", encoding="utf-8")
                text = "".join(file.readlines())
            self.files.append(file_path)
            self.createTab(text, file_path)

    def actionNewFile(self):
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save File", "", "All Files (*);", options=options
        )
        if fileName:
            if fileName.split("/")[-1].split(".")[-1] not in settings["languages"]:
                with open(fileName, "w", encoding="utf-8") as file:
                    file.write("")
                with open(fileName, "r", encoding="utf-8") as file_read:
                    text = file_read.readlines()
                    self.createTab(text, fileName)
            else:
                if (
                    settings["languages_type"][fileName.split("/")[-1].split(".")[-1]]
                    != 1
                ):
                    with open(fileName, "w", encoding="utf-8") as file:
                        file.write("")
                    with open(fileName, "r", encoding="utf-8") as file_read:
                        text = file_read.readlines()
                        self.createTab(text, fileName)
                else:
                    CustomDialog("Binary files not writable")

    def actionArgsLaunch(self):
        active_tab_index = self.tabWidget.currentIndex()
        active_tab_widget = self.tabWidget.widget(active_tab_index)
        if active_tab_widget:
            CodeEdit = active_tab_widget.findChild(CodeEdit, "CodeEdit")
            self.window = ArgsWindow(
                CodeEdit.filename, CodeEdit.fullfilepath, CodeEdit.language
            )
            self.window.show()

    def actionSettingsLaunch(self):
        window = SettingsWidget(settings, path_settings)
        self.tabWidget.addTab(window, "         Settings         ")

    def createTab(self, text, fileName):
        if "Welcome" in self.tabWidget.tabText(0):
            self.tabWidget.removeTab(0)
        self.popRecentFile(fileName)
        lang = fileName.split("/")[-1].split(".")[-1]
        self.CodeEdit = CodeEdit(self, lang, [], settings)
        self.CodeEdit.filename = path.basename(fileName)
        self.CodeEdit.fullfilepath = rf"{fileName}"
        self.CodeEdit.setObjectName("CodeEdit")
        if self.CodeEdit.mode == 0:
            self.CodeEdit.addText(text)
        else:
            self.CodeEdit.setPlainText("".join(text))
        if not self.CodeEdit.welcome:
            self.CodeEdit.textedit.textChanged.connect(self.setAsterisk)
        self.tabWidget.addTab(
            self.CodeEdit, f"       {fileName.split('/')[-1]}        "
        )

    def saveOpenFiles(self):
        for i in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(i)
            try:
                if tab.mode != 0:
                    open(tab.fullfilepath, "w", encoding="utf-8").write(
                        tab.toPlainText()
                    )
            except:
                pass

    def closeEvent(self, event):
        if self.unsavedfiles > 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "",
                "Сохранить файлы перед закрытием?",
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No
                | QtWidgets.QMessageBox.Cancel,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                saveRecent(list_recent_files)
                self.saveOpenFiles()
                saveSession(self.files)
                clear_backup()
                event.accept()
            elif reply == QtWidgets.QMessageBox.No:
                saveRecent(list_recent_files)
                saveSession(self.files)
                clear_backup()
                event.accept()
            elif reply == QtWidgets.QMessageBox.Cancel:
                pass
        else:
            clear_backup()
            saveRecent(list_recent_files)
            event.accept()

    def accept(self):
        self.saveOpenFiles()
        saveSession(self.files)
        self.dialog.close()

    def __del__(self):
        self.close()



if __name__ == "__main__":
    scriptDir = path.dirname(path.realpath(__file__))
    chdir(path.abspath(__file__).replace(path.basename(__file__), ""))
    app = QtWidgets.QApplication(argv)
    app.setWindowIcon(QIcon(scriptDir + path.sep + "src/icon2.png"))
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
    MainWindow.setWindowIcon(QIcon(scriptDir + path.sep + "src/icon2.png"))
    MainWindow.show()
    exit(app.exec_())
