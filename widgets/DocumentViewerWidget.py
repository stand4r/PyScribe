"""Read-only viewers for common office documents.

The viewer intentionally does not attempt to edit Office files. It gives users
fast, deterministic access to workbook sheets and document text without
requiring Microsoft Office on the machine.
"""
from pathlib import Path
from PyQt5 import QtWidgets, QtCore


class DocumentViewerWidget(QtWidgets.QWidget):
    """Display DOCX or XLSX content in a native, read-only PyScribe tab."""
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = str(file_path)
        self.setObjectName("documentViewer")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("documentStatus")
        layout.addWidget(self.status)
        self.load_document()

    def load_document(self):
        """Load the selected Office document using its lightweight Python parser."""
        suffix = Path(self.file_path).suffix.lower()
        try:
            if suffix == ".xlsx":
                self._load_xlsx()
            elif suffix == ".docx":
                self._load_docx()
            else:
                raise ValueError(f"Unsupported Office format: {suffix}")
        except Exception as exc:
            error = QtWidgets.QTextBrowser()
            error.setPlainText(f"Не удалось открыть документ:\n{exc}")
            self.stack.addWidget(error)
            self.stack.setCurrentWidget(error)
            self.status.setText("Read-only viewer · ошибка загрузки")

    def _load_xlsx(self):
        from openpyxl import load_workbook
        workbook = load_workbook(self.file_path, read_only=True, data_only=False)
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        total = 0
        for sheet in workbook.worksheets:
            table = QtWidgets.QTableWidget()
            rows = list(sheet.iter_rows(values_only=True))
            total += len(rows)
            max_cols = max((len(row) for row in rows), default=0)
            table.setRowCount(len(rows))
            table.setColumnCount(max_cols)
            table.setAlternatingRowColors(True)
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    item = QtWidgets.QTableWidgetItem("" if value is None else str(value))
                    table.setItem(r, c, item)
            table.resizeColumnsToContents()
            tabs.addTab(table, sheet.title)
        self.stack.addWidget(tabs)
        self.stack.setCurrentWidget(tabs)
        self.status.setText(f"XLSX · {len(workbook.worksheets)} лист(ов) · {total} строк · только чтение")
        workbook.close()

    def _load_docx(self):
        from docx import Document
        document = Document(self.file_path)
        browser = QtWidgets.QTextBrowser()
        cursor = browser.textCursor()
        for paragraph in document.paragraphs:
            cursor.insertText(paragraph.text)
            cursor.insertBlock()
        for table in document.tables:
            cursor.insertText("\n")
            for row in table.rows:
                cursor.insertText(" | ".join(cell.text.replace("\\n", " ") for cell in row.cells))
                cursor.insertBlock()
        self.stack.addWidget(browser)
        self.stack.setCurrentWidget(browser)
        self.status.setText(f"DOCX · {len(document.paragraphs)} абзацев · только чтение")
