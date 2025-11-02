"""
File Explorer Widget
Provides file system navigation and operations
"""

import os
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QFileInfo


class Explorer(QtWidgets.QTreeView):
    """File explorer widget with modern styling"""

    def __init__(self, parent=None):
        super(Explorer, self).__init__(parent=parent)

        self.setHeaderHidden(True)
        self.setColumnWidth(0, 300)
        self.setFixedWidth(400)

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.model.setIconProvider(CustomIconProvider())
        self.setModel(self.model)
        self.setRootIndex(self.model.index(QtCore.QDir.rootPath()))
        
        # Hide columns (size, type, date modified)
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)

        # Clean Glass стиль с белым текстом
        self.setStyleSheet(
            """
            QTreeView {
                background-color: rgba(30, 30, 30, 0.9);
                color: rgba(255, 255, 255, 0.95);
                border: none;
                font-size: 14px;
                padding-top: 5px;
                border-radius: 12px;
                margin: 5px;
                outline: none;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-weight: 400;
            }
            QTreeView::item {
                height: 36px;
                padding: 2px 12px;
                border-radius: 8px;
                margin: 2px 5px;
                border: none;
                color: rgba(255, 255, 255, 0.95);
            }
            QTreeView::item:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 1);
            }
            QTreeView::item:selected {
                background-color: rgba(255, 255, 255, 0.25);
                color: rgba(255, 255, 255, 1);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            """
        )

        # Enable anti-aliasing for smoothing
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)
        
        # Store clipboard for copy/paste operations
        self.clipboard = QtWidgets.QApplication.clipboard()
        self.copied_path = None

    def go_up(self):
        """Navigate to parent directory"""
        current_index = self.currentIndex()
        parent_index = self.model.parent(current_index)
        if parent_index.isValid():
            self.setRootIndex(parent_index)
            self.setCurrentIndex(parent_index)

    def refresh_model(self):
        """Refresh the file system model"""
        current_path = self.model.rootPath()
        self.model.setRootPath("")
        self.model.setRootPath(current_path)

    def open_context_menu(self, position):
        """Open styled context menu in Clean Glass style"""
        index = self.currentIndex()
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: rgba(40, 40, 40, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                padding: 8px;
                color: rgba(255, 255, 255, 0.95);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 6px;
                margin: 2px;
                color: rgba(255, 255, 255, 0.95);
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 1);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.2);
                margin: 4px 8px;
            }
            """
        )

        # New file action
        new_file_action = menu.addAction("📄 New File")
        new_file_action.triggered.connect(self.create_new_file)

        # New folder action
        new_folder_action = menu.addAction("📁 New Folder")
        new_folder_action.triggered.connect(self.create_new_folder)

        menu.addSeparator()

        # Open action - only for files
        if index.isValid() and not self.model.isDir(index):
            open_action = menu.addAction("📂 Open")
            open_action.triggered.connect(self.open_item)

        menu.addSeparator()

        # Copy action
        if index.isValid():
            copy_action = menu.addAction("📋 Copy")
            copy_action.triggered.connect(self.copy_item)

        # Paste action - only if we have something to paste
        if self.copied_path:
            paste_action = menu.addAction("📎 Paste")
            paste_action.triggered.connect(self.paste_item)

        menu.addSeparator()

        # Delete action - only for valid items
        if index.isValid():
            delete_action = menu.addAction("🗑️ Delete")
            delete_action.triggered.connect(self.delete_item)

        menu.exec_(self.viewport().mapToGlobal(position))

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
            "New File", 
            "Enter file name:",
            text="new_file.txt"
        )
        
        if ok and file_name:
            file_path = os.path.join(directory, file_name)
            
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
                    "Error", 
                    f"Could not create file: {str(e)}"
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
            "New Folder", 
            "Enter folder name:",
            text="New Folder"
        )
        
        if ok and folder_name:
            folder_path = os.path.join(directory, folder_name)
            
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
                    "Error", 
                    f"Could not create folder: {str(e)}"
                )

    def open_item(self):
        """Open selected item with default application"""
        index = self.currentIndex()
        if index.isValid() and not self.model.isDir(index):
            file_path = self.model.filePath(index)
            QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))

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
                    "Error",
                    f"Could not paste item: {str(e)}"
                )

    def delete_item(self):
        """Delete selected item with confirmation"""
        index = self.currentIndex()
        if not index.isValid():
            return
            
        file_path = self.model.filePath(index)
        item_name = os.path.basename(file_path)
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{item_name}'?",
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
                    "Error",
                    f"Could not delete item: {str(e)}"
                )

    def set_root_path(self, path):
        """Set root path for explorer"""
        if os.path.exists(path):
            self.model.setRootPath(path)
            self.setRootIndex(self.model.index(path))


class CustomIconProvider(QtWidgets.QFileIconProvider):
    """Custom icon provider for file explorer"""
    
    def icon(self, type):
        if type == QtWidgets.QFileIconProvider.Folder:
            # Try to load custom folder icon, fallback to default
            try:
                return QIcon("src/explorer.png")
            except:
                return super().icon(type)
        return super().icon(type)


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
        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        self.refresh_btn.setStyleSheet(button_style)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.explorer.refresh_model)
        
        # Home button
        self.home_btn = QtWidgets.QPushButton("🏠 Home")
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