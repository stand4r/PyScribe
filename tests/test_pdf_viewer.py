"""Tests for the PDF viewer (real zoom, fit modes, rotation, search).

Run: python tests/test_pdf_viewer.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402
from PyQt5 import QtWidgets  # noqa: E402

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _wait_for(predicate, timeout=8.0):
    app = _app()
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        try:
            if predicate():
                return True
        except RuntimeError:
            return False
        time.sleep(0.02)
    return False


def _make_pdf(folder: Path, pages: int = 2, text: str = "PyScribe PDF test", toc: list = None) -> Path:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=400, height=600)
        page.insert_text((48, 90), f"{text} - page {index + 1}", fontsize=14)
        page.insert_text((48, 130), "second line of the document", fontsize=11)
    if toc:
        document.set_toc(toc)
    path = folder / "sample.pdf"
    document.save(str(path))
    document.close()
    return path


def _settled(viewer, page=None) -> bool:
    pixmap = viewer.pdf_label.pixmap()
    if pixmap is None or pixmap.isNull():
        return False
    if "рендеринг" in viewer.status.text():
        return False
    if page is not None and viewer.current_page != page:
        return False
    return True


def _zoom_settled(viewer, zoom: float) -> bool:
    return (_settled(viewer) and abs(viewer.zoom - zoom) < 0.5
            and viewer.pdf_label.width() == viewer._display_size()[0]
            and viewer.pdf_label.height() == viewer._display_size()[1])


def _make_viewer(path: Path):
    from widgets.PDFViewerWidget import PDFViewerWidget
    _app()
    viewer = PDFViewerWidget()
    viewer.resize(900, 700)
    viewer.show()
    _app().processEvents()
    viewer.load_pdf(str(path))
    assert _wait_for(lambda: _settled(viewer)), "page was not rendered"
    return viewer


def _cleanup(viewer):
    try:
        viewer.close()
        viewer.pool.waitForDone(5000)
    except Exception:  # noqa: BLE001
        pass
    viewer.deleteLater()
    _app().processEvents()


def test_pdf_viewer_renders_and_navigates():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=2)
        viewer = _make_viewer(path)
        try:
            assert viewer.total_pages == 2
            assert viewer.current_page == 0
            assert viewer.page_spin.value() == 1
            changes = []
            viewer.page_changed.connect(lambda page, total: changes.append((page, total)))
            viewer.next_page()
            assert _wait_for(lambda: _settled(viewer, page=1))
            assert viewer.page_spin.value() == 2
            assert _wait_for(lambda: (2, 2) in changes), changes
            viewer.last_page()
            assert viewer.current_page == 1
            viewer.first_page()
            assert _wait_for(lambda: _settled(viewer, page=0))
            viewer.page_spin.setValue(2)
            assert _wait_for(lambda: _settled(viewer, page=1))
            assert viewer.page_spin.value() == 2
        finally:
            _cleanup(viewer)


def test_zoom_changes_displayed_size_not_only_sharpness():
    """The old viewer always squeezed the page into the label; zoom must scale."""
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=1)
        viewer = _make_viewer(path)
        try:
            viewer._set_zoom(100)
            assert _wait_for(lambda: _zoom_settled(viewer, 100))
            width_100 = viewer.pdf_label.width()
            height_100 = viewer.pdf_label.height()
            viewer._set_zoom(200)
            assert _wait_for(lambda: _zoom_settled(viewer, 200))
            assert viewer.pdf_label.width() >= width_100 * 1.8
            assert viewer.pdf_label.height() >= height_100 * 1.8
            viewer.zoom_out()
            assert _wait_for(lambda: viewer.zoom < 200 and _settled(viewer))
            viewer._set_zoom(100)
            assert _wait_for(lambda: _zoom_settled(viewer, 100))
            assert viewer.pdf_label.width() == width_100
            assert viewer.pdf_label.height() == height_100
            # The zoom combo is the normal way to change scale.
            index = viewer.zoom_combo.findData(150.0)
            assert index >= 0
            viewer.zoom_combo.setCurrentIndex(index)
            assert _wait_for(lambda: _zoom_settled(viewer, 150))
        finally:
            _cleanup(viewer)


def test_fit_width_and_page_modes_respect_viewport():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=1)
        viewer = _make_viewer(path)
        try:
            viewer.resize(700, 520)
            _app().processEvents()
            viewer.set_fit("width")

            def fit_width_ok():
                available = viewer.scroll.viewport().width() - 48 - 18
                return (_settled(viewer) and viewer._fit_mode == "width"
                        and abs(viewer.pdf_label.width() - available) <= 24)

            assert _wait_for(fit_width_ok), (
                viewer.pdf_label.width(), viewer.scroll.viewport().width())
            viewer.set_fit("page")
            assert _wait_for(lambda: _settled(viewer) and viewer._fit_mode == "page")
            assert viewer.pdf_label.height() <= viewer.scroll.viewport().height()
        finally:
            _cleanup(viewer)


def test_rotation_swaps_dimensions():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=1)
        viewer = _make_viewer(path)
        try:
            viewer._set_zoom(100)
            assert _wait_for(lambda: _zoom_settled(viewer, 100))
            width, height = viewer.pdf_label.width(), viewer.pdf_label.height()
            assert height > width
            viewer.rotate_page()
            assert _wait_for(lambda: viewer.pdf_label.width() == height
                             and viewer.pdf_label.height() == width)
        finally:
            _cleanup(viewer)


def test_search_finds_pages_and_cycles_matches():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=2, text="PyScribe PDF test")
        viewer = _make_viewer(path)
        try:
            viewer.search_edit.setText("PyScribe")
            viewer._start_search()
            assert _wait_for(lambda: viewer._search_pages == [0, 1]), viewer._search_pages
            assert viewer._search_total == 2
            assert _wait_for(lambda: "найдено" in viewer.status.text())
            viewer.next_match()
            assert _wait_for(lambda: _settled(viewer, page=1))
            viewer.previous_match()
            assert _wait_for(lambda: _settled(viewer, page=0))
            assert "найдено" in viewer.status.text()
        finally:
            _cleanup(viewer)


def test_search_without_matches_reports_it():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=1)
        viewer = _make_viewer(path)
        try:
            viewer.search_edit.setText("no-such-text-xyz")
            viewer._start_search()
            assert _wait_for(lambda: viewer._search_pages == []
                             and "не найдено" in viewer.status.text())
        finally:
            _cleanup(viewer)


def test_viewer_handles_missing_or_broken_file():
    from widgets.PDFViewerWidget import PDFViewerWidget
    _app()
    viewer = PDFViewerWidget()
    viewer.resize(600, 500)
    viewer.show()
    try:
        viewer.load_pdf(str(ROOT / "no-such-file.pdf"))
        assert "Ошибка" in viewer.pdf_label.text()
    finally:
        _cleanup(viewer)


def test_pdf_viewer_outline_and_bookmarks():
    with tempfile.TemporaryDirectory() as td:
        toc = [[1, "Введение", 1], [1, "Глава 1", 2]]
        path = _make_pdf(Path(td), pages=2, toc=toc)
        viewer = _make_viewer(path)
        try:
            assert viewer.toc_btn.isEnabled()
            assert viewer.outline_tree.topLevelItemCount() == 2
            # Click second bookmark
            item = viewer.outline_tree.topLevelItem(1)
            viewer._on_outline_item_clicked(item, 0)
            assert viewer.current_page == 1
        finally:
            _cleanup(viewer)


def test_pdf_viewer_text_copy_and_invert_colors():
    with tempfile.TemporaryDirectory() as td:
        path = _make_pdf(Path(td), pages=1, text="UniqueSampleText123")
        viewer = _make_viewer(path)
        try:
            viewer.copy_page_text()
            clip = QtWidgets.QApplication.clipboard().text()
            assert "UniqueSampleText123" in clip

            # Test invert colors
            viewer.invert_btn.setChecked(True)
            assert viewer.invert_colors is True
            assert _wait_for(lambda: _settled(viewer))
        finally:
            _cleanup(viewer)


TESTS = [
    ("test_pdf_viewer_renders_and_navigates", test_pdf_viewer_renders_and_navigates),
    ("test_zoom_changes_displayed_size_not_only_sharpness",
     test_zoom_changes_displayed_size_not_only_sharpness),
    ("test_fit_width_and_page_modes_respect_viewport",
     test_fit_width_and_page_modes_respect_viewport),
    ("test_rotation_swaps_dimensions", test_rotation_swaps_dimensions),
    ("test_search_finds_pages_and_cycles_matches",
     test_search_finds_pages_and_cycles_matches),
    ("test_search_without_matches_reports_it", test_search_without_matches_reports_it),
    ("test_viewer_handles_missing_or_broken_file",
     test_viewer_handles_missing_or_broken_file),
    ("test_pdf_viewer_outline_and_bookmarks", test_pdf_viewer_outline_and_bookmarks),
    ("test_pdf_viewer_text_copy_and_invert_colors", test_pdf_viewer_text_copy_and_invert_colors),
]


def main():
    failures = 0
    for name, fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"PASS {name}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
