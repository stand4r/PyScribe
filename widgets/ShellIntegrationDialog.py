"""Explorer integration dialog: «Открыть с помощью» and the context menu."""
from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from core import shell_integration

__all__ = ["ShellIntegrationDialog"]


class ShellIntegrationDialog(QtWidgets.QDialog):
    """One checkbox that registers or removes the per-user Explorer entries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Интеграция с проводником Windows")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setObjectName("shellIntegrationDialog")
        self._build()
        self._refresh()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Открывать файлы и папки в PyScribe")
        title.setObjectName("updateTitle")
        root.addWidget(title)

        description = QtWidgets.QLabel(
            "PyScribe добавит в меню проводника пункт «Открыть в PyScribe» для "
            "файлов и папок, а также появится в системном окне «Открыть с "
            "помощью». Записи создаются только для текущего пользователя "
            "(HKEY_CURRENT_USER) и не требуют прав администратора.")
        description.setWordWrap(True)
        description.setObjectName("updateVersion")
        root.addWidget(description)

        self.checkbox = QtWidgets.QCheckBox(
            "Добавить PyScribe в контекстное меню и «Открыть с помощью»")
        self.checkbox.toggled.connect(self._toggle)
        root.addWidget(self.checkbox)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("updateStatus")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        hint = QtWidgets.QLabel(
            "Файлы открываются в редакторе, папки — как проект.\n"
            "Если PyScribe уже запущен, новый файл откроется в текущем окне.")
        hint.setObjectName("updateVersion")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QtWidgets.QPushButton("Готово")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _refresh(self):
        registered = shell_integration.is_registered()
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(registered)
        self.checkbox.blockSignals(False)
        self.status.setText("Интеграция включена." if registered
                            else "Интеграция выключена.")

    def _toggle(self, checked: bool):
        if checked:
            ok, errors = shell_integration.register()
            message = "Готово: PyScribe добавлен в меню проводника." if ok \
                else "Не удалось добавить записи:\n" + "\n".join(errors[:4])
        else:
            ok, errors = shell_integration.unregister()
            message = "Записи удалены." if ok \
                else "Не удалось удалить записи:\n" + "\n".join(errors[:4])
        self.status.setText(message)
        if not ok:
            self.checkbox.blockSignals(True)
            self.checkbox.setChecked(not checked)
            self.checkbox.blockSignals(False)
