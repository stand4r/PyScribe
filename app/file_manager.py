"""PyScribe file management subsystem."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from utils.programs import saveRecent, backup
from core.activity_log import record_action
from widgets.Dialog import CustomDialog
from widgets.DocumentViewerWidget import DOCUMENT_EXTENSIONS, DocumentViewerWidget
from widgets.HexViewer import HexViewer
from widgets.DiagramViewerWidget import DIAGRAM_EXTENSIONS, DiagramViewerWidget

if TYPE_CHECKING:
    from app.main_window import ModernMainWindow


class FileManager:
    BINARY_EXTENSIONS = {
        ".bin", ".exe", ".out", ".dll", ".so", ".dylib",
        ".elf", ".hex", ".rom", ".img", ".iso", ".dat"
    }

    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window
        self.app_manager = main_window.app_manager

    def open_file(self, file_path: str):
        """Open a file using the appropriate editor/viewer."""
        record_action("file_open_requested")
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.is_file():
                CustomDialog(f"Файл не найден: {file_path}").exec_()
                return

            path_str = str(file_path_obj.resolve())
            if self._find_and_focus_open_tab(path_str):
                return

            suffix = file_path_obj.suffix.lower()
            if suffix in DIAGRAM_EXTENSIONS:
                self.open_diagram_file(path_str)
                return
            if suffix == ".pdf":
                self.open_pdf_file(path_str)
                return
            if suffix in {".csv", ".tsv", ".tab", ".xlsx", ".xlsm"}:
                self.open_table_file(path_str)
                return
            if suffix in DOCUMENT_EXTENSIONS:
                self.open_document_file(path_str)
                return

            if self._is_binary_file(file_path_obj, suffix):
                self.open_binary_file(path_str)
                return

            content = self._read_text(file_path_obj)
            backup(path_str)
            self.main_window.close_special_tab("welcome")
            self.main_window.create_editor_tab(content, path_str)
            if not self._find_and_focus_open_tab(path_str):
                # create_editor_tab failed (it reports the reason itself);
                # opening the raw text keeps the file reachable.
                self._open_plain_text_fallback(content, path_str)
                return
            self._register_file_open(path_str)

        except Exception as e:
            CustomDialog(f"Ошибка открытия файла: {str(e)}").exec_()

    def _open_plain_text_fallback(self, content: str, path_str: str):
        """Last-resort viewer when the rich editor could not be constructed."""
        try:
            from widgets.MarkdownViewerWidget import MarkdownViewerWidget
        except Exception:
            return
        try:
            viewer = MarkdownViewerWidget(file_path=path_str, content=content, parent=self.main_window)
            index = self.main_window.active_tab_widget.addTab(viewer, Path(path_str).name)
            self.main_window.active_tab_widget.setCurrentIndex(index)
        except Exception:
            pass

    def _match_tab_path(self, widget, path_str: str) -> bool:
        fpath = getattr(widget, "file_path", None)
        if not fpath:
            return False
        try:
            return str(Path(fpath).resolve()) == path_str
        except (OSError, TypeError):
            return False

    def _find_in_group(self, group, path_str: str):
        for i in range(group.count()):
            if self._match_tab_path(group.widget(i), path_str):
                return i
        return None

    def _find_and_focus_open_tab(self, path_str: str) -> bool:
        """Find an already-open tab matching path_str and switch to it."""
        for group in self.main_window.editor_groups():
            idx = self._find_in_group(group, path_str)
            if idx is not None:
                group.setCurrentIndex(idx)
                self.main_window.active_tab_widget = group
                return True
        return False

    def _is_binary_file(self, file_path_obj: Path, suffix: str) -> bool:
        """Check if file should be treated as binary."""
        if suffix in self.BINARY_EXTENSIONS:
            return True
        try:
            sample = file_path_obj.read_bytes()[:8192]
            return b"\x00" in sample
        except OSError:
            return False

    def _register_file_open(self, path_str: str):
        """Record file into recent history and session files."""
        if path_str not in self.app_manager.session_files:
            self.app_manager.session_files.append(path_str)
        if path_str in self.app_manager.recent_files:
            self.app_manager.recent_files.remove(path_str)
        self.app_manager.recent_files.insert(0, path_str)
        saveRecent(self.app_manager.recent_files[:20])

        if getattr(self.main_window, "recent_files_menu", None) is not None:
            self.main_window.ui_manager._update_recent_files_menu()
        if self.main_window._welcome_tab is not None:
            self.main_window._welcome_tab.set_recent_files(self.app_manager.recent_files)

    @staticmethod
    def _read_text(file_path: Path) -> str:
        """Decode source/text files without crashing on BOM or non-UTF-8 files."""
        data = file_path.read_bytes()
        encodings = ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1251", "latin-1")
        for enc in encodings:
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def open_table_file(self, file_path: str):
        """Open CSV/TSV/XLSX in a high-performance table viewer."""
        try:
            from widgets.TableViewerWidget import TableViewerWidget
            path_str = str(Path(file_path).resolve())
            if self._find_and_focus_table_tab(path_str):
                return

            viewer = TableViewerWidget(path_str, self.main_window)
            viewer.open_editor_requested.connect(lambda fp: self.open_text_editor(fp))
            name = Path(file_path).name
            tab_index = self.main_window.active_tab_widget.addTab(viewer, f"Таблица: {name}")
            self.main_window.active_tab_widget.setCurrentIndex(tab_index)
            self._register_file_open(path_str)
            self.app_manager.logger.info("Opened table file: %s", file_path)
        except Exception as e:
            CustomDialog(f"Ошибка открытия таблицы: {str(e)}").exec_()

    def _find_table_in_group(self, group, path_str: str, cls):
        for i in range(group.count()):
            w = group.widget(i)
            if isinstance(w, cls) and getattr(w, "file_path", None) == path_str:
                return i
        return None

    def _find_and_focus_table_tab(self, path_str: str) -> bool:
        from widgets.TableViewerWidget import TableViewerWidget
        for group in self.main_window.editor_groups():
            idx = self._find_table_in_group(group, path_str, TableViewerWidget)
            if idx is not None:
                group.setCurrentIndex(idx)
                self.main_window.active_tab_widget = group
                return True
        return False

    def open_document_file(self, file_path: str):
        """Open a native Office document tab."""
        viewer = DocumentViewerWidget(file_path, self.main_window)
        viewer.file_path = Path(file_path)
        index = self.main_window.active_tab_widget.addTab(viewer, Path(file_path).name)
        self.main_window.active_tab_widget.setCurrentIndex(index)
        self.app_manager.logger.info("Opened office document: %s", file_path)

    def open_binary_file(self, file_path: str):
        """Open a binary file in a read-only hex editor tab."""
        try:
            path_str = str(Path(file_path).resolve())
            for group in self.main_window.editor_groups():
                for i in range(group.count()):
                    w = group.widget(i)
                    if isinstance(w, HexViewer) and getattr(w, "file_path", None) == Path(path_str):
                        group.setCurrentIndex(i)
                        self.main_window.active_tab_widget = group
                        return

            viewer = HexViewer(self.main_window)
            viewer.file_path = Path(file_path)
            viewer.load_file(Path(file_path).read_bytes())

            name = Path(file_path).name
            tab_index = self.main_window.active_tab_widget.addTab(viewer, f"HEX: {name}")
            self.main_window.active_tab_widget.setCurrentIndex(tab_index)
            self._register_file_open(path_str)
        except Exception as e:
            CustomDialog(f"Ошибка открытия HEX: {str(e)}").exec_()

    def open_recent_file(self, file_path: str):
        self.open_file(file_path)
        if file_path in self.app_manager.recent_files:
            self.app_manager.recent_files.remove(file_path)
        self.app_manager.recent_files.insert(0, file_path)
        saveRecent(self.app_manager.recent_files)

    def save_file(self, editor) -> bool:
        if self.main_window.is_special_widget(editor) or isinstance(editor, HexViewer):
            return False
        if not hasattr(editor, 'save_file'):
            return False
        ok = editor.save_file()
        if ok and hasattr(editor, 'editor') and hasattr(editor.editor, 'document'):
            editor.editor.document().setModified(False)
        return ok

    def _save_group_files(self, group):
        for i in range(group.count()):
            editor = group.widget(i)
            if not self.main_window.is_special_widget(editor) and self.save_file(editor):
                self.main_window.remove_unsaved_marker(i, group=group)

    def save_all_files(self):
        for group in self.main_window.editor_groups():
            self._save_group_files(group)
        self.main_window.recalculate_unsaved_count()

    def open_pdf_file(self, file_path: str):
        """Открыть PDF файл в специальном viewer"""
        try:
            from widgets.PDFViewerWidget import PDFViewerWidget

            pdf_viewer = PDFViewerWidget(self.main_window)
            file_name = Path(file_path).name
            tab_index = self.main_window.active_tab_widget.addTab(pdf_viewer, file_name)
            self.main_window.active_tab_widget.setCurrentIndex(tab_index)
            # Load after the tab is current: the viewer needs a real viewport
            # size to calculate fit-width instead of starting at 100%.
            pdf_viewer.open_pdf(file_path)

            if file_path not in self.app_manager.session_files:
                self.app_manager.session_files.append(file_path)

        except Exception as e:
            CustomDialog(f"Ошибка открытия PDF: {str(e)}").exec()

    def open_diagram_file(self, path_str: str):
        viewer = DiagramViewerWidget(path_str, self.main_window)
        viewer.open_editor_requested.connect(self.open_text_editor)
        group = self.main_window.active_tab_widget
        index = group.addTab(viewer, f"Диаграмма: {Path(path_str).name}")
        group.setCurrentIndex(index)
        self._register_file_open(path_str)

    def open_markdown_file(self, file_path: str, source=None):
        """Открыть Markdown файл в rich-режиме предпросмотра."""
        try:
            from widgets.MarkdownViewerWidget import MarkdownViewerWidget
            path_str = str(Path(file_path).resolve())

            if self._find_and_focus_markdown_tab(path_str, source):
                return

            viewer = MarkdownViewerWidget(file_path=path_str, parent=self.main_window)
            if source is not None:
                viewer.bind_source(source)
            viewer.open_editor_requested.connect(self.open_text_editor)
            viewer.open_preview_requested.connect(self.open_markdown_file)

            file_name = Path(file_path).name
            tab_index = self.main_window.active_tab_widget.addTab(viewer, f"Просмотр: {file_name}")
            self.main_window.active_tab_widget.setCurrentIndex(tab_index)
            self._register_file_open(path_str)

        except Exception as e:
            CustomDialog(f"Ошибка открытия Markdown: {str(e)}").exec()

    def _find_markdown_in_group(self, group, path_str: str, cls):
        for i in range(group.count()):
            w = group.widget(i)
            if isinstance(w, cls) and getattr(w, "file_path", None) == path_str:
                return i
        return None

    def _find_and_focus_markdown_tab(self, path_str: str, source=None) -> bool:
        from widgets.MarkdownViewerWidget import MarkdownViewerWidget
        for group in self.main_window.editor_groups():
            idx = self._find_markdown_in_group(group, path_str, MarkdownViewerWidget)
            if idx is not None:
                group.setCurrentIndex(idx)
                self.main_window.active_tab_widget = group
                viewer = group.widget(idx)
                if source is not None:
                    viewer.bind_source(source)
                else:
                    viewer.reload()
                return True
        return False

    def open_text_editor(self, file_path: str):
        """Force open a file in code/text editor mode."""
        try:
            path_str = str(Path(file_path).resolve())
            if self._find_and_focus_text_tab(path_str):
                return

            content = self._read_text(Path(file_path))
            self.main_window.close_special_tab("welcome")
            self.main_window.create_editor_tab(content, path_str)
        except Exception as e:
            CustomDialog(f"Ошибка открытия в редакторе: {str(e)}").exec()

    def _find_text_in_group(self, group, path_str: str):
        for i in range(group.count()):
            w = group.widget(i)
            if isinstance(w, (HexViewer, DiagramViewerWidget)) or hasattr(w, "browser"):
                continue
            if getattr(w, "file_path", None) == path_str:
                return i
        return None

    def _find_and_focus_text_tab(self, path_str: str) -> bool:
        for group in self.main_window.editor_groups():
            idx = self._find_text_in_group(group, path_str)
            if idx is not None:
                group.setCurrentIndex(idx)
                self.main_window.active_tab_widget = group
                return True
        return False
