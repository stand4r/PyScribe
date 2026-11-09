"""Tests for scan rules: ignored directories, limits and analysis integration.

Run: python tests/test_ignore_rules.py
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ignore_rules import (
    MAX_SOURCE_BYTES,
    should_skip_dir,
    should_skip_file,
    walk_files,
)


def _make_project(root: Path, node_modules_files: int = 120) -> None:
    """A project whose bulk lives in directories that must be skipped."""
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (root / "src" / "pkg" / "util.py").write_text("VALUE = 2\n", encoding="utf-8")

    junk = root / "node_modules" / "pkg"
    junk.mkdir(parents=True)
    for index in range(node_modules_files):
        (junk / f"module{index}.js").write_text("var x = 1;\n", encoding="utf-8")

    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    venv = root / "venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "site.py").write_text("import os\n", encoding="utf-8")


def test_skip_rules_cover_common_junk():
    for name in (".git", "node_modules", "__pycache__", ".venv", "venv312",
                 "dist", "build", "site-packages", ".mypy_cache", "target",
                 "bin", "obj", "Debug", "packages"):
        assert should_skip_dir(name), name
    # A folder that may hold real project code must not be skipped.
    for name in ("src", "app", "core", "tests", "docs", "tools", "scripts"):
        assert not should_skip_dir(name), name

    assert should_skip_file(Path("package-lock.json"))
    assert should_skip_file(Path("bundle.min.js"))
    assert should_skip_file(Path("data.csv.map"))
    assert not should_skip_file(Path("app.py"))


def test_walk_prunes_ignored_directories():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        result = walk_files(root)
        names = sorted(p.name for p in result.files)
        assert "app.py" in names and "util.py" in names
        # Nothing from node_modules, .git or venv may appear.
        assert not any(name.startswith("module") for name in names), names
        assert "HEAD" not in names and "site.py" not in names
        assert result.skipped_dirs >= 3


def test_walk_is_fast_because_it_does_not_descend():
    """Pruning during traversal is what keeps large projects openable."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root, node_modules_files=400)
        started = time.perf_counter()
        result = walk_files(root, extensions={".py"})
        elapsed = time.perf_counter() - started
        assert len(result.files) == 2
        # rglob over the same tree has to stat every file; this stays cheap.
        assert elapsed < 2.0, f"обход занял {elapsed:.2f}s"


def test_max_files_limit_sets_truncated():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        for index in range(30):
            (root / "src" / f"file{index}.py").write_text("x = 1\n", encoding="utf-8")
        result = walk_files(root, extensions={".py"}, max_files=10)
        assert len(result.files) == 10
        assert result.truncated is True
        assert result.limit == 10


def test_large_files_are_skipped():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "small.py").write_text("x = 1\n", encoding="utf-8")
        big = root / "src" / "generated.py"
        big.write_text("x = 1\n" + "y = 2\n" * (MAX_SOURCE_BYTES // 6 + 100),
                       encoding="utf-8")
        result = walk_files(root, extensions={".py"})
        names = [p.name for p in result.files]
        assert "small.py" in names
        assert "generated.py" not in names
        assert result.skipped_files >= 1


def test_gitignore_and_pyscribeignore_are_honoured():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "vendor_code").mkdir()
        (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (root / "vendor_code" / "lib.py").write_text("y = 2\n", encoding="utf-8")
        (root / "src" / "debug.log").write_text("noise\n", encoding="utf-8")
        (root / ".gitignore").write_text("vendor_code/\n*.log\n", encoding="utf-8")
        result = walk_files(root)
        names = {p.name for p in result.files}
        assert "app.py" in names
        assert "lib.py" not in names
        assert "debug.log" not in names

        (root / ".pyscribeignore").write_text("src/app.py\n", encoding="utf-8")
        result = walk_files(root)
        assert "app.py" not in {p.name for p in result.files}


def test_analysis_uses_the_pruned_walk():
    """End-to-end: the analyzer sees only real sources."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        from core.project_intelligence import ProjectIntelligenceEngine
        engine = ProjectIntelligenceEngine(str(root), enabled_analyzers={"structure"})
        analysis = engine.analyze()
        assert analysis.scan_truncated is False
        assert analysis.skipped_dirs >= 3
        languages_files = [f for f in analysis.files.values()]
        assert len(languages_files) == 2, list(analysis.files)
        assert all(str(f.path).endswith(".py") for f in languages_files)


def test_analysis_reports_truncation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        for index in range(20):
            (root / "src" / f"f{index}.py").write_text("x = 1\n", encoding="utf-8")
        from core.project_intelligence import ProjectIntelligenceEngine
        engine = ProjectIntelligenceEngine(str(root), enabled_analyzers={"structure"})
        engine.max_files = 5
        analysis = engine.analyze()
        assert analysis.scan_truncated is True
        assert len(analysis.files) <= 5
        assert any(issue.code == "SCAN_LIMIT" for issue in analysis.issues)


def test_workspace_index_skips_ignored_dirs():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex(str(root))
        indexed = {str(path) for path in index.file_symbols}
        assert any(path.endswith("app.py") for path in indexed), indexed
        assert not any("module" in path for path in indexed), indexed


def test_index_can_be_built_in_batches():
    """Deferred indexing keeps the UI responsive when a project opens."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex()
        index.set_root(str(root), defer=True)
        assert index.pending_count >= 2, index.pending_count
        assert index.symbols == {}
        assert index.process_batch(1) is True
        assert index.symbols, "первый пакет должен добавить символы"
        guard = 0
        while index.process_batch(1):
            guard += 1
            assert guard < 50, "пакеты не завершаются"
        assert index.pending_count == 0
        assert index.file_symbols


def test_build_directories_are_skipped():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        for junk in ("bin", "obj", "Debug", "packages"):
            folder = root / junk
            folder.mkdir()
            (folder / "junk.py").write_text("y = 2\n", encoding="utf-8")
        result = walk_files(root, extensions={".py"})
        names = sorted(p.name for p in result.files)
        assert names == ["app.py"], names
        assert result.skipped_dirs >= 4
        assert "bin" in result.skipped_dir_names


if __name__ == "__main__":
    tests = [
        ("test_skip_rules_cover_common_junk", test_skip_rules_cover_common_junk),
        ("test_walk_prunes_ignored_directories", test_walk_prunes_ignored_directories),
        ("test_walk_is_fast_because_it_does_not_descend",
         test_walk_is_fast_because_it_does_not_descend),
        ("test_max_files_limit_sets_truncated", test_max_files_limit_sets_truncated),
        ("test_large_files_are_skipped", test_large_files_are_skipped),
        ("test_gitignore_and_pyscribeignore_are_honoured",
         test_gitignore_and_pyscribeignore_are_honoured),
        ("test_analysis_uses_the_pruned_walk", test_analysis_uses_the_pruned_walk),
        ("test_analysis_reports_truncation", test_analysis_reports_truncation),
        ("test_workspace_index_skips_ignored_dirs", test_workspace_index_skips_ignored_dirs),
        ("test_index_can_be_built_in_batches", test_index_can_be_built_in_batches),
        ("test_build_directories_are_skipped", test_build_directories_are_skipped),
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
