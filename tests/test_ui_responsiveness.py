"""Tests for GUI-thread responsiveness work.

Every millisecond spent on the GUI thread is a millisecond in which no Qt
animation advances, so the work that used to run there (project analysis,
completion indexing, ``git`` queries, per-keystroke re-indexing) is now
deferred, batched, cached or moved to the thread pool.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets  # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _pump(ms: int):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        _APP.processEvents()
        time.sleep(0.005)


def _make_project(root: Path, lines: int = 40):
    (root / "src").mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"def function_{i}():\n    value_{i} = {i}\n    return value_{i}"
                     for i in range(lines))
    (root / "src" / "app.py").write_text(body + "\n", encoding="utf-8")
    (root / "src" / "module.py").write_text("class Widget:\n    def draw(self):\n        pass\n",
                                            encoding="utf-8")


# ----------------------------------------------------------------------
# Completion index: batching, thread-safe parsing
# ----------------------------------------------------------------------
def test_index_batch_respects_time_budget():
    """A batch never runs much longer than its budget, even with big files."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root, lines=200)
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex()
        index.prepare_root(str(root))
        index.set_pending_files(index.scan_source_files())
        assert index.pending_count >= 2
        started = time.perf_counter()
        index.process_batch(limit=500, budget_ms=2.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        # One file may overshoot; the whole batch must not.
        assert elapsed_ms < 120.0, elapsed_ms
        assert index.symbols, "the first slice must index something"


def test_index_parsing_is_thread_safe_and_mergeable():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex()
        index.prepare_root(str(root))
        paths = index.scan_source_files()
        parsed = index.parse_files(paths)
        assert parsed, "parse_files must return results"
        # Parsing must not touch the index: merging is a separate step.
        assert index.symbols == {}
        index.apply_parsed(parsed)
        assert "function_0" in index.symbols, index.symbols
        assert any(key.endswith("app.py") for key in index.file_symbols)


def test_take_batch_paths_advances_the_cursor():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_project(root)
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex()
        index.prepare_root(str(root))
        index.set_pending_files(index.scan_source_files())
        first = index.take_batch_paths(1)
        assert len(first) == 1
        second = index.take_batch_paths(10)
        assert second and first[0] not in second
        assert index.pending_count == 0


def test_generation_changes_with_the_root():
    with tempfile.TemporaryDirectory() as td:
        from core.workspace_index import WorkspaceIndex
        index = WorkspaceIndex()
        before = index.generation
        index.prepare_root(str(Path(td)))
        assert index.generation > before


def test_stale_index_slice_is_dropped():
    """A slice parsed for the previous project must not leak into the new one."""
    from app.main_window import ModernMainWindow

    class _Index:
        generation = 5

        def __init__(self):
            self.merged = []

        def apply_parsed(self, parsed):
            self.merged.append(parsed)

    class _Stub:
        _on_index_batch_parsed = ModernMainWindow._on_index_batch_parsed
        workspace_index = _Index()

    stub = _Stub()
    stub._on_index_batch_parsed([("old.py", set(), {})], generation=4)
    assert stub.workspace_index.merged == [], "stale results must be ignored"
    stub._on_index_batch_parsed([("new.py", set(), {})], generation=5)
    assert len(stub.workspace_index.merged) == 1


# ----------------------------------------------------------------------
# Background helper
# ----------------------------------------------------------------------
def test_run_async_delivers_on_gui_thread():
    from services.background import run_async
    import threading
    result = {}

    def work():
        return threading.current_thread().name

    def done(value):
        result["value"] = value
        result["thread"] = threading.current_thread().name

    run_async(work, on_done=done)
    _pump(1500)
    assert "value" in result, "callback never ran"
    assert result["value"] != "MainThread"
    assert result["thread"] == "MainThread"


def test_run_async_reports_errors():
    from services.background import run_async
    errors = []
    run_async(lambda: 1 / 0, on_error=errors.append)
    _pump(1200)
    assert errors and "division" in errors[0]


# ----------------------------------------------------------------------
# Per-file diagnostics cache
# ----------------------------------------------------------------------
def test_console_analysis_is_cached_and_invalidated():
    from widgets.ConsoleWidget import ConsoleWidget

    class _Issue:
        severity = "warning"
        file = "app.py"
        line = 3
        code = "W001"
        message = "demo"

    class _Info:
        issues = (_Issue(),)
        language = "python"
        lines = 10
        functions = 1
        classes = 0
        complexity = 2
        metrics = {}

    class _Engine:
        enabled_analyzers = {"structure"}
        root = "C:/project"

        def __init__(self):
            self.calls = 0

        def analyze_file(self, path, content=None):
            self.calls += 1
            return _Info()

    engine = _Engine()
    widget = ConsoleWidget()
    try:
        widget.set_file_context("C:/project/app.py", engine=engine, content="x = 1\n")
        widget.set_file_context("C:/project/app.py", engine=engine, content="x = 1\n")
        assert engine.calls == 1, "unchanged content must reuse the cached analysis"
        widget.set_file_context("C:/project/app.py", engine=engine, content="x = 2\n")
        assert engine.calls == 2, "edited content must be re-analysed"
        assert widget.problems_list.count() == 1
    finally:
        widget.deleteLater()


def test_analysis_signature_tracks_engine_and_content():
    from widgets.ConsoleWidget import ConsoleWidget

    class _Engine:
        def __init__(self, analyzers, root="C:/p"):
            self.enabled_analyzers = analyzers
            self.root = root

    first = ConsoleWidget._analysis_signature("a.py", "x = 1", _Engine({"structure"}))
    same = ConsoleWidget._analysis_signature("a.py", "x = 1", _Engine({"structure"}))
    other_content = ConsoleWidget._analysis_signature("a.py", "x = 2", _Engine({"structure"}))
    other_engine = ConsoleWidget._analysis_signature("a.py", "x = 1", _Engine({"health"}))
    assert first == same
    assert first != other_content
    assert first != other_engine


# ----------------------------------------------------------------------
# Git panel: no subprocess storm while a project is being opened
# ----------------------------------------------------------------------
def test_git_panel_defers_refresh_until_shown():
    from widgets.GitPanel import GitPanel

    class _Panel(GitPanel):
        def __init__(self):
            super().__init__()
            self.refreshes = 0

        def refresh(self):
            self.refreshes += 1

    panel = _Panel()
    try:
        panel.set_root(str(ROOT))
        assert panel.refreshes == 0, "a hidden git panel must not query git"
        assert panel._needs_refresh is True
        panel.show()
        _pump(200)
        assert panel.refreshes == 1, "showing the panel refreshes it"
        panel.set_root(str(ROOT))
        assert panel.refreshes == 2, "a visible panel refreshes immediately"
    finally:
        panel.hide()
        panel.deleteLater()


def test_git_state_is_read_off_the_gui_thread():
    """Opening Source Control must not spawn git processes on the GUI thread."""
    import threading

    from widgets.GitPanel import GitPanel

    panel = GitPanel()
    panel.root_path = str(ROOT)
    calls = []

    def fake_run(args, timeout=15):
        calls.append((threading.current_thread().name, tuple(args)))
        if list(args) == ["branch", "--show-current"]:
            return True, "main"
        if list(args) == ["status", "--porcelain"]:
            return True, "M  app/main.py\n?? notes.txt\n"
        if list(args) == ["remote", "get-url", "origin"]:
            return True, ""
        if list(args) == ["branch", "--list"]:
            return True, "* main\n"
        return True, ""

    panel._run = fake_run
    try:
        panel.refresh()
        assert calls == [], "refresh() must not run git synchronously"
        _pump(1500)
        assert calls, "the worker never queried git"
        assert all(name != "MainThread" for name, _ in calls), calls
        assert panel.current_branch == "main"
        assert panel.files.count() == 2, panel.files.count()
        assert panel._state_busy is False
    finally:
        panel.deleteLater()


def test_git_refresh_requests_are_coalesced():
    import threading

    from widgets.GitPanel import GitPanel

    panel = GitPanel()
    panel.root_path = str(ROOT)
    branch_calls = []

    def fake_run(args, timeout=15):
        if list(args) == ["branch", "--show-current"]:
            branch_calls.append(threading.current_thread().name)
            return True, "main"
        if list(args) == ["status", "--porcelain"]:
            return True, ""
        if list(args) == ["remote", "get-url", "origin"]:
            return True, ""
        if list(args) == ["branch", "--list"]:
            return True, "* main\n"
        return True, ""

    panel._run = fake_run
    try:
        panel.refresh()
        panel.refresh()
        panel.refresh()
        _pump(1500)
        # Three calls while a read is in flight collapse into one extra read.
        assert len(branch_calls) <= 2, f"workers stacked: {branch_calls}"
        assert panel._state_busy is False
    finally:
        panel.deleteLater()


# ----------------------------------------------------------------------
# Deferred analysis actions
# ----------------------------------------------------------------------
def _window_stub(panel):
    from app.main_window import ModernMainWindow

    class _StatusBar:
        def __init__(self):
            self.messages = []

        def showMessage(self, message, timeout=0):
            self.messages.append(message)

    class _Stub:
        _analysis_ready = staticmethod(ModernMainWindow._analysis_ready)
        _analysis_disabled = staticmethod(ModernMainWindow._analysis_disabled)
        _ensure_engine_analysis = ModernMainWindow._ensure_engine_analysis
        _defer_until_analysis = ModernMainWindow._defer_until_analysis
        _drain_analysis_actions = ModernMainWindow._drain_analysis_actions
        intelligence_panel = panel

        def __init__(self):
            self.status_bar = _StatusBar()

    return _Stub()


def test_ensure_engine_analysis_never_analyses_inline():
    """The heavy analysis must be started on the worker, not run here."""
    class _Engine:
        analysis = None
        root = "C:/p"

        def analyze(self):        # pragma: no cover - must never be called
            raise AssertionError("analysis ran on the GUI thread")

    class _Panel:
        engine = _Engine()

        def __init__(self):
            self.refreshed = 0

        def refresh(self):
            self.refreshed += 1

        def set_project(self, root):
            raise AssertionError("an already opened project must just refresh")

    panel = _Panel()
    window = _window_stub(panel)
    engine = window._ensure_engine_analysis(panel.engine, "C:/p")
    assert engine is panel.engine
    assert panel.refreshed == 1
    assert window._analysis_ready(engine) is False


def test_deferred_actions_run_when_analysis_finishes():
    class _Analysis:
        duration_ms = 12
        files = {}

    class _Engine:
        analysis = _Analysis()
        root = "C:/p"

    class _Panel:
        engine = _Engine()

    window = _window_stub(_Panel())
    done = []
    window._defer_until_analysis(lambda: done.append("graph"))
    window._defer_until_analysis(lambda: done.append("passport"))
    assert done == []
    window._drain_analysis_actions()
    assert done == ["graph", "passport"]
    # The queue is drained exactly once.
    window._drain_analysis_actions()
    assert done == ["graph", "passport"]


def test_placeholder_analysis_is_not_ready():
    """A fresh engine exposes an empty placeholder — that is not "analysed"."""
    class _Analysis:
        duration_ms = 0
        files = {}

    class _Engine:
        analysis = _Analysis()
        root = "C:/p"

    window = _window_stub(None)
    assert window._analysis_ready(_Engine()) is False
    assert window._analysis_ready(None) is False


def test_ready_engine_short_circuits_analysis_start():
    class _Analysis:
        duration_ms = 25
        files = {}

    class _Engine:
        analysis = _Analysis()
        root = "C:/p"

    class _Panel:
        engine = _Engine()

        def refresh(self):        # pragma: no cover - must not be called
            raise AssertionError("refresh must not run for an analysed project")

    panel = _Panel()
    window = _window_stub(panel)
    assert window._ensure_engine_analysis(panel.engine, "C:/p") is panel.engine


def test_failed_analysis_does_not_restart_in_a_loop():
    class _Engine:
        analysis = None
        root = "C:/p"

    class _Panel:
        engine = _Engine()

        def refresh(self):        # pragma: no cover - must not be called
            raise AssertionError("a failed analysis must not be restarted here")

    panel = _Panel()
    window = _window_stub(panel)
    window._analysis_failed = True
    assert window._ensure_engine_analysis(panel.engine, "C:/p") is panel.engine
    done = []
    window._defer_until_analysis(lambda: done.append("graph"))
    assert done == [], "actions must not pile up after a failure"
    assert getattr(window, "_analysis_pending_actions", []) == []


TESTS = [
    test_index_batch_respects_time_budget,
    test_index_parsing_is_thread_safe_and_mergeable,
    test_take_batch_paths_advances_the_cursor,
    test_generation_changes_with_the_root,
    test_stale_index_slice_is_dropped,
    test_run_async_delivers_on_gui_thread,
    test_run_async_reports_errors,
    test_console_analysis_is_cached_and_invalidated,
    test_analysis_signature_tracks_engine_and_content,
    test_git_panel_defers_refresh_until_shown,
    test_git_state_is_read_off_the_gui_thread,
    test_git_refresh_requests_are_coalesced,
    test_ensure_engine_analysis_never_analyses_inline,
    test_deferred_actions_run_when_analysis_finishes,
    test_placeholder_analysis_is_not_ready,
    test_ready_engine_short_circuits_analysis_start,
    test_failed_analysis_does_not_restart_in_a_loop,
]


def main():
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {test.__name__}: {exc!r}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
