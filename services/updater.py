"""Update pipeline for PyScribe.

Two update modes are supported:

* **source checkout** (``.git`` next to ``main.py``) — ``git pull --ff-only``
  when the working tree is clean, then the app restarts itself;
* **installed build** (PyInstaller bundle) — download the release installer
  asset, verify its SHA-256 and start it with Inno Setup's silent flags so the
  running app is closed and reopened by the installer.

Everything network-related is blocking and lives here; the dialog runs these
functions off the GUI thread.

Public API
----------
``check_for_update()``        latest release + whether it is newer
``download_asset()``          stream one asset with progress and checksum
``can_update_from_git()``     source checkout is clean and on a tracking branch
``git_update()``              run ``git pull --ff-only``
``pick_installer_asset()``    choose ``PyScribe-Setup-*.exe`` from a release
``restart_application()``     relaunch this PyScribe instance
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.app_version import app_root, current_version, is_newer
from core.subprocess_utils import run_hidden

__all__ = [
    "GITHUB_REPO",
    "RELEASES_PAGE",
    "ReleaseAsset",
    "ReleaseInfo",
    "UpdateError",
    "check_for_update",
    "download_asset",
    "installer_command",
    "launch_installer",
    "pick_installer_asset",
    "can_update_from_git",
    "git_update",
    "git_worktree_clean",
    "restart_application",
]

GITHUB_REPO = "stand4r/PyScribe"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
_UA = "PyScribe-Updater/1.0 (+%s)" % RELEASES_PAGE
_DOWNLOAD_CHUNK = 64 * 1024


class UpdateError(RuntimeError):
    """A user-readable updater failure."""

    def __init__(self, message: str, kind: str = "generic"):
        super().__init__(message)
        self.kind = kind


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    digest: str = ""

    @property
    def sha256(self) -> str:
        value = (self.digest or "").strip().lower()
        if value.startswith("sha256:"):
            value = value.split(":", 1)[1]
        return value


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    name: str
    notes: str
    page_url: str
    published_at: str = ""
    assets: List[ReleaseAsset] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "ReleaseInfo":
        from core.app_version import normalize_version
        tag = str(data.get("tag_name") or "")
        assets = []
        for item in data.get("assets") or []:
            url = str(item.get("browser_download_url") or "")
            name = str(item.get("name") or "")
            if not url or not name:
                continue
            assets.append(ReleaseAsset(
                name=name,
                url=url,
                size=int(item.get("size") or 0),
                digest=str(item.get("digest") or ""),
            ))
        return cls(
            version=normalize_version(tag or data.get("name") or ""),
            tag=tag,
            name=str(data.get("name") or tag or "PyScribe"),
            notes=str(data.get("body") or ""),
            page_url=str(data.get("html_url") or RELEASES_PAGE),
            published_at=str(data.get("published_at") or ""),
            assets=assets,
        )


def fetch_latest_release(timeout: float = 15.0) -> ReleaseInfo:
    """GET the latest published release; raises :class:`UpdateError`."""
    request = urllib.request.Request(
        API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _UA},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise UpdateError("GitHub ограничил частоту проверок. Попробуйте позже.",
                              kind="rate_limit") from exc
        if exc.code == 404:
            raise UpdateError("Релизы PyScribe не найдены на GitHub.", kind="not_found") from exc
        raise UpdateError(f"GitHub ответил кодом {exc.code}.", kind="http") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError("Не удалось связаться с GitHub. Проверьте интернет.",
                          kind="network") from exc
    try:
        data = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError("GitHub вернул неожиданный ответ.", kind="protocol") from exc
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise UpdateError("В ответе GitHub нет номера версии.", kind="protocol")
    return ReleaseInfo.from_api(data)


def check_for_update(current: Optional[str] = None,
                     timeout: float = 15.0) -> Tuple[ReleaseInfo, bool]:
    """Return ``(release, newer)`` for the latest GitHub release."""
    installed = str(current or current_version())
    release = fetch_latest_release(timeout=timeout)
    return release, is_newer(release.version, installed)


def pick_installer_asset(release: ReleaseInfo) -> Optional[ReleaseAsset]:
    """Prefer the Inno Setup installer, then any other exe (never uninstallers)."""
    candidates = [asset for asset in release.assets
                  if asset.name.lower().endswith(".exe")
                  and "unins" not in asset.name.lower()]
    if not candidates:
        return None
    setup = [asset for asset in candidates if "setup" in asset.name.lower()]
    return (setup or candidates)[0]


def download_asset(asset: ReleaseAsset, destination: Optional[Path] = None,
                   progress: Optional[Callable[[int, int], None]] = None,
                   timeout: float = 60.0) -> Path:
    """Stream *asset* to disk, verify its SHA-256 and return the path."""
    folder = Path(destination) if destination else Path(tempfile.gettempdir()) / "PyScribe-updates"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / asset.name
    request = urllib.request.Request(asset.url, headers={"User-Agent": _UA})
    digest = hashlib.sha256()
    downloaded = 0
    total = int(asset.size or 0)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(target, "wb") as handle:
            while True:
                chunk = response.read(_DOWNLOAD_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, total or downloaded)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise UpdateError("Не удалось скачать обновление. Проверьте соединение.",
                          kind="download") from exc

    expected = asset.sha256
    if expected and digest.hexdigest().lower() != expected:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise UpdateError("Скачанный файл повреждён (не совпала контрольная сумма).",
                          kind="checksum")
    return target


def installer_command(path: Path) -> List[str]:
    """Inno Setup flags: install silently, close and restart PyScribe."""
    return [str(path), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS",
            "/NORESTART", "/NOCANCEL"]


def launch_installer(path: Path) -> None:
    """Start the installer detached; the caller is expected to quit the app."""
    from core.subprocess_utils import popen_detached
    popen_detached(installer_command(path))


# ---------------------------------------------------------------------------
# Source checkout mode
# ---------------------------------------------------------------------------
def _git_executable() -> Optional[str]:
    return shutil.which("git")


def git_worktree_clean() -> bool:
    """True when ``git status --porcelain`` is empty (no local edits)."""
    git = _git_executable()
    if git is None:
        return False
    try:
        result = run_hidden([git, "status", "--porcelain"], cwd=str(app_root()),
                            timeout=30, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and not (result.stdout or "").strip()


def can_update_from_git() -> bool:
    """A source checkout can update itself when git is available and clean."""
    if getattr(sys, "frozen", False):
        return False
    if not (app_root() / ".git").exists():
        return False
    if _git_executable() is None:
        return False
    return git_worktree_clean()


def git_update(timeout: float = 180.0) -> str:
    """``git pull --ff-only`` in the project root; returns combined output."""
    git = _git_executable()
    if git is None:
        raise UpdateError("Git не найден в системе.", kind="git")
    try:
        result = run_hidden([git, "pull", "--ff-only"], cwd=str(app_root()),
                            timeout=timeout, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError("Не удалось запустить git.", kind="git") from exc
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        raise UpdateError(output or "git pull завершился с ошибкой.", kind="git")
    return output or "Уже обновлено."


def restart_application() -> None:
    """Relaunch PyScribe (source checkout or frozen build)."""
    from PyQt5 import QtCore
    if getattr(sys, "frozen", False):
        QtCore.QProcess.startDetached(sys.executable, [])
        return
    script = app_root() / "main.py"
    QtCore.QProcess.startDetached(sys.executable, [str(script)])


def release_notes_lines(release: ReleaseInfo, limit: int = 4000) -> str:
    """Release notes safe for a QTextBrowser (plain text)."""
    text = (release.notes or "").strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "\n…"
    return text or "Описание изменений не указано."
