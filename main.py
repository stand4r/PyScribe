from sys import exit, argv, executable
from os import path, chdir

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor

from utils.FabricRunCode import *
from utils.programs import *
from widgets.QArgsEditor import ArgsWindow
from widgets.QCodeEditor import CodeTextEdit
from widgets.SettingsWidget import SettingsWidget
from widgets.Dialog import CustomDialog


path_settings = path.dirname(path.realpath(__file__))
settings = load_settings(path_settings)
main_color = settings["settings"]['main_color']#1e1f1e
first_color = settings["settings"]['first_color']#191819
second_color = settings["settings"]['second_color']#131313
languages = settings["languages"]


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
        self.button_run = QtWidgets.QPushButton("▶")
        self.button_run.setFlat(True)
        self.button_run.setStyleSheet("border:none; padding-right:10px; padding-left:10px; ")
        self.button_run.setFont(QFont("Console", 20))
        self.button_run.clicked.connect(self.actionRunCode)
        self.button_settings = QtWidgets.QPushButton("⚙")
        self.button_settings.setFlat(True)
        self.button_settings.setStyleSheet("border:none;padding-right:10px; padding-bottom:5px;")
        self.button_settings.setFont(QFont("Console", 18))
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
                                    "margin-top:20px;\n"
                                    )
        self.tabWidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setObjectName("tabWidget")
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.setStyleSheet(
            "QTabBar::close-button {image: url(src/close.png);}"
            "QTabWidget::tab-bar {border:none;}"
            "QTabBar::tab {background-color: #1F2228; width: 150px; height: 30px; border-width: 0px; padding-right: 20px; font-size: 16px; letter-spacing: 1px; border: none; border-bottom-color: #16171D;}"
            "QTabBar::tab:selected {background-color: #16171D; border: none; color: #ffffff;}"
            "QTabBar::tab:!selected {background-color: #1F2228; border: none;color: #ffffff;}"
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
        self.label_status = QtWidgets.QLabel("run code")
        self.label_status.setFont(QtGui.QFont("Console", 11))
        self.verticalLayout.addWidget(self.tabWidget)
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

    def loadSession(self, files):
        for file in files:
            try:
                if path.basename(file).split('/')[-1].split('.')[-1] not in ["bin", "exe", "out"]:
                    self.createTab(open(rf"{file}", "r").readlines(), file)
                else:
                    self.createTab(open(rf"{file}", "rb").read(), file)
            except:
                pass

    def closeTab(self, currentIndex):
        active_tab_widget = self.tabWidget.widget(currentIndex)
        self.files.remove(active_tab_widget.fullfilepath)
        self.tabWidget.removeTab(currentIndex)
        if active_tab_widget.language != "bin" and active_tab_widget.language != "out" and active_tab_widget.language != "exe":
            self.actionSaveFile(currentIndex)

    def actionRunCode(self):
        active_tab_index = self.tabWidget.currentIndex()
        CodeEdit = self.tabWidget.widget(active_tab_index)

        with open(CodeEdit.fullfilepath, 'w') as codefile:
            codefile.write(CodeEdit.toPlainText())
        try:
            if self.CodeEdit.language == "c":
                compile_program_c(CodeEdit.fullfilepath)
            elif self.CodeEdit.language == "cpp":
                compile_program_cpp(CodeEdit.fullfilepath)
            try:
                RunCodeClass(self.CodeEdit.fullfilepath, self.CodeEdit.filename, self.CodeEdit.language).process()
            except:
                CustomDialog("Error running code").exec()
        except:
            CustomDialog("Compilation error").exec()

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
        try:
            lang = fileName.split('/')[-1].split('.')[-1]
            self.CodeEdit = CodeTextEdit(self, languages[lang])
            self.CodeEdit.filename = path.basename(fileName)
            self.CodeEdit.fullfilepath = rf"{fileName}"
            self.CodeEdit.setObjectName("CodeEdit")
            if self.CodeEdit.language == "bin" or self.CodeEdit.language == "out" or self.CodeEdit.language == "exe":
                self.CodeEdit.addText(text)
            else:
                self.CodeEdit.setPlainText("".join(text))
            self.tabWidget.addTab(self.CodeEdit, fileName.split('/')[-1])
        except:
            CustomDialog("Open file error").exec()

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
