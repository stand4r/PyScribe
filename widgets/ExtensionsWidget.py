"""Manage installed extensions and their context actions."""
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl


class ExtensionsWidget(QtWidgets.QWidget):
    """Manage installed extensions from application settings."""
    def __init__(self, extension_manager, parent=None):
        super().__init__(parent)
        self.manager = extension_manager
        self._build()
        self.refresh()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addStretch()
        refresh = QtWidgets.QPushButton("Обновить")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        root.addLayout(toolbar)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("extensionsManagerList")
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(lambda item: self._show_details(item))
        root.addWidget(self.list, 1)

    def refresh(self):
        self.list.clear()
        extensions = self.manager.list_extensions()
        if not extensions:
            item = QtWidgets.QListWidgetItem("Нет установленных расширений")
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.list.addItem(item)
        else:
            for ext in extensions:
                item = QtWidgets.QListWidgetItem(f"{ext.get('name', ext.get('id', 'Extension'))}  ·  {ext.get('version', '')}")
                item.setData(QtCore.Qt.UserRole, ext.get("id"))
                item.setToolTip(ext.get("id", ""))
                self.list.addItem(item)
        for ext_id, error in self.manager.errors.items():
            item = QtWidgets.QListWidgetItem(f"{ext_id}  ·  ошибка загрузки")
            item.setData(QtCore.Qt.UserRole, ext_id)
            item.setToolTip(error)
            self.list.addItem(item)

    def _context_menu(self, pos):
        item = self.list.itemAt(pos)
        menu = QtWidgets.QMenu(self)
        if item and item.data(QtCore.Qt.UserRole):
            ext_id = item.data(QtCore.Qt.UserRole)
            menu.addAction("Сведения", lambda: self._show_details(item))
            menu.addSeparator()
            menu.addAction("Открыть папку расширения", lambda: self._open_extension_folder(ext_id))
            menu.addAction("Перезагрузить расширения", self._reload_extensions)
        else:
            menu.addAction("Обновить", self.refresh)
        menu.exec_(self.list.viewport().mapToGlobal(pos))

    def _reload_extensions(self):
        root = getattr(self.manager.context, "root_path", None)
        self.manager.set_project_root(str(root) if root else None)
        self.refresh()

    def _open_extension_folder(self, ext_id):
        manifest = self.manager.manifests.get(ext_id, {})
        entry = manifest.get("entry")
        if not entry:
            return
        for directory, data in self.manager.discover():
            if data.get("id") == ext_id:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
                return

    def _show_details(self, item):
        ext_id = item.data(QtCore.Qt.UserRole)
        manifest = self.manager.manifests.get(ext_id, {})
        text = "\n".join(f"{k}: {v}" for k, v in manifest.items()) or "Нет данных"
        QtWidgets.QMessageBox.information(self, "Расширение", text)
