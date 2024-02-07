from functools import partial

from PyQt5 import QtWidgets, QtCore, QtGui

from utils.programs import *


class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, settings, pathSettings):
        super().__init__()
        self.path_settings = pathSettings
        self.settings = settings
        self.settings_0 = settings["settings"]
        self.setupUi()

    def setupUi(self):
        self.setMinimumSize(QtCore.QSize(1080, 720))
        self.setMaximumSize(QtCore.QSize(4050, 4050))
        self.setStyleSheet("background-color:  #191819;\n"
                           "color: #ffffff")
        self.layout = QtWidgets.QFormLayout(self)
        self.buttonSave = QtWidgets.QPushButton("Save")
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(14)
        for key, value in self.settings_0.items():
            locals()["self.label_"+key] = QtWidgets.QLabel(key)
            locals()["self.label_" + key].setFont(font)
            locals()["self.edit_"+key] = QtWidgets.QLineEdit(str(value))
            locals()["self.edit_" + key].setFont(font)
            self.layout.addRow(locals()["self.label_"+key], locals()["self.edit_"+key])
        self.buttonSave.clicked.connect(partial(self.save, locals()))
        self.layout.addRow(self.buttonSave)

    def save(self, locales):
        settings_update = {}
        for key, value in self.settings_0.items():
            settings_update[locales["self.label_"+key].text()] = locales["self.edit_"+key].text()
        self.settings["settings"] = settings_update
        update_settings(self.path_settings, self.settings)
        self.close()
