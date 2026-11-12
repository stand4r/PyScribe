"""Tests for the project task board (`core/project_tasks.py`).

Run: python tests/test_project_tasks.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.project_tasks import PRIORITIES, STATUSES, TaskStore


def test_empty_store_has_no_file():
    with tempfile.TemporaryDirectory() as td:
        store = TaskStore(td)
        assert store.tasks == []
        assert store.path.name == "tasks.json"
        assert store.path.parent.name == ".pyscribe"
        assert not store.path.exists()
        assert store.stats()["total"] == 0


def test_add_persist_and_reload():
    with tempfile.TemporaryDirectory() as td:
        store = TaskStore(td)
        first = store.add("Разобрать модуль импорта", priority="high",
                          file="core/a.py", line=42, source="analysis")
        store.add("Проверить пустой ввод")
        assert store.stats()["total"] == 2
        assert store.path.is_file()

        reloaded = TaskStore(td)
        assert reloaded.stats()["total"] == 2
        again = reloaded.find(first.id)
        assert again is not None
        assert again.title == "Разобрать модуль импорта"
        assert again.priority == "high"
        assert again.line == 42


def test_status_transitions_and_done_cleanup():
    with tempfile.TemporaryDirectory() as td:
        store = TaskStore(td)
        task = store.add("Сделать X")
        assert task.status == "todo"
        store.set_status(task.id, "doing")
        assert store.find(task.id).status == "doing"
        store.toggle_done(task.id)
        assert store.find(task.id).is_done
        store.toggle_done(task.id)
        assert store.find(task.id).status == "todo"
        store.set_status(task.id, "done")
        assert store.clear_done() == 1
        assert store.stats()["total"] == 0


def test_remove_and_update():
    with tempfile.TemporaryDirectory() as td:
        store = TaskStore(td)
        task = store.add("Старое имя")
        store.update(task.id, title="Новое имя", priority="low")
        assert store.find(task.id).title == "Новое имя"
        assert store.find(task.id).priority == "low"
        assert store.remove(task.id) is True
        assert store.remove(task.id) is False
        assert store.stats()["total"] == 0


def test_sorting_puts_active_high_priority_first():
    with tempfile.TemporaryDirectory() as td:
        store = TaskStore(td)
        low = store.add("низкий приоритет", priority="low")
        high = store.add("высокий приоритет", priority="high")
        done = store.add("готовое", priority="high")
        store.set_status(done.id, "done")
        doing = store.add("в работе", priority="medium")
        store.set_status(doing.id, "doing")
        order = [task.id for task in store.tasks]
        assert order.index(doing.id) < order.index(high.id)
        assert order.index(high.id) < order.index(low.id)
        assert order.index(low.id) < order.index(done.id)


def test_broken_file_is_reported_not_raised():
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td) / ".pyscribe"
        folder.mkdir()
        (folder / "tasks.json").write_text("{ broken", encoding="utf-8")
        store = TaskStore(td)
        assert store.tasks == []
        assert store.error


def test_unknown_values_are_normalized():
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td) / ".pyscribe"
        folder.mkdir()
        (folder / "tasks.json").write_text(
            '{"tasks": [{"title": "x", "status": "bogus", "priority": "nonexistent_priority"}]}',
            encoding="utf-8")
        store = TaskStore(td)
        task = store.tasks[0]
        assert task.status in STATUSES
        assert task.status == "todo"
        assert task.priority in PRIORITIES
        assert task.priority == "medium"


def test_switching_project_resets_the_board():
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        store = TaskStore(first)
        store.add("задача первого проекта")
        assert store.stats()["total"] == 1
        store.set_root(second)
        assert store.stats()["total"] == 0
        store.set_root(None)
        assert store.path is None
        assert store.save() is False


if __name__ == "__main__":
    tests = [
        ("test_empty_store_has_no_file", test_empty_store_has_no_file),
        ("test_add_persist_and_reload", test_add_persist_and_reload),
        ("test_status_transitions_and_done_cleanup", test_status_transitions_and_done_cleanup),
        ("test_remove_and_update", test_remove_and_update),
        ("test_sorting_puts_active_high_priority_first",
         test_sorting_puts_active_high_priority_first),
        ("test_broken_file_is_reported_not_raised", test_broken_file_is_reported_not_raised),
        ("test_unknown_values_are_normalized", test_unknown_values_are_normalized),
        ("test_switching_project_resets_the_board", test_switching_project_resets_the_board),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
