"""Application version helpers (single source of truth: the ``VERSION`` file).

The updater, the About dialog and the installer all read the same file, so a
release only has to change one line. Frozen builds carry ``VERSION`` inside the
PyInstaller bundle; source checkouts read it from the project root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

__all__ = [
    "app_root",
    "current_version",
    "normalize_version",
    "version_tuple",
    "is_newer",
]


def app_root() -> Path:
    """Directory that contains ``VERSION``, ``main.py`` and the packages."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def current_version() -> str:
    """Version string such as ``"1.1.0"`` (never raises)."""
    for candidate in (app_root() / "VERSION", Path.cwd() / "VERSION"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text.lstrip("vV").strip()
    return "0.0.0"


def normalize_version(value: object) -> str:
    """``v1.2.0``/``release 1.2`` → ``1.2.0``/``1.2``."""
    text = str(value or "").strip()
    match = re.search(r"\d+(?:\.\d+)*", text)
    return match.group(0) if match else "0"


def version_tuple(value: object) -> tuple[int, ...]:
    """Comparable tuple: ``"1.10.2"`` → ``(1, 10, 2)`` (missing parts are 0)."""
    parts = [int(part) for part in normalize_version(value).split(".") if part.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(remote: object, local: object) -> bool:
    """True when *remote* is a strictly newer version than *local*."""
    return version_tuple(remote) > version_tuple(local)
