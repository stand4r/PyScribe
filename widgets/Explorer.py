from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon, QDesktopServices, QFont
from PyQt5.QtCore import Qt

class Explorer(QtWidgets.QTreeView):
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
        self.hide()

        # Скрытие столбцов
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
            QTreeView::branch:has-siblings:!adjoins-item {
                border-image: url(vline.png) 0;
            }
            QTreeView::branch:has-siblings:adjoins-item {
                border-image: url(branch-more.png) 0;
            }
            QTreeView::branch:!has-children:!has-siblings:adjoins-item {
                border-image: url(branch-end.png) 0;
            }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                border-image: none;
                image: url(branch-closed.png);
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings  {
                border-image: none;
                image: url(branch-open.png);
            }
        """
        )

        # Включение антиалиасинга для сглаживания
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def go_up(self):
        current_index = self.currentIndex()
        parent_index = self.model.parent(current_index)
        if parent_index.isValid():
            self.collapse(current_index)
            self.setRootIndex(parent_index)
            self.setCurrentIndex(parent_index)

    def open_context_menu(self, position):
        # Стилизованное контекстное меню в стиле Clean Glass
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
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
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

        open_action = menu.addAction("📁 Open")
        open_action.triggered.connect(self.open_item)

        menu.addSeparator()

        copy_action = menu.addAction("📋 Copy")
        copy_action.triggered.connect(self.copy_item)

        paste_action = menu.addAction("📎 Paste")
        paste_action.triggered.connect(self.paste_item)

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(self.delete_item)

        menu.exec_(self.viewport().mapToGlobal(position))

    def open_item(self):
        index = self.currentIndex()
        if not self.model.isDir(index):
            file_path = self.model.filePath(index)
            QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))

    def copy_item(self):
        index = self.currentIndex()
        file_path = self.model.filePath(index)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(file_path)

    def paste_item(self):
        clipboard = QtWidgets.QApplication.clipboard()
        dest_dir = self.model.filePath(self.currentIndex())
        file_path = clipboard.text()
        if QtCore.QFile.exists(file_path):
            file_name = QtCore.QFileInfo(file_path).fileName()
            QtCore.QFile.copy(file_path, QtCore.QDir(dest_dir).filePath(file_name))

    def delete_item(self):
        index = self.currentIndex()
        file_path = self.model.filePath(index)
        if self.model.isDir(index):
            QtCore.QDir(file_path).removeRecursively()
        else:
            QtCore.QFile.remove(file_path)

class CustomIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, type):
        if type == QtWidgets.QFileIconProvider.Folder:
            return QIcon("src/explorer.png")
        return super().icon(type)

class YouTubeStyleToolBar(QtWidgets.QWidget):
    def __init__(self, explorer, parent=None):
        super().__init__(parent)
        self.explorer = explorer
        self.init_ui()
        
    def init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)
        
        # Стиль кнопок в стиле YouTube
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
        
        # Кнопка Назад
        self.back_btn = QtWidgets.QPushButton("⬅️ Back")
        self.back_btn.setStyleSheet(button_style)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        
        # Кнопка Вперед
        self.forward_btn = QtWidgets.QPushButton("➡️ Forward")
        self.forward_btn.setStyleSheet(button_style)
        self.forward_btn.setCursor(Qt.PointingHandCursor)
        
        # Кнопка Вверх
        self.up_btn = QtWidgets.QPushButton("⬆️ Up")
        self.up_btn.setStyleSheet(button_style)
        self.up_btn.setCursor(Qt.PointingHandCursor)
        self.up_btn.clicked.connect(self.explorer.go_up)
        
        # Добавляем кнопки в layout
        layout.addWidget(self.back_btn)
        layout.addWidget(self.forward_btn)
        layout.addWidget(self.up_btn)
        layout.addStretch()
        
        # Устанавливаем фон панели
        self.setStyleSheet("""
            YouTubeStyleToolBar {
                background-color: rgba(40, 40, 40, 0.8);
                border-radius: 12px;
                margin: 2px;
            }
        """)
    
    def go_home(self):
        home_path = QtCore.QDir.homePath()
        self.explorer.setRootIndex(self.explorer.model.index(home_path))
    
    def refresh(self):
        current_index = self.explorer.currentIndex()
        self.explorer.model.refresh(current_index)
