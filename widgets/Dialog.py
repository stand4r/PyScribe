"""PyScribe widgets/Dialog.py: application module and reusable component."""
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel


class CustomDialog(QDialog):
    def __init__(self, text=""):
        super().__init__()

        self.setWindowTitle("Сообщение")

        QBtn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(QBtn)
        ok_btn = self.buttonBox.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setText("ОК")
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(12)
        message = QLabel(text)
        message.setStyleSheet("font-size: 13px;")
        message.setWordWrap(True)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        self.setStyleSheet("""
            QDialog { border-radius: 10px; }
            QPushButton { border-radius: 6px; min-width: 80px; min-height: 28px; padding: 4px 12px; }
        """)
