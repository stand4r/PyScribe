from PyQt5 import QtCore, QtGui, QtWidgets
from widgets.QTerminal import *
from os import getcwd, getlogin
from socket import gethostname



class Ui_MainWindow(QtWidgets.QMainWindow):
    def setupUi(self):
        menubar = self.menuBar()
        fmenu = menubar.addMenu("File")
        self.setObjectName("MainWindow")
        self.setWindowOpacity(0.5) 
        self.setMinimumSize(QtCore.QSize(300, 250))
        self.setMaximumSize(QtCore.QSize(4050, 4050))
        self.setStyleSheet("background-color:  #191819;\n"
        "color: #ffffff")
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setStyleSheet("background-color: #191819")
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setStyleSheet("background-color: #1e1f1e;\n"
        "color: #000000\n")
        self.tabWidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setObjectName("tabWidget")
        self.tabWidget.setStyleSheet(
            "QTabBar::tab {background-color: #1e1f1e; width: 150px; height: 30px; border-width: 1px; padding-right: 20px; font-size: 16px; letter-spacing: 1px; border: 1px solid blue; border-top-right-radius: 8px; border-top-left-radius: 8px;}"
            "QTabBar::tab:selected {background-color: #131313; border: 1px solid #3b3b3b; color: #d4d4d4;border-bottom-color: #131313;}"  # Стиль для активной вкладки
            "QTabBar::tab:!selected {background-color: #1e1f1e; border: 1px solid #4f4843;color: #d4d4d4; border-bottom-color: #3b3b3b;}"  # Дополнительный стиль для неактивной вкладки
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
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionRun)
        self.menuFile.addAction(self.actionNew)
        self.menuRun.addAction(self.actionConfig)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuRun.menuAction())
        self.ResultText = QTerminal(self.centralwidget)
        self.ResultText.setStyleSheet("background-color: #131313;\n"
        "color: #ffffff;\n"
        "padding: 7px; letter-spacing: 1px; padding-top: 40px;")
        self.ResultText.setObjectName("ResultText")
        self.verticalLayout.addWidget(self.tabWidget, 5)
        self.verticalLayout.addWidget(self.ResultText, 3)
        self.retranslateUi()
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(self)

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