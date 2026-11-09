"""Tests for GitHub updates and Windows Explorer integration.

Run: python tests/test_updates_and_shell.py
"""
import hashlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.app_version import (current_version, is_newer, normalize_version,  # noqa: E402
                              version_tuple)
from core import shell_integration  # noqa: E402
from services import updater  # noqa: E402

_APP = None


def _qapp():
    global _APP
    if _APP is None:
        from PyQt5 import QtWidgets
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


API_FIXTURE = {
    "tag_name": "v1.2.0",
    "name": "PyScribe 1.2.0",
    "body": "- Новый агент\n- Обновления из GitHub",
    "html_url": "https://github.com/stand4r/PyScribe/releases/tag/v1.2.0",
    "published_at": "2026-11-10T10:00:00Z",
    "assets": [
        {"name": "PyScribe-Setup-v1.2.0.exe",
         "browser_download_url": "https://example.invalid/setup.exe",
         "size": 1234,
         "digest": "sha256:" + "a" * 64},
        {"name": "PyScribe-Source.zip",
         "browser_download_url": "https://example.invalid/source.zip",
         "size": 99, "digest": ""},
    ],
}


def test_version_helpers():
    assert normalize_version("v1.10.2") == "1.10.2"
    assert version_tuple("1.2") == (1, 2, 0)
    assert version_tuple("v2.0.0") > version_tuple("1.9.9")
    assert is_newer("1.10.0", "1.9.9")
    assert not is_newer("1.1.0", "1.1.0")
    assert current_version() == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_release_parsing_and_installer_choice():
    release = updater.ReleaseInfo.from_api(API_FIXTURE)
    assert release.version == "1.2.0"
    assert release.tag == "v1.2.0"
    assert release.page_url.endswith("/releases/tag/v1.2.0")
    assert "Новый агент" in release.notes
    assert [asset.name for asset in release.assets] == [
        "PyScribe-Setup-v1.2.0.exe", "PyScribe-Source.zip"]
    assert release.assets[0].sha256 == "a" * 64
    chosen = updater.pick_installer_asset(release)
    assert chosen is not None and chosen.name == "PyScribe-Setup-v1.2.0.exe"
    # Uninstallers and non-exe assets are never offered.
    release.assets = [
        updater.ReleaseAsset("unins000.exe", "https://example.invalid/u.exe"),
        updater.ReleaseAsset("PyScribe-Source.zip", "https://example.invalid/s.zip"),
    ]
    assert updater.pick_installer_asset(release) is None


def test_check_for_update_compares_versions():
    release = updater.ReleaseInfo.from_api(API_FIXTURE)
    original = updater.fetch_latest_release
    updater.fetch_latest_release = lambda timeout=15.0: release
    try:
        found, newer = updater.check_for_update("1.1.0")
        assert found.version == "1.2.0" and newer is True
        found, newer = updater.check_for_update("1.2.0")
        assert newer is False
        found, newer = updater.check_for_update("1.3.0")
        assert newer is False
    finally:
        updater.fetch_latest_release = original


def test_installer_command_is_silent_and_restarts():
    command = updater.installer_command(Path(r"C:\Temp\PyScribe-Setup-v1.2.0.exe"))
    assert command[0].endswith("PyScribe-Setup-v1.2.0.exe")
    assert "/SILENT" in command
    assert "/CLOSEAPPLICATIONS" in command
    assert "/RESTARTAPPLICATIONS" in command


def _serve(payload: bytes):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_download_asset_verifies_checksum_and_reports_progress():
    payload = b"PyScribe installer bytes" * 400
    server = _serve(payload)
    try:
        port = server.server_address[1]
        digest = hashlib.sha256(payload).hexdigest()
        asset = updater.ReleaseAsset(
            name="PyScribe-Setup-v1.2.0.exe",
            url=f"http://127.0.0.1:{port}/setup.exe",
            size=len(payload), digest="sha256:" + digest)
        progress = []
        with tempfile.TemporaryDirectory() as td:
            path = updater.download_asset(asset, Path(td),
                                          progress=lambda done, total: progress.append(done))
            assert path.is_file()
            assert path.read_bytes() == payload
            assert progress and progress[-1] == len(payload)
    finally:
        server.shutdown()


def test_download_rejects_corrupted_payload():
    payload = b"not the expected installer" * 10
    server = _serve(payload)
    try:
        port = server.server_address[1]
        asset = updater.ReleaseAsset(
            name="PyScribe-Setup-v1.2.0.exe",
            url=f"http://127.0.0.1:{port}/setup.exe",
            size=len(payload), digest="sha256:" + "0" * 64)
        with tempfile.TemporaryDirectory() as td:
            try:
                updater.download_asset(asset, Path(td))
            except updater.UpdateError as exc:
                assert exc.kind == "checksum"
            else:
                raise AssertionError("corrupted payload was accepted")
            assert not (Path(td) / asset.name).exists()
    finally:
        server.shutdown()


def test_open_external_target_opens_files_and_folders():
    """«Открыть с помощью» opens files in the editor and folders as projects."""
    import tempfile
    from app.application import open_external_target

    class FileManager:
        def __init__(self):
            self.opened = []

        def open_file(self, path):
            self.opened.append(path)

    class ProjectHandler:
        def __init__(self):
            self.calls = []

        def on_project_opened(self, config, choose_analyzers=True):
            self.calls.append((config, choose_analyzers))

    class Window:
        pass

    window = Window()
    window.file_manager = FileManager()
    window.project_handler = ProjectHandler()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        file = root / "app.py"
        file.write_text("x = 1\n", encoding="utf-8")
        assert open_external_target(window, str(file)) == "file"
        assert window.file_manager.opened == [str(file)]
        assert open_external_target(window, str(root)) == "folder"
        config, choose = window.project_handler.calls[0]
        assert config.root_path == str(root)
        assert config.name == root.name
        assert choose is False, "folder open must not show the analyzer dialog"
        assert open_external_target(window, str(root / "missing.txt")) == "missing"


def test_shell_integration_commands_and_entries():
    command = shell_integration.command_line()
    assert '"%1"' in command
    assert "main.py" in command or getattr(sys, "frozen", False)
    assert shell_integration.background_command_line().endswith('"%V"')

    entries = shell_integration.registration_entries()
    keys = {entry["key"] for entry in entries}
    assert shell_integration.APPLICATIONS_KEY in keys
    assert rf"{shell_integration.CLASSES}\*\shell\PyScribe\command" in keys
    assert rf"{shell_integration.CLASSES}\Directory\shell\PyScribe\command" in keys
    assert rf"{shell_integration.CLASSES}\Directory\Background\shell\PyScribe" in keys
    assert rf"{shell_integration.FILE_PROGID_KEY}\shell\open\command" in keys
    assert len(entries) >= len(shell_integration.SUPPORTED_TYPES) + 8
    for entry in entries:
        assert entry["key"].startswith("Software\\Classes")
    assert isinstance(shell_integration.is_registered(), bool)


def test_update_dialog_renders_release_without_network():
    from widgets.UpdateDialog import UpdateDialog
    _qapp()
    release = updater.ReleaseInfo.from_api(API_FIXTURE)
    dialog = UpdateDialog(None, release=release, newer=True)
    try:
        assert "1.2.0" in dialog.title_label.text()
        assert "1.2.0" in dialog.version_label.text()
        assert "Новый агент" in dialog.notes.toPlainText()
        assert dialog.action_btn.text() in ("Скачать и установить", "Обновить из git")
        assert dialog.action_btn.isEnabled()
        assert dialog.page_btn.isVisible() or dialog.page_btn.text() == "Страница релиза"
    finally:
        dialog.deleteLater()


def test_update_dialog_shows_up_to_date_state():
    from widgets.UpdateDialog import UpdateDialog
    _qapp()
    release = updater.ReleaseInfo.from_api(API_FIXTURE)
    dialog = UpdateDialog(None, release=release, newer=False)
    try:
        assert "последняя версия" in dialog.title_label.text()
        assert dialog.action_btn.text() == "Проверить снова"
    finally:
        dialog.deleteLater()


TESTS = [
    ("test_version_helpers", test_version_helpers),
    ("test_release_parsing_and_installer_choice", test_release_parsing_and_installer_choice),
    ("test_check_for_update_compares_versions", test_check_for_update_compares_versions),
    ("test_installer_command_is_silent_and_restarts",
     test_installer_command_is_silent_and_restarts),
    ("test_download_asset_verifies_checksum_and_reports_progress",
     test_download_asset_verifies_checksum_and_reports_progress),
    ("test_download_rejects_corrupted_payload", test_download_rejects_corrupted_payload),
    ("test_shell_integration_commands_and_entries",
     test_shell_integration_commands_and_entries),
    ("test_open_external_target_opens_files_and_folders",
     test_open_external_target_opens_files_and_folders),
    ("test_update_dialog_renders_release_without_network",
     test_update_dialog_renders_release_without_network),
    ("test_update_dialog_shows_up_to_date_state",
     test_update_dialog_shows_up_to_date_state),
]


def main():
    failures = 0
    for name, fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"PASS {name}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
