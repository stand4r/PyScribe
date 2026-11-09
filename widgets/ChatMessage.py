"""Rich rendering of assistant answers in the AI chat.

Two things differ from a plain rich-text label:

* inline code is drawn as a **rounded chip**. Qt rich text cannot round an
  inline background, so the text uses a sentinel background colour that is
  converted into a custom character property and painted as a rounded
  rectangle behind the glyphs.
* fenced code blocks are rendered with the **real editor core**
  (``ModernSyntaxHighlighter`` from ``widgets.QCodeEditor``) so answers are
  highlighted exactly like the code editor.
"""
from __future__ import annotations

import html
import re
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = ["AssistantMessage", "CodeSnippet", "InlineCodeText",
           "split_markdown_blocks", "markdown_to_html"]

# Rich text cannot carry a radius, so inline code is marked with a colour that
# is re-interpreted as a custom property after parsing.
SENTINEL_BG = "#010203"
INLINE_PROP = int(QtGui.QTextFormat.UserProperty) + 1

CHIP_BG = "#2A2A2C"
CHIP_RADIUS = 5.0
CHIP_PAD_X = 2.0


def _forward_wheel_to_chat(widget: QtWidgets.QWidget, event) -> bool:
    """Scroll the surrounding transcript for a wheel event over a text block.

    Paragraphs and short snippets are fitted to their content, so their own
    (hidden) scrollbars must not swallow the wheel — otherwise every block
    behaves like a separate scroller.
    """
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QtWidgets.QScrollArea):
        parent = parent.parentWidget()
    if parent is None:
        return False
    bar = parent.verticalScrollBar()
    bar.setValue(bar.value() - event.angleDelta().y())
    return True

TEXT = "#E6E6E8"
MUTED = "#8B949E"
BORDER = "#2B2B2D"
SURFACE = "#1B1B1E"
CODE_TEXT = "#D9D9DE"
TABLE_HEAD_BG = "#202024"
TABLE_BORDER = "#303035"

# Chat text follows the workbench font settings and UI scale. Fixed 13.5px
# looked tiny next to the 110%-scaled chrome and was reported as unreadable.
LINE_HEIGHT = 1.65


def _ui_scale_factor() -> float:
    try:
        from utils.settings_manager import get_settings_manager
        percent = float(get_settings_manager().get_setting("ui_scale_percent", 100) or 100)
    except Exception:
        percent = 100.0
    return max(0.75, min(2.0, percent / 100.0))


def chat_font_px() -> int:
    """Body font size of the chat, in CSS pixels (comfortably ≥ chrome)."""
    try:
        from utils.settings_manager import get_settings_manager
        base = float(get_settings_manager().get_setting("ui_font_size", 13) or 13)
    except Exception:
        base = 13.0
    return max(16, int(round(base * _ui_scale_factor())) + 2)


def chat_code_font_px() -> int:
    return max(15, chat_font_px() - 1)


def chat_small_px() -> int:
    return max(13, chat_font_px() - 3)


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------
def split_markdown_blocks(text: str) -> List[Tuple[str, object]]:
    """Split an answer into consecutive ``("text", html)`` and ``("code", …)``.

    Code fences become separate widgets, so the text parts are rendered without
    any ``<pre>`` markup.
    """
    lines = str(text or "").splitlines()
    blocks: List[Tuple[str, object]] = []
    text_lines: List[str] = []
    code_lines: List[str] = []
    code_lang = ""
    in_code = False

    def flush_text():
        if text_lines:
            html_text = markdown_to_html("\n".join(text_lines))
            if html_text.strip():
                blocks.append(("text", html_text))
            text_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                blocks.append(("code", (code_lang or "text",
                                         "\n".join(code_lines))))
                code_lines = []
                code_lang = ""
                in_code = False
            else:
                flush_text()
                in_code = True
                code_lang = stripped[3:].strip()
            continue
        if in_code:
            code_lines.append(line)
        else:
            text_lines.append(line)
    if in_code:
        blocks.append(("code", (code_lang or "text", "\n".join(code_lines))))
    flush_text()
    return blocks


def _inline(value: str, chip: bool = True) -> str:
    safe = html.escape(value)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", safe)
    # Inline code: a sentinel background is converted into a rounded chip by
    # ``_decorate_inline_code``. Tables pass ``chip=False``: a grid of filled
    # chips read as a wall of gray blocks, so cells use plain monospace.
    if chip:
        safe = re.sub(
            r"`([^`]+)`",
            r'<span style="background:%s; color:%s; font-family:\'Cascadia Mono\','
            r'Consolas,monospace; font-size:%dpx;">&#8201;\1&#8201;</span>'
            % (SENTINEL_BG, TEXT, chat_code_font_px()),
            safe)
    else:
        safe = re.sub(
            r"`([^`]+)`",
            r'<span style="color:%s; font-family:\'Cascadia Mono\','
            r'Consolas,monospace; font-size:%dpx;">\1</span>'
            % (CODE_TEXT, chat_code_font_px() - 1),
            safe)
    safe = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  r'<a href="\2" style="color:#6FA8DC; text-decoration:none;">\1</a>',
                  safe)
    return safe


def _list_row(marker: str, content_html: str, body_px: int,
              marker_width: int) -> str:
    """One list item as a two-column row (proper hanging indent).

    Wrapped continuation lines used to start under the number/bullet instead of
    under the item text, which made the list look like one fused block.
    """
    return (
        f'<table cellspacing="0" cellpadding="0" style="margin:0 0 7px 0;">'
        f'<tr>'
        f'<td width="{marker_width}" valign="top" style="color:{MUTED};'
        f' font-size:{body_px}px; line-height:{LINE_HEIGHT};">{marker}</td>'
        f'<td style="font-size:{body_px}px; line-height:{LINE_HEIGHT};">'
        f'{content_html}</td>'
        f'</tr></table>'
    )


def markdown_to_html(text: str) -> str:
    """Convert prose markdown into safe rich text (no code fences here).

    Every non-empty line becomes its own paragraph: models write one sentence
    per line without blank lines between them, and joining those lines with a
    plain ``<br>`` produced a dense, unreadable wall of text.
    """
    lines = str(text or "").splitlines()
    blocks: List[str] = []
    paragraph: List[str] = []
    index = 0
    body = chat_font_px()

    def flush():
        if paragraph:
            text = "<br>".join(paragraph)
            # A line that is entirely bold is the model's sub-heading.
            if len(paragraph) == 1 and re.fullmatch(r"<b>.+</b>", text, flags=re.S):
                blocks.append(
                    f'<p style="margin:14px 0 8px 0; font-size:{body + 2}px;'
                    f' font-weight:600; line-height:1.35;">{text}</p>')
            else:
                blocks.append(
                    f'<p style="margin:0 0 12px 0; font-size:{body}px;'
                    f' line-height:{LINE_HEIGHT};">' + text + "</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush()
            index += 1
            continue

        # Table
        if (stripped.startswith("|") and index + 1 < len(lines)
                and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[index + 1])
                and "-" in lines[index + 1]):
            flush()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            index += 2
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append([c.strip() for c in
                             lines[index].strip().strip("|").split("|")])
                index += 1
            column_width = max(14, 100 // max(1, len(header)))
            head_html = "".join(
                f'<th align="left" valign="top" width="{column_width}%"'
                f' style="padding:9px 12px; color:{MUTED};'
                f' font-size:{body - 2}px; font-weight:600;'
                f' background:{TABLE_HEAD_BG};'
                f' border-bottom:1px solid {TABLE_BORDER};">{_inline(c, chip=False)}</th>'
                for c in header)
            body_html = ""
            for cells in rows:
                padded = (cells + [""] * len(header))[:len(header)]
                body_html += "<tr>" + "".join(
                    f'<td valign="top" style="padding:10px 12px;'
                    f' font-size:{body - 1}px; line-height:1.55;'
                    f' border-bottom:1px solid {TABLE_BORDER};">'
                    f'{_inline(c, chip=False)}</td>' for c in padded) + "</tr>"
            blocks.append(
                f'<table cellspacing="0" cellpadding="0" width="100%"'
                f' style="margin:12px 0 16px 0; border-collapse:collapse;">'
                f'<tr>{head_html}</tr>{body_html}</table>')
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            size = body + {1: 6, 2: 3, 3: 2}.get(level, 1)
            top = 18 if level <= 2 else 14
            blocks.append(
                f'<p style="margin:{top}px 0 8px 0; font-size:{size}px;'
                f' font-weight:600; line-height:1.3;">{_inline(heading.group(2))}</p>')
            index += 1
            continue

        if re.match(r"^\s*([-*+])\s+", line):
            flush()
            items = []
            while index < len(lines) and re.match(r"^\s*([-*+])\s+", lines[index]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[index])
                items.append(_list_row("•", _inline(content), body, 22))
                index += 1
            blocks.extend(items)
            continue

        ordered = re.match(r"^\s*(\d+)[.)]\s+", line)
        if ordered:
            flush()
            items = []
            counter = int(ordered.group(1))
            while index < len(lines):
                match = re.match(r"^\s*(\d+)[.)]\s+", lines[index])
                if not match:
                    break
                content = re.sub(r"^\s*\d+[.)]\s+", "", lines[index])
                number = f"{counter}."
                items.append(_list_row(number, _inline(content), body,
                                       14 + 9 * len(number)))
                counter += 1
                index += 1
            blocks.extend(items)
            continue

        if stripped.startswith(">"):
            flush()
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(_inline(lines[index].strip().lstrip(">").strip()))
                index += 1
            blocks.append(
                f'<table cellspacing="0" cellpadding="0" style="margin:10px 0;"><tr>'
                f'<td width="3" bgcolor="#3F3F42"></td>'
                f'<td style="padding:6px 12px; color:{MUTED};'
                f' font-size:{body}px; line-height:{LINE_HEIGHT};">'
                f'{"<br>".join(quote)}</td></tr></table>')
            continue

        if re.match(r"^\s*(---+|\*\*\*+)\s*$", line):
            flush()
            blocks.append(f'<p style="margin:14px 0; border-top:1px solid {BORDER};"></p>')
            index += 1
            continue

        paragraph.append(_inline(stripped))
        flush()
        index += 1

    flush()
    return "".join(blocks)


# ---------------------------------------------------------------------------
# Inline code text
# ---------------------------------------------------------------------------
class InlineCodeText(QtWidgets.QTextBrowser):
    """Read-only rich text with rounded chips behind inline code.

    The text height always follows the content, so the widget can live inside a
    normal vertical layout instead of scrolling on its own.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)
        self.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; "
            f"color: {TEXT}; selection-background-color: #2C5A7A; "
            "selection-color: #FFFFFF; }")
        self.document().setDocumentMargin(0)
        # Long URLs / paths without spaces used to overflow the line and get
        # clipped at the bubble edge; break anywhere as a last resort.
        option = self.document().defaultTextOption()
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)
        self.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.LinksAccessibleByMouse)
        self.setOpenExternalLinks(True)
        self._chips: List[Tuple[int, int, int]] = []
        self.viewport().installEventFilter(self)

    # -- scrolling -----------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QtCore.QEvent.Wheel:
            if _forward_wheel_to_chat(self, event):
                return True
        return super().eventFilter(obj, event)

    # -- content -------------------------------------------------------
    def set_html(self, html_text: str):
        body = (f'<div style="color:{TEXT}; font-size:{chat_font_px()}px;'
                f' line-height:{LINE_HEIGHT};">{html_text or ""}</div>')
        self.setHtml(body)
        self._normalize_tables()
        self._decorate_inline_code()
        self._fit_height()

    def _normalize_tables(self):
        """Make markdown tables fit the bubble instead of overflowing it.

        Qt sizes table columns from their content, so a three-column table with
        paths and Russian headings was drawn wider than the 300px sidebar and
        the right column was clipped. A percentage width plus small padding
        keeps the table inside the text column.
        """
        document = self.document()
        stack = [document.rootFrame()]
        while stack:
            frame = stack.pop()
            if isinstance(frame, QtGui.QTextTable):
                # List rows are 2-column tables with a short marker cell; they
                # must keep their own column widths instead of being stretched.
                marker = ""
                if frame.columns() == 2 and frame.rows() > 0:
                    marker = frame.cellAt(0, 0).firstCursorPosition().block().text().strip()
                is_list_row = bool(re.fullmatch(r"(•|\d{1,3}\.)", marker))
                if not is_list_row:
                    fmt = frame.format()
                    fmt.setWidth(QtGui.QTextLength(QtGui.QTextLength.PercentageLength, 100))
                    fmt.setCellPadding(0)
                    fmt.setCellSpacing(0)
                    frame.setFormat(fmt)
            stack.extend(frame.childFrames())

    def wheelEvent(self, event):
        # The transcript is one scroll area; these blocks are fitted to their
        # content, so the wheel must scroll the chat, not the paragraph.
        event.ignore()

    def _decorate_inline_code(self):
        """Turn the sentinel background into a custom property (chip marker)."""
        document = self.document()
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    fmt = fragment.charFormat()
                    if fmt.background().style() != QtCore.Qt.NoBrush and \
                            fmt.background().color().name().lower() == SENTINEL_BG:
                        cursor = QtGui.QTextCursor(document)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position() + fragment.length(),
                                           QtGui.QTextCursor.KeepAnchor)
                        new_fmt = QtGui.QTextCharFormat(fmt)
                        new_fmt.clearBackground()
                        new_fmt.setProperty(INLINE_PROP, True)
                        cursor.setCharFormat(new_fmt)
                        iterator = block.begin()
                        continue
                iterator += 1
            block = block.next()

    # -- geometry ------------------------------------------------------
    def _fit_height(self):
        height = self.document().size().height()
        self.setFixedHeight(max(18, int(height) + 6))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    # -- painting ------------------------------------------------------
    def paintEvent(self, event):
        self._paint_chips()
        super().paintEvent(event)

    def _paint_chips(self):
        document = self.document()
        layout = document.documentLayout()
        if layout is None:
            return
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(CHIP_BG))
        try:
            block = document.begin()
            while block.isValid():
                text_layout = block.layout()
                block_rect = layout.blockBoundingRect(block)
                if text_layout is not None:
                    iterator = block.begin()
                    while not iterator.atEnd():
                        fragment = iterator.fragment()
                        if fragment.isValid() and                                 fragment.charFormat().property(INLINE_PROP):
                            self._paint_fragment_chip(
                                painter, block, text_layout, block_rect, fragment)
                        iterator += 1
                block = block.next()
        finally:
            painter.end()

    @staticmethod
    def _paint_fragment_chip(painter, block, text_layout, block_rect, fragment):
        """Draw the chip behind one inline-code fragment (possibly wrapped)."""
        start = fragment.position() - block.position()
        end = start + fragment.length()
        if start < 0 or text_layout.lineCount() == 0:
            return
        line = text_layout.lineForTextPosition(start)
        if not line.isValid():
            return
        guard = 0
        while line.isValid() and guard < 64:
            guard += 1
            line_start = line.textStart()
            line_end = line_start + line.textLength()
            if line_start >= end:
                break
            seg_start = max(start, line_start)
            seg_end = min(end, line_end)
            if seg_end <= seg_start:
                break
            x1 = line.cursorToX(seg_start)[0]
            x2 = line.cursorToX(seg_end)[0]
            rect = QtCore.QRectF(
                min(x1, x2) - CHIP_PAD_X,
                block_rect.top() + line.y() + 1,
                abs(x2 - x1) + CHIP_PAD_X * 2,
                line.height() - 2)
            painter.drawRoundedRect(rect, CHIP_RADIUS, CHIP_RADIUS)
            next_index = line.lineNumber() + 1
            if next_index >= text_layout.lineCount():
                break
            line = text_layout.lineAt(next_index)


# ---------------------------------------------------------------------------
# Code block on top of the editor core
# ---------------------------------------------------------------------------
class _CodeView(QtWidgets.QPlainTextEdit):
    """Read-only code view that hands the wheel to the chat when it can't scroll.

    Without this, the wheel over a short snippet scrolled the snippet instead
    of the conversation — every block felt like its own scroll area.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewport().installEventFilter(self)

    def _can_scroll(self) -> bool:
        return (self.verticalScrollBar().maximum() > 0
                or self.horizontalScrollBar().maximum() > 0)

    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QtCore.QEvent.Wheel:
            if not self._can_scroll() and _forward_wheel_to_chat(self, event):
                return True
        return super().eventFilter(obj, event)


class CodeSnippet(QtWidgets.QWidget):
    """One fenced code block, highlighted by the editor's own highlighter."""

    MAX_HEIGHT = 380

    def __init__(self, code: str, language: str = "", parent=None):
        super().__init__(parent)
        self._code = code.rstrip("\n")
        self._language = (language or "text").strip().lower()
        self.setObjectName("chatCodeSnippet")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QtWidgets.QFrame()
        header.setObjectName("chatCodeHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(10, 3, 6, 3)
        header_layout.setSpacing(6)
        title = QtWidgets.QLabel(self._language)
        title.setObjectName("chatCodeLanguage")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.copy_btn = QtWidgets.QToolButton()
        self.copy_btn.setObjectName("chatCodeCopy")
        self.copy_btn.setText("Копировать")
        self.copy_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.copy_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.copy_btn.clicked.connect(self.copy_code)
        header_layout.addWidget(self.copy_btn)
        root.addWidget(header)

        self.view = _CodeView()
        self.view.setObjectName("chatCodeView")
        self.view.setReadOnly(True)
        self.view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.view.setPlainText(self._code)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # Wrapping keeps narrow chat columns readable; a horizontal scrollbar
        # inside a 300px bubble was hiding half of every long code line.
        self.view.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.view.document().setDocumentMargin(10)
        self._apply_font()
        self._install_highlighter()
        root.addWidget(self.view)
        self._fit_height()

    def _apply_font(self):
        try:
            from utils.settings_manager import get_settings_manager
            sm = get_settings_manager()
            family = str(sm.get_setting("editor_font", "Cascadia Code")
                         or "Cascadia Code")
            size = int(sm.get_setting("editor_font_size", 13) or 13)
        except Exception:
            family, size = "Cascadia Code", 13
        # Chat code must stay readable: the editor font may be configured very
        # small (9pt), so the chat never goes below 11pt and follows UI scale.
        points = max(11, size)
        if _ui_scale_factor() > 1.05:
            points = max(points, int(round(points * min(1.35, _ui_scale_factor()))))
        font = QtGui.QFont(family, points)
        font.setStyleHint(QtGui.QFont.Monospace)
        self.view.setFont(font)

    def _install_highlighter(self):
        """Highlight with the code editor's own highlighter and rules."""
        try:
            from core.language_services import LanguageProviderFactory
            from widgets.QCodeEditor import ModernSyntaxHighlighter
        except Exception:
            return
        language = self._language
        aliases = {"py": "python", "js": "javascript", "ts": "typescript",
                   "bash": "shell", "sh": "shell", "text": "python"}
        language = aliases.get(language, language)
        try:
            config = LanguageProviderFactory.get_language_config(language)
        except Exception:
            return
        try:
            self.highlighter = ModernSyntaxHighlighter(self.view.document(), config)
        except Exception:
            self.highlighter = None

    def _fit_height(self):
        """Height from the *wrapped* line count, not the document size.

        ``document().size()`` is meaningless before the widget has a width, so
        the old calculation clipped multi-line snippets to a single line. Long
        lines are wrapped (there is no horizontal scrollbar any more), so their
        visual line count is estimated from the font metrics.
        """
        metrics = QtGui.QFontMetrics(self.view.font())
        viewport_width = self.view.viewport().width()
        if viewport_width <= 0:
            viewport_width = max(1, self.width() - 2)
        available = max(40, viewport_width - 20)   # document margin + padding
        wrapped_lines = 0
        for line in (self._code.splitlines() or [""]):
            advance = metrics.horizontalAdvance(line)
            wrapped_lines += max(1, -(-advance // available))
        content = wrapped_lines * metrics.lineSpacing() + 18
        if content > self.MAX_HEIGHT:
            self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.view.setFixedHeight(self.MAX_HEIGHT)
        else:
            self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.view.setFixedHeight(max(28, int(content)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    def copy_code(self):
        try:
            QtWidgets.QApplication.clipboard().setText(self._code)
            self.copy_btn.setText("Скопировано")
            QtCore.QTimer.singleShot(
                1200, lambda: self.copy_btn.setText("Копировать")
                if self.copy_btn else None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Whole message
# ---------------------------------------------------------------------------
class AssistantMessage(QtWidgets.QWidget):
    """An assistant answer: prose blocks interleaved with code snippets."""

    def __init__(self, markdown: str = "", parent=None):
        super().__init__(parent)
        self._width = 520
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._parts: List[QtWidgets.QWidget] = []
        self._markdown = ""
        self.set_markdown(markdown or "")

    # -- content -------------------------------------------------------
    def set_markdown(self, markdown: str):
        self._markdown = markdown or ""
        for part in self._parts:
            try:
                self._layout.removeWidget(part)
                part.setParent(None)
                part.deleteLater()
            except RuntimeError:
                pass
        self._parts.clear()
        for kind, payload in split_markdown_blocks(self._markdown):
            if kind == "code":
                language, code = payload
                widget = CodeSnippet(code, language, self)
            else:
                widget = InlineCodeText(self)
                widget.set_html(payload)
            self._layout.addWidget(widget)
            self._parts.append(widget)
        self.set_width(self._width)

    def text(self) -> str:
        return self._markdown

    def plain_text(self) -> str:
        return self._markdown

    # -- geometry ------------------------------------------------------
    def set_width(self, width: int):
        self._width = max(180, int(width))
        for part in self._parts:
            try:
                part.setFixedWidth(self._width)
                if isinstance(part, InlineCodeText):
                    part._fit_height()
                elif isinstance(part, CodeSnippet):
                    part._fit_height()
            except RuntimeError:
                pass
        self.updateGeometry()
