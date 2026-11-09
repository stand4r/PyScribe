"""Fast asynchronous PDF viewer based on PyMuPDF.

Document metadata is opened on the GUI thread, while page rasterization is
performed by QThreadPool workers so large PDFs do not freeze the workbench.
"""
from pathlib import Path
from typing import Optional
import os
import fitz
from PyQt5 import QtCore, QtGui, QtWidgets


class _PdfRenderBridge(QtCore.QObject):
    rendered = QtCore.pyqtSignal(bytes, int)
    failed = QtCore.pyqtSignal(str)


class _PdfRenderTask(QtCore.QRunnable):
    def __init__(self, path: str, page: int, zoom: float, receiver):
        super().__init__()
        self.path, self.page, self.zoom, self.bridge = path, page, zoom, receiver

    def run(self):
        try:
            document = fitz.open(self.path)
            page = document.load_page(self.page)
            pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
            payload = pix.tobytes("png")
            document.close()
            self.bridge.rendered.emit(payload, self.page)
        except Exception as exc:
            self.bridge.failed.emit(str(exc))


class PDFViewerWidget(QtWidgets.QWidget):
    """Read-only PDF viewer with non-blocking page rendering."""
    page_changed = QtCore.pyqtSignal(int, int)
    document_loaded = QtCore.pyqtSignal(str)
    document_closed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path: Optional[str] = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 100
        self._render_generation = 0
        self.pool = QtCore.QThreadPool.globalInstance()
        self._bridge = _PdfRenderBridge()
        self._bridge.rendered.connect(self._render_finished)
        self._bridge.failed.connect(self._render_failed)
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QtWidgets.QToolBar()
        self.first_btn = toolbar.addAction("⏮")
        self.prev_btn = toolbar.addAction("◀")
        self.page_combo = QtWidgets.QComboBox(); self.page_combo.setFixedWidth(90)
        toolbar.addWidget(self.page_combo)
        self.next_btn = toolbar.addAction("▶")
        self.last_btn = toolbar.addAction("⏭")
        toolbar.addSeparator()
        self.zoom_out_btn = toolbar.addAction("−")
        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.zoom_slider.setRange(25, 300); self.zoom_slider.setValue(100); self.zoom_slider.setFixedWidth(120)
        toolbar.addWidget(self.zoom_slider)
        self.zoom_in_btn = toolbar.addAction("+")
        self.zoom_label = QtWidgets.QLabel("100%")
        toolbar.addWidget(self.zoom_label)
        layout.addWidget(toolbar)
        self.pdf_label = QtWidgets.QLabel("Открытие PDF…")
        self.pdf_label.setAlignment(QtCore.Qt.AlignCenter)
        self.pdf_label.setMinimumSize(400, 300)
        self.pdf_label.setObjectName("pdfPage")
        layout.addWidget(self.pdf_label, 1)
        self.status = QtWidgets.QLabel("Готово")
        layout.addWidget(self.status)
        self.first_btn.triggered.connect(lambda: self.goto_page(0))
        self.prev_btn.triggered.connect(lambda: self.goto_page(self.current_page - 1))
        self.next_btn.triggered.connect(lambda: self.goto_page(self.current_page + 1))
        self.last_btn.triggered.connect(lambda: self.goto_page(self.total_pages - 1))
        self.page_combo.currentIndexChanged.connect(self.goto_page)
        self.zoom_slider.valueChanged.connect(self._zoom_changed)
        self.zoom_out_btn.triggered.connect(lambda: self.zoom_slider.setValue(max(25, self.zoom_slider.value() - 25)))
        self.zoom_in_btn.triggered.connect(lambda: self.zoom_slider.setValue(min(300, self.zoom_slider.value() + 25)))

    def open_pdf(self, file_path: str = None):
        """Open a PDF and render its first page asynchronously."""
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path: str):
        """Read only PDF metadata synchronously; page pixels are rendered in a worker."""
        self.pdf_label.setText("Загрузка PDF…")
        document = None
        try:
            document = fitz.open(file_path)
            self.current_file_path = str(Path(file_path).resolve())
            self.total_pages = len(document)
            document.close()
            self.current_page = 0
            self.page_combo.blockSignals(True)
            self.page_combo.clear()
            self.page_combo.addItems([str(i + 1) for i in range(self.total_pages)])
            self.page_combo.blockSignals(False)
            self.document_loaded.emit(self.current_file_path)
            self._request_render()
        except Exception as exc:
            if document:
                document.close()
            self.pdf_label.setText(f"Ошибка PDF: {exc}")

    def _request_render(self):
        if not self.current_file_path or self.total_pages <= 0:
            self.pdf_label.setText("Пустой PDF")
            return
        self._render_generation += 1
        self.status.setText(f"Страница {self.current_page + 1} / {self.total_pages} · рендеринг…")
        self.pool.start(_PdfRenderTask(self.current_file_path, self.current_page, self.zoom_level / 100.0, self._bridge))

    @QtCore.pyqtSlot(bytes, int)
    def _render_finished(self, payload: bytes, page: int):
        if page != self.current_page:
            return
        image = QtGui.QImage.fromData(payload, "PNG")
        if image.isNull():
            self.pdf_label.setText("Не удалось отобразить страницу")
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        self.pdf_label.setPixmap(pixmap.scaled(self.pdf_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.status.setText(f"Страница {page + 1} / {self.total_pages}")
        self.page_changed.emit(page + 1, self.total_pages)

    @QtCore.pyqtSlot(str)
    def _render_failed(self, message: str):
        self.pdf_label.setText(f"Ошибка рендера: {message}")

    def goto_page(self, page: int):
        if 0 <= int(page) < self.total_pages:
            self.current_page = int(page)
            self.page_combo.blockSignals(True); self.page_combo.setCurrentIndex(self.current_page); self.page_combo.blockSignals(False)
            self._request_render()

    def first_page(self): self.goto_page(0)
    def previous_page(self): self.goto_page(self.current_page - 1)
    def next_page(self): self.goto_page(self.current_page + 1)
    def last_page(self): self.goto_page(self.total_pages - 1)
    def update_page_display_method(self): self._request_render()

    def zoom_in(self): self.zoom_slider.setValue(min(300, self.zoom_slider.value() + 25))
    def zoom_out(self): self.zoom_slider.setValue(max(25, self.zoom_slider.value() - 25))
    def zoom_fit(self): self.zoom_slider.setValue(100)

    def _zoom_changed(self, value: int):
        self.zoom_level = value
        self.zoom_label.setText(f"{value}%")
        if self.current_file_path:
            self._request_render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_file_path:
            QtCore.QTimer.singleShot(80, self._request_render)
