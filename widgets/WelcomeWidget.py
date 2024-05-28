from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Welcome(QtWidgets.QWidget):
    def __init__(self, parent=None, settings={}):
        super(Ui_Welcome, self).__init__(parent)
        QtCore.QMetaObject.connectSlotsByName(self)
        self.settings = settings
        self.welcome = True
        
        self.color = self.settings["settings"].get("second_color", "#FFFFFF")  # Используйте значение по умолчанию, если нет в настройках

        self.setObjectName("Main")
        
        # Создание лейаутов и виджетов
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        
        self.IconLabel = QtWidgets.QLabel(self)
        self.IconLabel.setMaximumSize(QtCore.QSize(150, 150))
        self.IconLabel.setText("")
        self.IconLabel.setPixmap(QtGui.QPixmap("./src/icon2.png"))
        self.IconLabel.setScaledContents(True)
        self.IconLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.IconLabel.setObjectName("IconLabel")
        self.horizontalLayout_3.addWidget(self.IconLabel)
        
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        
        self.WelcomLabel = QtWidgets.QLabel(self)
        self.WelcomLabel.setMaximumSize(QtCore.QSize(16777215, 70))
        font = QtGui.QFont()
        font.setFamily("Source Code Pro Light")
        font.setPointSize(17)
        self.WelcomLabel.setFont(font)
        self.WelcomLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.WelcomLabel.setObjectName("WelcomLabel")
        self.verticalLayout.addWidget(self.WelcomLabel)
        
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(40, -1, 40, 100)
        self.horizontalLayout.setSpacing(40)
        self.horizontalLayout.setObjectName("horizontalLayout")
        
        self.OpenFileButton = QtWidgets.QPushButton(self)
        font = QtGui.QFont()
        font.setFamily("Source Code Pro Light")
        font.setPointSize(14)
        self.OpenFileButton.setFont(font)
        self.OpenFileButton.setObjectName("OpenFileButton")
        self.horizontalLayout.addWidget(self.OpenFileButton)
        
        self.NewFileButton = QtWidgets.QPushButton(self)
        font = QtGui.QFont()
        font.setFamily("Source Code Pro Light")
        font.setPointSize(14)
        self.NewFileButton.setFont(font)
        self.NewFileButton.setObjectName("NewFileButton")
        self.horizontalLayout.addWidget(self.NewFileButton)
        
        self.verticalLayout.addLayout(self.horizontalLayout)
        
        # Установка стиля виджета после создания всех виджетов
        self.apply_styles()

        self.retranslateUi()

    def apply_styles(self):
        # Установка стиля для основного виджета
        self.setStyleSheet(f"QWidget#Main {{background-color: #131313;}}")
        
        # Установка стиля для конкретных виджетов
        self.WelcomLabel.setStyleSheet(f"background-color: {self.color};")
        self.IconLabel.setStyleSheet(f"background-color: {self.color};")
        self.OpenFileButton.setStyleSheet(f"border:none; color: blue; background-color: {self.color};")
        self.NewFileButton.setStyleSheet(f"border:none; color: blue; background-color: {self.color};")

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.WelcomLabel.setText(_translate("Main", "Welcome to PyScribe"))
        self.OpenFileButton.setText(_translate("Main", "Open file..."))
        self.NewFileButton.setText(_translate("Main", "New file..."))

