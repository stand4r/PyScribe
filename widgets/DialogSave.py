"""PyScribe widgets/DialogSave.py: application module and reusable component."""
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel


class CustomDialogSave(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Сохранение файлов")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        ok_btn = self.buttonBox.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setText("Сохранить")
        cancel_btn = self.buttonBox.button(QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setText("Отмена")

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(12)
        message = QLabel("Сохранить открытые файлы перед выходом?")
        message.setStyleSheet("font-size: 13px;")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        self.setStyleSheet("""
            QDialog { border-radius: 10px; }
            QPushButton { border-radius: 6px; min-width: 80px; min-height: 28px; padding: 4px 12px; }
        """)

    def reject(self):
        self.close()
