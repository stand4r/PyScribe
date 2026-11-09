"""Keyboard shortcut reference for PyScribe."""
from PyQt5 import QtWidgets, QtCore


class KeyboardShortcutsDialog(QtWidgets.QDialog):
    """Show the complete keyboard map without exposing shortcuts in normal UI."""

    SHORTCUTS = [
        ("Файлы", [
            ("Новый файл", "Ctrl+N"), ("Открыть файл", "Ctrl+O"),
            ("Открыть проект", "Ctrl+Shift+O"), ("Сохранить", "Ctrl+S"),
            ("Сохранить как", "Ctrl+Shift+S"), ("Закрыть редактор", "Ctrl+W"),
            ("Предпросмотр Markdown", "Ctrl+Shift+V"),
        ]),
        ("Редактор", [
            ("Отменить", "Ctrl+Z"), ("Повторить", "Ctrl+Y"),
            ("Вырезать", "Ctrl+X"), ("Копировать", "Ctrl+C"),
            ("Вставить", "Ctrl+V"), ("Выделить всё", "Ctrl+A"),
            ("Найти в файле", "Ctrl+F"), ("Заменить в файле", "Ctrl+H"),
            ("Перенос строк", "Alt+Z"),
            ("Переименовать символ", "F2"), ("Перейти к строке", "Ctrl+G"),
        ]),
        ("Навигация", [
            ("Быстрое открытие", "Ctrl+P"), ("Палитра команд", "Ctrl+Shift+P"),
            ("Поиск по проекту", "Ctrl+Shift+F"),
            ("Боковая панель", "Ctrl+\\"), ("Терминал", "Ctrl+`"),
            ("Панель CodeLens ", "Ctrl+Shift+B"),
            ("Запуск текущего блока", "Ctrl+Enter"),
        ]),
        ("Запуск", [
            ("Запустить текущий файл", "F5"), ("Запустить проект", "Ctrl+F5"),
        ]),
        ("Терминал", [
            ("Новый терминал", "Ctrl+Shift+`"), ("Закрыть вкладку терминала", "Ctrl+W"),
            ("Очистить терминал", "Ctrl+L"),
        ]),
        ("Редактор кода", [
            ("Увеличить шрифт", "Ctrl++"), ("Уменьшить шрифт", "Ctrl+-"),
            ("Сбросить масштаб", "Ctrl+0"), ("Комментарий строки", "Ctrl+/"),
            ("Дублировать строку", "Ctrl+D"), ("Удалить строку", "Ctrl+Shift+K"),
            ("Отступ блока", "Tab"), ("Уменьшить отступ", "Shift+Tab"),
        ]),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Горячие клавиши")
        self.setMinimumSize(620, 560)
        self.resize(720, 680)
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        title = QtWidgets.QLabel("Горячие клавиши")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        subtitle = QtWidgets.QLabel("Полный список действий. В обычном интерфейсе сочетания клавиш намеренно не отображаются.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("dialogSubtitle")
        root.addWidget(subtitle)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)
        for category, rows in self.SHORTCUTS:
            box = QtWidgets.QFrame()
            box.setObjectName("shortcutGroup")
            form = QtWidgets.QFormLayout(box)
            form.setContentsMargins(14, 10, 14, 10)
            form.setSpacing(7)
            label = QtWidgets.QLabel(category)
            label.setObjectName("shortcutGroupTitle")
            form.addRow(label, QtWidgets.QLabel())
            for action, key in rows:
                form.addRow(action, self._key_label(key))
            layout.addWidget(box)
        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        close = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        root.addWidget(close)

    @staticmethod
    def _key_label(text):
        label = QtWidgets.QLabel(text)
        label.setObjectName("shortcutKey")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setMinimumWidth(120)
        return label
