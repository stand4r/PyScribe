from json import load, dumps
from os import path

from PyQt5 import QtCore, QtWidgets, QtGui


class ArgsWindow(QtWidgets.QWidget):
    def __init__(self, filename, filepath, lang):
        super().__init__()
        self.filename = filename
        self.filepath = filepath
        self.lang = lang
        self.scriptDir = path.dirname(path.realpath(__file__))
        self.config_path = self.scriptDir + r"\config\launchArgs.json"
        self.exist_args = self.load_args(self.config_path, self.filepath)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("ArgsWindow")
        self.resize(634, 224)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMinimumSize(QtCore.QSize(634, 224))
        self.setMaximumSize(QtCore.QSize(634, 224))
        self.setAutoFillBackground(False)
        self.setStyleSheet("background-color: #1e1f1e;")
        self.label = QtWidgets.QLabel(self)
        self.label.setGeometry(QtCore.QRect(20, 20, 91, 31))
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        font.setUnderline(False)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white;")
        self.label.setObjectName("label")
        self.file_label = QtWidgets.QLabel(self)
        self.file_label.setGeometry(QtCore.QRect(70, 20, 221, 31))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.file_label.sizePolicy().hasHeightForWidth())
        self.file_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        self.file_label.setFont(font)
        self.file_label.setStyleSheet("color: white;")
        self.file_label.setText(self.filename)
        self.file_label.setObjectName("file_label")
        self.label_3 = QtWidgets.QLabel(self)
        self.label_3.setGeometry(QtCore.QRect(320, 20, 111, 31))
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        self.label_3.setFont(font)
        self.label_3.setStyleSheet("color: white;")
        self.label_3.setObjectName("label_3")
        self.language_label = QtWidgets.QLabel(self)
        self.language_label.setGeometry(QtCore.QRect(410, 20, 161, 31))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.language_label.sizePolicy().hasHeightForWidth())
        self.language_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        self.language_label.setFont(font)
        self.language_label.setStyleSheet("color: white;")
        self.language_label.setText(self.lang.capitalize())
        self.language_label.setObjectName("language_label")
        self.label_5 = QtWidgets.QLabel(self)
        self.label_5.setGeometry(QtCore.QRect(20, 110, 41, 31))
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        self.label_5.setFont(font)
        self.label_5.setStyleSheet("color: white;")
        self.label_5.setObjectName("label_5")
        self.args_edit = QtWidgets.QLineEdit(self)
        self.args_edit.setGeometry(QtCore.QRect(70, 110, 511, 31))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.args_edit.sizePolicy().hasHeightForWidth())
        self.args_edit.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(12)
        self.args_edit.setFont(font)
        self.args_edit.setStyleSheet("border: 1px solid white;\n"
                                     "color: white;")
        self.args_edit.setObjectName("args_edit")
        self.args_edit.setText(self.exist_args)
        self.pushButton = QtWidgets.QPushButton(self)
        self.pushButton.setGeometry(QtCore.QRect(20, 170, 101, 28))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton.sizePolicy().hasHeightForWidth())
        self.pushButton.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("MS Sans Serif")
        font.setPointSize(10)
        self.pushButton.setFont(font)
        self.pushButton.setStyleSheet("color: white;\n"
                                      "background-color: blue;\n"
                                      "border-radius: 15px")
        self.pushButton.setObjectName("pushButton")
        self.pushButton.clicked.connect(self.saveSettings)

        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("ArgsWindow", "Args Window"))
        self.label.setText(_translate("ArgsWindow", "File:"))
        self.label_3.setText(_translate("ArgsWindow", "Language:"))
        self.label_5.setText(_translate("ArgsWindow", "Args:"))
        self.pushButton.setText(_translate("ArgsWindow", "Save"))

    def saveSettings(self):
        flags = self.args_edit.text()
        if not self.exist_config(self.config_path) or self.clear_file(self.config_path):
            self.create_config(self.config_path)
        self.dump_args(self.config_path, self.filepath, flags)
        self.close()

    def exist_config(self, config):
        return path.exists(config)

    def create_config(self, config):
        open(config, "w").write("{\n\t\n}")

    def clear_file(self, config):
        return open(config, "r").readline() == ""

    def dump_args(self, config, filepath, args):
        jsonFile = open(config, "r")  # Open the JSON file for reading
        data = load(jsonFile)  # Read the JSON into the buffer
        jsonFile.close()  # Close the JSON file

        ## Working with buffered content
        data[filepath] = args

        ## Save our changes to JSON file
        jsonFile = open(config, "w+")
        jsonFile.write(dumps(data))
        jsonFile.close()

    def load_args(self, config, filepath) -> str:
        try:
            return load(open(config, "r"))[filepath]
        except:
            return ""

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Enter:
            self.saveSettings()
        else:
            super().keyPressEvent(event)
