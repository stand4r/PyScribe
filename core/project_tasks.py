"""Project task board («Диспетчер задач»).

Keeps a small, explicit list of things to do in the project — created by hand or
promoted from an analyzer recommendation — and stores it next to the project in
``.pyscribe/tasks.json`` so it survives restarts and travels with the repository.

No Qt imports here on purpose: the store is plain Python and unit-testable.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

__all__ = ["Task", "TaskStore", "CodeTaskScanner", "STATUSES", "PRIORITIES"]

STATUSES = {
    "todo": "К выполнению",
    "doing": "В работе",
    "done": "Готово",
}

PRIORITIES = {
    "urgent": "Срочный",
    "high": "Высокий",
    "medium": "Средний",
    "low": "Низкий",
}

_PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
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
    tag: str = "TASK"
    author: str = ""
    source: str = "manual"      # manual | code | analysis
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def normalize(self) -> "Task":
        self.status = self.status if self.status in STATUSES else "todo"
        self.priority = self.priority if self.priority in PRIORITIES else "medium"
        self.title = (self.title or "").strip() or "Без названия"
        self.line = int(self.line or 0)
        self.tag = (self.tag or "TASK").upper()
        self.author = (self.author or "").strip()
        return self

    @property
    def rel_file(self) -> str:
        return self.file

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def sort_key(self):
        return (_STATUS_ORDER.get(self.status, 9),
                _PRIORITY_ORDER.get(self.priority, 9),
                self.file.lower(),
                self.line,
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
                    tag=str(raw.get("tag", "TASK")),
                    author=str(raw.get("author", "")),
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
            file: str = "", line: int = 0, source: str = "manual",
            tag: str = "TASK", author: str = "") -> Task:
        task = Task(title=title, details=details, priority=priority, file=file,
                    line=line, source=source, tag=tag, author=author).normalize()
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

    # -- export --------------------------------------------------------
    def export_markdown(
        self,
        filepath: Optional[str | Path] = None,
        include_code_tasks: Optional[List[Task]] = None,
        include_done: bool = True,
    ) -> str:
        """Export tasks into GitHub-flavored Markdown document."""
        lines = ["# Задачи проекта (Project Tasks & To Do)\n"]

        all_tasks = list(self.tasks)
        if include_code_tasks:
            all_tasks.extend(include_code_tasks)

        todo_tasks = [t for t in all_tasks if not t.is_done]
        done_tasks = [t for t in all_tasks if t.is_done]

        if todo_tasks:
            lines.append("## К выполнению\n")
            for t in todo_tasks:
                loc = f" (`{t.file}:{t.line}`)" if t.file else ""
                prio = f"**[{t.priority.upper()}]** " if t.priority in ("urgent", "high") else ""
                lines.append(f"- [ ] {prio}{t.title}{loc}")
            lines.append("")

        if done_tasks and include_done:
            lines.append("## Завершено\n")
            for t in done_tasks:
                loc = f" (`{t.file}:{t.line}`)" if t.file else ""
                lines.append(f"- [x] {t.title}{loc}")
            lines.append("")

        md_content = "\n".join(lines)
        if filepath:
            Path(filepath).write_text(md_content, encoding="utf-8")
        return md_content

    def export_json(self, filepath: Optional[str | Path] = None, include_code_tasks: Optional[List[Task]] = None) -> str:
        """Export tasks as JSON string and optionally save to file."""
        all_tasks = list(self.tasks)
        if include_code_tasks:
            all_tasks.extend(include_code_tasks)
        payload = {
            "version": 1,
            "exported": time.time(),
            "count": len(all_tasks),
            "tasks": [asdict(t) for t in all_tasks],
        }
        json_content = json.dumps(payload, ensure_ascii=False, indent=2)
        if filepath:
            Path(filepath).write_text(json_content, encoding="utf-8")
        return json_content


SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
    "node_modules", "dist", "build", ".idea", ".vscode", ".pyscribe",
    ".pytest_cache", ".mypy_cache"
}

CODE_TASK_REGEX = re.compile(
    r'(?:#|//|/\*|\*|--|;)\s*(TODO|FIXME|HACK|BUG|XXX|OPTIMIZE|TEMP)(?:\(([^)]+)\))?\s*[:\-]?\s*(.*)$',
    re.IGNORECASE
)

TAG_PRIORITIES = {
    "FIXME": "urgent",
    "BUG": "urgent",
    "HACK": "high",
    "XXX": "high",
    "TODO": "medium",
    "OPTIMIZE": "low",
    "TEMP": "low",
}


class CodeTaskScanner:
    """Scans project files for in-code TODO/FIXME/BUG/HACK task comments."""

    @classmethod
    def scan_text(
        cls,
        text: str,
        file_path: str = "",
        root: Optional[Path] = None,
        rel_path: str = "",
    ) -> List[Task]:
        """Scan buffer text and return extracted tasks."""
        tasks: List[Task] = []
        rel_file = rel_path
        if not rel_file and file_path:
            p = Path(file_path)
            if root:
                try:
                    rel_file = str(p.relative_to(root)).replace("\\", "/")
                except ValueError:
                    rel_file = str(p).replace("\\", "/")
            else:
                rel_file = str(p).replace("\\", "/")

        for line_num, line in enumerate(text.splitlines(), start=1):
            m = CODE_TASK_REGEX.search(line)
            if not m:
                continue
            tag = m.group(1).upper()
            opts = (m.group(2) or "").strip()
            raw_desc = (m.group(3) or "").strip().rstrip("*/").strip() or tag
            priority = TAG_PRIORITIES.get(tag, "medium")
            author = ""
            if opts:
                for part in opts.split(","):
                    p_clean = part.strip()
                    if p_clean.startswith("@"):
                        author = p_clean
                    elif p_clean.lower() in PRIORITIES:
                        priority = p_clean.lower()

            # Stable task id
            task_id = f"code_{hash(f'{rel_file}:{line_num}:{tag}') & 0xFFFFFFFF:08x}"
            task = Task(
                id=task_id,
                title=f"[{tag}] {raw_desc}",
                details=raw_desc,
                status="todo",
                priority=priority,
                file=rel_file or file_path,
                line=line_num,
                tag=tag,
                author=author,
                source="code",
            ).normalize()
            tasks.append(task)
        return tasks

    @classmethod
    def scan_file(cls, file_path: Path | str, root: Optional[Path] = None) -> List[Task]:
        """Scan a single file on disk."""
        p = Path(file_path)
        if not p.is_file():
            return []
        try:
            if p.stat().st_size > 2 * 1024 * 1024:
                return []
            text = p.read_text(encoding="utf-8", errors="replace")
            return cls.scan_text(text, file_path=str(p), root=root)
        except Exception:
            return []

    @classmethod
    def scan_project(cls, root_path: Path | str, max_files: int = 1500) -> List[Task]:
        """Walk project directory and collect all code tasks."""
        root = Path(root_path).resolve()
        if not root.is_dir():
            return []
        tasks: List[Task] = []
        count = 0
        valid_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp",
            ".cs", ".go", ".rs", ".java", ".php", ".rb", ".sh", ".sql",
            ".yaml", ".yml", ".md", ".txt"
        }
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                count += 1
                if count > max_files:
                    break
                fp = Path(dirpath) / f
                if fp.suffix.lower() in valid_extensions:
                    file_tasks = cls.scan_file(fp, root=root)
                    tasks.extend(file_tasks)
            if count > max_files:
                break
        return tasks
