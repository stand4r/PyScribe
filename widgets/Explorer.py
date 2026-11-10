"""
File Explorer Widget
Provides file system navigation and operations
"""

import os
from design.icons import set_line_icon
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QFileInfo
from pathlib import Path


IGNORED_NAMES = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", ".gradle", "node_modules", "venv",
    ".venv", "env", "dist", "build", "target", "vendor", "coverage", ".coverage",
    ".cache", "tmp", "temp",
}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".class", ".o", ".obj", ".a", ".lib", ".tmp", ".log"}


class ProjectFileSystemModel(QtWidgets.QFileSystemModel):
    def _ignored(self, index):
        try:
            p = Path(self.filePath(index))
            return p.name in IGNORED_NAMES or p.suffix.lower() in IGNORED_SUFFIXES
        except Exception:
            return False

    def data(self, index, role=QtCore.Qt.DisplayRole):
        value = super().data(index, role)
        if self._ignored(index):
            if role == QtCore.Qt.ForegroundRole:
                return QtGui.QBrush(QtGui.QColor("#68717D"))
            if role == QtCore.Qt.FontRole:
                font = super().data(index, QtCore.Qt.FontRole) or QtGui.QFont()
                font = QtGui.QFont(font)
                font.setItalic(True)
                return font
            if role == QtCore.Qt.ToolTipRole:
                return "Игнорируется анализом проекта / сгенерированные файлы или кэш"
        return value



class Explorer(QtWidgets.QTreeView):
    """Project tree with a compact, task-focused context menu."""
    root_changed = QtCore.pyqtSignal(str)
    open_file_requested = QtCore.pyqtSignal(str)
    open_text_requested = QtCore.pyqtSignal(str)
    preview_markdown_requested = QtCore.pyqtSignal(str)
    run_requested = QtCore.pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(Explorer, self).__init__(parent=parent)

        self.setHeaderHidden(True)
        self.setColumnWidth(0, 300)
        self.workspace_root = None

        self.model = ProjectFileSystemModel()
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.model.setIconProvider(CustomIconProvider())
        self.setModel(self.model)
        self.setRootIndex(self.model.index(QtCore.QDir.rootPath()))
        
        # Hide columns (size, type, date modified)
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)

        self.setObjectName("fileExplorer")
        self.setUniformRowHeights(True)
        # VS Code explorer metrics: 22px rows, 8px indent step, 16px icons.
        self.setIndentation(8)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setAnimated(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)
        
        # Store clipboard for copy/paste operations
        self.clipboard = QtWidgets.QApplication.clipboard()
        self.copied_path = None

    def set_workspace_root(self, root_path):
        self.workspace_root = os.path.realpath(root_path) if root_path else None

    def _is_allowed_path(self, candidate, allow_missing=False):
        if not self.workspace_root:
            return True
        try:
            candidate = os.path.realpath(candidate)
            root = self.workspace_root
            if candidate == root:
                return True
            if not candidate.startswith(root + os.sep):
                return False
            if not allow_missing and not os.path.exists(candidate):
                return False
            return True
        except OSError:
            return False

    def go_up(self):
        """Navigate to parent directory"""
        current_index = self.currentIndex()
        parent_index = self.model.parent(current_index)
        if parent_index.isValid():
            self.setRootIndex(parent_index)
            self.setCurrentIndex(parent_index)
            self.root_changed.emit(self.model.filePath(parent_index))

    def refresh_model(self):
        """Refresh the file system model without jumping to the drive root.

        ``setRootPath`` also moves the view's root index, so the previous root
        index is captured and restored afterwards.
        """
        current_path = self.model.rootPath()
        current_root_index = self.rootIndex()
        self.model.setRootPath("")
        new_root = self.model.setRootPath(current_path)
        if current_root_index.isValid():
            self.setRootIndex(current_root_index)
        elif new_root.isValid():
            self.setRootIndex(new_root)
        # Short feedback so the user sees the refresh actually happened.
        try:
            from widgets.animations import flash
            flash(self.viewport(), color="#00F2FE", alpha=28, duration=320)
        except Exception:
            pass

    def open_context_menu(self, position):
        index = self.indexAt(position)
        if index.isValid():
            self.setCurrentIndex(index)
        path = self.model.filePath(index) if index.isValid() else self.model.rootPath()
        is_dir = bool(index.isValid() and self.model.isDir(index))
        menu = QtWidgets.QMenu(self)

        new_file = menu.addAction("Новый файл")
        new_folder = menu.addAction("Новая папка")
        new_file.triggered.connect(self.create_new_file)
        new_folder.triggered.connect(self.create_new_folder)

        if index.isValid():
            menu.addSeparator()
            if not is_dir:
                open_action = menu.addAction("Открыть")
                open_action.triggered.connect(self.open_item)
                suffix = Path(path).suffix.lower()
                if suffix in {".csv", ".tsv", ".tab"}:
                    text_action = menu.addAction("Открыть в редакторе (как текст)")
                    text_action.triggered.connect(lambda checked=False, p=path: self.open_text_requested.emit(p))
                elif suffix in {".md", ".markdown"}:
                    preview_action = menu.addAction("Предпросмотр Markdown")
                    preview_action.triggered.connect(lambda checked=False, p=path: self.preview_markdown_requested.emit(p))
                if Path(path).suffix.lower() in {".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".cs", ".go", ".rs", ".php", ".rb", ".kt", ".swift", ".sh", ".lua", ".pl"}:
                    menu.addSeparator()
                    run_action = menu.addAction("Запуск")
                    run_action.triggered.connect(lambda checked=False, p=path: self.run_requested.emit(p, False))
            rename_action = menu.addAction("Переименовать")
            rename_action.triggered.connect(self.rename_item)
            copy_path_action = menu.addAction("Копировать путь")
            copy_path_action.triggered.connect(lambda: QtWidgets.QApplication.clipboard().setText(path))
            reveal_action = menu.addAction("Показать в проводнике")
            reveal_action.triggered.connect(lambda: QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path) if not is_dir else path)))
            menu.addSeparator()
            delete_action = menu.addAction("Удалить")
            delete_action.triggered.connect(self.delete_item)

        menu.exec_(self.viewport().mapToGlobal(position))

    def rename_item(self):
        index = self.currentIndex()
        if not index.isValid():
            return
        old_path = self.model.filePath(index)
        old_name = os.path.basename(old_path)
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old_name)
        if not ok or not new_name or new_name == old_name:
            return
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if not self._is_allowed_path(new_path, allow_missing=True):
            QtWidgets.QMessageBox.warning(self, "Переименовать", "Целевой путь должен оставаться внутри папки проекта.")
            return
        try:
            if os.path.exists(new_path):
                QtWidgets.QMessageBox.warning(self, "Переименовать", "Файл или папка с таким именем уже существует.")
                return
            os.rename(old_path, new_path)
            self.refresh_model()
            new_index = self.model.index(new_path)
            if new_index.isValid():
                self.setCurrentIndex(new_index)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Ошибка переименования", str(exc))

    def create_new_file(self):
        """Create a new file in current directory"""
        index = self.currentIndex()
        if index.isValid() and self.model.isDir(index):
            directory = self.model.filePath(index)
        else:
            # If directory is selected, use it, otherwise use parent of file
            if index.isValid():
                directory = os.path.dirname(self.model.filePath(index))
            else:
                directory = self.model.rootPath()
        
        # Create input dialog for file name
        file_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Новый файл", 
            "Введите имя файла:",
            text="new_file.txt"
        )
        
        if ok and file_name:
            file_path = os.path.join(directory, file_name)
            if not self._is_allowed_path(file_path, allow_missing=True):
                QtWidgets.QMessageBox.warning(self, "Новый файл", "Файл должен оставаться внутри папки проекта.")
                return
            
            # Create empty file
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write("")
                
                # Refresh the model
                self.refresh_model()
                
                # Select the new file
                new_index = self.model.index(file_path)
                if new_index.isValid():
                    self.setCurrentIndex(new_index)
                    self.scrollTo(new_index)
                    
            except (IOError, OSError) as e:
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Ошибка", 
                    f"Не удалось создать файл: {str(e)}"
                )

    def create_new_folder(self):
        """Create a new folder in current directory"""
        index = self.currentIndex()
        if index.isValid() and self.model.isDir(index):
            directory = self.model.filePath(index)
        else:
            # If directory is selected, use it, otherwise use parent of file
            if index.isValid():
                directory = os.path.dirname(self.model.filePath(index))
            else:
                directory = self.model.rootPath()
        
        # Create input dialog for folder name
        folder_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Новая папка", 
            "Введите имя папки:",
            text="Новая папка"
        )
        
        if ok and folder_name:
            folder_path = os.path.join(directory, folder_name)
            if not self._is_allowed_path(folder_path, allow_missing=True):
                QtWidgets.QMessageBox.warning(self, "Новая папка", "Папка должна оставаться внутри папки проекта.")
                return
            
            # Create directory
            try:
                os.makedirs(folder_path, exist_ok=True)
                
                # Refresh the model
                self.refresh_model()
                
                # Select the new folder
                new_index = self.model.index(folder_path)
                if new_index.isValid():
                    self.setCurrentIndex(new_index)
                    self.expand(new_index)
                    self.scrollTo(new_index)
            except (OSError, IOError) as e:
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Ошибка", 
                    f"Не удалось создать папку: {str(e)}"
                )

    def open_item(self):
        """Open selected item with default application"""
        index = self.currentIndex()
        if index.isValid() and not self.model.isDir(index):
            file_path = self.model.filePath(index)
            self.open_file_requested.emit(file_path)

    def copy_item(self):
        """Copy selected item path for later paste operation"""
        index = self.currentIndex()
        if index.isValid():
            self.copied_path = self.model.filePath(index)

    def paste_item(self):
        """Paste copied item to current directory"""
        if not self.copied_path:
            return
            
        index = self.currentIndex()
        if index.isValid() and self.model.isDir(index):
            dest_dir = self.model.filePath(index)
        else:
            # If file is selected, use its parent directory
            if index.isValid():
                dest_dir = os.path.dirname(self.model.filePath(index))
            else:
                dest_dir = self.model.rootPath()
        
        if os.path.exists(self.copied_path):
            try:
                # Get source name and create destination path
                source_name = os.path.basename(self.copied_path)
                dest_path = os.path.join(dest_dir, source_name)
                if not self._is_allowed_path(dest_path, allow_missing=True):
                    QtWidgets.QMessageBox.warning(self, "Вставить", "Целевой путь должен оставаться внутри папки проекта.")
                    return
                
                # Copy file or directory
                if os.path.isfile(self.copied_path):
                    # For files
                    import shutil
                    shutil.copy2(self.copied_path, dest_path)
                else:
                    # For directories
                    import shutil
                    shutil.copytree(self.copied_path, dest_path)
                
                # Refresh model
                self.refresh_model()
                
            except (OSError, IOError, shutil.Error) as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Не удалось вставить: {str(e)}"
                )

    def delete_item(self):
        """Delete selected item with confirmation"""
        index = self.currentIndex()
        if not index.isValid():
            return
            
        file_path = self.model.filePath(index)
        if not self._is_allowed_path(file_path):
            QtWidgets.QMessageBox.warning(self, "Удаление", "Выбранный элемент находится вне папки проекта.")
            return
        item_name = os.path.basename(file_path)
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить «{item_name}»?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                if self.model.isDir(index):
                    # Delete directory recursively
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    # Delete file
                    os.remove(file_path)
                
                # Refresh model
                self.refresh_model()
                
            except (OSError, IOError, shutil.Error) as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Не удалось удалить элемент: {str(e)}"
                )

    def set_root_path(self, path):
        """Set root path for explorer"""
        self.set_workspace_root(path)
        if os.path.exists(path):
            self.model.setRootPath(path)
            self.setRootIndex(self.model.index(path))


class CustomIconProvider(QtWidgets.QFileIconProvider):
    """Stable project icons. QFileSystemModel passes QFileInfo, not the enum type."""
    def icon(self, info):
        icon_dir = Path(__file__).resolve().parent.parent / "src" / "icons"
        try:
            if isinstance(info, QtCore.QFileInfo):
                if info.isDir():
                    return QIcon(str(icon_dir / "folder.svg"))
                suffix = info.suffix().lower()
                mapping = {
                    "py": "python.svg", "pyw": "python.svg",
                    "js": "javascript.svg", "mjs": "javascript.svg", "cjs": "javascript.svg",
                    "ts": "typescript.svg", "tsx": "typescript.svg",
                    "html": "html.svg", "htm": "html.svg",
                    "css": "css.svg", "scss": "css.svg", "sass": "css.svg",
                    "json": "json.svg", "jsonc": "json.svg",
                    "md": "markdown.svg", "markdown": "markdown.svg",
                    "txt": "text.svg", "log": "text.svg",
                    "c": "c.svg", "h": "c.svg",
                    "cpp": "cpp.svg", "cc": "cpp.svg", "cxx": "cpp.svg", "hpp": "cpp.svg",
                }
                return QIcon(str(icon_dir / mapping.get(suffix, "file.svg")))
        except Exception:
            pass
        return super().icon(info)


class YouTubeStyleToolBar(QtWidgets.QWidget):
    """YouTube-style toolbar for file explorer"""
    
    def __init__(self, explorer, parent=None):
        super().__init__(parent)
        self.explorer = explorer
        self.init_ui()
        
    def init_ui(self):
        """Initialize toolbar UI"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)
        
        # YouTube-style button styling
        button_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 14px;
                padding: 4px 5px;
                color: rgba(255, 255, 255, 0.95);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 6px;
                max-width: 30px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """
        
        # Up button
        self.up_btn = QtWidgets.QPushButton("⬆️ Up")
        self.up_btn.setStyleSheet(button_style)
        self.up_btn.setCursor(Qt.PointingHandCursor)
        self.up_btn.clicked.connect(self.explorer.go_up)
        
        # Refresh button
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        set_line_icon(self.refresh_btn, "reload")
        self.refresh_btn.setStyleSheet(button_style)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.explorer.refresh_model)
        
        # Home button
        self.home_btn = QtWidgets.QPushButton("Home")
        set_line_icon(self.home_btn, "home")
        self.home_btn.setStyleSheet(button_style)
        self.home_btn.setCursor(Qt.PointingHandCursor)
        self.home_btn.clicked.connect(self.go_home)
        
        # Add buttons to layout
        layout.addWidget(self.up_btn)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.home_btn)
        layout.addStretch()
        
        # Set panel background
        self.setStyleSheet("""
            YouTubeStyleToolBar {
                background-color: rgba(40, 40, 40, 0.8);
                border-radius: 12px;
                margin: 2px;
            }
        """)
    
    def go_home(self):
        """Navigate to home directory"""
        home_path = QtCore.QDir.homePath()
        self.explorer.set_root_path(home_path)