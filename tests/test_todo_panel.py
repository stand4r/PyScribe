"""Unit and UI integration tests for the PyScribe To Do Panel (widgets/TodoPanel.py).
Verified for the Microsoft To Do-inspired design and task management.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtWidgets
from core.project_tasks import CodeTaskScanner, Task, TaskStore
from widgets.TodoPanel import CheckCircleButton, StarButton, TaskCardWidget, TodoPanel


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


# =============================================================================
# 1. Custom Microsoft To Do Controls Tests
# =============================================================================
def test_check_circle_button(qapp):
    btn = CheckCircleButton(checked=False)
    assert not btn.isChecked()
    btn.click()
    assert btn.isChecked()
    btn.click()
    assert not btn.isChecked()


def test_star_button(qapp):
    star = StarButton(starred=False)
    assert not star.isChecked()
    star.click()
    assert star.isChecked()
    star.click()
    assert not star.isChecked()


# =============================================================================
# 2. TaskCardWidget Tests
# =============================================================================
def test_task_card_signals(qapp):
    task = Task(id="t1", title="Купить кофе", priority="medium", status="todo")
    card = TaskCardWidget(task)

    status_events = []
    card.task_status_changed.connect(lambda tid, done: status_events.append((tid, done)))
    card.check_circle.click()
    assert len(status_events) == 1
    assert status_events[0] == ("t1", True)

    prio_events = []
    card.task_priority_changed.connect(lambda tid, prio: prio_events.append((tid, prio)))
    card.star_btn.click()
    assert len(prio_events) == 1
    assert prio_events[0] == ("t1", "urgent")


# =============================================================================
# 3. TodoPanel UI & Interaction Tests
# =============================================================================
class DummyEditor:
    def __init__(self, file_path="core/engine.py", line=42, code="# sample"):
        self.file_path = file_path
        self.line = line
        self.code = code

    def get_cursor_line(self):
        return self.line

    def get_code(self):
        return self.code


class DummyMainWindow:
    def __init__(self):
        self._current_editor = DummyEditor()

    def get_current_editor(self):
        return self._current_editor


def test_todo_panel_initialization(qapp):
    panel = TodoPanel()
    assert panel.objectName() == "todoPanel"
    assert panel.search_input is not None
    assert panel.cards_container is not None
    assert panel._filter_chips is not None
    assert "all" in panel._filter_chips
    assert "urgent" in panel._filter_chips
    assert "doing" in panel._filter_chips
    assert "done" in panel._filter_chips
    assert panel.current_filter == "all"


def test_todo_panel_quick_add(qapp):
    main_win = DummyMainWindow()
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel(main_window=main_win)
        panel.set_project(td)

        # 1. Normal task
        panel.input_task_title.setText("Подготовить релиз")
        panel._create_quick_task()

        assert len(panel.task_store.tasks) == 1
        t1 = panel.task_store.tasks[0]
        assert t1.title == "Подготовить релиз"
        assert t1.priority == "medium"
        assert panel.input_task_title.text() == ""

        # 2. Starred task
        panel.input_task_title.setText("Исправить баг в парсере")
        panel.add_star_btn.setChecked(True)
        panel._create_quick_task()

        assert len(panel.task_store.tasks) == 2
        t2 = next((t for t in panel.task_store.tasks if t.title == "Исправить баг в парсере"), None)
        assert t2 is not None
        assert t2.priority == "urgent"
        assert t2.file == ""
        assert t2.line == 0


def test_todo_panel_filter_chips(qapp):
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel()
        panel.set_project(td)

        panel.task_store.add("Срочная задача", priority="urgent")
        panel.task_store.add("В работе задача", priority="medium")
        doing = panel.task_store.tasks[-1]
        panel.task_store.set_status(doing.id, "doing")

        done = panel.task_store.add("Выполненная задача", priority="low")
        panel.task_store.set_status(done.id, "done")

        # 1. Filter: all
        panel._set_filter("all")
        assert panel.current_filter == "all"

        # 2. Filter: urgent
        panel._set_filter("urgent")
        assert panel.current_filter == "urgent"

        # 3. Filter: doing
        panel._set_filter("doing")
        assert panel.current_filter == "doing"

        # 4. Filter: done
        panel._set_filter("done")
        assert panel.current_filter == "done"


def test_todo_panel_search_filtering(qapp):
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel()
        panel.set_project(td)

        panel.task_store.add("Оптимизировать UI рендер")
        panel.task_store.add("Написать документацию")

        panel.search_input.setText("UI")
        assert panel.search_query == "ui"

        panel.search_input.setText("НЕ_СУЩЕСТВУЕТ_XYZ")
        assert panel.search_query == "не_существует_xyz"


def test_todo_panel_collapsible_completed(qapp):
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel()
        panel.set_project(td)

        t = panel.task_store.add("Готовая задача")
        panel.task_store.set_status(t.id, "done")
        panel._render_tasks()

        assert panel.completed_collapsed is False
        panel._toggle_completed_section()
        assert panel.completed_collapsed is True
        panel._toggle_completed_section()
        assert panel.completed_collapsed is False


def test_todo_panel_location_jump_signal(qapp):
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel()
        panel.set_project(td)

        file_path = os.path.join(td, "src", "main.py")
        panel.task_store.add("Задача с привязкой", file=file_path, line=77)
        panel._render_tasks()

        jumped = []
        panel.open_location_requested.connect(lambda f, l: jumped.append((f, l)))

        panel._jump_to_location(file_path, 77)
        assert len(jumped) == 1
        assert jumped[0] == (file_path, 77)


def test_todo_panel_live_badge_signal(qapp):
    with tempfile.TemporaryDirectory() as td:
        panel = TodoPanel()
        badges = []
        panel.task_count_changed.connect(lambda cnt, urg: badges.append((cnt, urg)))

        panel.set_project(td)
        panel.task_store.add("Обычная задача", priority="medium")
        panel._render_tasks()

        assert len(badges) >= 1
        last_count, last_urgent = badges[-1]
        assert last_count == 1
        assert last_urgent is False

        panel.task_store.add("Срочная задача", priority="urgent")
        panel._render_tasks()
        last_count, last_urgent = badges[-1]
        assert last_count == 2
        assert last_urgent is True
