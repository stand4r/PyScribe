"""Project task board («Диспетчер задач»).

Keeps a small, explicit list of things to do in the project — created by hand or
promoted from an analyzer recommendation — and stores it next to the project in
``.pyscribe/tasks.json`` so it survives restarts and travels with the repository.

No Qt imports here on purpose: the store is plain Python and unit-testable.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

__all__ = ["Task", "TaskStore", "STATUSES", "PRIORITIES"]

STATUSES = {
    "todo": "К выполнению",
    "doing": "В работе",
    "done": "Готово",
}

PRIORITIES = {
    "high": "Высокий",
    "medium": "Средний",
    "low": "Низкий",
}

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_STATUS_ORDER = {"doing": 0, "todo": 1, "done": 2}


@dataclass
class Task:
    """One item on the project board."""

    title: str
    details: str = ""
    status: str = "todo"
    priority: str = "medium"
    file: str = ""
    line: int = 0
    source: str = "manual"      # manual | analysis
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def normalize(self) -> "Task":
        self.status = self.status if self.status in STATUSES else "todo"
        self.priority = self.priority if self.priority in PRIORITIES else "medium"
        self.title = (self.title or "").strip() or "Без названия"
        self.line = int(self.line or 0)
        return self

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def sort_key(self):
        return (_STATUS_ORDER.get(self.status, 9),
                _PRIORITY_ORDER.get(self.priority, 9),
                self.title.lower())


class TaskStore:
    """Loads, edits and persists the task list of one project."""

    FILE_NAME = "tasks.json"
    FOLDER = ".pyscribe"

    def __init__(self, project_root: Optional[str] = None):
        self.root: Optional[Path] = None
        self.tasks: List[Task] = []
        self.error: str = ""
        if project_root:
            self.set_root(project_root)

    # -- storage -------------------------------------------------------
    @property
    def path(self) -> Optional[Path]:
        if self.root is None:
            return None
        return self.root / self.FOLDER / self.FILE_NAME

    def set_root(self, project_root: Optional[str]) -> None:
        self.root = Path(project_root).resolve() if project_root else None
        self.tasks = []
        self.error = ""
        if self.root is not None:
            self.load()

    def load(self) -> List[Task]:
        """Read the board; a missing or broken file means an empty board."""
        self.tasks = []
        self.error = ""
        path = self.path
        if path is None or not path.is_file():
            return self.tasks
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.error = f"Не удалось прочитать задачи: {exc}"
            return self.tasks
        items = data.get("tasks", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return self.tasks
        for raw in items:
            if not isinstance(raw, dict):
                continue
            try:
                self.tasks.append(Task(
                    title=str(raw.get("title", "")),
                    details=str(raw.get("details", "")),
                    status=str(raw.get("status", "todo")),
                    priority=str(raw.get("priority", "medium")),
                    file=str(raw.get("file", "")),
                    line=int(raw.get("line", 0) or 0),
                    source=str(raw.get("source", "manual")),
                    id=str(raw.get("id") or uuid.uuid4().hex[:12]),
                    created=float(raw.get("created", time.time())),
                    updated=float(raw.get("updated", time.time())),
                ).normalize())
            except (TypeError, ValueError):
                continue
        self._sort()
        return self.tasks

    def save(self) -> bool:
        """Write the board; never raises (returns False and sets ``error``)."""
        path = self.path
        if path is None:
            self.error = "Проект не открыт"
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "updated": time.time(),
                "tasks": [asdict(task) for task in self.tasks],
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            self.error = ""
            return True
        except OSError as exc:
            self.error = f"Не удалось сохранить задачи: {exc}"
            return False

    # -- editing -------------------------------------------------------
    def add(self, title: str, details: str = "", priority: str = "medium",
            file: str = "", line: int = 0, source: str = "manual") -> Task:
        task = Task(title=title, details=details, priority=priority, file=file,
                    line=line, source=source).normalize()
        self.tasks.append(task)
        self._sort()
        self.save()
        return task

    def find(self, task_id: str) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def update(self, task_id: str, **changes) -> Optional[Task]:
        task = self.find(task_id)
        if task is None:
            return None
        for key, value in changes.items():
            if hasattr(task, key) and key not in ("id", "created"):
                setattr(task, key, value)
        task.updated = time.time()
        task.normalize()
        self._sort()
        self.save()
        return task

    def set_status(self, task_id: str, status: str) -> Optional[Task]:
        return self.update(task_id, status=status)

    def toggle_done(self, task_id: str) -> Optional[Task]:
        task = self.find(task_id)
        if task is None:
            return None
        return self.set_status(task_id, "todo" if task.is_done else "done")

    def remove(self, task_id: str) -> bool:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) == before:
            return False
        self.save()
        return True

    def clear_done(self) -> int:
        done = [t for t in self.tasks if t.is_done]
        if not done:
            return 0
        self.tasks = [t for t in self.tasks if not t.is_done]
        self.save()
        return len(done)

    # -- queries -------------------------------------------------------
    def filtered(self, status: Optional[str] = None) -> List[Task]:
        if not status:
            return list(self.tasks)
        return [t for t in self.tasks if t.status == status]

    def stats(self) -> Dict[str, int]:
        result = {key: 0 for key in STATUSES}
        for task in self.tasks:
            result[task.status] = result.get(task.status, 0) + 1
        result["total"] = len(self.tasks)
        return result

    def _sort(self) -> None:
        self.tasks.sort(key=lambda task: task.sort_key)
