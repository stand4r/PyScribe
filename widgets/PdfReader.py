from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl


class PdfReader(QWidget):
    def __init__(self, text, fileName):
        super().__init__()
        self.welcome = True

        pdf_view = QWebEngineView()

        url = QUrl.fromLocalFile(rf"{fileName}")   
        pdf_view.setUrl(url)

        layout = QVBoxLayout()
        layout.addWidget(pdf_view)

        self.setLayout(layout)