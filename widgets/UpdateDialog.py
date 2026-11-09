"""Update dialog: check GitHub releases, download, install or git-pull.

The network work runs on ``QThread`` objects; the dialog only renders state.
Two paths are supported (see :mod:`services.updater`):

* source checkout → ``git pull --ff-only`` then restart;
* installed build → download ``PyScribe-Setup-*.exe``, verify SHA-256, start the
  installer with silent flags (it closes and restarts the running app).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from core.app_version import current_version
from services import updater

__all__ = ["UpdateDialog"]


class _CheckThread(QtCore.QThread):
    done = QtCore.pyqtSignal(object, bool)
    failed = QtCore.pyqtSignal(str)

    def run(self):
        try:
            release, newer = updater.check_for_update(current_version())
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.failed.emit(str(exc))
            return
        self.done.emit(release, newer)


class _DownloadThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int)
    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, asset: updater.ReleaseAsset, parent=None):
        super().__init__(parent)
        self._asset = asset

    def run(self):
        try:
            path = updater.download_asset(
                self._asset,
                progress=lambda done, total: self.progress.emit(int(done), int(total)))
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.failed.emit(str(exc))
            return
        self.done.emit(str(path))


class _GitThread(QtCore.QThread):
    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def run(self):
        try:
            output = updater.git_update()
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.failed.emit(str(exc))
            return
        self.done.emit(output)


class UpdateDialog(QtWidgets.QDialog):
    """«Доступно обновление» with release notes, progress and install buttons."""

    def __init__(self, parent=None, auto: bool = False,
                 release: Optional[updater.ReleaseInfo] = None,
                 newer: Optional[bool] = None):
        super().__init__(parent)
        self.setWindowTitle("Обновление PyScribe")
        self.setWindowModality(QtCore.Qt.NonModal if auto else QtCore.Qt.WindowModal)
        self.setMinimumWidth(580)
        self.setObjectName("updateDialog")
        self._auto = bool(auto)
        self._release = release
        self._newer = newer
        self._installer_path: Optional[Path] = None
        self._threads: list = []
        self._alive = True
        self._check_token = 0
        self._current = current_version()
        self._build()
        if release is None:
            self._start_check()
        else:
            self._render_release()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(14)
        icon_label = QtWidgets.QLabel()
        icon = _app_icon()
        if icon is not None:
            icon_label.setPixmap(icon.pixmap(44, 44))
        icon_label.setFixedSize(44, 44)
        header.addWidget(icon_label)
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = QtWidgets.QLabel("Проверка обновлений")
        self.title_label.setObjectName("updateTitle")
        self.version_label = QtWidgets.QLabel(f"Установлена версия v{self._current}")
        self.version_label.setObjectName("updateVersion")
        titles.addWidget(self.title_label)
        titles.addWidget(self.version_label)
        header.addLayout(titles, 1)
        root.addLayout(header)

        self.notes = QtWidgets.QTextBrowser()
        self.notes.setObjectName("updateNotes")
        self.notes.setReadOnly(True)
        self.notes.setOpenExternalLinks(True)
        self.notes.setMinimumHeight(170)
        self.notes.setMaximumHeight(230)
        root.addWidget(self.notes, 1)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("updateStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(8)
        self.page_btn = QtWidgets.QPushButton("Страница релиза")
        self.page_btn.clicked.connect(self._open_release_page)
        self.page_btn.setVisible(False)
        buttons.addWidget(self.page_btn)
        buttons.addStretch(1)
        self.retry_btn = QtWidgets.QPushButton("Повторить")
        self.retry_btn.clicked.connect(self._start_check)
        self.retry_btn.setVisible(False)
        buttons.addWidget(self.retry_btn)
        self.later_btn = QtWidgets.QPushButton("Позже")
        self.later_btn.clicked.connect(self._close_later)
        buttons.addWidget(self.later_btn)
        self.action_btn = QtWidgets.QPushButton("Обновить")
        self.action_btn.setObjectName("updateAction")
        self.action_btn.setDefault(True)
        self.action_btn.setEnabled(False)
        self.action_btn.clicked.connect(self._on_action)
        self._style_action_button()
        buttons.addWidget(self.action_btn)
        root.addLayout(buttons)

    def _style_action_button(self):
        """Primary button follows the user's accent colour (QSS tokens may vary)."""
        try:
            from utils.settings_manager import get_settings_manager
            accent = str(get_settings_manager().get_setting("accent_color", "#5EA6FF")
                         or "#5EA6FF")
        except Exception:  # noqa: BLE001
            accent = "#5EA6FF"
        self.action_btn.setStyleSheet(
            "QPushButton { background:%s; color:#FFFFFF; border:none;"
            " border-radius:6px; padding:7px 16px; font-weight:600; }"
            "QPushButton:hover { background:%s; }"
            "QPushButton:disabled { background:#3A3A3E; color:#8B949E; }" % (accent, accent))

    def _set_busy(self, busy: bool):
        self.action_btn.setEnabled(not busy)
        self.page_btn.setEnabled(not busy)
        self.retry_btn.setEnabled(not busy)

    def _status(self, text: str, error: bool = False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color:#E58A8A;" if error else "color:#8B949E;")

    # ------------------------------------------------------------------
    # Checking
    # ------------------------------------------------------------------
    def _start_check(self):
        if not self._alive:
            return
        self._check_token += 1
        token = self._check_token
        self.title_label.setText("Проверка обновлений")
        self.version_label.setText(f"Установлена версия v{self._current}")
        self._status("Соединяюсь с GitHub…")
        self.retry_btn.setVisible(False)
        self.progress.setVisible(False)
        self.action_btn.setText("Обновить")
        self.action_btn.setEnabled(False)
        self._set_busy(True)
        self.notes.setPlainText("")
        thread = _CheckThread(self)
        thread.done.connect(
            lambda release, newer, t=token: self._on_checked(release, newer, t))
        thread.failed.connect(lambda message, t=token: self._on_check_failed(message, t))
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @QtCore.pyqtSlot(object, bool)
    def _on_checked(self, release, newer: bool, token: Optional[int] = None):
        if not self._alive or (token is not None and token != self._check_token):
            return
        self._release = release
        self._newer = bool(newer)
        self._remember_check_time()
        self._render_release()
        if self._auto:
            if not newer:
                self.close()
                return
            skipped = _skipped_version()
            if skipped and _same_version(skipped, release.version):
                self.close()
                return
            self._notify_window(f"Доступно обновление PyScribe v{release.version} — "
                                "Справка → Проверить обновления")
            self.show()

    def _on_check_failed(self, message: str, token: Optional[int] = None):
        if not self._alive or (token is not None and token != self._check_token):
            return
        self._set_busy(False)
        self.title_label.setText("Не удалось проверить обновления")
        self._status(message, error=True)
        self.retry_btn.setVisible(True)
        self.page_btn.setVisible(True)
        self.later_btn.setText("Закрыть")
        self.action_btn.setEnabled(False)
        if self._auto:
            self.close()

    def _render_release(self):
        release = self._release
        if release is None:
            return
        self.later_btn.setText("Позже")
        self._set_busy(False)
        self.retry_btn.setVisible(False)
        self.page_btn.setVisible(True)
        self.notes.setPlainText(updater.release_notes_lines(release))
        if self._newer:
            self.title_label.setText(f"Доступно обновление v{release.version}")
            self.version_label.setText(
                f"Установлена v{self._current}  ·  доступна v{release.version}")
            self._status("Что нового — ниже. Обновление можно установить сейчас.")
            if updater.can_update_from_git():
                self.action_btn.setText("Обновить из git")
            elif updater.pick_installer_asset(release) is not None:
                self.action_btn.setText("Скачать и установить")
            else:
                self.action_btn.setText("Открыть страницу релиза")
            self.action_btn.setEnabled(True)
        else:
            self.title_label.setText("У вас последняя версия")
            self.version_label.setText(f"Установлена v{self._current}")
            self._status("Новых релизов на GitHub нет — обновление не требуется.")
            self.action_btn.setText("Проверить снова")
            self.action_btn.setEnabled(True)
            self.later_btn.setText("Закрыть")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_action(self):
        if not self._newer:
            self._start_check()
            return
        if updater.can_update_from_git():
            self._start_git_update()
            return
        asset = updater.pick_installer_asset(self._release) if self._release else None
        if asset is None:
            self._open_release_page()
            self._status("Готовый установщик не найден — открываю страницу релиза.")
            return
        self._start_download(asset)

    def _save_work(self):
        window = self.parent()
        for name in ("action_save_all_files", "save_all_files"):
            handler = getattr(window, name, None)
            if callable(handler):
                try:
                    handler()
                except Exception:  # noqa: BLE001 - never block the update
                    pass
                return

    def _start_git_update(self):
        self._set_busy(True)
        self._status("Обновляю проект из git…")
        self.progress.setVisible(False)
        thread = _GitThread(self)
        thread.done.connect(self._on_git_done)
        thread.failed.connect(self._on_git_failed)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @QtCore.pyqtSlot(str)
    def _on_git_done(self, output: str):
        if not self._alive:
            return
        self._set_busy(False)
        self.title_label.setText("Обновление загружено")
        self._status("Перезапустите PyScribe, чтобы применить обновление.")
        self.action_btn.setText("Перезапустить")
        self.action_btn.setEnabled(True)
        try:
            self.action_btn.clicked.disconnect()
        except TypeError:
            pass
        self.action_btn.clicked.connect(self._restart)
        self.later_btn.setText("Закрыть")

    def _on_git_failed(self, message: str):
        if not self._alive:
            return
        self._set_busy(False)
        self._status(message, error=True)
        self.action_btn.setText("Открыть страницу релиза")
        self.action_btn.setEnabled(True)
        try:
            self.action_btn.clicked.disconnect()
        except TypeError:
            pass
        self.action_btn.clicked.connect(self._open_release_page)

    def _start_download(self, asset: updater.ReleaseAsset):
        self._save_work()
        self._set_busy(True)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._status(f"Скачиваю {asset.name}…")
        thread = _DownloadThread(asset, self)
        thread.progress.connect(self._on_progress)
        thread.done.connect(self._on_downloaded)
        thread.failed.connect(self._on_download_failed)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @QtCore.pyqtSlot(int, int)
    def _on_progress(self, done: int, total: int):
        if not self._alive:
            return
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(done * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    @QtCore.pyqtSlot(str)
    def _on_downloaded(self, path: str):
        if not self._alive:
            return
        self._installer_path = Path(path)
        self.progress.setVisible(False)
        self._set_busy(False)
        self.title_label.setText("Обновление скачано")
        self._status("Файл проверен. Установить и перезапустить PyScribe?")
        self.action_btn.setText("Установить и перезапустить")
        self.action_btn.setEnabled(True)
        try:
            self.action_btn.clicked.disconnect()
        except TypeError:
            pass
        self.action_btn.clicked.connect(self._install)

    def _on_download_failed(self, message: str):
        if not self._alive:
            return
        self.progress.setVisible(False)
        self._set_busy(False)
        self._status(message, error=True)
        self.action_btn.setText("Повторить скачивание")
        self.action_btn.setEnabled(True)
        try:
            self.action_btn.clicked.disconnect()
        except TypeError:
            pass
        self.action_btn.clicked.connect(self._on_action)

    def _install(self):
        if self._installer_path is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Установка обновления",
            "PyScribe будет закрыт, установщик обновит файлы и запустит "
            "приложение снова.\n\nПродолжить?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if answer != QtWidgets.QMessageBox.Yes:
            return
        self._save_work()
        try:
            updater.launch_installer(self._installer_path)
        except OSError as exc:
            self._status(f"Не удалось запустить установщик: {exc}", error=True)
            return
        # Do NOT quit here: the installer receives /CLOSEAPPLICATIONS and will
        # close PyScribe itself, then /RESTARTAPPLICATIONS brings it back after
        # the files are replaced. Quitting first would leave nothing to restart.
        self._status("Установщик запущен. PyScribe закроется и откроется снова.")
        self.action_btn.setEnabled(False)

    def _restart(self):
        self._save_work()
        updater.restart_application()
        QtCore.QTimer.singleShot(200, QtWidgets.QApplication.quit)

    def _open_release_page(self):
        url = self._release.page_url if self._release else updater.RELEASES_PAGE
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _close_later(self):
        self._remember_skipped()
        self.close()

    # ------------------------------------------------------------------
    # Settings / lifecycle
    # ------------------------------------------------------------------
    def _remember_check_time(self):
        try:
            from utils.settings_manager import get_settings_manager
            manager = get_settings_manager()
            manager.settings["update_last_check"] = QtCore.QDateTime.currentDateTimeUtc() \
                .toString(QtCore.Qt.ISODate)
            manager.save_settings()
        except Exception:  # noqa: BLE001 - settings are best effort
            pass

    def _remember_skipped(self):
        if not (self._newer and self._release):
            return
        try:
            from utils.settings_manager import get_settings_manager
            manager = get_settings_manager()
            manager.settings["update_skipped_version"] = self._release.version
            manager.save_settings()
        except Exception:  # noqa: BLE001
            pass

    def _notify_window(self, text: str):
        window = self.parent()
        status = getattr(window, "status_bar", None)
        if status is not None:
            try:
                status.showMessage(text, 20000)
            except RuntimeError:
                pass

    def closeEvent(self, event):
        self._alive = False
        super().closeEvent(event)


def _app_icon() -> Optional[QtGui.QIcon]:
    path = Path(__file__).resolve().parent.parent / "src" / "icon_app_128.png"
    if not path.exists():
        path = path.with_name("icon_app.png")
    if path.exists():
        return QtGui.QIcon(str(path))
    return None


def _skipped_version() -> str:
    try:
        from utils.settings_manager import get_settings_manager
        return str(get_settings_manager().get_setting("update_skipped_version", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _same_version(left: str, right: str) -> bool:
    from core.app_version import version_tuple
    return version_tuple(left) == version_tuple(right)
