"""PDF viewer based on PyMuPDF with real zoom, scrolling, search, TOC and text extraction.

Features:
* Document outline / Table of Contents (collapsible bookmarks tree);
* Page navigation (spin box, first/prev/next/last, Home/End/PageUp/PageDown, Ctrl+G jump);
* Zoom in/out, presets, Ctrl+wheel, fit width (Ctrl+1), fit page (Ctrl+0);
* Page rotation (Ctrl+R) with swapped dimensions;
* Drag-to-pan and double-click toggle between fit width and 100%;
* Full-document text search with highlighted matches on current page;
* Password-protected PDF support;
* Text extraction and copying (dialog and clipboard);
* Export page as PNG image;
* Night reading / inverted colors mode;
* Asynchronous rendering on QThreadPool with pixmap caching.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz
from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = ["PDFViewerWidget"]

BASE_DPI = 96.0          # 100% zoom means 96 CSS pixels per PDF inch
MIN_ZOOM = 10.0
MAX_ZOOM = 400.0
PAGE_MARGIN = 24
ZOOM_PRESETS = (25, 50, 75, 100, 125, 150, 200, 300, 400)
CACHE_LIMIT = 6
CACHE_MAX_PIXELS = 16_000_000


class _RenderBridge(QtCore.QObject):
    rendered = QtCore.pyqtSignal(object)


class _SearchBridge(QtCore.QObject):
    results = QtCore.pyqtSignal(object)


class _PdfRenderTask(QtCore.QRunnable):
    """Rasterise one page off the GUI thread."""

    def __init__(self, path: str, page: int, zoom: float, rotation: int,
                 dpr: float, generation: int, search: str, receiver,
                 password: str = "", invert_colors: bool = False):
        super().__init__()
        self.path = path
        self.page_index = page
        self.zoom = zoom
        self.rotation = rotation
        self.dpr = dpr
        self.generation = generation
        self.search = search
        self.bridge = receiver
        self.password = password
        self.invert_colors = invert_colors

    def run(self):
        document = None
        try:
            document = fitz.open(self.path)
            if self.password:
                document.authenticate(self.password)
            page = document.load_page(self.page_index)
            scale = (BASE_DPI / 72.0) * (self.zoom / 100.0) * self.dpr
            matrix = fitz.Matrix(scale, scale).prerotate(self.rotation)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            rect = page.rect
            width, height = rect.width, rect.height
            if self.rotation % 180:
                width, height = height, width

            hits = page.search_for(self.search) if self.search else []
            if hits or self.invert_colors:
                image = QtGui.QImage(pixmap.samples, pixmap.width, pixmap.height,
                                     pixmap.stride,
                                     QtGui.QImage.Format_RGB888).copy()
                if self.invert_colors:
                    image.invertPixels()
                if hits:
                    painter = QtGui.QPainter(image)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.setBrush(QtGui.QColor(255, 214, 0, 95))
                    for rect_hit in hits:
                        mapped = rect_hit * matrix
                        painter.drawRect(QtCore.QRectF(
                            mapped.x0, mapped.y0, mapped.width, mapped.height))
                    painter.end()
                buffer = QtCore.QBuffer()
                buffer.open(QtCore.QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                payload = bytes(buffer.data())
            else:
                payload = pixmap.tobytes("png")
            document.close()
            self.bridge.rendered.emit({
                "png": payload,
                "page": self.page_index,
                "generation": self.generation,
                "zoom": self.zoom,
                "rotation": self.rotation,
                "dpr": self.dpr,
                "size": (width, height),
                "hits": len(hits),
            })
        except Exception as exc:  # noqa: BLE001
            if document is not None:
                try:
                    document.close()
                except Exception:
                    pass
            self.bridge.rendered.emit({
                "error": str(exc), "page": self.page_index,
                "generation": self.generation})


class _PdfSearchTask(QtCore.QRunnable):
    """Scan the whole document for a query (no rendering)."""

    def __init__(self, path: str, query: str, generation: int, bridge, password: str = ""):
        super().__init__()
        self.path = path
        self.query = query
        self.generation = generation
        self.bridge = bridge
        self.password = password

    def run(self):
        document = None
        try:
            document = fitz.open(self.path)
            if self.password:
                document.authenticate(self.password)
            pages: List[Tuple[int, int]] = []
            total = 0
            for index in range(len(document)):
                hits = document.load_page(index).search_for(self.query)
                if hits:
                    pages.append((index, len(hits)))
                    total += len(hits)
            document.close()
            self.bridge.results.emit({
                "query": self.query, "generation": self.generation,
                "pages": pages, "total": total})
        except Exception as exc:  # noqa: BLE001
            if document is not None:
                try:
                    document.close()
                except Exception:
                    pass
            self.bridge.results.emit({"error": str(exc),
                                      "generation": self.generation})


class PDFViewerWidget(QtWidgets.QWidget):
    """Full-featured PDF viewer with bookmarks, search, and text tools."""

    page_changed = QtCore.pyqtSignal(int, int)
    document_loaded = QtCore.pyqtSignal(str)
    document_closed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path: Optional[str] = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom = 100.0
        self.rotation = 0
        self.pdf_password = ""
        self.invert_colors = False
        self._fit_mode: Optional[str] = None       # "width" | "page" | None
        self._page_pt: Tuple[float, float] = (595.0, 842.0)
        self._page_sizes: Dict[int, Tuple[float, float]] = {}
        self._render_generation = 0
        self._search_generation = 0
        self._search_term = ""
        self._search_pages: List[int] = []
        self._search_total = 0
        self._search_index = 0
        self._cache: "OrderedDict[tuple, QtGui.QPixmap]" = OrderedDict()
        self._drag_origin: Optional[QtCore.QPoint] = None
        self._drag_scroll: Optional[Tuple[int, int]] = None
        self._pan_widget: Optional[QtWidgets.QWidget] = None
        self._fit_timer = QtCore.QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(90)
        self._fit_timer.timeout.connect(self._apply_fit)
        self.pool = QtCore.QThreadPool.globalInstance()
        self._bridge = _RenderBridge()
        self._bridge.rendered.connect(self._render_finished)
        self._search_bridge = _SearchBridge()
        self._search_bridge.results.connect(self._search_finished)

        self.setObjectName("pdfViewer")
        self._build()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self):
        self.setStyleSheet("""
            QWidget#pdfViewer {
                background: #1e1e1e;
                color: #cccccc;
            }
            #pdfToolbar {
                background: #252526;
                border-bottom: 1px solid #333333;
                padding: 2px 6px;
            }
            #pdfOutlinePanel {
                background: #252526;
                border-right: 1px solid #333333;
            }
            #pdfOutlineTree {
                background: #1e1e1e;
                color: #cccccc;
                border: none;
                font-size: 9pt;
            }
            #pdfOutlineTree::item:hover {
                background: #2a2d2e;
            }
            #pdfOutlineTree::item:selected {
                background: #094771;
                color: #ffffff;
            }
            #pdfScroll {
                background: #282828;
            }
            #pdfCanvas {
                background: #282828;
            }
            #pdfStatus {
                background: #252526;
                color: #999999;
                border-top: 1px solid #333333;
                padding: 3px 10px;
                font-size: 9pt;
            }
            QLineEdit#pdfSearch {
                background: #3c3c3c;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QSpinBox#pdfPageSpin, QComboBox#pdfZoomCombo, QToolButton#pdfTool {
                background: #333333;
                color: #cccccc;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QToolButton#pdfTool:hover {
                background: #3a3d41;
                border-color: #007acc;
            }
            QToolButton#pdfTool:checked {
                background: #007acc;
                color: #ffffff;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        self.body_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.body_splitter.setObjectName("pdfSplitter")

        # Outline Sidebar (Bookmarks)
        self.outline_panel = QtWidgets.QWidget()
        self.outline_panel.setObjectName("pdfOutlinePanel")
        self.outline_panel.setFixedWidth(220)
        outline_layout = QtWidgets.QVBoxLayout(self.outline_panel)
        outline_layout.setContentsMargins(4, 4, 4, 4)
        outline_layout.setSpacing(4)
        outline_title = QtWidgets.QLabel("Оглавление")
        outline_title.setStyleSheet("font-weight: bold; color: #00F2FE; padding: 4px;")
        outline_layout.addWidget(outline_title)
        self.outline_tree = QtWidgets.QTreeWidget()
        self.outline_tree.setObjectName("pdfOutlineTree")
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.itemClicked.connect(self._on_outline_item_clicked)
        outline_layout.addWidget(self.outline_tree)
        self.outline_panel.setVisible(False)
        self.body_splitter.addWidget(self.outline_panel)

        # Scroll area with canvas
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("pdfScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setFocusPolicy(QtCore.Qt.NoFocus)
        self.scroll.viewport().installEventFilter(self)

        self.canvas = QtWidgets.QWidget()
        self.canvas.setObjectName("pdfCanvas")
        self.canvas.setFocusPolicy(QtCore.Qt.NoFocus)
        self.canvas.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_context_menu)

        self.canvas_layout = QtWidgets.QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN,
                                              PAGE_MARGIN, PAGE_MARGIN)
        self.canvas_layout.setSpacing(0)
        self.canvas_layout.addStretch(1)

        self.pdf_label = QtWidgets.QLabel("Открытие PDF…")
        self.pdf_label.setObjectName("pdfPage")
        self.pdf_label.setAlignment(QtCore.Qt.AlignCenter)
        self.pdf_label.setFocusPolicy(QtCore.Qt.NoFocus)
        self.pdf_label.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.pdf_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.pdf_label.customContextMenuRequested.connect(self._show_context_menu)

        self.canvas_layout.addWidget(self.pdf_label, 0, QtCore.Qt.AlignCenter)
        self.canvas_layout.addStretch(1)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self.pdf_label)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        self.pdf_label.setGraphicsEffect(shadow)

        self.scroll.setWidget(self.canvas)
        self.canvas.installEventFilter(self)
        self.pdf_label.installEventFilter(self)

        self.body_splitter.addWidget(self.scroll)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)

        root.addWidget(self.body_splitter, 1)

        self.status = QtWidgets.QLabel("Готово")
        self.status.setObjectName("pdfStatus")
        root.addWidget(self.status)
        self._sync_page_controls()

    def _build_toolbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setObjectName("pdfToolbar")
        bar.setFixedHeight(38)
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(3)

        # TOC Toggle button
        self.toc_btn = self._tool_button("outline", "Оглавление документа")
        self.toc_btn.setCheckable(True)
        self.toc_btn.toggled.connect(self._toggle_outline)
        row.addWidget(self.toc_btn)

        row.addWidget(self._separator())

        self.first_btn = self._tool_button("first", "Первая страница (Home)")
        self.first_btn.clicked.connect(self.first_page)
        row.addWidget(self.first_btn)
        self.prev_btn = self._tool_button("back", "Предыдущая страница (Page Up)")
        self.prev_btn.clicked.connect(self.previous_page)
        row.addWidget(self.prev_btn)

        self.page_spin = QtWidgets.QSpinBox()
        self.page_spin.setObjectName("pdfPageSpin")
        self.page_spin.setRange(1, 1)
        self.page_spin.setFixedWidth(58)
        self.page_spin.setAlignment(QtCore.Qt.AlignCenter)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(lambda value: self.goto_page(value - 1))
        row.addWidget(self.page_spin)

        self.total_label = QtWidgets.QLabel("/ 0")
        self.total_label.setObjectName("pdfTotal")
        row.addWidget(self.total_label)

        self.next_btn = self._tool_button("forward", "Следующая страница (Page Down)")
        self.next_btn.clicked.connect(self.next_page)
        row.addWidget(self.next_btn)
        self.last_btn = self._tool_button("last", "Последняя страница (End)")
        self.last_btn.clicked.connect(self.last_page)
        row.addWidget(self.last_btn)

        row.addWidget(self._separator())

        self.zoom_out_btn = self._tool_button("minus", "Уменьшить (Ctrl+−)")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        row.addWidget(self.zoom_out_btn)

        self.zoom_combo = QtWidgets.QComboBox()
        self.zoom_combo.setObjectName("pdfZoomCombo")
        self.zoom_combo.setFixedWidth(100)
        self.zoom_combo.addItem("По ширине", "fit_width")
        self.zoom_combo.addItem("Страница", "fit_page")
        for preset in ZOOM_PRESETS:
            self.zoom_combo.addItem(f"{preset}%", float(preset))
        self.zoom_combo.currentIndexChanged.connect(self._zoom_combo_changed)
        row.addWidget(self.zoom_combo)

        self.zoom_in_btn = self._tool_button("add", "Увеличить (Ctrl+=)")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        row.addWidget(self.zoom_in_btn)

        self.fit_width_btn = self._tool_button("fit-width", "По ширине окна (Ctrl+1)")
        self.fit_width_btn.clicked.connect(lambda: self.set_fit("width"))
        row.addWidget(self.fit_width_btn)

        self.fit_page_btn = self._tool_button("fit-page", "Вся страница (Ctrl+0)")
        self.fit_page_btn.clicked.connect(lambda: self.set_fit("page"))
        row.addWidget(self.fit_page_btn)

        self.rotate_btn = self._tool_button("rotate", "Повернуть на 90° (Ctrl+R)")
        self.rotate_btn.clicked.connect(self.rotate_page)
        row.addWidget(self.rotate_btn)

        # Invert colors (night mode)
        self.invert_btn = self._tool_button("moon", "Инвертировать цвета (ночной режим)")
        self.invert_btn.setCheckable(True)
        self.invert_btn.toggled.connect(self._toggle_invert)
        row.addWidget(self.invert_btn)

        # Text extraction
        self.text_btn = self._tool_button("document", "Текст страницы (просмотр и копирование)")
        self.text_btn.clicked.connect(self.show_page_text_dialog)
        row.addWidget(self.text_btn)

        row.addStretch(1)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("pdfSearch")
        self.search_edit.setPlaceholderText("Найти в PDF…")
        self.search_edit.setFixedWidth(140)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self._start_search)
        self.search_edit.textChanged.connect(self._on_search_text)
        row.addWidget(self.search_edit)

        self.search_next_btn = self._tool_button("down", "Следующее совпадение")
        self.search_next_btn.clicked.connect(self.next_match)
        self.search_next_btn.setVisible(False)
        row.addWidget(self.search_next_btn)

        self.search_prev_btn = self._tool_button("up", "Предыдущее совпадение")
        self.search_prev_btn.clicked.connect(self.previous_match)
        self.search_prev_btn.setVisible(False)
        row.addWidget(self.search_prev_btn)

        return bar

    @staticmethod
    def _tool_button(icon: str, tooltip: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("pdfTool")
        set_line_icon(button, icon)
        button.setAccessibleName(tooltip)
        button.setToolTip(tooltip)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.setAutoRaise(True)
        button.setMinimumWidth(28)
        return button

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setObjectName("pdfSeparator")
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFixedWidth(9)
        return line

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def open_pdf(self, file_path: str = None):
        """Open a PDF (or show the file picker) and render its first page."""
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Открыть PDF", "", "PDF (*.pdf)")
        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path: str):
        """Read metadata synchronously; page pixels are rendered in a worker."""
        document = None
        try:
            document = fitz.open(file_path)
            self.current_file_path = str(Path(file_path).resolve())

            # Password handling
            if document.is_encrypted or document.needs_pass:
                pwd, ok = QtWidgets.QInputDialog.getText(
                    self, "PDF защищён паролем",
                    "Введите пароль для открытия документа:",
                    QtWidgets.QLineEdit.Password
                )
                if not ok:
                    self.pdf_label.setText("Документ защищён паролем")
                    self.status.setText("Открытие отменено")
                    document.close()
                    return
                auth_rc = document.authenticate(pwd)
                if auth_rc <= 0:
                    self.pdf_label.setText("Неверный пароль")
                    self.status.setText("Ошибка авторизации")
                    document.close()
                    return
                self.pdf_password = pwd
            else:
                self.pdf_password = ""

            self.total_pages = len(document)
            if self.total_pages:
                first = document.load_page(0).rect
                self._page_pt = (first.width, first.height)
                self._page_sizes = {0: self._page_pt}

            # Load Bookmarks / Table of Contents
            self._load_outline(document)

            document.close()
            document = None
        except Exception as exc:  # noqa: BLE001
            if document is not None:
                try:
                    document.close()
                except Exception:
                    pass
            self.pdf_label.setText(f"Ошибка PDF: {exc}")
            self.status.setText("Не удалось открыть PDF")
            return

        if not self.total_pages:
            self.pdf_label.setText("Пустой PDF")
            self.status.setText("Документ не содержит страниц")
            return

        self.current_page = 0
        self.rotation = 0
        self._cache.clear()
        self._clear_search(render=False)
        self._sync_page_controls()
        self.document_loaded.emit(self.current_file_path)

        # Fit width by default
        self._fit_mode = "width"
        self.zoom = self._zoom_for_fit("width", default=100.0)
        self._sync_zoom_combo()
        self._request_render()
        self._fit_timer.start()

    def _load_outline(self, document):
        self.outline_tree.clear()
        try:
            toc = document.get_toc()
        except Exception:
            toc = []

        if not toc:
            self.toc_btn.setEnabled(False)
            self.toc_btn.setToolTip("Оглавление отсутствует в этом документе")
            self.outline_panel.setVisible(False)
            self.toc_btn.setChecked(False)
            return

        self.toc_btn.setEnabled(True)
        self.toc_btn.setToolTip("Оглавление документа")
        stack = {0: self.outline_tree.invisibleRootItem()}
        for item in toc:
            level = item[0]
            title = item[1]
            page = item[2]
            parent = stack.get(level - 1, self.outline_tree.invisibleRootItem())
            tree_item = QtWidgets.QTreeWidgetItem(parent, [title])
            tree_item.setData(0, QtCore.Qt.UserRole, max(0, page - 1))
            tree_item.setToolTip(0, f"{title} (стр. {page})")
            stack[level] = tree_item

        self.outline_tree.expandToDepth(1)

    def _toggle_outline(self, visible: bool):
        self.outline_panel.setVisible(visible)

    def _on_outline_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int):
        target_page = item.data(0, QtCore.Qt.UserRole)
        if target_page is not None:
            self.goto_page(int(target_page))

    def _toggle_invert(self, checked: bool):
        self.invert_colors = checked
        self._cache.clear()
        self._request_render()

    # ------------------------------------------------------------------
    # Page navigation
    # ------------------------------------------------------------------
    def goto_page(self, page: int):
        if self.total_pages <= 0:
            return
        page = max(0, min(int(page), self.total_pages - 1))
        if page == self.current_page and self.pdf_label.pixmap() is not None:
            self.scroll.verticalScrollBar().setValue(0)
            return
        self.current_page = page
        self._sync_page_controls()
        if self._search_pages and page in self._search_pages:
            self._search_index = self._search_pages.index(page)
        self._request_render()

    def first_page(self):
        self.goto_page(0)

    def previous_page(self):
        self.goto_page(self.current_page - 1)

    def next_page(self):
        self.goto_page(self.current_page + 1)

    def last_page(self):
        self.goto_page(self.total_pages - 1)

    def prompt_goto_page(self):
        if self.total_pages <= 0:
            return
        val, ok = QtWidgets.QInputDialog.getInt(
            self, "Перейти к странице",
            f"Номер страницы (1..{self.total_pages}):",
            self.current_page + 1, 1, max(1, self.total_pages)
        )
        if ok:
            self.goto_page(val - 1)

    def update_page_display_method(self):
        """Compatibility with the previous viewer API."""
        self._request_render()

    def _sync_page_controls(self):
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, max(1, self.total_pages))
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)
        self.total_label.setText(f"/ {self.total_pages}")
        has_pages = self.total_pages > 0
        for button in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            button.setEnabled(has_pages)

    # ------------------------------------------------------------------
    # Zoom / fit / rotation
    # ------------------------------------------------------------------
    def _page_css_size(self, zoom: Optional[float] = None) -> Tuple[float, float]:
        zoom = self.zoom if zoom is None else zoom
        factor = (BASE_DPI / 72.0) * (zoom / 100.0)
        return (self._page_pt[0] * factor, self._page_pt[1] * factor)

    def _viewport_size(self) -> Tuple[int, int]:
        width = max(120, self.scroll.viewport().width() - PAGE_MARGIN * 2 - 18)
        height = max(120, self.scroll.viewport().height() - PAGE_MARGIN * 2 - 18)
        return width, height

    def _zoom_for_fit(self, mode: str, default: float = 100.0) -> float:
        width, height = self._viewport_size()
        if self.scroll.viewport().width() < 200:
            return default
        base_w = self._page_pt[0] * BASE_DPI / 72.0
        base_h = self._page_pt[1] * BASE_DPI / 72.0
        if base_w <= 1 or base_h <= 1:
            return default
        if mode == "width":
            zoom = 100.0 * width / base_w
        else:
            zoom = 100.0 * min(width / base_w, height / base_h)
        return max(MIN_ZOOM, min(MAX_ZOOM, zoom))

    def set_fit(self, mode: str):
        self._fit_mode = mode
        self.zoom = self._zoom_for_fit(mode)
        self._sync_zoom_combo()
        self._request_render()

    def _apply_fit(self):
        if not self.current_file_path or self._fit_mode is None:
            return
        target = self._zoom_for_fit(self._fit_mode)
        if abs(target - self.zoom) < 0.4:
            return
        self.zoom = target
        self._sync_zoom_combo()
        self._request_render()

    def _set_zoom(self, zoom: float, render: bool = True):
        self._fit_mode = None
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, float(zoom)))
        self._sync_zoom_combo()
        if render:
            self._request_render()

    def zoom_in(self):
        self._step_zoom(1)

    def zoom_out(self):
        self._step_zoom(-1)

    def zoom_fit(self):
        self.set_fit("page")

    def _step_zoom(self, direction: int):
        presets = list(ZOOM_PRESETS)
        if direction > 0:
            target = next((value for value in presets if value > self.zoom + 0.5),
                          presets[-1])
        else:
            target = next((value for value in reversed(presets)
                           if value < self.zoom - 0.5), presets[0])
        self._set_zoom(target)

    def _zoom_combo_changed(self, index: int):
        data = self.zoom_combo.itemData(index)
        if data == "fit_width":
            self.set_fit("width")
        elif data == "fit_page":
            self.set_fit("page")
        elif isinstance(data, float):
            self._set_zoom(data)

    def _sync_zoom_combo(self):
        self.zoom_combo.blockSignals(True)
        if self._fit_mode == "width":
            self.zoom_combo.setCurrentIndex(0)
        elif self._fit_mode == "page":
            self.zoom_combo.setCurrentIndex(1)
        else:
            text = f"{int(round(self.zoom))}%"
            index = self.zoom_combo.findText(text)
            if index < 0:
                self.zoom_combo.addItem(text, float(self.zoom))
                index = self.zoom_combo.count() - 1
            self.zoom_combo.setCurrentIndex(index)
        self.zoom_combo.blockSignals(False)

    def rotate_page(self):
        if not self.current_file_path:
            return
        self.rotation = (self.rotation + 90) % 360
        self._page_pt = (self._page_pt[1], self._page_pt[0])
        self._page_sizes = {}
        self._cache.clear()
        if self._fit_mode:
            self.zoom = self._zoom_for_fit(self._fit_mode)
            self._sync_zoom_combo()
        self._request_render()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _display_size(self, zoom: Optional[float] = None) -> Tuple[int, int]:
        width, height = self._page_css_size(zoom)
        return max(1, int(round(width))), max(1, int(round(height)))

    def _cache_key(self) -> tuple:
        return (self.current_page, round(self.zoom, 1), self.rotation,
                self._search_term, round(self.devicePixelRatioF(), 2), self.invert_colors)

    def _request_render(self):
        if not self.current_file_path or self.total_pages <= 0:
            return
        key = self._cache_key()
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            self._apply_pixmap(cached, self.zoom, self.rotation,
                               self._page_sizes.get(self.current_page, self._page_pt))
            return
        self._render_generation += 1
        self.status.setText(f"Страница {self.current_page + 1} из {self.total_pages}"
                            f" · рендеринг…")
        self.pool.start(_PdfRenderTask(
            self.current_file_path, self.current_page, self.zoom, self.rotation,
            self.devicePixelRatioF(), self._render_generation, self._search_term,
            self._bridge, self.pdf_password, self.invert_colors))

    @QtCore.pyqtSlot(object)
    def _render_finished(self, payload: dict):
        if not isinstance(payload, dict):
            return
        if payload.get("generation") != self._render_generation:
            return
        if payload.get("error"):
            self.status.setText(f"Ошибка рендера: {payload['error']}")
            return
        if payload.get("page") != self.current_page:
            return
        image = QtGui.QImage.fromData(payload["png"], "PNG")
        if image.isNull():
            self.status.setText("Не удалось отобразить страницу")
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(float(payload.get("dpr", 1.0)))
        size = tuple(payload.get("size") or self._page_pt)
        self._page_sizes[self.current_page] = (float(size[0]), float(size[1]))
        self._page_pt = (float(size[0]), float(size[1]))
        if pixmap.width() * pixmap.height() <= CACHE_MAX_PIXELS:
            self._cache[self._cache_key()] = pixmap
            while len(self._cache) > CACHE_LIMIT:
                self._cache.popitem(last=False)
        self._apply_pixmap(pixmap, float(payload.get("zoom", self.zoom)),
                           int(payload.get("rotation", self.rotation)),
                           (float(size[0]), float(size[1])),
                           hits=int(payload.get("hits", 0)))

    def _apply_pixmap(self, pixmap: QtGui.QPixmap, zoom: float, rotation: int,
                      size_pt: Tuple[float, float], hits: int = 0):
        self._page_pt = size_pt
        width, height = self._display_size(zoom)
        self.pdf_label.setFixedSize(width, height)
        self.pdf_label.setPixmap(pixmap)
        self.pdf_label.setText("")
        self.page_changed.emit(self.current_page + 1, self.total_pages)
        self._scroll_to_page_top()
        self._update_status(hits)
        if self._fit_mode:
            available = self.scroll.viewport().width() - PAGE_MARGIN * 2 - 18
            if available > 120 and abs(width - available) > 2:
                self._fit_timer.start()

    def _scroll_to_page_top(self):
        QtCore.QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(0))

    def _update_status(self, hits: int = 0):
        width, height = self._page_pt
        zoom_text = (f"по ширине ({int(round(self.zoom))}%)"
                     if self._fit_mode == "width"
                     else f"страница ({int(round(self.zoom))}%)"
                     if self._fit_mode == "page"
                     else f"{int(round(self.zoom))}%")
        text = (f"Страница {self.current_page + 1} из {self.total_pages}"
                f"  ·  {zoom_text}  ·  {width:.0f}×{height:.0f} pt")
        if self._search_term:
            if self._search_total:
                text += (f"  ·  найдено: {self._search_total} "
                         f"(стр. {len(self._search_pages)})")
            else:
                text += "  ·  ничего не найдено"
        elif hits:
            text += f"  ·  совпадений на странице: {hits}"
        self.status.setText(text)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _on_search_text(self, text: str):
        if not text.strip() and self._search_term:
            self._clear_search()

    def _start_search(self):
        query = self.search_edit.text().strip()
        if not query:
            self._clear_search()
            return
        if not self.current_file_path:
            return
        self._search_generation += 1
        self.status.setText(f"Поиск «{query}» по документу…")
        self.pool.start(_PdfSearchTask(self.current_file_path, query,
                                       self._search_generation, self._search_bridge,
                                       self.pdf_password))

    @QtCore.pyqtSlot(object)
    def _search_finished(self, payload: dict):
        if not isinstance(payload, dict):
            return
        if payload.get("generation") != self._search_generation:
            return
        if payload.get("error"):
            self.status.setText(f"Ошибка поиска: {payload['error']}")
            return
        query = str(payload.get("query") or "")
        pages = [int(page) for page, _count in payload.get("pages") or []]
        self._search_term = query
        self._search_pages = pages
        self._search_total = int(payload.get("total") or 0)
        self._search_index = 0
        self.search_next_btn.setVisible(bool(pages))
        self.search_prev_btn.setVisible(bool(pages))
        if pages:
            target = next((page for page in pages if page >= self.current_page), pages[0])
            self._search_index = pages.index(target)
            if target == self.current_page:
                self._cache.clear()
                self._request_render()
            else:
                self.goto_page(target)
        else:
            self._cache.clear()
            self._request_render()
            self.status.setText(f"«{query}» не найдено")

    def next_match(self):
        if not self._search_pages:
            return
        self._search_index = (self._search_index + 1) % len(self._search_pages)
        self.goto_page(self._search_pages[self._search_index])

    def previous_match(self):
        if not self._search_pages:
            return
        self._search_index = (self._search_index - 1) % len(self._search_pages)
        self.goto_page(self._search_pages[self._search_index])

    def _clear_search(self, render: bool = True):
        self._search_generation += 1
        self._search_term = ""
        self._search_pages = []
        self._search_total = 0
        self._search_index = 0
        self.search_next_btn.setVisible(False)
        self.search_prev_btn.setVisible(False)
        self._cache.clear()
        if render:
            self._request_render()

    # ------------------------------------------------------------------
    # Text Extraction and Image Export
    # ------------------------------------------------------------------
    def show_page_text_dialog(self):
        if not self.current_file_path or self.total_pages <= 0:
            return
        try:
            document = fitz.open(self.current_file_path)
            if self.pdf_password:
                document.authenticate(self.pdf_password)
            page = document.load_page(self.current_page)
            text = page.get_text("text")
            document.close()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Ошибка извлечения текста", str(exc))
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Текст страницы {self.current_page + 1} — {Path(self.current_file_path).name}")
        dialog.resize(620, 500)
        d_layout = QtWidgets.QVBoxLayout(dialog)

        text_edit = QtWidgets.QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        text_edit.setFont(QtGui.QFont("Cascadia Code", 10))
        d_layout.addWidget(text_edit)

        b_layout = QtWidgets.QHBoxLayout()
        copy_btn = QtWidgets.QPushButton("Копировать в буфер")
        copy_btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(text))
        close_btn = QtWidgets.QPushButton("Закрыть")
        close_btn.clicked.connect(dialog.accept)
        b_layout.addWidget(copy_btn)
        b_layout.addStretch()
        b_layout.addWidget(close_btn)
        d_layout.addLayout(b_layout)

        dialog.exec_()

    def copy_page_text(self):
        if not self.current_file_path or self.total_pages <= 0:
            return
        try:
            document = fitz.open(self.current_file_path)
            if self.pdf_password:
                document.authenticate(self.pdf_password)
            page = document.load_page(self.current_page)
            text = page.get_text("text")
            document.close()
            QtWidgets.QApplication.clipboard().setText(text)
            self.status.setText("Текст текущей страницы скопирован в буфер обмена")
        except Exception as exc:
            self.status.setText(f"Ошибка копирования текста: {exc}")

    def save_page_as_image(self):
        pixmap = self.pdf_label.pixmap()
        if not pixmap or pixmap.isNull():
            return
        default_name = f"{Path(self.current_file_path).stem}_page_{self.current_page + 1}.png" if self.current_file_path else "page.png"
        out_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Сохранить страницу как изображение", default_name, "PNG Image (*.png)"
        )
        if out_path:
            pixmap.save(out_path, "PNG")
            self.status.setText(f"Страница сохранена: {Path(out_path).name}")

    def _show_context_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        act_copy_text = menu.addAction("Копировать текст страницы")
        act_copy_text.triggered.connect(self.copy_page_text)
        act_text_dialog = menu.addAction("Просмотр текста страницы…")
        act_text_dialog.triggered.connect(self.show_page_text_dialog)
        act_save_img = menu.addAction("Сохранить страницу как изображение (PNG)…")
        act_save_img.triggered.connect(self.save_page_as_image)
        menu.addSeparator()
        act_goto = menu.addAction("Перейти к странице… (Ctrl+G)")
        act_goto.triggered.connect(self.prompt_goto_page)
        act_rotate = menu.addAction("Повернуть на 90° (Ctrl+R)")
        act_rotate.triggered.connect(self.rotate_page)
        menu.addSeparator()
        act_fit_w = menu.addAction("По ширине окна (Ctrl+1)")
        act_fit_w.triggered.connect(lambda: self.set_fit("width"))
        act_fit_p = menu.addAction("Вся страница (Ctrl+0)")
        act_fit_p.triggered.connect(lambda: self.set_fit("page"))
        menu.exec_(self.canvas.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj in (self.scroll.viewport(), self.canvas, self.pdf_label):
            kind = event.type()
            if kind == QtCore.QEvent.Wheel and event.modifiers() & QtCore.Qt.ControlModifier:
                self._step_zoom(1 if event.angleDelta().y() > 0 else -1)
                return True
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                if self._can_pan():
                    self._drag_origin = event.globalPos()
                    self._pan_widget = obj
                    self._drag_scroll = (self.scroll.horizontalScrollBar().value(),
                                         self.scroll.verticalScrollBar().value())
                    obj.setCursor(QtCore.Qt.ClosedHandCursor)
                    return True
            elif kind == QtCore.QEvent.MouseMove and self._drag_origin is not None:
                delta = event.globalPos() - self._drag_origin
                hbar = self.scroll.horizontalScrollBar()
                vbar = self.scroll.verticalScrollBar()
                hbar.setValue(self._drag_scroll[0] - delta.x())
                vbar.setValue(self._drag_scroll[1] - delta.y())
                return True
            elif kind == QtCore.QEvent.MouseButtonRelease and self._drag_origin is not None:
                self._drag_origin = None
                self._drag_scroll = None
                if self._pan_widget is not None:
                    self._pan_widget.unsetCursor()
                    self._pan_widget = None
                return True
            elif kind == QtCore.QEvent.MouseButtonDblClick:
                self.set_fit("page" if self._fit_mode == "width" else "width")
                return True
        return super().eventFilter(obj, event)

    def _can_pan(self) -> bool:
        return (self.pdf_label.width() > self.scroll.viewport().width()
                or self.pdf_label.height() > self.scroll.viewport().height())

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        if modifiers & QtCore.Qt.ControlModifier:
            if key in (QtCore.Qt.Key_Plus, QtCore.Qt.Key_Equal):
                self.zoom_in()
                return
            if key == QtCore.Qt.Key_Minus:
                self.zoom_out()
                return
            if key == QtCore.Qt.Key_0:
                self.set_fit("page")
                return
            if key == QtCore.Qt.Key_1:
                self.set_fit("width")
                return
            if key == QtCore.Qt.Key_R:
                self.rotate_page()
                return
            if key == QtCore.Qt.Key_F:
                self.search_edit.setFocus()
                self.search_edit.selectAll()
                return
            if key == QtCore.Qt.Key_G:
                self.prompt_goto_page()
                return
        if key == QtCore.Qt.Key_PageDown:
            self.next_page()
            return
        if key == QtCore.Qt.Key_PageUp:
            self.previous_page()
            return
        if key == QtCore.Qt.Key_Home:
            self.first_page()
            return
        if key == QtCore.Qt.Key_End:
            self.last_page()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 680
        for widget in (self.first_btn, self.last_btn,
                       self.fit_page_btn, self.rotate_btn, self.invert_btn, self.text_btn):
            widget.setVisible(not compact)
        self.search_edit.setFixedWidth(110 if compact else 140)
        if self.current_file_path and self._fit_mode:
            self._fit_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus(QtCore.Qt.OtherFocusReason)
        if self.current_file_path and self._fit_mode:
            self._fit_timer.start()

    def closeEvent(self, event):
        self._render_generation += 1
        self._search_generation += 1
        self.document_closed.emit()
        super().closeEvent(event)
