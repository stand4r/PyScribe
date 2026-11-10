"""Read-only, theme-aware viewer for Office and OpenDocument text."""
from pathlib import Path

from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets

from services.background import run_async
from services.office_reader import OfficeReader

DOCUMENT_EXTENSIONS = {".docx", ".odt"}


class _ReadingDocument(QtGui.QTextDocument):
    def __init__(self, images=(), parent=None):
        super().__init__(parent)
        self._images = {url.toString(): image for url, image in images}

    def loadResource(self, resource_type, url):
        if resource_type == QtGui.QTextDocument.ImageResource:
            return self._images.get(url.toString())
        return None


def _make_layout(path, preview, dark, gui_thread):
    preview = preview or OfficeReader(path)
    paper = QtGui.QColor("#232731" if dark else "#fffdf9")
    ink = QtGui.QColor("#cbd4e0" if dark else "#303943")
    document = _ReadingDocument(preview.images)
    document.setDocumentMargin(0)
    margins = preview.margins
    document.setPageSize(QtCore.QSizeF(
        max(1, preview.sheet.width() - margins.left() - margins.right()),
        max(1, preview.sheet.height() - margins.top() - margins.bottom()),
    ))
    def tint(amount):
        return QtGui.QColor(*(round(a + (b - a) * amount)
                              for a, b in zip(paper.getRgb()[:3], ink.getRgb()[:3]))).name()

    link = "#a2bccd" if paper.lightness() < 128 else "#426478"
    document.setDefaultStyleSheet(f"""
        body {{ font-family: "Segoe UI"; font-size: 12pt; color: {ink.name()}; }}
        p, li {{ margin-top: 3px; margin-bottom: 9px; line-height: 133%; }}
        h1 {{ font-size: 22pt; margin-top: 16px; margin-bottom: 11px; }}
        h2 {{ font-size: 17pt; margin-top: 14px; margin-bottom: 8px; }}
        h3, h4, h5, h6 {{ font-size: 14pt; margin-top: 12px; margin-bottom: 6px; }}
        a {{ color: {link}; }}
        td, th {{ border-bottom: 1px solid {tint(0.20)}; }}
        th {{ text-align: left; }}
        .tableHeader {{ background-color: {tint(0.13)}; }}
        .tableStripe {{ background-color: {tint(0.045)}; }}
    """)
    document.setHtml("<body>" + (preview.content or "<p>Документ пуст.</p>") + "</body>")
    page_count = max(1, document.pageCount())
    document.moveToThread(gui_thread)
    return preview, document, page_count, paper, ink


class _LoadingArc(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(28, 28)
        self._angle = 0
        self._timer = QtCore.QTimer(self, interval=30)
        self._timer.timeout.connect(self._advance)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _advance(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(3, 3, -3, -3)
        painter.setPen(QtGui.QPen(self.palette().mid().color(), 2))
        painter.drawEllipse(rect)
        painter.setPen(QtGui.QPen(self.palette().text().color(), 2))
        painter.drawArc(rect, -self._angle * 16, 105 * 16)
        painter.end()


class _PageCanvas(QtWidgets.QAbstractScrollArea):
    """Paint only visible pages of a locally laid-out text document."""

    page_changed = QtCore.pyqtSignal(int, int)
    gap = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = _ReadingDocument(parent=self)
        self.sheet = QtCore.QSizeF(794, 1123)  # A4 at 96 dpi
        self.margins = QtCore.QMarginsF(88, 88, 88, 88)
        self.paper = QtGui.QColor("#fffdf9")
        self.ink = QtGui.QColor("#303943")
        self.zoom = 1.0
        self.page_count = 1
        self._wheel_remainder = 0.0
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.verticalScrollBar().setSingleStep(48)
        self.verticalScrollBar().valueChanged.connect(self._emit_page)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.viewport().setMouseTracking(True)

    def show_document(self, document, page_count, sheet, margins):
        old = self.document
        self.document = document
        document.setParent(self)
        old.deleteLater()
        self.page_count = page_count
        self.sheet = sheet
        self.margins = margins
        self._sync_scrollbars()

    def _scale(self):
        available = max(1, self.viewport().width() - 2 * self.gap)
        return min(1.0, available / self.sheet.width()) * self.zoom

    def _page_pitch(self):
        return self.sheet.height() * self._scale() + self.gap

    def _sync_scrollbars(self):
        count = self.page_count
        height = round(count * self._page_pitch() + self.gap)
        width = round(self.sheet.width() * self._scale() + 2 * self.gap)
        for bar, extent, viewport in (
            (self.verticalScrollBar(), height, self.viewport().height()),
            (self.horizontalScrollBar(), width, self.viewport().width()),
        ):
            bar.setPageStep(viewport)
            bar.setRange(0, max(0, extent - viewport))
        self._emit_page()
        self.viewport().update()

    def _emit_page(self, *_args):
        count = self.page_count
        page = min(count, int(self.verticalScrollBar().value() / self._page_pitch()) + 1)
        self.page_changed.emit(page, count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_scrollbars()

    def change_zoom(self, factor):
        bar = self.verticalScrollBar()
        page_offset = bar.value() / self._page_pitch()
        self.zoom = min(3.0, max(0.5, self.zoom * factor))
        self._sync_scrollbars()
        bar.setValue(round(page_offset * self._page_pitch()))

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            self.change_zoom(1.12 ** (delta / 120))
            event.accept()
            return
        if not event.modifiers() & QtCore.Qt.ShiftModifier:
            pixels = event.pixelDelta().y()
            angle = event.angleDelta().y()
            if pixels or angle:
                delta = pixels * 2.0 if pixels else angle * 1.5
                self._wheel_remainder += delta
                step = int(self._wheel_remainder)
                self._wheel_remainder -= step
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() - step)
                event.accept()
                return
        super().wheelEvent(event)

    def _sheet_left(self, scale):
        width = self.sheet.width() * scale
        return max(self.gap, (self.viewport().width() - width) / 2) - self.horizontalScrollBar().value()

    def _link_at(self, point):
        scale = self._scale()
        pitch = self._page_pitch()
        offset = point.y() + self.verticalScrollBar().value() - self.gap
        page = int(offset // pitch)
        size = self.document.pageSize()
        x = (point.x() - self._sheet_left(scale)) / scale - self.margins.left()
        y = (offset - page * pitch) / scale - self.margins.top()
        if 0 <= page < self.page_count and 0 <= x < size.width() and 0 <= y < size.height():
            return self.document.documentLayout().anchorAt(QtCore.QPointF(x, page * size.height() + y))
        return ""

    def mouseMoveEvent(self, event):
        link = self._link_at(event.pos())
        self.viewport().setCursor(QtCore.Qt.PointingHandCursor if link else QtCore.Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def _goto_bookmark(self, name):
        block = self.document.begin()
        while block.isValid():
            fragments = block.begin()
            while not fragments.atEnd():
                fragment = fragments.fragment()
                if fragment.isValid() and name in fragment.charFormat().anchorNames():
                    rect = self.document.documentLayout().blockBoundingRect(block)
                    height = self.document.pageSize().height()
                    page = int(rect.top() // height)
                    within_page = self.margins.top() + rect.top() - page * height
                    self.verticalScrollBar().setValue(
                        round(page * self._page_pitch() + within_page * self._scale()))
                    return
                fragments += 1
            block = block.next()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            url = QtCore.QUrl(self._link_at(event.pos()))
            if url.scheme().lower() in {"http", "https", "mailto"}:
                QtGui.QDesktopServices.openUrl(url)
                return
            if url.hasFragment() and not url.scheme() and not url.path():
                self._goto_bookmark(url.fragment())
                return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self.viewport())
        painter.fillRect(event.rect(), self.palette().window())
        scale = self._scale()
        pitch = self._page_pitch()
        offset = self.verticalScrollBar().value()
        first = max(0, int((offset - self.gap) // pitch))
        last = min(self.page_count,
                   int((offset + self.viewport().height()) // pitch) + 1)
        width = self.sheet.width() * scale
        height = self.sheet.height() * scale
        left = self._sheet_left(scale)
        size = self.document.pageSize()
        context = QtGui.QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QtGui.QPalette.Text, self.ink)
        for page in range(first, last):
            top = self.gap + page * pitch - offset
            rect = QtCore.QRectF(left, top, width, height)
            painter.fillRect(rect.translated(2, 3), QtGui.QColor(0, 0, 0, 38))
            painter.fillRect(rect, self.paper)
            painter.save()
            painter.translate(left + self.margins.left() * scale,
                              top + self.margins.top() * scale)
            painter.scale(scale, scale)
            painter.setClipRect(QtCore.QRectF(0, 0, size.width(), size.height()))
            painter.translate(0, -page * size.height())
            context.clip = QtCore.QRectF(0, page * size.height(), size.width(), size.height())
            self.document.documentLayout().draw(painter, context)
            painter.restore()
        painter.end()


class DocumentViewerWidget(QtWidgets.QWidget):
    """Read document packages and lay out their pages without a converter."""

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = str(file_path)
        self.setObjectName("documentViewer")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        toolbar = QtWidgets.QHBoxLayout()
        name = QtWidgets.QLabel(Path(self.file_path).name)
        name.setTextFormat(QtCore.Qt.PlainText)
        name.setObjectName("markdownTitle")
        name.setToolTip(self.file_path)
        name.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        toolbar.addWidget(name, 1)
        layout.addLayout(toolbar)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("documentStatus")
        layout.addWidget(self.status)

        suffix = Path(self.file_path).suffix.lower()
        if suffix == ".xlsx":
            from widgets.TableViewerWidget import TableViewerWidget
            self.stack.addWidget(TableViewerWidget(self.file_path, parent=self))
            self.status.hide()
            return

        self._theme = QtWidgets.QComboBox()
        self._theme.setAccessibleName("Тема страницы")
        self._theme.addItems(["Белая страница", "Тёмная страница"])
        toolbar.addWidget(self._theme)
        self.canvas = _PageCanvas(self)
        self.canvas.page_changed.connect(self._show_page_number)
        self.stack.addWidget(self.canvas)
        for icon, tooltip, factor in (
            ("minus", "Уменьшить масштаб", 1 / 1.15),
            ("add", "Увеличить масштаб", 1.15),
        ):
            button = QtWidgets.QToolButton()
            set_line_icon(button, icon)
            button.setAccessibleName(tooltip)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, value=factor: self.canvas.change_zoom(value))
            toolbar.addWidget(button)
        self._theme.currentIndexChanged.connect(self._render)
        self._preview = None
        self._busy = False
        self._loading = QtWidgets.QWidget()
        wait_layout = QtWidgets.QVBoxLayout(self._loading)
        wait_layout.addStretch(1)
        label = QtWidgets.QLabel("Открываем документ…")
        label.setAlignment(QtCore.Qt.AlignCenter)
        wait_layout.addWidget(label)
        wait_layout.addWidget(_LoadingArc(), 0, QtCore.Qt.AlignHCenter)
        wait_layout.addStretch(1)
        self.stack.addWidget(self._loading)
        self._render()

    def _show_page_number(self, page, total):
        self.status.setText(f"Страница {page} из {total} · Режим чтения")

    def _render(self, *_args):
        if self._busy:
            return
        self._busy = True
        self._theme.setEnabled(False)
        self._scroll_position = self.canvas.verticalScrollBar().value()
        self.stack.setCurrentWidget(self._loading)
        self.status.setText("Чтение и раскладка страниц…")
        path, preview = self.file_path, self._preview
        dark = self._theme.currentIndex() == 1
        gui_thread = self.thread()
        run_async(lambda: _make_layout(path, preview, dark, gui_thread),
                  self._document_ready, self._show_error)

    def _document_ready(self, result):
        preview, document, page_count, paper, ink = result
        self._preview = preview
        self.canvas.paper, self.canvas.ink = paper, ink
        self.canvas.show_document(document, page_count, preview.sheet, preview.margins)
        self.stack.setCurrentWidget(self.canvas)
        self.canvas.verticalScrollBar().setValue(self._scroll_position)
        self._busy = False
        self._theme.setEnabled(True)

    def _show_error(self, message):
        error = QtWidgets.QLabel(f"Не удалось открыть документ:\n{message}")
        error.setTextFormat(QtCore.Qt.PlainText)
        error.setWordWrap(True)
        error.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(error)
        self.stack.setCurrentWidget(error)
        self.status.setText("Ошибка чтения")
        self._busy = False
