from functools import partial

from PyQt5 import QtWidgets, QtCore, QtGui

from utils.programs import *


class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, settings, pathSettings):
        super().__init__()
        self.path_settings = pathSettings
        self.settings = settings
        self.settings_0 = settings["settings"]
        self.main_color = self.settings_0 ['main_color']#013B81
        self.text_color = self.settings_0 ["text_color"]#ABB2BF
        self.first_color = self.settings_0 ['first_color']#16171D
        self.second_color = self.settings_0 ['second_color']#131313
        self.tab_color = self.settings_0 ['tab_color']#1F2228
        self.font_size = int(settings["settings"]["fontsize"])
        self.setupUi()

    def setupUi(self):
        self.setStyleSheet(f"background-color:  {self.first_color};\n"
                           "color: #ffffff;")
        self.layout = QtWidgets.QFormLayout(self)
        self.buttonSave = QtWidgets.QPushButton("Save")
        self.buttonSave.setStyleSheet(f"border: 1px solid blue; border-radius:10px; color: blue; margin-left: 80px; padding-left: 20px; padding-right: 20px;")
        font = QtGui.QFont()
        font.setFamily("MS UI Gothic")
        font.setPointSize(self.font_size)
        for key, value in self.settings_0.items():
            locals()["self.label_"+key] = QtWidgets.QLabel(key)
            locals()["self.label_" + key].setFont(font)
            locals()["self.label_" + key].setStyleSheet("padding-right: 50px;")
            locals()["self.edit_"+key] = QtWidgets.QLineEdit(str(value))
            locals()["self.edit_" + key].setFont(font)
            self.layout.addRow(locals()["self.label_"+key], locals()["self.edit_"+key])
            self.layout.addRow(QtWidgets.QLabel())
        self.buttonSave.clicked.connect(partial(self.save, locals()))
        self.buttonSave.setMaximumSize(QtCore.QSize(180, 30))
        self.buttonSave.setMinimumSize(QtCore.QSize(180, 30))
       
        self.layout.addRow(self.buttonSave)

    def save(self, locales):
        settings_update = {}
        for key, value in self.settings_0.items():
            settings_update[locales["self.label_"+key].text()] = locales["self.edit_"+key].text()
        self.settings["settings"] = settings_update
        update_settings(self.path_settings, self.settings)
        self.close()
