"""PyScribe widgets/AboutDialog.py: modern About dialog."""
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets


class AboutDialog(QtWidgets.QDialog):
    """Modern, sleek About dialog for PyScribe."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе PyScribe")
        self.setFixedSize(520, 480)
        self.setModal(True)
        self.setObjectName("aboutDialog")
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 24)
        root.setSpacing(16)

        root.addLayout(self._create_header())
        root.addWidget(self._create_separator())
        root.addWidget(self._create_description())
        root.addWidget(self._create_features_card())
        root.addStretch()
        root.addLayout(self._create_footer_buttons())

    def _create_header(self) -> QtWidgets.QHBoxLayout:
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(16)

        icon_label = QtWidgets.QLabel()
        base_src = Path(__file__).resolve().parent.parent / "src"
        icon_path = base_src / "icon_app_128.png"
        if not icon_path.exists():
            icon_path = base_src / "icon_app.png"
        if icon_path.exists():
            pixmap = QtGui.QPixmap(str(icon_path)).scaled(
                56, 56, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(56, 56)
        header.addWidget(icon_label)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setSpacing(4)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("PyScribe")
        title.setObjectName("aboutTitle")
        title_row.addWidget(title)

        version_path = base_src.parent / "VERSION"
        try:
            version = version_path.read_text(encoding="utf-8").strip()
        except OSError:
            version = ""
        badge = QtWidgets.QLabel(f"v{version}" if version else "")
        badge.setObjectName("aboutBadge")
        title_row.addWidget(badge)
        title_row.addStretch()
        title_col.addLayout(title_row)

        tagline = QtWidgets.QLabel("Project Intelligence IDE")
        tagline.setObjectName("aboutTagline")
        title_col.addWidget(tagline)
        header.addLayout(title_col, 1)
        return header

    @staticmethod
    def _create_separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("background: #25303C; max-height: 1px;")
        return line

    @staticmethod
    def _create_description() -> QtWidgets.QLabel:
        desc = QtWidgets.QLabel(
            "Быстрая и функциональная среда разработки с глубоким анализом архитектуры, "
            "встроенным интерактивным терминалом и единой системой тем оформления."
        )
        desc.setObjectName("aboutDesc")
        desc.setWordWrap(True)
        return desc

    @staticmethod
    def _create_features_card() -> QtWidgets.QFrame:
        features_card = QtWidgets.QFrame()
        features_card.setObjectName("aboutFeaturesCard")
        f_layout = QtWidgets.QVBoxLayout(features_card)
        f_layout.setContentsMargins(12, 10, 12, 10)
        f_layout.setSpacing(6)

        features = [
            ("⚡", "Современный редактор кода с подсветкой и автодополнением"),
            ("🔍", "Анализ архитектуры, зависимостей и метрик проекта"),
            ("🖥️", "Встроенный терминал с поддержкой командной строки"),
            ("🎨", "Динамическая дизайн-система с поддержкой готовых тем"),
        ]
        for icon_str, text in features:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            i_lbl = QtWidgets.QLabel(icon_str)
            i_lbl.setObjectName("aboutFeatureIcon")
            t_lbl = QtWidgets.QLabel(text)
            t_lbl.setObjectName("aboutFeatureText")
            row.addWidget(i_lbl)
            row.addWidget(t_lbl, 1)
            f_layout.addLayout(row)
        return features_card

    def _create_footer_buttons(self) -> QtWidgets.QHBoxLayout:
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)

        github_btn = QtWidgets.QPushButton("GitHub Репозиторий")
        github_btn.setCursor(QtCore.Qt.PointingHandCursor)
        github_btn.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/stand4r/PyScribe"))
        )
        btn_row.addWidget(github_btn)

        issues_btn = QtWidgets.QPushButton("Сообщить об ошибке")
        issues_btn.setCursor(QtCore.Qt.PointingHandCursor)
        issues_btn.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/stand4r/PyScribe/issues"))
        )
        btn_row.addWidget(issues_btn)

        update_btn = QtWidgets.QPushButton("Проверить обновления")
        update_btn.setCursor(QtCore.Qt.PointingHandCursor)
        update_btn.setToolTip("Сверить версию с GitHub-релизами и установить обновление")
        update_btn.clicked.connect(self._check_updates)
        btn_row.addWidget(update_btn)
        btn_row.addStretch()

        close_btn = QtWidgets.QPushButton("Закрыть")
        close_btn.setObjectName("primary")
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(90)
        btn_row.addWidget(close_btn)
        return btn_row

    def _check_updates(self):
        """Close «О программе» and open the update dialog on the main window."""
        self.accept()
        window = self.parent()
        handler = getattr(window, "action_check_updates", None)
        if callable(handler):
            QtCore.QTimer.singleShot(0, handler)
