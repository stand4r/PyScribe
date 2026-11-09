"""PyScribe widgets/QNewFileDialog.py: application module and reusable component."""
from core.logging_config import get_logger
from fileinput import filename

from PyQt5.QtWidgets import QWidget, QFileDialog


class FileSaveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.file = []

    def initUI(self):
        self.setGeometry(300, 300, 300, 200)
        self.setWindowTitle('Save File')
        self.showSaveDialog()

    def showSaveDialog(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*);", options=options)

        if fileName:
            self.file.append(filename)
            logger.info("Selected file:", fileName)


logger = get_logger("QNewFileDialog")
