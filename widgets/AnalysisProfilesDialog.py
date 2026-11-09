"""Project analysis selection expressed as goals and concrete checks."""
from PyQt5 import QtCore, QtGui, QtWidgets


class ProjectAnalyzerDialog(QtWidgets.QDialog):
    PROFILES = {
        "recommended": ("Общий обзор", "Познакомиться с проектом и найти проблемные места.", {"structure", "dependencies", "health"}),
        "quality": ("Улучшить код", "Найти сложные функции и накопившиеся недоработки.", {"structure", "metrics", "health"}),
        "security": ("Проверить безопасность", "Найти потенциально опасные конструкции в коде.", {"structure", "security"}),
        "architecture": ("Разобраться в связях", "Узнать, какие части проекта зависят друг от друга.", {"structure", "dependencies"}),
        "deep": ("Все проверки", "Проверить код, его связи и скомпилированные файлы.", {"structure", "dependencies", "metrics", "health", "security", "binaries"}),
        "none": ("Открыть без анализа", "Начать работу с проектом без фоновых проверок.", set()),
    }
    ANALYZER_INFO = {
        "structure": ("Карта кода", "Найдёт файлы, классы и функции. Поможет ориентироваться в проекте."),
        "dependencies": ("Связи между файлами", "Покажет импорты и зависимости: какие части кода связаны друг с другом."),
        "metrics": ("Размер и сложность кода", "Оценит объём кода и сложность функций, чтобы выделить трудные для поддержки места."),
        "health": ("Недоработки и качество", "Найдёт признаки проблем в коде и пометки TODO / FIXME. Сформирует общую оценку качества."),
        "security": ("Риски безопасности", "Проверит потенциально опасные конструкции статическим анализом. Это не гарантия отсутствия уязвимостей."),
        "binaries": ("Скомпилированные файлы", "Изучит структуру и метаданные EXE, DLL, ELF и других бинарных файлов, если они есть в проекте."),
    }

    def __init__(self, project, current=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_analyzers = set(self.PROFILES["recommended"][2] if current is None else current)
        self._syncing = False
        self._profile_buttons = {}
        self._checks = {}
        self.setObjectName("analysisChooser")
        name = project.get("name", "Проект") if isinstance(project, dict) else project.name
        self.setWindowTitle(f"Настроить анализ · {name}")
        self.resize(900, 700)
        self.setFont(QtGui.QFont("Segoe UI", 9))
        self._build(name)
        self._update_plan()

    def _label(self, text, role, parent_layout):
        label = QtWidgets.QLabel(text)
        label.setObjectName(role)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.PlainText)
        parent_layout.addWidget(label)
        return label

    def _scroll(self, content):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _build(self, name):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)
        self._label("Что проверить в проекте?", "analysisChooserTitle", root)
        self._label(f"{name} · Выберите готовый набор или отметьте нужные проверки справа.", "analysisChooserHint", root)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(18)
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)
        self._label("ГОТОВЫЕ НАБОРЫ", "analysisChooserSection", left_layout)
        self.profile_group = QtWidgets.QButtonGroup(self)
        self.profile_group.setExclusive(True)
        for key, (title, description, _) in self.PROFILES.items():
            frame = QtWidgets.QFrame()
            frame.setObjectName("analysisChoiceCard")
            layout = QtWidgets.QVBoxLayout(frame)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(3)
            button = QtWidgets.QRadioButton(title)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setAccessibleName(title + ". " + description)
            self.profile_group.addButton(button)
            self._profile_buttons[key] = button
            layout.addWidget(button)
            hint = self._label(description, "analysisChooserHint", layout)
            hint.setContentsMargins(23, 0, 0, 0)
            button.toggled.connect(lambda checked, f=frame: self._style_card(f, checked))
            button.clicked.connect(lambda checked=False, k=key: self._profile_selected(k))
            left_layout.addWidget(frame)
        self.custom_button = QtWidgets.QRadioButton("Свой набор")
        self.custom_button.setToolTip("Отметьте отдельные проверки справа")
        self.profile_group.addButton(self.custom_button)
        left_layout.addWidget(self.custom_button)
        left_layout.addStretch()
        body.addWidget(self._scroll(left), 2)

        right = QtWidgets.QFrame()
        right.setObjectName("analysisChecksPanel")
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(8)
        self.plan_text = self._label("", "analysisChecksTitle", right_layout)
        self._label("Галочка означает, что проверка включена. Можно изменить любой набор.", "analysisChooserHint", right_layout)
        checks = QtWidgets.QWidget()
        checks_layout = QtWidgets.QVBoxLayout(checks)
        checks_layout.setContentsMargins(0, 2, 4, 2)
        checks_layout.setSpacing(8)
        for key, (title, description) in self.ANALYZER_INFO.items():
            frame = QtWidgets.QFrame()
            frame.setObjectName("analysisChoiceCard")
            layout = QtWidgets.QVBoxLayout(frame)
            layout.setContentsMargins(10, 9, 10, 9)
            layout.setSpacing(4)
            check = QtWidgets.QCheckBox(title)
            check.setCursor(QtCore.Qt.PointingHandCursor)
            check.setAccessibleName(title + ". " + description)
            check.setChecked(key in self.selected_analyzers)
            layout.addWidget(check)
            hint = self._label(description, "analysisChooserHint", layout)
            hint.setContentsMargins(23, 0, 0, 0)
            self._checks[key] = check
            check.toggled.connect(lambda checked, k=key: self._check_changed(k, checked))
            checks_layout.addWidget(frame)
        checks_layout.addStretch()
        right_layout.addWidget(self._scroll(checks), 1)
        body.addWidget(right, 3)
        root.addLayout(body, 1)
        self.result_hint = self._label("", "analysisChooserHint", root)
        buttons = QtWidgets.QDialogButtonBox()
        self.open_button = buttons.addButton("Открыть проект", QtWidgets.QDialogButtonBox.AcceptRole)
        self.open_button.setObjectName("primary")
        self.open_button.setDefault(True)
        buttons.addButton("Отмена", QtWidgets.QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _style_card(self, frame, selected):
        frame.setProperty("selected", selected)
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        frame.update()

    def _profile_selected(self, key):
        self.selected_analyzers = set(self.PROFILES[key][2])
        self._update_plan()

    def _check_changed(self, key, checked):
        if self._syncing:
            return
        if checked:
            self.selected_analyzers.add(key)
        else:
            self.selected_analyzers.discard(key)
        self._update_plan()

    def _update_plan(self):
        self._syncing = True
        try:
            matching = next((key for key, (_, _, values) in self.PROFILES.items()
                             if values == self.selected_analyzers), None)
            if matching:
                self._profile_buttons[matching].setChecked(True)
            else:
                self.custom_button.setChecked(True)
            for key, check in self._checks.items():
                check.setChecked(key in self.selected_analyzers)
            self.plan_text.setText(f"Включено проверок: {len(self.selected_analyzers)} из {len(self.ANALYZER_INFO)}")
            if self.selected_analyzers:
                self.result_hint.setText("Результаты появятся в разделе «Анализ проекта». Набор проверок сохранится для этого проекта.")
            else:
                self.result_hint.setText("Проект откроется без фонового анализа. Выбор сохранится для этого проекта.")
        finally:
            self._syncing = False

    def accept(self):
        self.selected_analyzers = sorted(self.selected_analyzers)
        super().accept()
