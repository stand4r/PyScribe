"""Windows Explorer integration: "Открыть с помощью" and a context menu entry.

Everything is registered under ``HKCU\\Software\\Classes`` — per-user, no
administrator rights, easy to remove:

* ``Applications\\PyScribe`` makes PyScribe appear in the system **«Открыть с
  помощью»** dialog (``SupportedTypes`` lists the extensions);
* ``*\\shell\\PyScribe`` adds **«Открыть в PyScribe»** to the context menu of any
  file, ``Directory`` / ``Directory\\Background`` for folders;
* ``PyScribe.File`` + ``*\\OpenWithProgids`` covers files whose extension is not
  associated with anything yet.

The launcher for a source checkout is ``pythonw.exe main.py "%1"``; frozen
builds point at ``PyScribe.exe`` directly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from core.app_version import app_root

__all__ = [
    "APP_KEY_NAME",
    "PROGID",
    "SUPPORTED_TYPES",
    "command_line",
    "background_command_line",
    "is_registered",
    "launcher",
    "register",
    "registration_entries",
    "supported_types",
    "unregister",
]

APP_KEY_NAME = "PyScribe"
PROGID = "PyScribe.File"
CLASSES = r"Software\Classes"
APPLICATIONS_KEY = rf"{CLASSES}\Applications\{APP_KEY_NAME}"
FILE_PROGID_KEY = rf"{CLASSES}\{PROGID}"

# Extensions for the "Open with" list. They do not change the default handler.
SUPPORTED_TYPES = (
    ".py", ".pyw", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".log", ".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx",
    ".c", ".h", ".cpp", ".cc", ".hpp", ".cs", ".java", ".kt", ".go", ".rs",
    ".php", ".rb", ".sql", ".xml", ".bat", ".cmd", ".ps1", ".sh", ".env",
    ".csv", ".tsv", ".gitignore", ".gitattributes",
)


def _quote(value: str) -> str:
    return '"' + str(value).replace('"', r'\"') + '"'


def launcher() -> Tuple[str, List[str]]:
    """Executable and leading arguments that start PyScribe."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    executable = Path(sys.executable)
    windowed = executable.with_name("pythonw.exe")
    if windowed.exists():
        executable = windowed
    return str(executable), [str(app_root() / "main.py")]


def command_line(placeholder: str = "%1") -> str:
    """Full ``shell\\open\\command`` value for a file/folder placeholder."""
    executable, arguments = launcher()
    parts = [_quote(executable)] + [_quote(argument) for argument in arguments]
    parts.append(_quote(placeholder))
    return " ".join(parts)


def background_command_line() -> str:
    """Context-menu command for a folder background (``%V``)."""
    return command_line("%V")


def icon_value() -> str:
    """Icon spec accepted by the registry (``path`` or ``path,0``)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}",0'
    icon = app_root() / "src" / "PyScribe.ico"
    if icon.exists():
        return f'"{icon}"'
    return ""


def supported_types() -> Tuple[str, ...]:
    return SUPPORTED_TYPES


def registration_entries() -> List[dict]:
    """Describe every registry value PyScribe owns (pure, no writes).

    Each entry is ``{"key": <subkey under HKCU>, "name": <value name or "" >,
    "value": <data>}``. The tests check the generated commands and paths without
    touching a real registry.
    """
    entries: List[dict] = [
        # --- "Open with" application entry -----------------------------
        {"key": APPLICATIONS_KEY, "name": "ApplicationName", "value": "PyScribe"},
        {"key": APPLICATIONS_KEY, "name": "ApplicationCompany",
         "value": "PyScribe Development Team"},
        {"key": rf"{APPLICATIONS_KEY}\shell\open\command",
         "name": "", "value": command_line()},
        {"key": rf"{APPLICATIONS_KEY}\shell\open", "name": "FriendlyAppName",
         "value": "PyScribe"},
        # --- ProgID used by OpenWithProgids ----------------------------
        {"key": FILE_PROGID_KEY, "name": "FriendlyTypeName", "value": "Файл PyScribe"},
        {"key": rf"{FILE_PROGID_KEY}\DefaultIcon", "name": "", "value": icon_value()},
        {"key": rf"{FILE_PROGID_KEY}\shell\open\command", "name": "",
         "value": command_line()},
        {"key": rf"{CLASSES}\*\OpenWithProgids", "name": PROGID, "value": ""},
        # --- Explorer context menu -------------------------------------
        {"key": rf"{CLASSES}\*\shell\{APP_KEY_NAME}", "name": "MUIVerb",
         "value": "Открыть в PyScribe"},
        {"key": rf"{CLASSES}\*\shell\{APP_KEY_NAME}", "name": "Icon",
         "value": icon_value()},
        {"key": rf"{CLASSES}\*\shell\{APP_KEY_NAME}\command", "name": "",
         "value": command_line()},
        {"key": rf"{CLASSES}\Directory\shell\{APP_KEY_NAME}", "name": "MUIVerb",
         "value": "Открыть папку в PyScribe"},
        {"key": rf"{CLASSES}\Directory\shell\{APP_KEY_NAME}", "name": "Icon",
         "value": icon_value()},
        {"key": rf"{CLASSES}\Directory\shell\{APP_KEY_NAME}\command", "name": "",
         "value": command_line()},
        {"key": rf"{CLASSES}\Directory\Background\shell\{APP_KEY_NAME}", "name": "MUIVerb",
         "value": "Открыть в PyScribe"},
        {"key": rf"{CLASSES}\Directory\Background\shell\{APP_KEY_NAME}", "name": "Icon",
         "value": icon_value()},
        {"key": rf"{CLASSES}\Directory\Background\shell\{APP_KEY_NAME}\command",
         "name": "", "value": background_command_line()},
    ]
    for extension in SUPPORTED_TYPES:
        entries.append({"key": rf"{APPLICATIONS_KEY}\SupportedTypes",
                        "name": extension, "value": ""})
    if icon_value():
        entries.append({"key": APPLICATIONS_KEY, "name": "ApplicationIcon",
                        "value": icon_value()})
    return entries


def _winreg():
    if os.name != "nt":
        return None
    import winreg
    return winreg


def is_registered() -> bool:
    """True when the Explorer integration is present for the current user."""
    winreg = _winreg()
    if winreg is None:
        return False
    for key in (rf"{APPLICATIONS_KEY}\shell\open\command",
                rf"{CLASSES}\*\shell\{APP_KEY_NAME}\command"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key):
                pass
        except OSError:
            return False
    return True


def register() -> Tuple[bool, List[str]]:
    """Create all per-user registry entries. Returns ``(ok, errors)``."""
    winreg = _winreg()
    if winreg is None:
        return False, ["Интеграция с проводником доступна только в Windows."]
    errors: List[str] = []
    for entry in registration_entries():
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, entry["key"], 0,
                                    winreg.KEY_WRITE) as handle:
                if entry["name"]:
                    winreg.SetValueEx(handle, entry["name"], 0, winreg.REG_SZ,
                                      str(entry["value"]))
                else:
                    winreg.SetValueEx(handle, "", 0, winreg.REG_SZ,
                                      str(entry["value"]))
        except OSError as exc:
            errors.append(f"{entry['key']}: {exc}")
    # Best effort: notify Explorer so the menu appears without a restart.
    try:
        from core.subprocess_utils import run_hidden
        run_hidden(["ie4uinit.exe", "-show"], timeout=10,
                   capture_output=True, text=True)
    except Exception:  # noqa: BLE001 - purely cosmetic
        pass
    return not errors, errors


def _delete_tree(winreg, root, subkey: str) -> None:
    """Recursively remove *subkey* (ignores a missing key)."""
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as handle:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(handle, index))
                except OSError:
                    break
                index += 1
    except OSError:
        return
    for child in children:
        _delete_tree(winreg, root, rf"{subkey}\{child}")
    try:
        winreg.DeleteKey(root, subkey)
    except OSError:
        pass


def unregister() -> Tuple[bool, List[str]]:
    """Remove every entry created by :func:`register`."""
    winreg = _winreg()
    if winreg is None:
        return False, ["Интеграция с проводником доступна только в Windows."]
    errors: List[str] = []
    for subkey in (APPLICATIONS_KEY, FILE_PROGID_KEY,
                   rf"{CLASSES}\*\shell\{APP_KEY_NAME}",
                   rf"{CLASSES}\Directory\shell\{APP_KEY_NAME}",
                   rf"{CLASSES}\Directory\Background\shell\{APP_KEY_NAME}"):
        try:
            _delete_tree(winreg, winreg.HKEY_CURRENT_USER, subkey)
        except OSError as exc:
            errors.append(f"{subkey}: {exc}")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\*\OpenWithProgids",
                            0, winreg.KEY_WRITE) as handle:
            winreg.DeleteValue(handle, PROGID)
    except OSError:
        pass
    return not errors, errors
