"""PyScribe widgets/TodoPanel.py: Microsoft To Do-inspired Task & To-Do Panel.

A clean, modern, and beautiful task management sidebar for PyScribe, inspired
by the Microsoft To Do desktop app. Designed specifically for project and personal
tasks, with interactive check circles, importance stars (⭐), metadata pills,
collapsible completed sections, and seamless editor line binding.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal, pyqtSlot

from core.project_tasks import PRIORITIES, STATUSES, Task, TaskStore
from design.icons import line_icon, set_line_icon

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Microsoft To Do-Style Controls
# =============================================================================

class CheckCircleButton(QtWidgets.QAbstractButton):
    """Circular check button matching Microsoft To Do's completion control.

    - Unchecked: soft circular outline (#6E7681), hover reveals a faint check preview.
    - Checked: vibrant filled Fluent Blue circle (#0078D4) with a crisp white checkmark.
    """

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect = self.rect().adjusted(5, 5, -5, -5)

        if self.isChecked():
            # Filled circle (Fluent Blue)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor("#0078D4"))
            painter.drawEllipse(rect)

            # White checkmark
            painter.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            p1 = QtCore.QPointF(x + w * 0.28, y + h * 0.52)
            p2 = QtCore.QPointF(x + w * 0.45, y + h * 0.70)
            p3 = QtCore.QPointF(x + w * 0.74, y + h * 0.32)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            # Hollow circle outline
            border_color = QtGui.QColor("#0078D4" if self._hovered else "#6E7681")
            painter.setPen(QtGui.QPen(border_color, 1.8))
            painter.setBrush(QtGui.QColor("#0078D4" if self._hovered else "transparent"))
            if self._hovered:
                # Translucent hover effect
                painter.setBrush(QtGui.QColor(0, 120, 212, 40))
            painter.drawEllipse(rect)

            # Faint check on hover
            if self._hovered:
                painter.setPen(QtGui.QPen(QtGui.QColor("#0078D4"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                p1 = QtCore.QPointF(x + w * 0.28, y + h * 0.52)
                p2 = QtCore.QPointF(x + w * 0.45, y + h * 0.70)
                p3 = QtCore.QPointF(x + w * 0.74, y + h * 0.32)
                painter.drawLine(p1, p2)
                painter.drawLine(p2, p3)


class StarButton(QtWidgets.QAbstractButton):
    """Signature Microsoft To Do Importance (⭐) toggle button.

    - Unstarred: faint outline star (#6E7681).
    - Starred: bright golden star (#FFB900).
    """

    def __init__(self, starred: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(starred)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Отметить как важную задачу" if not starred else "Снять отметку важности")
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect = self.rect().adjusted(5, 5, -5, -5)
        cx = rect.center().x()
        cy = rect.center().y()
        r_outer = min(rect.width(), rect.height()) / 2.0
        r_inner = r_outer * 0.44

        import math
        points = []
        angle = -math.pi / 2.0
        step = math.pi / 5.0
        for i in range(10):
            r = r_outer if i % 2 == 0 else r_inner
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append(QtCore.QPointF(px, py))
            angle += step

        poly = QtGui.QPolygonF(points)

        if self.isChecked():
            painter.setPen(QtGui.QPen(QtGui.QColor("#FFB900"), 1.2))
            painter.setBrush(QtGui.QColor("#FFB900"))
            painter.drawPolygon(poly)
        else:
            color = QtGui.QColor("#FFB900" if self._hovered else "#6E7681")
            painter.setPen(QtGui.QPen(color, 1.4))
            painter.setBrush(QtGui.QColor(255, 185, 0, 35) if self._hovered else Qt.NoBrush)
            painter.drawPolygon(poly)


# =============================================================================
# Task Card Item Widget (Microsoft To Do style)
# =============================================================================

class TaskCardWidget(QtWidgets.QFrame):
    """An individual task card item formatted like Microsoft To Do."""

    task_status_changed = pyqtSignal(str, bool)   # (task_id, is_done)
    task_priority_changed = pyqtSignal(str, str) # (task_id, priority)
    task_delete_requested = pyqtSignal(str)      # (task_id)
    open_location_requested = pyqtSignal(str, int)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("taskCard")
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QFrame#taskCard {
                background: #252931;
                border: 1px solid #343A46;
                border-radius: 10px;
            }
            QFrame#taskCard:hover {
                background: #2D3440;
                border-color: #465367;
            }
        """)

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # 1. Circle Checkbox
        self.check_circle = CheckCircleButton(checked=self.task.is_done, parent=self)
        self.check_circle.setAccessibleName("Готовность задачи")
        self.check_circle.clicked.connect(self._on_check_clicked)
        layout.addWidget(self.check_circle, 0, Qt.AlignTop)

        # 2. Body: Title + Metadata Chips
        body_layout = QtWidgets.QVBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        # Title
        self.title_label = QtWidgets.QLabel(self.task.title)
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.NoTextInteraction)

        font = self.title_label.font()
        font.setPointSize(10)
        if self.task.is_done:
            font.setStrikeOut(True)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #A4AAB5;")
        else:
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #EDEDED; font-weight: 500;")
        body_layout.addWidget(self.title_label)

        # Metadata Row (Pills)
        meta_layout = QtWidgets.QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        # Priority Pill (if urgent or high)
        if self.task.priority in ("urgent", "high") and not self.task.is_done:
            prio_lbl = QtWidgets.QLabel("Срочно" if self.task.priority == "urgent" else "Высокий")
            prio_lbl.setStyleSheet("""
                background: #3A1D1D;
                color: #F85149;
                border: 1px solid #6E2626;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: bold;
            """)
            meta_layout.addWidget(prio_lbl)

        # Doing status pill
        if self.task.status == "doing" and not self.task.is_done:
            doing_lbl = QtWidgets.QLabel("В работе")
            doing_lbl.setStyleSheet("""
                background: #1C2D42;
                color: #58A6FF;
                border: 1px solid #234E7B;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            """)
            meta_layout.addWidget(doing_lbl)

        meta_layout.addStretch()
        body_layout.addLayout(meta_layout)
        layout.addLayout(body_layout, 1)

        # 3. Star Button (Importance ⭐)
        is_starred = self.task.priority in ("urgent", "high")
        self.star_btn = StarButton(starred=is_starred, parent=self)
        self.star_btn.setAccessibleName("Важность задачи")
        self.star_btn.clicked.connect(self._on_star_clicked)
        layout.addWidget(self.star_btn, 0, Qt.AlignTop)

    def _on_check_clicked(self):
        new_state = self.check_circle.isChecked()
        self.task_status_changed.emit(self.task.id, new_state)

    def _on_star_clicked(self):
        new_starred = self.star_btn.isChecked()
        new_priority = "urgent" if new_starred else "medium"
        self.task_priority_changed.emit(self.task.id, new_priority)

    def _on_location_clicked(self):
        if self.task.file:
            self.open_location_requested.emit(self.task.file, max(1, self.task.line))

    def mouseDoubleClickEvent(self, event):
        if self.task.file:
            self.open_location_requested.emit(self.task.file, max(1, self.task.line))
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1E1E22;
                border: 1px solid #323238;
                color: #EDEDED;
                padding: 4px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background: #0078D4;
                color: #FFFFFF;
            }
        """)

        # 1. Toggle Done
        act_toggle = menu.addAction(
            line_icon("back" if self.task.is_done else "check"),
            "Вернуть в активные" if self.task.is_done else "Отметить как выполненную"
        )
        act_toggle.triggered.connect(lambda: self.task_status_changed.emit(self.task.id, not self.task.is_done))

        # 2. Toggle Star
        is_starred = self.task.priority in ("urgent", "high")
        act_star = menu.addAction(line_icon("star"), "Снять отметку важности" if is_starred else "Отметить как важную")
        act_star.triggered.connect(lambda: self.task_priority_changed.emit(
            self.task.id, "medium" if is_starred else "urgent"
        ))

        # 3. Status
        status_menu = menu.addMenu("Статус")
        for s_key, s_label in STATUSES.items():
            act = status_menu.addAction(s_label)
            if self.task.status == s_key:
                act.setEnabled(False)
            act.triggered.connect(lambda checked=False, sk=s_key: self.task_status_changed.emit(self.task.id, sk == "done"))

        menu.addSeparator()

        # 4. Jump to code
        if self.task.file:
            act_goto = menu.addAction(line_icon("code"), "Перейти к привязанному коду")
            act_goto.triggered.connect(self._on_location_clicked)

        # 5. Copy Text
        act_copy = menu.addAction(line_icon("copy"), "Копировать текст задачи")
        act_copy.triggered.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.task.title))

        menu.addSeparator()

        # 6. Delete
        act_del = menu.addAction(line_icon("trash"), "Удалить задачу")
        act_del.triggered.connect(lambda: self.task_delete_requested.emit(self.task.id))

        menu.exec_(event.globalPos())


# =============================================================================
# Main Microsoft To Do-Style Panel
# =============================================================================

class TodoPanel(QtWidgets.QWidget):
    """Microsoft To Do-inspired Task and To Do workbench panel for PyScribe."""

    open_location_requested = pyqtSignal(str, int)  # (file_path, line)
    task_count_changed = pyqtSignal(int, bool)      # (active_count, has_urgent)

    def __init__(self, main_window=None, parent=None):
        q_parent = parent if isinstance(parent, QtWidgets.QWidget) else (
            main_window if isinstance(main_window, QtWidgets.QWidget) else None
        )
        super().__init__(q_parent)
        self.main_window = main_window
        self.setObjectName("todoPanel")

        self.root_path: Optional[Path] = None
        self.task_store: TaskStore = TaskStore(None)
        self.current_filter: str = "all"  # all, urgent, doing, done
        self.search_query: str = ""
        self.completed_collapsed: bool = False
        self.sort_mode: str = "default"   # default, importance, title

        self._build_ui()

    # =========================================================================
    # UI Construction
    # =========================================================================
    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 10)
        main_layout.setSpacing(10)

        # 1. Header (Microsoft To Do style)
        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        title_lbl = QtWidgets.QLabel("Задачи")
        title_lbl.setStyleSheet("font-size: 23px; font-weight: 700; color: #F4F6FA;")
        top_row.addWidget(title_lbl)

        top_row.addStretch()

        # Action Buttons
        self.btn_sort = QtWidgets.QToolButton()
        self.btn_sort.setToolTip("Сортировка задач")
        set_line_icon(self.btn_sort, "outline", size=14)
        self.btn_sort.setObjectName("msGhostBtn")
        self.btn_sort.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._build_sort_menu()
        top_row.addWidget(self.btn_sort)

        self.btn_refresh = QtWidgets.QToolButton()
        self.btn_refresh.setToolTip("Обновить задачи")
        set_line_icon(self.btn_refresh, "refresh", size=14)
        self.btn_refresh.setObjectName("msGhostBtn")
        self.btn_refresh.clicked.connect(self.refresh_tasks)
        top_row.addWidget(self.btn_refresh)

        self.btn_more = QtWidgets.QToolButton()
        self.btn_more.setToolTip("Дополнительно")
        set_line_icon(self.btn_more, "more", size=14)
        self.btn_more.setObjectName("msGhostBtn")
        self.btn_more.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._build_more_menu()
        top_row.addWidget(self.btn_more)

        header_layout.addLayout(top_row)

        # Dynamic Date / Subtitle
        self.subtitle_lbl = QtWidgets.QLabel(self._get_formatted_date())
        self.subtitle_lbl.setStyleSheet("font-size: 11px; color: #9E9EA7;")
        header_layout.addWidget(self.subtitle_lbl)

        main_layout.addLayout(header_layout)

        # 2. Microsoft To Do "Add a Task" Capsule Bar
        self.add_capsule = QtWidgets.QFrame()
        self.add_capsule.setObjectName("addCapsule")
        self.add_capsule.setStyleSheet("""
            QFrame#addCapsule {
                background: #232328;
                border: 1px solid #33333C;
                border-radius: 8px;
                padding: 4px 6px;
            }
            QFrame#addCapsule:focus-within {
                background: #28282E;
                border: 1px solid #0078D4;
            }
        """)
        add_layout = QtWidgets.QVBoxLayout(self.add_capsule)
        add_layout.setContentsMargins(6, 4, 6, 4)
        add_layout.setSpacing(6)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)

        add_button = QtWidgets.QToolButton()
        add_button.setObjectName("msGhostBtn")
        add_button.setToolTip("Добавить задачу")
        add_button.setAccessibleName("Добавить задачу")
        set_line_icon(add_button, "add", size=20)
        add_button.clicked.connect(self._create_quick_task)
        input_row.addWidget(add_button)

        self.input_task_title = QtWidgets.QLineEdit()
        self.input_task_title.setPlaceholderText("Добавить задачу (Enter)...")
        self.input_task_title.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #EDEDED;
                font-size: 13px;
                padding: 2px 0;
            }
            QLineEdit:focus { border: none; }
        """)
        self.input_task_title.returnPressed.connect(self._create_quick_task)
        input_row.addWidget(self.input_task_title, 1)

        self.add_star_btn = StarButton(starred=False, parent=self.add_capsule)
        self.add_star_btn.setToolTip("Сделать новую задачу важной")
        input_row.addWidget(self.add_star_btn)

        add_layout.addLayout(input_row)

        main_layout.addWidget(self.add_capsule)

        # 3. Search Bar
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Поиск задач...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.addAction(line_icon("search"), QtWidgets.QLineEdit.LeadingPosition)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1C1C20;
                border: 1px solid #2B2B32;
                border-radius: 6px;
                color: #C9D1D9;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #0078D4; }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.search_input)

        # 4. Smart Filter Pills (Segmented Ribbon)
        filter_layout = QtWidgets.QGridLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(4)

        self._filter_chips = {}
        for index, (key, label, icon) in enumerate((
            ("all", "Все", "checklist"),
            ("urgent", "Важные", "star"),
            ("doing", "В работе", "play"),
            ("done", "Готово", "check"),
        )):
            btn = QtWidgets.QPushButton(label)
            set_line_icon(btn, icon, size=14)
            btn.setCheckable(True)
            btn.setChecked(key == "all")
            btn.setObjectName("msFilterPill")
            btn.setStyleSheet("""
                QPushButton#msFilterPill {
                    background: #1C1C20;
                    color: #8E8E98;
                    border: 1px solid #2D2D35;
                    border-radius: 12px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton#msFilterPill:hover {
                    background: #25252C;
                    color: #D4D4D8;
                }
                QPushButton#msFilterPill:checked {
                    background: #0078D4;
                    color: #FFFFFF;
                    border-color: #0078D4;
                }
            """)
            btn.clicked.connect(lambda checked=False, k=key: self._set_filter(k))
            filter_layout.addWidget(btn, index // 2, index % 2)
            self._filter_chips[key] = btn

        main_layout.addLayout(filter_layout)

        # 5. Scroll Area with Task Cards
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.cards_container = QtWidgets.QWidget()
        self.cards_container.setObjectName("cardsContainer")
        self.cards_container.setStyleSheet("QWidget#cardsContainer { background: transparent; }")
        self.cards_layout = QtWidgets.QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(6)

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area, 1)

        # 6. Status Footer
        self.status_footer = QtWidgets.QLabel("")
        self.status_footer.setStyleSheet("color: #A4AAB5; font-size: 11px;")
        main_layout.addWidget(self.status_footer)

        # Ghost buttons general styling
        self.setStyleSheet("""
            QToolButton#msGhostBtn {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton#msGhostBtn::menu-indicator { image: none; width: 0; }
            QToolButton#msGhostBtn:hover, QToolButton#msGhostBtn:focus {
                background: #27272D;
                border-color: #383842;
            }
        """)

    def _get_formatted_date(self) -> str:
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        now = datetime.datetime.now()
        day_str = days[now.weekday()]
        return f"{day_str}, {now.day} {months[now.month - 1]}"

    def _build_sort_menu(self):
        menu = QtWidgets.QMenu(self.btn_sort)
        menu.setStyleSheet(self._menu_style())

        act_def = menu.addAction(line_icon("outline"), "По умолчанию")
        act_def.triggered.connect(lambda: self._set_sort_mode("default"))

        act_imp = menu.addAction(line_icon("star"), "По важности")
        act_imp.triggered.connect(lambda: self._set_sort_mode("importance"))

        act_title = menu.addAction(line_icon("down"), "По алфавиту")
        act_title.triggered.connect(lambda: self._set_sort_mode("title"))

        self.btn_sort.setMenu(menu)

    def _build_more_menu(self):
        menu = QtWidgets.QMenu(self.btn_more)
        menu.setStyleSheet(self._menu_style())

        act_md = menu.addAction(line_icon("document"), "Экспорт в Markdown (TODO.md)")
        act_md.triggered.connect(self._export_markdown)

        act_json = menu.addAction(line_icon("code"), "Экспорт в JSON")
        act_json.triggered.connect(self._export_json)

        menu.addSeparator()

        act_clear_done = menu.addAction(line_icon("trash"), "Удалить выполненные задачи")
        act_clear_done.triggered.connect(self._clear_done_tasks)

        self.btn_more.setMenu(menu)

    def _menu_style(self) -> str:
        return """
            QMenu {
                background: #1E1E22;
                border: 1px solid #323238;
                color: #EDEDED;
                padding: 4px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background: #0078D4;
                color: #FFFFFF;
            }
        """

    # =========================================================================
    # Lifecycle & Data Management
    # =========================================================================
    def set_project(self, project_root: Optional[str | Path]):
        """Bind panel to opened project or clear when closed."""
        self.root_path = Path(project_root).resolve() if project_root else None
        self.task_store.set_root(str(self.root_path) if self.root_path else None)
        self.refresh_tasks()

    def refresh_tasks(self):
        """Reload project tasks and update view."""
        if self.root_path and self.root_path.is_dir():
            self.task_store.load()
        self._render_tasks()

    def _set_sort_mode(self, mode: str):
        self.sort_mode = mode
        self._render_tasks()

    def _set_filter(self, filter_key: str):
        self.current_filter = filter_key
        for k, btn in self._filter_chips.items():
            btn.setChecked(k == filter_key)
        self._render_tasks()

    def _on_search_changed(self, text: str):
        self.search_query = text.strip().lower()
        self._render_tasks()

    # =========================================================================
    # Task Creation & Mutation
    # =========================================================================
    def _create_quick_task(self):
        """Quick add task from the Microsoft To Do capsule bar."""
        title = self.input_task_title.text().strip()
        if not title:
            return

        priority = "urgent" if self.add_star_btn.isChecked() else "medium"
        self.task_store.add(
            title=title,
            priority=priority,
            source="manual",
            tag="TASK"
        )

        self.input_task_title.clear()
        self.add_star_btn.setChecked(False)
        self._render_tasks()

    def _on_task_status_changed(self, task_id: str, is_done: bool):
        self.task_store.set_status(task_id, "done" if is_done else "todo")
        self._render_tasks()

    def _on_task_priority_changed(self, task_id: str, priority: str):
        self.task_store.update(task_id, priority=priority)
        self._render_tasks()

    def _on_task_delete_requested(self, task_id: str):
        self.task_store.remove(task_id)
        self._render_tasks()

    def _jump_to_location(self, file_rel_or_abs: str, line: int):
        if not file_rel_or_abs:
            return
        abs_path = (self.root_path / file_rel_or_abs).resolve() if self.root_path else Path(file_rel_or_abs).resolve()
        line = max(1, line)
        self.open_location_requested.emit(str(abs_path), line)
        if self.main_window and hasattr(self.main_window, "open_analysis_location"):
            self.main_window.open_analysis_location(str(abs_path), line)

    def _toggle_completed_section(self):
        self.completed_collapsed = not self.completed_collapsed
        self._render_tasks()

    # =========================================================================
    # Rendering
    # =========================================================================
    def _matches_filter(self, task: Task) -> bool:
        # Category Filter
        if self.current_filter == "urgent" and task.priority not in ("urgent", "high"):
            return False
        elif self.current_filter == "doing" and task.status != "doing":
            return False
        elif self.current_filter == "done" and not task.is_done:
            return False

        # Text Search
        if self.search_query:
            haystack = f"{task.title} {task.details} {task.file} {task.priority}".lower()
            if self.search_query not in haystack:
                return False

        return True

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_tasks(self):
        """Populate scroll area with cards in Microsoft To Do aesthetic."""
        self._clear_layout(self.cards_layout)

        all_tasks = list(self.task_store.tasks)
        active_count = sum(1 for t in all_tasks if not t.is_done)
        has_urgent = any(t.priority in ("urgent", "high") and not t.is_done for t in all_tasks)

        self.task_count_changed.emit(active_count, has_urgent)

        filtered = [t for t in all_tasks if self._matches_filter(t)]

        # Sorting
        if self.sort_mode == "importance":
            filtered.sort(key=lambda t: (0 if t.priority == "urgent" else (1 if t.priority == "high" else 2), t.created))
        elif self.sort_mode == "title":
            filtered.sort(key=lambda t: t.title.lower())
        else:
            # Default: active high priority first, completed last
            filtered.sort(key=lambda t: t.sort_key)

        active_tasks = [t for t in filtered if not t.is_done]
        done_tasks = [t for t in filtered if t.is_done]

        # 1. Render Active Task Cards
        for t in active_tasks:
            card = TaskCardWidget(t, parent=self.cards_container)
            card.task_status_changed.connect(self._on_task_status_changed)
            card.task_priority_changed.connect(self._on_task_priority_changed)
            card.task_delete_requested.connect(self._on_task_delete_requested)
            card.open_location_requested.connect(self._jump_to_location)
            self.cards_layout.addWidget(card)

        # 2. Render Collapsible Completed Section (Microsoft To Do style)
        if done_tasks:
            # Section separator & header button
            done_header_btn = QtWidgets.QPushButton()
            set_line_icon(done_header_btn, "chevron-right" if self.completed_collapsed else "chevron-down", size=16)
            done_header_btn.setText("Завершено")
            done_header_btn.setCursor(Qt.PointingHandCursor)
            done_header_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8E8E98;
                    border: none;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 8px 4px 4px 4px;
                }
                QPushButton:hover {
                    color: #D4D4D8;
                }
            """)
            done_header_btn.clicked.connect(self._toggle_completed_section)
            self.cards_layout.addWidget(done_header_btn)

            if not self.completed_collapsed:
                for t in done_tasks:
                    card = TaskCardWidget(t, parent=self.cards_container)
                    card.task_status_changed.connect(self._on_task_status_changed)
                    card.task_priority_changed.connect(self._on_task_priority_changed)
                    card.task_delete_requested.connect(self._on_task_delete_requested)
                    card.open_location_requested.connect(self._jump_to_location)
                    self.cards_layout.addWidget(card)

        # 3. Empty State
        if not active_tasks and not done_tasks:
            empty_frame = QtWidgets.QFrame()
            empty_l = QtWidgets.QVBoxLayout(empty_frame)
            empty_l.setContentsMargins(20, 40, 20, 40)
            empty_l.setSpacing(10)
            empty_l.setAlignment(Qt.AlignCenter)

            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(line_icon("checklist", "#78B9FF").pixmap(38, 38))
            icon_lbl.setAlignment(Qt.AlignCenter)
            empty_l.addWidget(icon_lbl)

            msg_title = QtWidgets.QLabel("Задачи не найдены" if all_tasks else "Список задач пуст")
            msg_title.setAlignment(Qt.AlignCenter)
            msg_title.setStyleSheet("color: #EDEDED; font-size: 14px; font-weight: 600;")
            empty_l.addWidget(msg_title)

            msg_desc = QtWidgets.QLabel("Измените запрос или фильтр." if all_tasks
                                       else "Добавьте задачу, чтобы спланировать работу.")
            msg_desc.setAlignment(Qt.AlignCenter)
            msg_desc.setWordWrap(True)
            msg_desc.setStyleSheet("color: #71717A; font-size: 12px;")
            empty_l.addWidget(msg_desc)

            self.cards_layout.addWidget(empty_frame)

        self.cards_layout.addStretch(1)

        # Footer update
        total_done = sum(1 for t in all_tasks if t.is_done)
        self.status_footer.setText("")

    # =========================================================================
    # Import / Export
    # =========================================================================
    def _export_markdown(self):
        default_path = (self.root_path / "TODO.md") if self.root_path else Path("TODO.md")
        fp, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Экспорт задач в Markdown", str(default_path), "Markdown Files (*.md);;All Files (*)"
        )
        if fp:
            self.task_store.export_markdown(filepath=fp, include_done=True)
            QtWidgets.QMessageBox.information(self, "Экспорт завершён", f"Задачи успешно экспортированы в {Path(fp).name}")

    def _export_json(self):
        default_path = (self.root_path / "tasks_export.json") if self.root_path else Path("tasks_export.json")
        fp, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Экспорт задач в JSON", str(default_path), "JSON Files (*.json);;All Files (*)"
        )
        if fp:
            self.task_store.export_json(filepath=fp)
            QtWidgets.QMessageBox.information(self, "Экспорт завершён", f"Задачи успешно экспортированы в {Path(fp).name}")

    def _clear_done_tasks(self):
        cleared = self.task_store.clear_done()
        self._render_tasks()
        QtWidgets.QMessageBox.information(self, "Очистка", f"Удалено выполненных задач: {cleared}")
