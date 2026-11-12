"""PyScribe widgets/WelcomeWidget.py: application module and reusable component."""
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from widgets.ProjectManager import project_manager


class AnimatedCard(QtWidgets.QFrame):
    """Card widget with smooth hover transitions, custom painting, and non-blocking children."""
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None, has_accent_bar=False):
        super().__init__(parent)
        self.has_accent_bar = has_accent_bar
        self._hover_progress = 0.0
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        # Cards paint their own surface; QSS must not fill them.
        self.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        self.anim = QtCore.QPropertyAnimation(self, b"hoverProgress", self)
        self.anim.setDuration(140)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

    def getHoverProgress(self) -> float:
        return self._hover_progress

    def setHoverProgress(self, val: float):
        self._hover_progress = val
        self.update()

    hoverProgress = QtCore.pyqtProperty(float, getHoverProgress, setHoverProgress)

    def reset_hover(self):
        """Force the non-hovered look (used after construction)."""
        try:
            self.anim.stop()
        except RuntimeError:
            pass
        self._hover_progress = 0.0
        self.update()

    def showEvent(self, event):
        # A card can receive a synthetic Enter during layout; start clean.
        if not self.underMouse():
            self._hover_progress = 0.0
        super().showEvent(event)

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._hover_progress)
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._hover_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        p = max(0.0, min(1.0, self._hover_progress))
        # At rest the card keeps a faint surface plus a subtle hairline border so
        # it never blends into the page background; hovering fades both up.
        if p <= 0.001:
            bg_col = QtGui.QColor(0x25, 0x25, 0x26, 120)
        else:
            bg_col = QtGui.QColor(
                int(0x25 + (0x2A - 0x25) * p),
                int(0x25 + (0x2D - 0x25) * p),
                int(0x26 + (0x2E - 0x26) * p),
                int(120 + 135 * p),
            )
        # Rest border is intentionally low-contrast (#3A3A3C) but visible.
        r_br = int(0x3A + (0x45 - 0x3A) * p)
        br_col = QtGui.QColor(r_br, r_br, r_br, int(150 + 105 * p))

        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QtGui.QPen(br_col, 1.0))
        painter.setBrush(QtGui.QBrush(bg_col))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        # Left accent line (VS Code uses it only for the focused list item).
        if self.has_accent_bar and p > 0.01:
            accent_col = QtGui.QColor(0x00, 0x78, 0xD4, int(255 * p))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(accent_col))
            bar_height = (rect.height() - 16) * p
            bar_top = rect.top() + (rect.height() - bar_height) / 2
            painter.drawRoundedRect(QtCore.QRectF(rect.left(), bar_top, 2.0, bar_height), 1.0, 1.0)


# Alias for backward compatibility
ClickableFrame = AnimatedCard


class Ui_Welcome(QtWidgets.QWidget):
    recent_project_requested = QtCore.pyqtSignal(object)
    open_project_requested = QtCore.pyqtSignal()
    recent_file_requested = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, settings=None, recent_files=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.recent_files = list(recent_files or [])
        self.welcome = True
        self.setObjectName('Main')
        self._build()
        self.apply_styles()
        self.retranslateUi()
        self.refresh_recent_projects()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(48, 42, 48, 42)
        root.setSpacing(20)
        root.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)

        icon = QtWidgets.QLabel()
        icon.setFixedSize(120, 120)
        icon.setObjectName('welcomeIcon')
        # No plate, no border: only the two slashes of the PyScribe mark.
        icon.setStyleSheet('background: transparent; border: none;')
        mark_path = Path(__file__).resolve().parent.parent / 'src' / 'icon_mark_256.png'
        if not mark_path.exists():
            mark_path = Path(__file__).resolve().parent.parent / 'src' / 'icon_mark.png'
        pixmap = QtGui.QPixmap(str(mark_path))
        icon.setPixmap(pixmap.scaled(104, 104, QtCore.Qt.KeepAspectRatio,
                                     QtCore.Qt.SmoothTransformation))
        icon.setScaledContents(False)
        icon.setAlignment(QtCore.Qt.AlignCenter)

        title = QtWidgets.QLabel('PyScribe')
        title.setObjectName('welcomeTitle')
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("background: transparent; border: none;")
        branding = QtWidgets.QHBoxLayout()
        branding.setSpacing(8)
        branding.addStretch()
        branding.addWidget(icon, 0, QtCore.Qt.AlignVCenter)
        branding.addWidget(title, 0, QtCore.Qt.AlignVCenter)
        branding.addStretch()
        root.addLayout(branding)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(10)
        self.open_project_card = self.create_action_card('Открыть проект', 'Открыть папку проекта')
        self.new_file_card = self.create_action_card('Новый файл', 'Создать новый файл')
        self.open_file_card = self.create_action_card('Открыть файл', 'Открыть существующий файл')
        actions.addWidget(self.open_project_card)
        actions.addWidget(self.new_file_card)
        actions.addWidget(self.open_file_card)
        root.addLayout(actions)

        section = QtWidgets.QFrame()
        section.setObjectName('welcomeRecentSection')
        sl = QtWidgets.QVBoxLayout(section)
        sl.setContentsMargins(16, 14, 16, 14)
        sl.setSpacing(10)
        header = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel('Недавние проекты')
        label.setObjectName('welcomeSectionTitle')
        header.addWidget(label); header.addStretch()
        sl.addLayout(header)

        self.recent_scroll = QtWidgets.QScrollArea()
        self.recent_scroll.setWidgetResizable(True)
        self.recent_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.recent_container = QtWidgets.QWidget()
        self.recent_layout = QtWidgets.QVBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(6)
        self.recent_layout.addStretch()
        self.recent_scroll.setWidget(self.recent_container)
        sl.addWidget(self.recent_scroll, 1)
        root.addWidget(section, 1)

        self.empty_recent = QtWidgets.QLabel('Нет недавних проектов')
        self.empty_recent.setAlignment(QtCore.Qt.AlignCenter)
        self.empty_recent.setObjectName('welcomeMuted')
        self.empty_recent.setVisible(False)
        sl.addWidget(self.empty_recent)

    def create_action_card(self, title, description):
        card = AnimatedCard(has_accent_bar=False)
        card.setObjectName('welcomeAction')
        card.setMinimumSize(190, 60)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        t = QtWidgets.QLabel(title); t.setObjectName('welcomeActionTitle')
        t.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        d = QtWidgets.QLabel(description); d.setObjectName('welcomeActionDescription')
        d.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(t); layout.addWidget(d)
        card.title_label = t; card.desc_label = d
        return card

    def _project_card(self, project):
        card = AnimatedCard(has_accent_bar=True)
        card.setObjectName('welcomeProject')
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        name = QtWidgets.QLabel(project.get_display_name())
        name.setObjectName('welcomeProjectName')
        name.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        path = QtWidgets.QLabel(project.root_path)
        path.setObjectName('welcomeProjectPath')
        path.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        info = QtWidgets.QVBoxLayout()
        info.setSpacing(2)
        info.addWidget(name)
        info.addWidget(path)
        layout.addLayout(info, 1)

        opened = QtWidgets.QLabel(project.get_last_opened_display())
        opened.setObjectName('welcomeProjectTime')
        opened.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(opened)

        card.clicked.connect(lambda p=project: self.recent_project_requested.emit(p))
        card.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        def _on_custom_menu(pos, p=project, c=card):
            menu = QtWidgets.QMenu(c)
            open_act = menu.addAction("Открыть проект")
            del_act = menu.addAction("Удалить из недавних")
            chosen = menu.exec_(c.mapToGlobal(pos))
            if chosen == open_act:
                self.recent_project_requested.emit(p)
            elif chosen == del_act:
                project_manager.delete_project(p.root_path)
                self.refresh_recent_projects()
        card.customContextMenuRequested.connect(_on_custom_menu)
        return card


    def refresh_recent_projects(self):
        while self.recent_layout.count() > 1:
            item = self.recent_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        projects = project_manager.get_recent_projects(8)
        for project in projects:
            self.recent_layout.insertWidget(self.recent_layout.count() - 1, self._project_card(project))
        self.empty_recent.setVisible(not projects)
        self.recent_scroll.setVisible(bool(projects))

    def showEvent(self, event):
        """Stagger the action cards in the first time the page appears."""
        super().showEvent(event)
        if getattr(self, "_cards_animated", False):
            return
        self._cards_animated = True
        cards = [self.open_project_card, self.new_file_card, self.open_file_card]
        cards = [c for c in cards if c is not None]
        if not cards:
            return
        try:
            from widgets.animations import stagger, fade_in, DURATION
            stagger(cards, 55, lambda card: fade_in(card, duration=DURATION["normal"]))
        except Exception:
            pass

    def set_recent_files(self, files):
        self.recent_files = list(files or [])

    def apply_styles(self):
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        # Flat, VS Code-like welcome page: one 24px headline, 13px body text,
        # 12px secondary text and no neon accents. The cards paint their own
        # surface (AnimatedCard.paintEvent), so their QSS background must stay
        # transparent or the stylesheet would hide the painted hover state.
        self.setStyleSheet('''
            #welcomeTitle { font-size: 24px; font-weight: 300; color: #CCCCCC; background: transparent; }
            #welcomeAction, #welcomeProject { background: transparent; background-color: transparent; border: none; }
            #welcomeAction QLabel, #welcomeProject QLabel { background: transparent; background-color: transparent; border: none; }
            #welcomeActionTitle, #welcomeProjectName { background: transparent; color: #CCCCCC; font-size: 13px; font-weight: 400; }
            #welcomeActionDescription, #welcomeProjectPath, #welcomeProjectTime, #welcomeMuted { background: transparent; color: #8C8C8C; font-size: 12px; }
            #welcomeRecentSection { background: #181818; border: 1px solid #2B2B2B; border-radius: 2px; }
            #welcomeRecentSection QScrollArea, #welcomeRecentSection QScrollArea > QWidget, #welcomeRecentSection QScrollArea > QWidget > QWidget { background: transparent; border: none; }
            #welcomeSectionTitle { background: transparent; color: #CCCCCC; font-size: 13px; font-weight: 400; }
        ''')
        for card in (getattr(self, 'open_project_card', None), getattr(self, 'new_file_card', None),
                     getattr(self, 'open_file_card', None)):
            if card is not None:
                card.reset_hover()

    def retranslateUi(self):
        self.new_file_card.title_label.setText('Новый файл')
        self.new_file_card.desc_label.setText('Создать новый файл')
        self.open_file_card.title_label.setText('Открыть файл')
        self.open_file_card.desc_label.setText('Открыть существующий файл')
        self.open_project_card.title_label.setText('Открыть проект')
        self.open_project_card.desc_label.setText('Открыть папку проекта')

    def connect_signals(self, new_file_handler, open_file_handler, open_project_handler=None):
        self.new_file_card.clicked.connect(new_file_handler)
        self.open_file_card.clicked.connect(open_file_handler)
        if open_project_handler:
            self.open_project_card.clicked.connect(open_project_handler)

    def get_cards(self):
        return {'new_file': self.new_file_card, 'open_file': self.open_file_card, 'open_project': self.open_project_card}
