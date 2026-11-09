"""Which files a project scan should touch.

A naive ``Path.rglob('*')`` walks into ``node_modules``, ``.git`` and virtual
environments *before* the loop can filter them out — on a large project that is
hundreds of thousands of paths in memory, which is both slow and a crash risk.
Everything here exists so scans prune those directories during the walk instead
of after it.

The rules are intentionally conservative: only directories and files that can
never be project source are skipped. ``.gitignore`` is honoured on top of that,
and ``.pyscribeignore`` can add project-specific patterns.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple

__all__ = [
    "IGNORED_DIR_NAMES",
    "MAX_SOURCE_BYTES",
    "MAX_FILES_DEFAULT",
    "ScanResult",
    "should_skip_dir",
    "should_skip_file",
    "scan_project",
    "walk_files",
]

# Directory names that never contain project source. Compared lower-case.
# Deliberately excludes ambiguous names (a "bin" or "images" folder may hold
# real project files), so nothing that could be source is hidden.
IGNORED_DIR_NAMES: Set[str] = {
    # version control / tooling metadata
    ".git", ".hg", ".svn", ".bzr", "_darcs", ".idea", ".vscode", ".vs",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox", ".eggs",
    ".ipynb_checkpoints", ".terraform", ".serverless", ".parcel-cache",
    ".next", ".nuxt", ".svelte-kit", ".angular", ".turbo", ".yarn", ".pnpm-store",
    # python environments and caches
    "__pycache__", ".venv", "venv", "env", "virtualenv", "site-packages",
    "node_modules", "bower_components", "jspm_packages", "htmlcov", ".coverage",
    # build output
    "dist", "build", "out", "obj", "bin", "target", "coverage", "installer_output",
    "artifacts", "publish", "testresults", "debug", "release", "x64", "x86",
    # vendored third-party code and package caches
    "vendor", "vendors", "third_party", "third-party", "pods", "deriveddata",
    "packages", ".pnpm", ".cache", "temp", "tmp",
    # bulky, never-source directories
    "logs", "screenshoots", "screenshots", "__snapshots__",
}

# Files that are generated, minified or locked and carry no useful structure.
IGNORED_FILE_NAMES: Set[str] = {
    ".ds_store", "thumbs.db", "desktop.ini",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "pipfile.lock", "cargo.lock", "composer.lock", "gemfile.lock", "mix.lock",
}

# Glob patterns for generated / bundled files.
IGNORED_FILE_PATTERNS: Tuple[str, ...] = (
    "*.min.js", "*.min.css", "*.bundle.js", "*.chunk.js", "*.map",
    "*.generated.*", "*.g.dart", "*.designer.cs", "*_pb2.py", "*_pb2_grpc.py",
    "*.pb.go", "*.svgz", "*.zip", "*.tar", "*.gz", "*.7z", "*.rar",
)

# A single source file larger than this is almost certainly generated data.
# It also bounds GIL stalls: parsing a multi-megabyte file blocks the UI
# thread for as long as the C-level parse runs, which reads as a frozen window.
MAX_SOURCE_BYTES = 512 * 1024

# Upper bound for one scan. Protects against pathological trees; the UI reports
# when the list was cut short.
MAX_FILES_DEFAULT = 4000

IGNORE_FILE_NAME = ".pyscribeignore"

# Binary formats are skipped unless the binary analyzer explicitly asks for them.
BINARY_SUFFIXES: Set[str] = {
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib", ".o", ".obj", ".class",
    ".pyc", ".pyd", ".wasm", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".mp3", ".mp4", ".avi", ".mkv", ".wav", ".flac", ".mov",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}


@dataclass
class ScanResult:
    """Outcome of a project scan, including what was skipped and why."""

    files: List[Path] = field(default_factory=list)
    truncated: bool = False
    skipped_dirs: int = 0
    skipped_files: int = 0
    limit: Optional[int] = None
    # Names of skipped directories (capped) so the UI can explain the numbers.
    skipped_dir_names: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.files)

    def _note_dir(self, name: str) -> None:
        if name not in self.skipped_dir_names and len(self.skipped_dir_names) < 40:
            self.skipped_dir_names.append(name)


def should_skip_dir(name: str) -> bool:
    """True for directories that never hold project source."""
    lowered = (name or "").lower()
    if not lowered:
        return True
    if lowered in IGNORED_DIR_NAMES:
        return True
    # Virtualenvs are often named `.venv312` / `venv-build` / `env2`.
    base = lowered.lstrip(".")
    if base.startswith(("venv", "env")) and len(base) > 3:
        if any(ch.isdigit() or ch in "-_." for ch in base[3:]):
            return True
    return False


def should_skip_file(path: Path) -> bool:
    """True for generated, binary or lock files."""
    name = path.name.lower()
    if name in IGNORED_FILE_NAMES:
        return True
    for pattern in IGNORED_FILE_PATTERNS:
        if fnmatch(name, pattern):
            return True
    return False


def _load_patterns(root: Path) -> List[str]:
    """Patterns from .gitignore and .pyscribeignore (relative, POSIX style)."""
    patterns: List[str] = []
    for file_name in (".gitignore", IGNORE_FILE_NAME):
        path = root / file_name
        try:
            if not path.is_file():
                continue
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                patterns.append(line.replace("\\", "/").rstrip("/"))
        except OSError:
            continue
    return patterns


def _matches_patterns(relative_posix: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    parts = relative_posix.split("/")
    for pattern in patterns:
        if "/" in pattern:
            if fnmatch(relative_posix, pattern) or fnmatch(relative_posix, f"{pattern}/*"):
                return True
        else:
            if any(fnmatch(part, pattern) for part in parts):
                return True
    return False


def walk_files(root: Path, *, extensions: Optional[Iterable[str]] = None,
               max_files: Optional[int] = MAX_FILES_DEFAULT,
               max_bytes: Optional[int] = MAX_SOURCE_BYTES,
               use_ignore_files: bool = True) -> ScanResult:
    """Walk *root*, pruning ignored directories **during** traversal.

    ``Path.rglob`` cannot do this: it descends into ``node_modules`` and then the
    caller filters paths, which is where the memory and time went.

    ``os.scandir`` is used instead of ``os.walk`` because Windows returns the
    file size together with the directory entry: the size filter then costs no
    extra ``stat`` call per file, which matters a lot on cloud-synced folders.
    """
    result = ScanResult(limit=max_files)
    root = Path(root)
    if not root.exists():
        return result
    allowed = {ext.lower() for ext in extensions} if extensions else None
    patterns = _load_patterns(root) if use_ignore_files else []
    root_str = str(root)

    stack: List[Tuple[str, str]] = [(root_str, "")]
    while stack:
        dir_path, rel_prefix = stack.pop()
        try:
            with os.scandir(dir_path) as iterator:
                entries = list(iterator)
        except OSError:
            # Permission denied on a subdirectory must not abort the scan.
            continue

        subdirs: List[Tuple[str, str]] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            relative = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            if is_dir:
                if should_skip_dir(entry.name):
                    result.skipped_dirs += 1
                    result._note_dir(entry.name)
                    continue
                if patterns and _matches_patterns(relative, patterns):
                    result.skipped_dirs += 1
                    result._note_dir(entry.name)
                    continue
                subdirs.append((entry.path, relative))
                continue

            path = Path(entry.path)
            if should_skip_file(path):
                result.skipped_files += 1
                continue
            if allowed is not None and path.suffix.lower() not in allowed:
                continue
            if patterns and _matches_patterns(relative, patterns):
                result.skipped_files += 1
                continue
            if max_bytes:
                try:
                    if entry.stat().st_size > max_bytes:
                        result.skipped_files += 1
                        continue
                except OSError:
                    result.skipped_files += 1
                    continue
            result.files.append(path)
            if max_files and len(result.files) >= max_files:
                result.truncated = True
                return result

        # Depth-first with a stable alphabetical order.
        stack.extend(reversed(sorted(subdirs, key=lambda item: item[1].lower())))
    return result


def scan_project(root: Path, *, extensions: Optional[Iterable[str]] = None,
                 max_files: Optional[int] = MAX_FILES_DEFAULT,
                 max_bytes: Optional[int] = MAX_SOURCE_BYTES,
                 use_ignore_files: bool = True) -> ScanResult:
    """Alias with a clearer name for callers that just need the file list."""
    return walk_files(root, extensions=extensions, max_files=max_files,
                      max_bytes=max_bytes, use_ignore_files=use_ignore_files)
