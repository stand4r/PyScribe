"""A native Markdown reading view with navigation and live editor updates."""
from bisect import bisect_right
from pathlib import Path
import re
import unicodedata

from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets


class _ReadingBrowser(QtWidgets.QTextBrowser):
    def loadResource(self, resource_type, url):
        # Previewing a file should not make network requests for embedded images.
        resolved = self.document().baseUrl().resolved(url)
        if resource_type == QtGui.QTextDocument.ImageResource and resolved.isLocalFile():
            return super().loadResource(resource_type, resolved)
        return None


class MarkdownViewerWidget(QtWidgets.QWidget):
    open_editor_requested = QtCore.pyqtSignal(str)
    open_preview_requested = QtCore.pyqtSignal(str)

    def __init__(self, file_path="", content=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._raw_content = ""
        self._source = None
        self._headings = []
        self._positions = []
        self._anchors = {}
        self.setObjectName("markdownViewer")
        self._render_timer = QtCore.QTimer(self, singleShot=True, interval=180)
        self._render_timer.timeout.connect(self.reload)
        self._build_ui()
        if content is None:
            self.reload()
        else:
            self.set_markdown(content)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        header = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel()
        self.title_label.setTextFormat(QtCore.Qt.PlainText)
        self.title_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.title_label.setObjectName("markdownTitle")
        header.addWidget(self.title_label, 1)
        self.progress = QtWidgets.QLabel()
        header.addWidget(self.progress)
        root.addLayout(header)

        toolbar = QtWidgets.QHBoxLayout()
        def button(label, icon, tip, slot):
            control = QtWidgets.QToolButton()
            control.setText(label)
            set_line_icon(control, icon)
            control.setAccessibleName(tip)
            control.setToolTip(tip)
            if slot is not None:
                control.clicked.connect(slot)
            toolbar.addWidget(control)
            return control

        self.outline_btn = button("Разделы", "outline", "Показать или скрыть оглавление", None)
        self.outline_btn.setCheckable(True)
        self.outline_btn.toggled.connect(self._toggle_outline)
        button("Поиск", "search", "Найти в документе (Ctrl+F)", self._show_search)
        button("", "minus", "Уменьшить текст", lambda: self.browser.zoomOut())
        button("", "add", "Увеличить текст", lambda: self.browser.zoomIn())
        toolbar.addStretch(1)
        menu_btn = button("", "more", "Действия с документом", None)
        menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(menu_btn)
        menu.addAction("Обновить", self.reload)
        menu.addAction("Копировать исходный Markdown", self._copy_markdown)
        edit = menu.addAction("Открыть в редакторе", self._request_editor)
        edit.setEnabled(bool(self.file_path))
        menu_btn.setMenu(menu)
        root.addLayout(toolbar)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Найти в документе…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._find_next)
        self.search.hide()
        root.addWidget(self.search)
        self._find_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence.Find, self)
        self._find_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self._find_shortcut.activated.connect(self._show_search)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(8)
        self.outline = QtWidgets.QTreeWidget()
        self.outline.setObjectName("markdownOutline")
        self.outline.setHeaderHidden(True)
        self.outline.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.outline.setFixedWidth(205)
        self.outline.setAccessibleName("Оглавление")
        self.outline.currentItemChanged.connect(self._outline_selected)
        self.outline.hide()
        body.addWidget(self.outline)
        reading = QtWidgets.QHBoxLayout()
        self.browser = _ReadingBrowser()
        self.browser.setObjectName("markdownBrowser")
        self.browser.setFont(QtGui.QFont("Segoe UI", 11))
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._open_link)
        self.browser.setMaximumWidth(850)
        self.browser.verticalScrollBar().valueChanged.connect(self._update_position)
        self.browser.verticalScrollBar().rangeChanged.connect(self._update_position)
        reading.addStretch(1)
        reading.addWidget(self.browser, 20)
        reading.addStretch(1)
        body.addLayout(reading, 1)
        root.addLayout(body, 1)

    def bind_source(self, source):
        if source is self._source:
            self.reload()
            return
        if self._source is not None:
            self._source.textChanged.disconnect(self._schedule_render)
            self._source.destroyed.disconnect(self._source_closed)
        self._source = source
        source.textChanged.connect(self._schedule_render)
        source.destroyed.connect(self._source_closed)
        self.reload()

    def _schedule_render(self):
        self._render_timer.start()

    def _source_closed(self):
        self._source = None
        self._render_timer.stop()

    def load_file(self, file_path):
        self.file_path = file_path
        try:
            content = Path(file_path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as error:
            self.set_markdown("")
            self.browser.setPlainText(f"Не удалось прочитать файл: {error}")
            return
        self.set_markdown(content)

    @staticmethod
    def _mix(start, end, fraction):
        return QtGui.QColor(*(round(a + (b - a) * fraction)
                             for a, b in zip(start.getRgb()[:3], end.getRgb()[:3])))

    def _style_tables(self, frame, paper, text):
        for child in frame.childFrames():
            if isinstance(child, QtGui.QTextTable):
                fmt = child.format()
                fmt.setBorder(0)
                fmt.setCellSpacing(0)
                fmt.setCellPadding(0)
                fmt.setTopMargin(10)
                fmt.setBottomMargin(16)
                child.setFormat(fmt)
                header = self._mix(paper, text, 0.13)
                stripe = self._mix(paper, text, 0.045)
                rule = self._mix(paper, text, 0.19)
                for row in range(child.rows()):
                    for column in range(child.columns()):
                        cell = child.cellAt(row, column)
                        style = cell.format().toTableCellFormat()
                        style.setBackground(header if row == 0 else stripe if row % 2 else paper)
                        style.setLeftPadding(11)
                        style.setRightPadding(11)
                        style.setTopPadding(7)
                        style.setBottomPadding(7)
                        style.setBottomBorder(1)
                        style.setBottomBorderBrush(rule)
                        style.setBottomBorderStyle(QtGui.QTextFrameFormat.BorderStyle_Solid)
                        cell.setFormat(style)
            self._style_tables(child, paper, text)

    def _style_links(self, block, color):
        segments = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().anchorHref():
                segments.append((fragment.position(), fragment.length()))
            iterator += 1
        if segments:
            style = QtGui.QTextCharFormat()
            style.setForeground(color)
            style.setFontUnderline(True)
            cursor = QtGui.QTextCursor(block)
            for position, length in segments:
                cursor.setPosition(position)
                cursor.setPosition(position + length, QtGui.QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(style)

    def set_markdown(self, markdown_text):
        bar = self.browser.verticalScrollBar()
        fraction = bar.value() / max(1, bar.maximum())
        saved_position = self.browser.textCursor().position()
        self._raw_content = markdown_text
        name = Path(self.file_path).name if self.file_path else "Markdown"
        self.title_label.setText(name)
        self.title_label.setToolTip(self.file_path or name)
        doc = self.browser.document()
        doc.setBaseUrl(QtCore.QUrl.fromLocalFile(str(Path(self.file_path).resolve())) if self.file_path else QtCore.QUrl())
        doc.setDocumentMargin(22)
        features = QtGui.QTextDocument.MarkdownFeatures(
            QtGui.QTextDocument.MarkdownDialectGitHub | QtGui.QTextDocument.MarkdownNoHTML)
        doc.setMarkdown(markdown_text, features)
        self._headings.clear()
        self._positions.clear()
        self._anchors.clear()
        self.outline.blockSignals(True)
        self.outline.clear()
        palette = self.browser.palette()
        paper = palette.base().color()
        text = palette.text().color()
        cool = QtGui.QColor("#83a8bb" if paper.lightness() < 128 else "#426478")
        link = self._mix(text, cool, 0.55)
        self._style_tables(doc.rootFrame(), paper, text)
        parents = []
        block = doc.begin()
        while block.isValid():
            fmt = block.blockFormat()
            level = fmt.headingLevel()
            fmt.setTopMargin(18 if level else 0)
            fmt.setBottomMargin(10 if level else 7)
            fmt.setLineHeight(124, QtGui.QTextBlockFormat.ProportionalHeight)
            if fmt.hasProperty(QtGui.QTextFormat.BlockCodeFence):
                fmt.setBackground(palette.alternateBase())
                fmt.setLeftMargin(8)
                fmt.setBottomMargin(0)
            if fmt.intProperty(QtGui.QTextFormat.BlockQuoteLevel):
                fmt.setLeftMargin(18)
                fmt.setBackground(palette.alternateBase())
            cursor = QtGui.QTextCursor(block)
            cursor.setBlockFormat(fmt)
            self._style_links(block, link)
            if level:
                title = block.text()
                item = QtWidgets.QTreeWidgetItem([title])
                item.setToolTip(0, title)
                while parents and parents[-1][0] >= level:
                    parents.pop()
                if parents:
                    parents[-1][1].addChild(item)
                else:
                    self.outline.addTopLevelItem(item)
                parents.append((level, item))
                position = block.position()
                item.setData(0, QtCore.Qt.UserRole, position)
                self._headings.append(item)
                self._positions.append(position)
                slug = re.sub(r"[^\w\- ]", "", unicodedata.normalize("NFC", title).lower()).replace(" ", "-")
                anchor = slug
                index = 1
                while anchor in self._anchors:
                    anchor = f"{slug}-{index}"
                    index += 1
                self._anchors[anchor] = position
            block = block.next()
        self.outline.expandAll()
        self.outline.blockSignals(False)
        self.outline_btn.setEnabled(bool(self._headings))
        self._toggle_outline(self.outline_btn.isChecked())
        words = len(doc.toPlainText().split())
        self._reading_minutes = max(1, (words + 219) // 220) if words else 0
        cursor = QtGui.QTextCursor(doc)
        cursor.setPosition(min(saved_position, doc.characterCount() - 1))
        self.browser.setTextCursor(cursor)
        bar.setValue(round(fraction * bar.maximum()))
        self._update_position()

    def reload(self):
        if self._source is not None:
            self.set_markdown(self._source.toPlainText())
        elif self.file_path:
            self.load_file(self.file_path)
        else:
            self.set_markdown(self._raw_content)

    def _toggle_outline(self, checked):
        self.outline.setVisible(checked and bool(self._headings))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.outline.setFixedWidth(min(205, max(110, event.size().width() // 3)))

    def _show_search(self):
        self.search.setVisible(True)
        self.search.setFocus()
        self.search.selectAll()

    def _find_next(self):
        phrase = self.search.text()
        if not phrase:
            return
        if not self.browser.find(phrase):
            previous = self.browser.textCursor()
            self.browser.moveCursor(QtGui.QTextCursor.Start)
            if not self.browser.find(phrase):
                self.browser.setTextCursor(previous)
                QtWidgets.QToolTip.showText(self.search.mapToGlobal(self.search.rect().bottomLeft()), "Совпадений нет")

    def _jump(self, position):
        cursor = QtGui.QTextCursor(self.browser.document())
        cursor.setPosition(position)
        self.browser.setTextCursor(cursor)
        bar = self.browser.verticalScrollBar()
        bar.setValue(bar.value() + self.browser.cursorRect(cursor).top() - 10)

    def _outline_selected(self, item, _previous):
        if item is not None:
            self._jump(item.data(0, QtCore.Qt.UserRole))

    def _update_position(self, *_args):
        if not hasattr(self, "_reading_minutes"):
            return
        bar = self.browser.verticalScrollBar()
        percent = round(100 * bar.value() / bar.maximum()) if bar.maximum() else 100
        self.progress.setText(f"{self._reading_minutes} мин · {percent}%")
        position = self.browser.cursorForPosition(QtCore.QPoint(8, 12)).position()
        index = bisect_right(self._positions, position) - 1
        self.progress.setToolTip(self._headings[index].text(0) if index >= 0 else "")
        with QtCore.QSignalBlocker(self.outline):
            self.outline.setCurrentItem(self._headings[index] if index >= 0 else None)

    def _open_link(self, url):
        if url.hasFragment() and not url.path() and not url.scheme():
            position = self._anchors.get(url.fragment())
            if position is not None:
                self._jump(position)
        elif url.scheme().lower() in {"https", "http", "mailto"}:
            QtGui.QDesktopServices.openUrl(url)
        else:
            target = self.browser.document().baseUrl().resolved(url)
            if target.isLocalFile():
                path = Path(target.toLocalFile())
                if path.suffix.lower() in {".md", ".markdown"} and path.is_file():
                    self.open_preview_requested.emit(str(path))

    def _copy_markdown(self):
        QtGui.QGuiApplication.clipboard().setText(self._raw_content)

    def _request_editor(self):
        if self.file_path:
            self.open_editor_requested.emit(self.file_path)
