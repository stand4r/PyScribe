"""Tests for HexViewer (virtual table, data inspector, search, goto offset, copy formats).

Run: pytest tests/test_hex_viewer.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtWidgets
from widgets.HexViewer import HexViewer, HexTableModel, DataInspectorWidget

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_hex_table_model_virtual_rows():
    _app()
    # 40 bytes = 2 full 16-byte rows + 1 partial 8-byte row = 3 rows
    data = b"A" * 40
    model = HexTableModel(data, bytes_per_row=16)
    assert model.rowCount() == 3
    assert model.columnCount() == 18  # Col 0 (Offset) + 16 bytes + Col 17 (ASCII)

    # Offset of row 0 is 00000000, row 1 is 00000010 (16), row 2 is 00000020 (32)
    assert model.data(model.index(0, 0)) == "00000000"
    assert model.data(model.index(1, 0)) == "00000010"
    assert model.data(model.index(2, 0)) == "00000020"

    # Hex display of 'A' (ASCII 65 = 0x41)
    assert model.data(model.index(0, 1)) == "41"
    # ASCII display
    assert model.data(model.index(0, 17)) == "AAAAAAAAAAAAAAAA"


def test_hex_viewer_load_file():
    _app()
    with tempfile.TemporaryDirectory() as td:
        bin_path = Path(td) / "sample.bin"
        payload = b"\x7F\x45\x4C\x46\x02\x01\x01\x00" + b"\x00" * 24
        bin_path.write_bytes(payload)

        viewer = HexViewer()
        viewer.file_path = bin_path
        viewer.load_file(payload)

        assert viewer.data == payload
        assert "sample.bin" in viewer.info_label.text()
        assert "32 bytes" in viewer.info_label.text()
        assert viewer.model.rowCount() == 2


def test_hex_data_inspector():
    _app()
    inspector = DataInspectorWidget()
    # Payload: 0x01, 0x00, 0x00, 0x00 -> u32 = 1 (Little Endian)
    payload = b"\x01\x00\x00\x00\x05\x00\x00\x00"
    inspector.update_inspector(payload, 0)

    assert inspector.lbl_offset.text() == "0x00000000 (0)"
    assert inspector.lbl_binary.text() == "00000001"
    assert inspector.lbl_int8.text() == "1"
    assert inspector.lbl_uint8.text() == "1"
    assert inspector.lbl_uint32.text() == "1"

    # Toggle Big Endian
    inspector._toggle_endian()
    assert not inspector.is_little_endian
    # In Big Endian, 0x01000000 = 16,777,216
    assert inspector.lbl_uint32.text() == "16,777,216"


def test_hex_viewer_search():
    _app()
    viewer = HexViewer()
    payload = b"Hello, world! This is a test string."
    viewer.load_file(payload)

    # Search for "world" text
    viewer.search_type_combo.setCurrentIndex(0)  # Text
    viewer.search_edit.setText("world")
    viewer._find_next()

    assert "Найдено: 1" in viewer.match_lbl.text()
    assert viewer.current_offset == 7  # 'Hello, ' is 7 bytes

    # Search for HEX
    viewer.search_type_combo.setCurrentIndex(1)  # HEX
    viewer.search_edit.setText("54 68 69 73")  # "This" in hex
    viewer._find_next()
    assert "Найдено: 1" in viewer.match_lbl.text()
    assert viewer.current_offset == 14


def test_hex_viewer_goto_offset():
    _app()
    viewer = HexViewer()
    viewer.load_file(b"\x00" * 1024)

    # Goto hex offset
    ok = viewer.goto_offset("0x100")
    assert ok
    assert viewer.current_offset == 256

    # Goto decimal offset
    ok = viewer.goto_offset("512")
    assert ok
    assert viewer.current_offset == 512

    # Out of range offset
    ok = viewer.goto_offset("2048")
    assert not ok


def test_hex_viewer_copy_formats():
    _app()
    viewer = HexViewer()
    payload = b"\x48\x65\x6C\x6C\x6F"  # "Hello"
    viewer.load_file(payload)
    viewer.table_view.selectAll()

    # Copy Hex
    viewer.copy_selected("hex")
    assert QtWidgets.QApplication.clipboard().text() == "48 65 6C 6C 6F"

    # Copy C Array
    viewer.copy_selected("c_array")
    assert QtWidgets.QApplication.clipboard().text() == "0x48, 0x65, 0x6C, 0x6C, 0x6F"

    # Copy ASCII
    viewer.copy_selected("ascii")
    assert QtWidgets.QApplication.clipboard().text() == "Hello"

    # Copy Base64
    viewer.copy_selected("base64")
    assert QtWidgets.QApplication.clipboard().text() == "SGVsbG8="


def test_hex_viewer_zoom():
    _app()
    viewer = HexViewer()
    old_size = viewer.font_size
    viewer.add_font_size()
    assert viewer.font_size == old_size + 1
    viewer.pop_font_size()
    assert viewer.font_size == old_size
