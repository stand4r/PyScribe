"""PyScribe utils/WorkspaceIndex.py: application module and reusable component."""
import ast
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env", "node_modules", "dist", "build", ".idea", ".vscode"}
SOURCE_EXTENSIONS = {".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".kt", ".swift", ".css", ".html"}

# Completion only needs declaration names. Parsing a generated 15k-line module
# costs far more than the whole rest of a batch, so oversized files are skipped
# instead of stalling the GUI thread that runs the indexer.
MAX_INDEX_BYTES = 192 * 1024


class WorkspaceIndex:
    """Lightweight project symbol index used by editor completion.

    It intentionally works without external language servers: Python files use
    the stdlib AST, while other supported source files use conservative
    declaration regexes. This gives project-wide completion while keeping the
    application self-contained.
    """

    def __init__(self, root: Optional[str] = None):
        self.root: Optional[Path] = None
        self.symbols: Dict[str, Set[str]] = {}
        self.file_symbols: Dict[str, Set[str]] = {}
        self.file_members: Dict[str, Set[str]] = {}
        self.class_members: Dict[str, Set[str]] = {}
        self.file_class_members: Dict[str, Set[str]] = {}
        self.structure_symbols: Dict[str, Set[str]] = {}
        self.structure_members: Dict[str, Set[str]] = {}
        self._pending: List[Path] = []
        self._pending_index = 0
        self._generation = 0
        if root:
            self.set_root(root)

    @property
    def generation(self) -> int:
        """Bumped whenever the root changes, so stale parses can be dropped."""
        return self._generation

    def _clear(self) -> None:
        self.symbols.clear()
        self.file_symbols.clear()
        self.file_members.clear()
        self.class_members.clear()
        self.file_class_members.clear()
        self.structure_symbols.clear()
        self.structure_members.clear()

    def set_root(self, root: Optional[str], defer: bool = False) -> None:
        """Point the index at a project.

        ``defer=True`` scans the file list but leaves parsing to
        :meth:`process_batch`. Opening a large project used to parse every file
        synchronously on the UI thread, which froze the window and could end in
        a crash on huge trees.
        """
        self.root = Path(root).resolve() if root else None
        self._clear()
        self._pending = []
        self._pending_index = 0
        self._generation += 1
        if self.root and self.root.exists():
            if defer:
                self._pending = list(self._iter_source_files())
            else:
                self.rebuild()

    # -- incremental building ------------------------------------------
    def prepare_root(self, root: Optional[str]) -> None:
        """Point the index at *root* without scanning the tree yet.

        The scan itself (thousands of ``scandir`` calls) is the expensive part
        and is run off the GUI thread; :meth:`set_pending_files` then feeds the
        discovered files to :meth:`process_batch`.
        """
        self.root = Path(root).resolve() if root else None
        self._clear()
        self._pending = []
        self._pending_index = 0
        self._generation += 1

    def scan_source_files(self) -> List[Path]:
        """Return the source files of the current root (safe in a worker thread)."""
        return list(self._iter_source_files())

    def set_pending_files(self, files: Iterable[Path]) -> None:
        """Load a file list produced by :meth:`scan_source_files`."""
        self._pending = list(files)
        self._pending_index = 0

    @property
    def pending_count(self) -> int:
        return max(0, len(self._pending) - self._pending_index)

    def process_batch(self, limit: int = 40,
                      budget_ms: Optional[float] = None) -> bool:
        """Index pending files. Returns True while work remains.

        ``budget_ms`` caps the time spent on the GUI thread. A fixed number of
        files per batch meant a batch of large modules blocked the event loop
        for hundreds of milliseconds, freezing every running animation; the
        time budget keeps one slice within a few frames.
        """
        if not self._pending:
            return False
        limit = max(1, int(limit))
        deadline = None
        if budget_ms is not None and float(budget_ms) > 0:
            deadline = time.perf_counter() + float(budget_ms) / 1000.0
        index = self._pending_index
        total = len(self._pending)
        processed = 0
        while index < total and processed < limit:
            path = self._pending[index]
            index += 1
            processed += 1
            try:
                self.update_file(path)
            except Exception:
                # One unreadable/odd file must not abort the whole index.
                pass
            if deadline is not None and time.perf_counter() >= deadline:
                break
        self._pending_index = index
        if index >= total:
            self._pending = []
            self._pending_index = 0
            return False
        return True

    def rebuild(self) -> None:
        if not self.root:
            return
        self._clear()
        self._pending = []
        self._pending_index = 0
        for path in self._iter_source_files():
            try:
                self.update_file(path)
            except Exception:
                continue

    def _iter_source_files(self) -> Iterable[Path]:
        """Source files for the completion index, with ignored dirs pruned.

        Building the index used to ``rglob`` the whole tree, so opening a large
        project spent its time on ``node_modules`` and virtualenv files.
        """
        if self.root is None:
            return []
        from core.ignore_rules import MAX_FILES_DEFAULT, MAX_SOURCE_BYTES, walk_files
        scan = walk_files(self.root, extensions=SOURCE_EXTENSIONS,
                          max_files=MAX_FILES_DEFAULT, max_bytes=MAX_SOURCE_BYTES)
        self.last_scan = scan
        return list(scan.files)

    def _read(self, path: Path) -> str:
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                return ""
        except OSError:
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def update_file(self, path: Path, content: Optional[str] = None) -> None:
        path = Path(path).resolve()
        symbols, members = self._parse_one(path, content)
        self._store(str(path), symbols, members)

    def _parse_one(self, path: Path, content: Optional[str] = None
                   ) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """Read + parse one file; touches no index state, so it is thread safe."""
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            return set(), {}
        if content is None:
            try:
                if path.stat().st_size > MAX_INDEX_BYTES:
                    return set(), {}
            except OSError:
                return set(), {}
        code = content if content is not None else self._read(path)
        return self._extract(path, code)

    def _store(self, path_key: str, symbols: Set[str],
               members: Dict[str, Set[str]]) -> None:
        """Replace the indexed symbols of one file."""
        old = self.file_symbols.pop(path_key, set())
        for symbol in old:
            locations = self.symbols.get(symbol)
            if locations:
                locations.discard(path_key)
                if not locations:
                    self.symbols.pop(symbol, None)
        self.file_members.pop(path_key, None)
        for class_name in self.file_class_members.pop(path_key, set()):
            self.class_members.pop(class_name, None)

        self.file_class_members[path_key] = set(members.keys())
        for class_name, class_members in members.items():
            self.class_members[class_name] = set(class_members)
        flat_members = set().union(*members.values()) if members else set()
        self.file_symbols[path_key] = symbols
        self.file_members[path_key] = flat_members
        for symbol in symbols:
            self.symbols.setdefault(symbol, set()).add(path_key)

    # -- parsing on a worker thread ------------------------------------
    def parse_buffer(self, path: Path, content: str):
        """Parse an editor snapshot without mutating the index."""
        path = Path(path).resolve()
        symbols, members = self._parse_one(path, content)
        return [(str(path), symbols, members)]

    def take_batch_paths(self, limit: int = 40) -> List[Path]:
        """Reserve the next pending paths so they can be parsed elsewhere."""
        if not self._pending:
            return []
        end = min(len(self._pending), self._pending_index + max(1, int(limit)))
        batch = self._pending[self._pending_index:end]
        self._pending_index = end
        if self._pending_index >= len(self._pending):
            self._pending = []
            self._pending_index = 0
        return batch

    def parse_files(self, paths: Iterable[Path]) -> List[Tuple[str, Set[str], Dict[str, Set[str]]]]:
        """Parse *paths* without touching index state (worker-thread safe)."""
        parsed = []
        for path in paths:
            try:
                path = Path(path)
                symbols, members = self._parse_one(path)
                parsed.append((str(path.resolve()), symbols, members))
            except Exception:
                # One unreadable/odd file must not abort the whole index.
                continue
        return parsed

    def apply_parsed(self, parsed) -> None:
        """Merge results of :meth:`parse_files` into the index (GUI thread)."""
        for path_key, symbols, members in parsed or []:
            self._store(path_key, symbols, members)

    def _extract(self, path: Path, code: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
        symbols: Set[str] = set()
        members: Dict[str, Set[str]] = {}
        if path.suffix.lower() in {".py", ".pyw"}:
            try:
                tree = ast.parse(code)
            except SyntaxError:
                tree = None
            if tree is not None:
                self._collect_declarations(tree.body, symbols, members)
                return symbols, members

        patterns = [
            r"\b(?:class|interface|struct|enum|type)\s+([A-Za-z_]\w*)",
            r"\b(?:def|func|fn|function|fun)\s+([A-Za-z_]\w*)",
            r"\b(?:const|let|var|val|public|private|static)\s+([A-Za-z_]\w*)",
            r"\b([A-Za-z_]\w*)\s*=\s*(?:function|\([^\n]*\)\s*=>)",
        ]
        for pattern in patterns:
            symbols.update(re.findall(pattern, code))
        return symbols, members

    @classmethod
    def _collect_declarations(cls, statements, symbols: Set[str],
                              members: Dict[str, Set[str]]) -> None:
        """Collect top-level declarations without walking expressions.

        ``ast.walk`` visited every name of every expression, so refreshing the
        index for a 2.8k-line module blocked the GUI thread for ~100 ms — and
        while the GUI thread works, every animation in the window is frozen.
        Declarations live in statement lists, which are cheap to scan.
        """
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(node.name)
            elif isinstance(node, ast.ClassDef):
                symbols.add(node.name)
                members[node.name] = cls._class_members(node.body)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        symbols.add(alias.asname or alias.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                cls._add_targets(node, symbols)
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                # Conditional imports and platform-dependent declarations.
                nested = list(getattr(node, "body", []) or [])
                nested += list(getattr(node, "orelse", []) or [])
                nested += list(getattr(node, "finalbody", []) or [])
                for handler in getattr(node, "handlers", []) or []:
                    nested += list(getattr(handler, "body", []) or [])
                cls._collect_declarations(nested, symbols, members)

    @staticmethod
    def _class_members(statements) -> Set[str]:
        names: Set[str] = set()
        for child in statements:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                WorkspaceIndex._add_targets(child, names)
        return names

    @staticmethod
    def _add_targets(node, out: Set[str]) -> None:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                out.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    if isinstance(element, ast.Name):
                        out.add(element.id)

    def apply_analysis(self, analysis) -> None:
        """Merge Project Intelligence's canonical structural tree into completion data."""
        self.structure_symbols.clear()
        self.structure_members.clear()
        nodes = getattr(analysis, "structure_nodes", []) or []
        by_parent = {}
        for node in nodes:
            by_parent.setdefault(getattr(node, "parent_id", ""), []).append(node)
            file_key = str(getattr(node, "file", ""))
            if file_key:
                self.structure_symbols.setdefault(file_key, set()).add(node.name)
        for node in nodes:
            children = by_parent.get(getattr(node, "id", ""), [])
            if children:
                self.structure_members[node.name] = {c.name for c in children if getattr(c, "name", None)}
                file_key = str(getattr(node, "file", ""))
                self.file_members.setdefault(file_key, set()).update(self.structure_members[node.name])
        for file_key, names in self.structure_symbols.items():
            self.file_symbols.setdefault(file_key, set()).update(names)
            for name in names:
                self.symbols.setdefault(name, set()).add(file_key)

    def complete_members(self, class_name: str, prefix: str = "") -> List[str]:
        values = set(self.class_members.get(class_name, set())) | set(self.structure_members.get(class_name, set()))
        p = prefix.lower()
        return sorted([v for v in values if v.lower().startswith(p)], key=str.lower)

    def complete(self, prefix: str = "", language: str = "") -> List[str]:
        prefix_l = prefix.lower()
        result = []
        for symbol in self.symbols:
            if not prefix_l or symbol.lower().startswith(prefix_l):
                result.append(symbol)
        return sorted(result, key=lambda x: (not x.lower().startswith(prefix_l), x.lower()))

    def describe(self, symbol: str) -> str:
        locations = self.symbols.get(symbol, set())
        if not locations:
            return "Workspace symbol"
        if self.root:
            try:
                relative = Path(next(iter(locations))).relative_to(self.root)
                return f"Workspace • {relative}"
            except ValueError:
                pass
        return "Workspace symbol"

    def all_symbols(self) -> List[str]:
        return sorted(self.symbols)
