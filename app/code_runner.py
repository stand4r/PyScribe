"""PyScribe code execution dispatcher."""
from __future__ import annotations

from typing import TYPE_CHECKING
from widgets.Dialog import CustomDialog

if TYPE_CHECKING:
    from app.main_window import ModernMainWindow


class CodeRunner:
    def __init__(self, main_window: 'ModernMainWindow'):
        self.main_window = main_window

    def run_code(self):
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            CustomDialog("Нет активного редактора").exec()
            return

        if hasattr(current_editor, 'save_file'):
            if not current_editor.save_file():
                CustomDialog("Не удалось сохранить файл перед выполнением").exec_()
                return

        file_path = getattr(current_editor, 'file_path', None)
        if not file_path:
            CustomDialog("Нет связанного файла для текущей вкладки").exec()
            return

        args = self.main_window.load_launch_arguments(str(file_path))

        working_dir = None
        if hasattr(self.main_window, 'current_project') and self.main_window.current_project:
            working_dir = self.main_window.current_project.root_path

        self.main_window.run_in_terminal(str(file_path), args, working_dir)
