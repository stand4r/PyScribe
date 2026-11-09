"""Tests for the assistant message renderer (`widgets/ChatMessage.py`).

Run: python tests/test_chat_render.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtGui, QtWidgets

from widgets.ChatMessage import (
    INLINE_PROP,
    AssistantMessage,
    CodeSnippet,
    InlineCodeText,
    SENTINEL_BG,
    markdown_to_html,
    split_markdown_blocks,
)

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

SAMPLE = (
    "## Заголовок\n\n"
    "Текст с `items[::-1]` внутри.\n\n"
    "```python\n"
    "items = [1, 2, 3]\n"
    "print(items[::-1])\n"
    "```\n\n"
    "После кода.\n"
)


def test_split_markdown_blocks():
    blocks = split_markdown_blocks(SAMPLE)
    kinds = [kind for kind, _ in blocks]
    assert kinds == ["text", "code", "text"], kinds
    language, code = blocks[1][1]
    assert language == "python"
    assert "print(items[::-1])" in code
    # Prose never contains fences or <pre>.
    for kind, payload in blocks:
        if kind == "text":
            assert "```" not in payload
            assert "<pre" not in payload


def test_inline_code_becomes_custom_property():
    widget = InlineCodeText()
    widget.set_html('<p>Используй <span style="background:%s;">items[::-1]</span></p>'
                    % SENTINEL_BG)
    marked = 0
    leftover = 0
    block = widget.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                fmt = fragment.charFormat()
                if fmt.property(INLINE_PROP):
                    marked += 1
                if fmt.background().style() != 0 and \
                        fmt.background().color().name().lower() == SENTINEL_BG:
                    leftover += 1
            iterator += 1
        block = block.next()
    assert marked >= 1, "inline code must be marked for rounded painting"
    assert leftover == 0, "sentinel background must be cleared"


def test_inline_code_html_uses_sentinel_and_monospace():
    blocks = split_markdown_blocks("Просто `code` тут")
    html_text = blocks[0][1]
    assert SENTINEL_BG in html_text
    assert "Cascadia Mono" in html_text or "monospace" in html_text


def test_assistant_message_builds_parts():
    message = AssistantMessage(SAMPLE)
    assert message.text() == SAMPLE
    snippets = message.findChildren(CodeSnippet)
    assert len(snippets) == 1
    assert "print(items[::-1])" in snippets[0].view.toPlainText()
    texts = message.findChildren(InlineCodeText)
    assert len(texts) >= 2


def test_code_snippet_uses_editor_highlighter():
    snippet = CodeSnippet("def f():\n    return 1\n", "python")
    highlighter = getattr(snippet, "highlighter", None)
    assert highlighter is not None, "code blocks must use the editor highlighter"
    from widgets.QCodeEditor import ModernSyntaxHighlighter
    assert isinstance(highlighter, ModernSyntaxHighlighter)
    # Height covers all lines, not just the first one.
    metrics = QtGui.QFontMetrics(snippet.view.font())
    assert snippet.view.height() >= metrics.lineSpacing() * 2


def test_code_snippet_copy_puts_code_on_clipboard():
    snippet = CodeSnippet("print('chat')\n", "python")
    snippet.copy_code()
    assert "print('chat')" in QtWidgets.QApplication.clipboard().text()


def test_long_snippet_is_scrollable():
    code = "\n".join(f"value_{i} = {i}" for i in range(80))
    snippet = CodeSnippet(code, "python")
    assert snippet.view.height() <= CodeSnippet.MAX_HEIGHT
    assert snippet.view.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded


def test_message_resizes_parts():
    message = AssistantMessage(SAMPLE)
    message.set_width(340)
    snippets = message.findChildren(CodeSnippet)
    assert snippets and snippets[0].width() == 340


def test_numbered_list_uses_hanging_indent():
    """Wrapped item text must align under the text, not under the number."""
    html_text = markdown_to_html("1. Первый длинный пункт списка\n2. Второй пункт")
    assert html_text.count("<table") == 2, html_text
    assert 'width="32"' in html_text
    assert "margin:0 0 7px 0" in html_text


def test_fully_bold_line_becomes_subheading():
    html_text = markdown_to_html("**Исправленный вариант**")
    assert "font-weight:600" in html_text
    assert "font-size:18px" in html_text, html_text


def test_table_cells_use_plain_code_and_header_background():
    """A grid of filled chips read as a wall of gray blocks; cells stay plain."""
    html_text = markdown_to_html(
        "| Баг | Было → стало |\n| :--- | :--- |\n"
        "| `ARCHITECTURE_MULTIPLIERS` мёртвая | добавлены Zen 4 |")
    assert SENTINEL_BG not in html_text, "no chip sentinel inside table cells"
    assert "background:#202024" in html_text, "header row needs a quiet background"
    assert 'valign="top"' in html_text
    assert "padding:10px 12px" in html_text


def test_long_url_wraps_instead_of_overflowing():
    """A long unbroken token must not push the text beyond the bubble."""
    widget = InlineCodeText()
    widget.setFixedWidth(300)
    widget.set_html('<p>Ссылка: https://example.com/' + "a" * 120 + "</p>")
    widget.show()
    _APP.processEvents()
    _APP.processEvents()
    document = widget.document()
    assert document.size().width() <= widget.viewport().width() + 1, (
        document.size().width(), widget.viewport().width())
    assert widget.height() > 36, "wrapped lines need more than one line of height"
    widget.deleteLater()


def test_code_snippet_wraps_long_lines_without_scrollbar():
    snippet = CodeSnippet("value = '" + "x" * 200 + "'\nnext_line = 2\n", "python")
    snippet.setFixedWidth(320)
    snippet.show()
    _APP.processEvents()
    snippet._fit_height()
    view = snippet.view
    assert view.horizontalScrollBar().maximum() == 0, "long lines must wrap"
    assert view.lineWrapMode() == view.WidgetWidth
    needed = 3 * view.fontMetrics().lineSpacing() + 18
    assert view.height() >= needed - 6, (view.height(), needed)
    snippet.deleteLater()


def test_paragraph_lets_the_transcript_scroll():
    """Wheel over a fitted paragraph must scroll the chat, not the paragraph."""
    from PyQt5 import QtGui
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    content = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(content)
    for index in range(12):
        block = InlineCodeText()
        block.setFixedWidth(300)
        block.set_html(f"<p>Строка {index} с <code>inline</code> текстом</p>")
        layout.addWidget(block)
    area.setWidget(content)
    area.resize(340, 200)
    area.show()
    _APP.processEvents()
    bar = area.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum())
    before = bar.value()
    target = content.findChildren(InlineCodeText)[0]
    event = QtGui.QWheelEvent(QtCore.QPointF(5, 5), QtCore.QPointF(5, 5),
                              QtCore.QPoint(0, 0), QtCore.QPoint(0, 120),
                              QtCore.Qt.NoButton, QtCore.Qt.NoModifier,
                              QtCore.Qt.NoScrollPhase, False)
    _APP.sendEvent(target.viewport(), event)
    assert bar.value() < before, "wheel must scroll the surrounding chat"
    area.deleteLater()


if __name__ == "__main__":
    tests = [
        ("test_split_markdown_blocks", test_split_markdown_blocks),
        ("test_inline_code_becomes_custom_property", test_inline_code_becomes_custom_property),
        ("test_inline_code_html_uses_sentinel_and_monospace",
         test_inline_code_html_uses_sentinel_and_monospace),
        ("test_assistant_message_builds_parts", test_assistant_message_builds_parts),
        ("test_code_snippet_uses_editor_highlighter", test_code_snippet_uses_editor_highlighter),
        ("test_code_snippet_copy_puts_code_on_clipboard",
         test_code_snippet_copy_puts_code_on_clipboard),
        ("test_long_snippet_is_scrollable", test_long_snippet_is_scrollable),
        ("test_message_resizes_parts", test_message_resizes_parts),
        ("test_numbered_list_uses_hanging_indent", test_numbered_list_uses_hanging_indent),
        ("test_fully_bold_line_becomes_subheading",
         test_fully_bold_line_becomes_subheading),
        ("test_table_cells_use_plain_code_and_header_background",
         test_table_cells_use_plain_code_and_header_background),
        ("test_long_url_wraps_instead_of_overflowing",
         test_long_url_wraps_instead_of_overflowing),
        ("test_code_snippet_wraps_long_lines_without_scrollbar",
         test_code_snippet_wraps_long_lines_without_scrollbar),
        ("test_paragraph_lets_the_transcript_scroll",
         test_paragraph_lets_the_transcript_scroll),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
