"""PyScribe widgets/MarkdownViewerWidget.py: Modern Markdown previewer with dark theme styling."""
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets


MARKDOWN_CSS = """
body, div, p {
    color: #D4D4D4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", Roboto, sans-serif;
    font-size: 13px;
    line-height: 1.6;
}
h1 {
    color: #58A6FF;
    font-size: 20px;
    font-weight: 700;
    border-bottom: 1px solid #30363D;
    padding-bottom: 6px;
    margin-top: 16px;
    margin-bottom: 12px;
}
h2 {
    color: #79C0FF;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid #21262D;
    padding-bottom: 4px;
    margin-top: 14px;
    margin-bottom: 10px;
}
h3 {
    color: #E6EDF3;
    font-size: 14px;
    font-weight: 600;
    margin-top: 12px;
    margin-bottom: 8px;
}
h4, h5, h6 {
    color: #A8A8A8;
    font-size: 13px;
    font-weight: 600;
}
code {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    background: #24292F;
    color: #F0883E;
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 12px;
}
pre {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 6px;
    padding: 10px 14px;
    color: #E6EDF3;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    margin: 10px 0;
}
blockquote {
    border-left: 4px solid #58A6FF;
    background: #161B22;
    padding: 8px 14px;
    margin: 10px 0;
    color: #A8A8A8;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
}
th {
    background: #161B22;
    color: #FFFFFF;
    font-weight: 600;
    border: 1px solid #30363D;
    padding: 6px 12px;
    text-align: left;
}
td {
    border: 1px solid #30363D;
    padding: 6px 12px;
    color: #D4D4D4;
}
tr:nth-child(even) {
    background: #12161C;
}
hr {
    border: none;
    border-top: 1px solid #30363D;
    margin: 16px 0;
}
ul, ol {
    padding-left: 22px;
    margin: 8px 0;
}
li {
    margin-bottom: 4px;
}
a {
    color: #58A6FF;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
"""


class MarkdownViewerWidget(QtWidgets.QWidget):
    """Full-featured Markdown preview tab with auto-reload and export."""
    open_editor_requested = QtCore.pyqtSignal(str)

    def __init__(self, file_path: str = "", content: str = "", parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._raw_content = content
        self.setObjectName("markdownViewer")
        self._build_ui()
        if file_path and not content:
            self.load_file(file_path)
        elif content:
            self.set_markdown(content)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        toolbar = QtWidgets.QFrame()
        toolbar.setObjectName("markdownToolbar")
        toolbar.setStyleSheet("""
            QFrame#markdownToolbar {
                background: #181818;
                border-bottom: 1px solid #2B2B2B;
                min-height: 34px;
                max-height: 34px;
            }
        """)
        tbl = QtWidgets.QHBoxLayout(toolbar)
        tbl.setContentsMargins(12, 2, 12, 2)
        tbl.setSpacing(8)

        self.title_label = QtWidgets.QLabel("Предпросмотр Markdown")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #D4D4D4;")
        tbl.addWidget(self.title_label)

        self.path_label = QtWidgets.QLabel("")
        self.path_label.setStyleSheet("font-size: 11px; color: #858585;")
        tbl.addWidget(self.path_label, 1)

        self.refresh_btn = QtWidgets.QToolButton()
        self.refresh_btn.setText("Обновить")
        self.refresh_btn.setToolTip("Перезагрузить файл с диска")
        self.refresh_btn.clicked.connect(self.reload)
        tbl.addWidget(self.refresh_btn)

        self.copy_btn = QtWidgets.QToolButton()
        self.copy_btn.setText("Копировать текст")
        self.copy_btn.setToolTip("Скопировать исходный Markdown в буфер обмена")
        self.copy_btn.clicked.connect(self._copy_markdown)
        tbl.addWidget(self.copy_btn)

        self.edit_btn = QtWidgets.QToolButton()
        self.edit_btn.setText("Редактировать")
        self.edit_btn.setToolTip("Открыть этот файл в текстовом редакторе кода")
        self.edit_btn.setStyleSheet("background: #0078D4; color: #FFFFFF; font-weight: 500;")
        self.edit_btn.clicked.connect(self._request_editor)
        tbl.addWidget(self.edit_btn)

        root.addWidget(toolbar)

        # Viewer browser
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setObjectName("markdownBrowser")
        self.browser.setReadOnly(True)
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("""
            QTextBrowser#markdownBrowser {
                background: #1E1E1E;
                color: #D4D4D4;
                border: none;
                padding: 16px 24px;
            }
        """)
        self.browser.document().setDefaultStyleSheet(MARKDOWN_CSS)
        root.addWidget(self.browser, 1)

    def load_file(self, file_path: str):
        self.file_path = file_path
        p = Path(file_path)
        if not p.exists():
            self.browser.setPlainText(f"Файл не найден: {file_path}")
            return

        self.title_label.setText(f"Предпросмотр: {p.name}")
        self.path_label.setText(str(p))

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                self.browser.setPlainText(f"Ошибка чтения: {e}")
                return

        self.set_markdown(content)

    def set_markdown(self, markdown_text: str):
        self._raw_content = markdown_text
        self.browser.setMarkdown(markdown_text)

    def reload(self):
        if self.file_path:
            self.load_file(self.file_path)

    def _copy_markdown(self):
        if self._raw_content:
            QtGui.QGuiApplication.clipboard().setText(self._raw_content)
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Markdown скопирован в буфер обмена")

    def _request_editor(self):
        if self.file_path:
            self.open_editor_requested.emit(self.file_path)
