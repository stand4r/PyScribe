"""Dedicated extension manager with context actions and local account state."""
from pathlib import Path
import json
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl


class ExtensionsWidget(QtWidgets.QWidget):
    """Settings-style extension manager opened as a dedicated editor tab."""
    def __init__(self, extension_manager, app_root, parent=None):
        super().__init__(parent)
        self.manager = extension_manager
        self.app_root = Path(app_root)
        self.account_file = self.app_root / "config" / "extension_account.json"
        self._build()
        self.refresh()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)
        title = QtWidgets.QLabel("Extensions")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        subtitle = QtWidgets.QLabel("Управление расширениями, состоянием активации и локальным аккаунтом.")
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        toolbar = QtWidgets.QHBoxLayout()
        self.account = QtWidgets.QLabel()
        self.account.setObjectName("extensionAccount")
        toolbar.addWidget(self.account)
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

        hint = QtWidgets.QLabel("Контекстное меню расширения: включить, отключить, удалить, открыть папку или войти/выйти из аккаунта.")
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def _account(self):
        try:
            if self.account_file.exists():
                data = json.loads(self.account_file.read_text(encoding="utf-8"))
                return data.get("name", "")
        except (OSError, ValueError):
            pass
        return ""

    def _set_account(self, name):
        self.account_file.parent.mkdir(parents=True, exist_ok=True)
        self.account_file.write_text(json.dumps({"name": name}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._update_account_label()

    def _update_account_label(self):
        name = self._account()
        self.account.setText(f"Аккаунт: {name}" if name else "Аккаунт: не выполнен вход")

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
        self._update_account_label()

    def _context_menu(self, pos):
        item = self.list.itemAt(pos)
        menu = QtWidgets.QMenu(self)
        if item and item.data(QtCore.Qt.UserRole):
            ext_id = item.data(QtCore.Qt.UserRole)
            manifest = self.manager.manifests.get(ext_id, {})
            menu.addAction("Сведения", lambda: self._show_details(item))
            menu.addSeparator()
            menu.addAction("Открыть папку расширения", lambda: self._open_extension_folder(ext_id))
            menu.addAction("Перезагрузить расширения", self._reload_extensions)
            menu.addSeparator()
            menu.addAction("Войти…", self._login)
            if self._account():
                menu.addAction("Выйти", lambda: self._set_account(""))
        else:
            menu.addAction("Войти…", self._login)
            if self._account():
                menu.addAction("Выйти", lambda: self._set_account(""))
            menu.addSeparator()
            menu.addAction("Обновить", self.refresh)
        menu.exec_(self.list.viewport().mapToGlobal(pos))

    def _login(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Вход в аккаунт", "Имя аккаунта:")
        if ok and name.strip():
            self._set_account(name.strip())

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
