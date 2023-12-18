from os import path
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from json import load, dump

class CompilerSettingsWindow(QWidget):
    def __init__(self, filename, filepath):
        super().__init__()
        self.filename = filename
        self.filepath = filepath
        self.scriptDir = path.dirname(path.realpath(__file__))
        self.config_path = self.scriptDir + r"\config\launchArgs.json"
        self.exist_args = self.load_args(self.config_path, self.filepath)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Настройки компиляции Си')
        self.setGeometry(100, 100, 400, 400)

        layout = QVBoxLayout()

        self.flags_file = QLabel(f'Файл: {self.filename}')
        self.flags_label = QLabel('Флаги компиляции:')
        self.flags_input = QLineEdit(self.exist_args)
        layout.addWidget(self.flags_file)
        layout.addWidget(self.flags_label)
        layout.addWidget(self.flags_input)

        # Кнопка для сохранения настроек
        self.save_button = QPushButton('Сохранить')
        self.save_button.clicked.connect(self.saveSettings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def saveSettings(self):
        flags = self.flags_input.text()
        if not self.exist_config(self.config_path):
            self.create_config(self.config_path)
        self.dump_args(self.config_path, self.filepath, flags)

    def exist_config(self, file_path):
        return path.exists(file_path)

    def create_config(self, file_path):
        open(file_path, "w").write("{\n}")

    def dump_args(self, config, filepath, args):
        with open(config, "w") as fp:
            args_file = load(open(filepath, "r"))
            args_file[filepath] = args
            dump(args_file, fp)

    def load_args(self, config, filepath) -> str:
        try:
            return load(open(config, "r"))[filepath]
        except:
            return ""