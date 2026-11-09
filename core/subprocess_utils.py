"""Start child processes without flashing a console window.

PyScribe is a windowed application (``pythonw``), so Windows gives every
console program started from it its own console window. That is the black
``cmd`` window the user sees flashing on each ``git`` call, compiler run or
MCP server start. Adding ``CREATE_NO_WINDOW`` (plus a hidden ``STARTUPINFO``)
suppresses it while stdin/stdout pipes keep working exactly as before.

The integrated terminal is *not* the right tool for these background jobs: it
is the user's interactive shell, so writing there would mix machine output with
their commands, steal the prompt and require parsing text to get exit codes.
All background work goes through this module instead.

Public API
----------
``hidden_process_kwargs()``   CreateProcess flags for the current platform
``run_hidden(argv, **kwargs)``      ``subprocess.run`` without a console window
``popen_hidden(argv, **kwargs)``    ``subprocess.Popen`` without a console window
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict

__all__ = ["CREATE_NO_WINDOW", "hidden_process_kwargs", "run_hidden",
           "popen_hidden", "popen_detached"]

#: ``CreateProcess`` flag: the child must not get a console window.
CREATE_NO_WINDOW = 0x08000000


def hidden_process_kwargs() -> Dict[str, Any]:
    """Return the ``subprocess`` keyword arguments that hide the child window."""
    if os.name != "nt":
        return {}
    kwargs: Dict[str, Any] = {"creationflags": CREATE_NO_WINDOW}
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is not None:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _merge(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Combine hidden-window defaults with caller keywords (caller wins)."""
    merged = dict(hidden_process_kwargs())
    merged.update(kwargs)
    return merged


def run_hidden(argv, check: bool = False, **kwargs):
    """``subprocess.run`` that never opens a console window."""
    return subprocess.run(argv, check=check, **_merge(kwargs))


def popen_hidden(argv, **kwargs):
    """``subprocess.Popen`` that never opens a console window."""
    return subprocess.Popen(argv, **_merge(kwargs))


def popen_detached(argv, **kwargs):
    """Start a GUI program (installer) with no console but a visible window.

    ``popen_hidden`` sets ``STARTUPINFO.wShowWindow = SW_HIDE``; that is right
    for background tools, but it would also hide an installer wizard. Here only
    ``CREATE_NO_WINDOW`` is applied, so a GUI child still paints normally.
    """
    kwargs.setdefault("close_fds", True)
    if os.name == "nt":
        kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.Popen(argv, **kwargs)
