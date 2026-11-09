"""Tests for TableViewerWidget (CSV, TSV, Excel, sorting, filtering, statistics, export).

Run: pytest tests/test_table_viewer.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openpyxl
from PyQt5 import QtCore, QtWidgets
from widgets.TableViewerWidget import TableViewerWidget, TableViewModel, TableSortFilterProxy, _parse_number

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_parse_number():
    assert _parse_number("123") == 123.0
    assert _parse_number("-45.67") == -45.67
    assert _parse_number("1 234,56") == 1234.56
    assert _parse_number("abc") is None
    assert _parse_number("") is None


def test_table_view_model_sorting():
    _app()
    headers = ["Имя", "Возраст", "Рейтинг"]
    rows = [
        ["Анна", "25", "4.8"],
        ["Борис", "9", "4.2"],
        ["Владимир", "100", "5.0"],
    ]
    model = TableViewModel(headers, rows)
    assert model.rowCount() == 3
    assert model.columnCount() == 3

    proxy = TableSortFilterProxy()
    proxy.setSourceModel(model)

    # Sort age column (index 1) ascending
    # With numeric-aware sorting, 9 must come before 25 and 100!
    proxy.sort(1, QtCore.Qt.AscendingOrder)
    assert proxy.data(proxy.index(0, 1)) == "9"
    assert proxy.data(proxy.index(1, 1)) == "25"
    assert proxy.data(proxy.index(2, 1)) == "100"

    # Sort descending
    proxy.sort(1, QtCore.Qt.DescendingOrder)
    assert proxy.data(proxy.index(0, 1)) == "100"
    assert proxy.data(proxy.index(1, 1)) == "25"
    assert proxy.data(proxy.index(2, 1)) == "9"


def test_table_view_search_filtering():
    _app()
    headers = ["Город", "Страна", "Население"]
    rows = [
        ["Москва", "Россия", "13000000"],
        ["Санкт-Петербург", "Россия", "5600000"],
        ["Минск", "Беларусь", "2000000"],
        ["Токио", "Япония", "14000000"],
    ]
    model = TableViewModel(headers, rows)
    proxy = TableSortFilterProxy()
    proxy.setSourceModel(model)

    # Filter for "Россия"
    proxy.set_filter_query("Россия")
    assert proxy.rowCount() == 2

    # Filter for "мин" (case-insensitive)
    proxy.set_filter_query("мин")
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "Минск"

    # Clear filter
    proxy.set_filter_query("")
    assert proxy.rowCount() == 4


def test_table_viewer_widget_csv_loading():
    _app()
    with tempfile.TemporaryDirectory() as td:
        csv_file = Path(td) / "test.csv"
        csv_file.write_text("ID;Product;Price\n1;Widget;19.99\n2;Gadget;49.50\n", encoding="utf-8")

        viewer = TableViewerWidget(str(csv_file))
        assert viewer.source_model is not None
        assert viewer.source_model.rowCount() == 2
        assert viewer.source_model.columnCount() == 3
        assert viewer.source_model.get_headers() == ["ID", "Product", "Price"]

        # Delimiter was auto-detected as ';'
        assert viewer.table_view.model().rowCount() == 2
        assert viewer.table_view.model().data(viewer.table_view.model().index(0, 1)) == "Widget"


def test_table_viewer_widget_header_toggle():
    _app()
    with tempfile.TemporaryDirectory() as td:
        csv_file = Path(td) / "test_no_hdr.csv"
        csv_file.write_text("A,B,C\n1,2,3\n4,5,6\n", encoding="utf-8")

        viewer = TableViewerWidget(str(csv_file))
        assert viewer.source_model.rowCount() == 2  # With header

        # Toggle header off
        viewer.header_btn.setChecked(False)
        assert viewer.source_model.rowCount() == 3  # Header is now data row 0
        assert viewer.source_model.get_headers() == ["Колонка 1", "Колонка 2", "Колонка 3"]


def test_table_viewer_widget_excel_multi_sheet():
    _app()
    with tempfile.TemporaryDirectory() as td:
        xlsx_file = Path(td) / "workbook.xlsx"
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Sales"
        ws1.append(["Quarter", "Revenue"])
        ws1.append(["Q1", 1000])
        ws1.append(["Q2", 1500])

        ws2 = wb.create_sheet("Costs")
        ws2.append(["Category", "Amount"])
        ws2.append(["Hosting", 200])

        wb.save(str(xlsx_file))
        wb.close()

        viewer = TableViewerWidget(str(xlsx_file))
        assert len(viewer.sheets_data) == 2
        assert "Sales" in viewer.sheets_data
        assert "Costs" in viewer.sheets_data
        assert viewer.sheet_tab_bar.count() == 2
        assert viewer.source_model.rowCount() == 2  # Sales has 2 rows

        # Switch to second sheet
        viewer.sheet_tab_bar.setCurrentIndex(1)
        assert viewer.current_sheet == "Costs"
        assert viewer.source_model.rowCount() == 1


def test_table_viewer_selection_statistics():
    _app()
    with tempfile.TemporaryDirectory() as td:
        csv_file = Path(td) / "stats.csv"
        csv_file.write_text("Item,Val1,Val2\nA,10,20\nB,30,40\n", encoding="utf-8")

        viewer = TableViewerWidget(str(csv_file))
        viewer.table_view.selectAll()
        viewer._on_selection_changed()

        info = viewer.status_right.text()
        assert "Сумма:" in info
        assert "100.00" in info  # 10 + 20 + 30 + 40 = 100
        assert "Среднее:" in info
        assert "25.00" in info


def test_table_viewer_copy_formats():
    _app()
    with tempfile.TemporaryDirectory() as td:
        csv_file = Path(td) / "copy_test.csv"
        csv_file.write_text("Col1,Col2\nX,Y\n", encoding="utf-8")

        viewer = TableViewerWidget(str(csv_file))
        viewer.table_view.selectAll()
        viewer.copy_selection(delimiter="\t")
        clip_text = QtWidgets.QApplication.clipboard().text()
        assert "X\tY" in clip_text

