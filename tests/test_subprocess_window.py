"""Tests for console-free child processes.

PyScribe runs as a windowed (``pythonw``) application, so a console program
started with a plain ``CreateProcess`` gets its own console window — the black
``cmd`` window that flashed on every git call. Every child process must go
through ``core.subprocess_utils``.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.subprocess_utils import (CREATE_NO_WINDOW, hidden_process_kwargs,  # noqa: E402
                                   popen_hidden, run_hidden)

RAW_CALL = re.compile(r"subprocess\.(?:run|Popen|call|check_output|check_call)\s*\(")


def test_hidden_kwargs_hide_the_console_window():
    kwargs = hidden_process_kwargs()
    if os.name == "nt":
        assert kwargs.get("creationflags") == CREATE_NO_WINDOW
        startupinfo = kwargs.get("startupinfo")
        assert startupinfo is not None, "STARTUPINFO must be provided on Windows"
        assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert startupinfo.wShowWindow == subprocess.SW_HIDE
    else:
        assert kwargs == {}


def test_run_hidden_captures_output():
    result = run_hidden([sys.executable, "-c", "print('hidden-ok')"],
                        capture_output=True, text=True)
    assert result.returncode == 0
    assert "hidden-ok" in result.stdout


def test_run_hidden_forwards_check():
    try:
        run_hidden([sys.executable, "-c", "raise SystemExit(3)"], check=True,
                   capture_output=True)
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 3
    else:
        raise AssertionError("CalledProcessError was expected")


def test_popen_hidden_has_no_window_and_pipes_work():
    proc = popen_hidden([sys.executable, "-c", "print('piped')"],
                        stdout=subprocess.PIPE, text=True)
    out, _ = proc.communicate(timeout=30)
    assert proc.returncode == 0
    assert "piped" in out


def _source_files():
    for folder in ("app", "core", "services", "utils", "widgets"):
        directory = ROOT / folder
        if directory.is_dir():
            yield from directory.rglob("*.py")
    main = ROOT / "main.py"
    if main.exists():
        yield main


def test_no_raw_subprocess_calls_outside_the_helper():
    allowed = {ROOT / "core" / "subprocess_utils.py"}
    offenders = []
    for path in _source_files():
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in RAW_CALL.finditer(text):
            line = text[:match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert not offenders, (
        "Дочерние процессы нужно запускать через core.subprocess_utils "
        f"(иначе при pythonw мигает окно консоли): {offenders}"
    )


TESTS = [
    test_hidden_kwargs_hide_the_console_window,
    test_run_hidden_captures_output,
    test_run_hidden_forwards_check,
    test_popen_hidden_has_no_window_and_pipes_work,
    test_no_raw_subprocess_calls_outside_the_helper,
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
