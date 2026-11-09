"""Clean Source Control workbench for Git repositories with GitHub Authentication."""
import os
import re
import subprocess
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices

from services.github_service import GitHubService
from core.subprocess_utils import run_hidden
from design.icons import codicon_icon


class GitHubLoginDialog(QtWidgets.QDialog):
    """GitHub Personal Access Token authentication dialog."""
    authenticated = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход в GitHub — PyScribe")
        self.setMinimumWidth(520)
        self.resize(600, 540)
        self.github_service = GitHubService.get_instance()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Вход в аккаунт GitHub")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        info = QtWidgets.QLabel(
            "Для отправки кода (Push), получения обновлений (Pull), клонирования приватных репозиториев "
            "и работы с проектами необходима авторизация через GitHub Personal Access Token (PAT)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #CCCCCC; font-size: 13px; line-height: 1.4;")
        layout.addWidget(info)

        guide_box = QtWidgets.QFrame()
        guide_box.setObjectName("githubTokenGuide")
        gl = QtWidgets.QVBoxLayout(guide_box)
        gl.setSpacing(6)
        g_title = QtWidgets.QLabel("Как получить токен за 1 минуту:")
        g_title.setStyleSheet("font-weight: bold; color: #58A6FF; font-size: 13px;")
        gl.addWidget(g_title)
        
        step1 = QtWidgets.QLabel("1. Нажмите кнопку ниже — откроется страница создания токена на GitHub.")
        step1.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        step1.setWordWrap(True)
        gl.addWidget(step1)
        step2 = QtWidgets.QLabel("2. Выберите срок (Expiration) и убедитесь, что включена галочка 'repo'.")
        step2.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        step2.setWordWrap(True)
        gl.addWidget(step2)
        step3 = QtWidgets.QLabel("3. Нажмите 'Generate token' внизу страницы, скопируйте его и вставьте сюда.")
        step3.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        step3.setWordWrap(True)
        gl.addWidget(step3)

        open_browser_btn = QtWidgets.QPushButton("Создать токен на GitHub ↗")
        open_browser_btn.setCursor(QtCore.Qt.PointingHandCursor)
        open_browser_btn.setStyleSheet("background: #238636; color: #FFFFFF; font-weight: bold; padding: 7px 14px; border-radius: 4px;")
        open_browser_btn.clicked.connect(self._open_token_page)
        gl.addWidget(open_browser_btn)
        layout.addWidget(guide_box)

        form = QtWidgets.QFormLayout()
        self.token_edit = QtWidgets.QLineEdit()
        self.token_edit.setPlaceholderText("ghp_... или github_pat_...")
        self.token_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.token_edit.setStyleSheet("padding: 6px 10px; font-size: 13px;")
        
        token_row = QtWidgets.QHBoxLayout()
        token_row.addWidget(self.token_edit, 1)
        self.show_token_btn = QtWidgets.QToolButton()
        self.show_token_btn.setText("👁")
        self.show_token_btn.setToolTip("Показать/скрыть токен")
        self.show_token_btn.clicked.connect(self._toggle_echo_mode)
        token_row.addWidget(self.show_token_btn)
        form.addRow("Токен (PAT):", token_row)
        layout.addLayout(form)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.status_label)

        buttons = QtWidgets.QDialogButtonBox()
        self.cancel_btn = buttons.addButton("Отмена", QtWidgets.QDialogButtonBox.RejectRole)
        self.login_btn = buttons.addButton("Войти в аккаунт", QtWidgets.QDialogButtonBox.AcceptRole)
        self.login_btn.setStyleSheet("background: #0078D4; color: white; font-weight: bold; padding: 6px 16px;")
        self.cancel_btn.clicked.connect(self.reject)
        self.login_btn.clicked.connect(self._do_login)
        layout.addWidget(buttons)

    def _toggle_echo_mode(self):
        if self.token_edit.echoMode() == QtWidgets.QLineEdit.Password:
            self.token_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.token_edit.setEchoMode(QtWidgets.QLineEdit.Password)

    def _open_token_page(self):
        url = "https://github.com/settings/tokens/new?scopes=repo,user&description=PyScribe%20IDE"
        QDesktopServices.openUrl(QUrl(url))

    def _do_login(self):
        token = self.token_edit.text().strip()
        if not token:
            self.status_label.setText("Пожалуйста, вставьте скопированный токен.")
            self.status_label.setStyleSheet("color: #F85149; font-size: 12px;")
            return

        self.login_btn.setEnabled(False)
        self.status_label.setText("Проверка токена через GitHub API…")
        self.status_label.setStyleSheet("color: #58A6FF; font-size: 12px;")
        QtWidgets.QApplication.processEvents()

        ok, user_info, msg = self.github_service.authenticate_with_token(token)
        self.login_btn.setEnabled(True)
        if ok and user_info:
            self.status_label.setText(f"✓ Успешно! Подключен аккаунт @{user_info['login']}")
            self.status_label.setStyleSheet("color: #3FB950; font-weight: bold; font-size: 13px;")
            self.authenticated.emit(user_info)
            QtCore.QTimer.singleShot(700, self.accept)
        else:
            self.status_label.setText(f"✗ Ошибка: {msg}")
            self.status_label.setStyleSheet("color: #F85149; font-size: 12px;")


class GitHubReposDialog(QtWidgets.QDialog):
    """View and clone user's repositories from GitHub."""
    repo_selected = QtCore.pyqtSignal(str, str)  # clone_url, repo_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мои репозитории на GitHub")
        self.resize(640, 480)
        self.github_service = GitHubService.get_instance()
        self.repos = []
        self._build()
        self._load_repos()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Ваши репозитории на GitHub")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QtWidgets.QToolButton()
        refresh_btn.setText("↻")
        refresh_btn.setToolTip("Обновить список")
        refresh_btn.clicked.connect(self._load_repos)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Поиск репозитория по названию…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_repos)
        layout.addWidget(self.search_edit)

        self.repo_list = QtWidgets.QListWidget()
        self.repo_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.repo_list, 1)

        self.status_label = QtWidgets.QLabel("Загрузка…")
        self.status_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(self.status_label)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QtWidgets.QPushButton("Закрыть")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        self.clone_btn = QtWidgets.QPushButton("Клонировать выбранный")
        self.clone_btn.setStyleSheet("background: #238636; color: white; font-weight: bold; padding: 6px 14px;")
        self.clone_btn.clicked.connect(self._clone_selected)
        buttons.addWidget(self.clone_btn)
        layout.addLayout(buttons)

    def _load_repos(self):
        self.status_label.setText("Загрузка репозиториев с GitHub…")
        QtWidgets.QApplication.processEvents()
        ok, repos, msg = self.github_service.list_user_repos()
        if ok:
            self.repos = repos
            self._filter_repos(self.search_edit.text())
            self.status_label.setText(f"Найдено репозиториев: {len(repos)}")
        else:
            self.status_label.setText(f"Ошибка: {msg}")

    def _filter_repos(self, text):
        query = text.strip().lower()
        self.repo_list.clear()
        for r in self.repos:
            if not query or query in r["full_name"].lower() or query in r["description"].lower():
                priv = " [Private]" if r["private"] else ""
                item = QtWidgets.QListWidgetItem(f"📦 {r['full_name']}{priv}\n   {r['description']} · Обновлен: {r['updated_at']}")
                item.setData(QtCore.Qt.UserRole, r)
                self.repo_list.addItem(item)

    def _clone_selected(self):
        item = self.repo_list.currentItem()
        if not item:
            return
        repo_data = item.data(QtCore.Qt.UserRole)
        if repo_data:
            self.repo_selected.emit(repo_data["clone_url"], repo_data["name"])
            self.accept()

    def _on_item_double_clicked(self, item):
        repo_data = item.data(QtCore.Qt.UserRole)
        if repo_data:
            self.repo_selected.emit(repo_data["clone_url"], repo_data["name"])
            self.accept()


class CreateGitHubRepoDialog(QtWidgets.QDialog):
    """Dialog to create a new repo on GitHub and push the current project."""
    repo_created = QtCore.pyqtSignal(str)  # clone_url

    def __init__(self, default_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Опубликовать проект на GitHub")
        self.setMinimumWidth(480)
        self.default_name = default_name
        self.github_service = GitHubService.get_instance()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Создать репозиторий на GitHub")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit(self.default_name)
        self.name_edit.setPlaceholderText("Имя репозитория (например, my-lab-work)")
        form.addRow("Название:", self.name_edit)

        self.desc_edit = QtWidgets.QLineEdit()
        self.desc_edit.setPlaceholderText("Краткое описание проекта (необязательно)")
        form.addRow("Описание:", self.desc_edit)

        self.private_check = QtWidgets.QCheckBox("Сделать приватным (доступен только вам)")
        form.addRow("", self.private_check)
        layout.addLayout(form)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.status_label)

        buttons = QtWidgets.QDialogButtonBox()
        cancel_btn = buttons.addButton("Отмена", QtWidgets.QDialogButtonBox.RejectRole)
        self.create_btn = buttons.addButton("Опубликовать на GitHub", QtWidgets.QDialogButtonBox.AcceptRole)
        self.create_btn.setStyleSheet("background: #238636; color: white; font-weight: bold; padding: 6px 14px;")
        cancel_btn.clicked.connect(self.reject)
        self.create_btn.clicked.connect(self._create_repo)
        layout.addWidget(buttons)

    def _create_repo(self):
        name = self.name_edit.text().strip()
        if not name:
            self.status_label.setText("Введите название репозитория.")
            self.status_label.setStyleSheet("color: #F85149;")
            return

        self.create_btn.setEnabled(False)
        self.status_label.setText("Создание репозитория на GitHub…")
        self.status_label.setStyleSheet("color: #58A6FF;")
        QtWidgets.QApplication.processEvents()

        ok, data, msg = self.github_service.create_repository(
            name=name,
            description=self.desc_edit.text().strip(),
            is_private=self.private_check.isChecked()
        )
        self.create_btn.setEnabled(True)
        if ok and data:
            clone_url = data.get("clone_url", "")
            self.status_label.setText("✓ Репозиторий успешно создан!")
            self.status_label.setStyleSheet("color: #3FB950;")
            self.repo_created.emit(clone_url)
            QtCore.QTimer.singleShot(500, self.accept)
        else:
            self.status_label.setText(f"Ошибка: {msg}")
            self.status_label.setStyleSheet("color: #F85149;")


class CloneGitHubDialog(QtWidgets.QDialog):
    """Clone a GitHub repository with support for authentication and auto-fill."""
    cloned = QtCore.pyqtSignal(str)

    def __init__(self, default_parent_dir=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Клонирование репозитория")
        self.setMinimumWidth(560)
        self.cloned_path = None
        self._default_parent = default_parent_dir or str(Path.home() / "PyScribeProjects")
        self.github_service = GitHubService.get_instance()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Клонирование репозитория")
        title.setObjectName("dialogTitle")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Введите URL GitHub или выберите из своих репозиториев.")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Quick button if logged in to pick from user's repos
        if self.github_service.is_authenticated():
            pick_box = QtWidgets.QHBoxLayout()
            pick_btn = QtWidgets.QPushButton("📋 Выбрать из моих репозиториев GitHub…")
            pick_btn.setStyleSheet("background: #21262D; border: 1px solid #30363D; color: #58A6FF; padding: 6px 12px; font-weight: bold; border-radius: 4px;")
            pick_btn.clicked.connect(self._open_repo_picker)
            pick_box.addWidget(pick_btn)
            pick_box.addStretch()
            layout.addLayout(pick_box)

        form = QtWidgets.QFormLayout()
        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/owner/repository или owner/repo")
        self.url_edit.textChanged.connect(self._auto_fill_name)
        form.addRow("Репозиторий:", self.url_edit)

        dest_row = QtWidgets.QHBoxLayout()
        self.dest_edit = QtWidgets.QLineEdit(self._default_parent)
        browse = QtWidgets.QPushButton("Обзор…")
        browse.clicked.connect(self._browse_dest)
        dest_row.addWidget(self.dest_edit, 1)
        dest_row.addWidget(browse)
        form.addRow("Папка назначения:", dest_row)

        self.name_edit = QtWidgets.QLineEdit()
        self._user_edited_name = False
        self.name_edit.textEdited.connect(lambda: setattr(self, "_user_edited_name", True))
        form.addRow("Имя папки:", self.name_edit)
        layout.addLayout(form)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("gitStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QtWidgets.QDialogButtonBox()
        cancel = buttons.addButton("Отмена", QtWidgets.QDialogButtonBox.RejectRole)
        self.clone_btn = buttons.addButton("Клонировать и открыть", QtWidgets.QDialogButtonBox.AcceptRole)
        self.clone_btn.setStyleSheet("background: #238636; color: white; font-weight: bold; padding: 6px 14px;")
        cancel.clicked.connect(self.reject)
        self.clone_btn.clicked.connect(self._start_clone)
        layout.addWidget(buttons)

    def _open_repo_picker(self):
        dialog = GitHubReposDialog(self)
        dialog.repo_selected.connect(self._on_repo_picked)
        dialog.exec_()

    def _on_repo_picked(self, clone_url: str, repo_name: str):
        self.url_edit.setText(clone_url)
        self.name_edit.setText(repo_name)
        self._user_edited_name = True

    def _auto_fill_name(self, text):
        clean = text.strip().rstrip("/")
        if clean.endswith(".git"):
            clean = clean[:-4]
        if "/" in clean and not self._user_edited_name:
            self.name_edit.setText(clean.split("/")[-1])

    def _browse_dest(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите родительскую папку", self.dest_edit.text())
        if folder:
            self.dest_edit.setText(folder)

    def _start_clone(self):
        raw = self.url_edit.text().strip()
        if not raw:
            self.status_label.setText("Введите адрес репозитория.")
            return

        clone_url = raw if re.match(r"^(https?|git@)", raw) else f"https://github.com/{raw}.git"
        parent = Path(self.dest_edit.text().strip() or self._default_parent)
        folder_name = self.name_edit.text().strip() or "repository"
        target = parent / folder_name

        parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and any(target.iterdir()):
            self.status_label.setText(f"Папка {target.name} уже существует и не пуста.")
            return

        self.clone_btn.setEnabled(False)
        self.status_label.setText("Клонирование репозитория…")
        QtWidgets.QApplication.processEvents()

        # Inject auth token if available so private repos work seamlessly
        actual_url = self.github_service.inject_token_into_url(clone_url)
        env = self.github_service.get_auth_git_env()

        try:
            result = run_hidden(
                ["git", "clone", actual_url, str(target)],
                cwd=str(parent),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                timeout=180
            )
            if result.returncode != 0:
                out = result.stdout.strip()
                # Clean any exposed token from error output
                token = self.github_service.get_token()
                if token:
                    out = out.replace(token, "***")
                self.status_label.setText(out or "Ошибка клонирования (Git clone failed)")
                self.clone_btn.setEnabled(True)
                return
        except (OSError, subprocess.SubprocessError) as exc:
            self.status_label.setText(str(exc))
            self.clone_btn.setEnabled(True)
            return

        self.cloned_path = str(target.resolve())
        self.cloned.emit(self.cloned_path)
        self.accept()


class GitPanel(QtWidgets.QFrame):
    """Source Control panel with full GitHub Authentication, Commit, Push, and Pull support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gitPanel")
        self.root_path = None
        self.current_branch = "HEAD"
        self.github_repo = None
        self.github_service = GitHubService.get_instance()
        self._needs_refresh = False
        # State read by _collect_state() on the worker thread.
        self._state_busy = False
        self._state_pending = False
        self._action_busy = False
        self._branches: list = []
        self._remote_url = ""
        self._build()

    def _button(self, text, handler=None, object_name=None):
        button = QtWidgets.QPushButton(text)
        if object_name:
            button.setObjectName(object_name)
        if handler:
            button.clicked.connect(handler)
        return button

    def _build(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("gitScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        content.setObjectName("gitContent")
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_auth_banner())
        layout.addWidget(self._build_github_card())
        layout.addWidget(self._build_publish_frame())
        layout.addLayout(self._build_sync_row())
        layout.addWidget(self._build_not_repo_frame())
        self._build_file_list(layout)
        footer = QtWidgets.QWidget()
        footer.setObjectName("gitFooter")
        footer_layout = QtWidgets.QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 6, 10, 10)
        footer_layout.setSpacing(6)
        self._build_commit_controls(footer_layout)
        outer.addWidget(footer)
        self._update_auth_ui()

    def _build_header(self) -> QtWidgets.QHBoxLayout:
        """VS Code-style section header: title on the left, 24px icon actions right."""
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)

        self.branch_btn = QtWidgets.QToolButton()
        self.branch_btn.setText("Нет репозитория")
        self.branch_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.branch_btn.setObjectName("gitBranchButton")
        self.branch_btn.setStyleSheet(
            "QToolButton { border: none; background: transparent; color: #CCCCCC;"
            " padding: 0 4px; font-size: 12px; } QToolButton:hover { background: #2A2D2E; border-radius: 2px; }"
        )
        self.branch_btn.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        header.addWidget(self.branch_btn, 1)
        header.addStretch()

        self.refresh_btn = QtWidgets.QToolButton()
        self.refresh_btn.setIcon(codicon_icon("refresh", 20, "#CCCCCC"))
        self.refresh_btn.setIconSize(QtCore.QSize(20, 20))
        self.refresh_btn.setToolTip("Обновить состояние Git")
        self.refresh_btn.setObjectName("gitAction")
        self.refresh_btn.clicked.connect(lambda: self.refresh())
        header.addWidget(self.refresh_btn)

        self.more_btn = QtWidgets.QToolButton()
        self.more_btn.setIcon(codicon_icon("settings-gear", 20, "#CCCCCC"))
        self.more_btn.setIconSize(QtCore.QSize(20, 20))
        self.more_btn.setText("")
        self.more_btn.setToolTip("Дополнительно")
        self.more_btn.setObjectName("gitAction")
        self.more_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.more_btn.setMenu(self._build_actions_menu())
        header.addWidget(self.more_btn)
        return header

    def _build_actions_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        for text, callback in (
            ("Получить изменения (Pull)", self.git_pull),
            ("Отправить изменения (Push)", self.git_push),
            ("Синхронизировать (Sync)", self.git_sync),
            ("", None),
            ("Создать ветку…", self._create_branch_dialog),
            ("Клонировать с GitHub…", self.show_clone_dialog),
            ("Инициализировать репозиторий", self.init_repository),
        ):
            if callback is None:
                menu.addSeparator()
                continue
            menu.addAction(text, callback)
        return menu

    def _build_auth_banner(self) -> QtWidgets.QFrame:
        self.auth_banner = QtWidgets.QFrame()
        self.auth_banner.setObjectName("gitAuthCard")
        abl = QtWidgets.QHBoxLayout(self.auth_banner)
        abl.setContentsMargins(8, 6, 8, 6)
        abl.setSpacing(6)

        self.user_avatar_label = QtWidgets.QLabel("🐙")
        self.user_avatar_label.setStyleSheet("font-size: 16px;")
        abl.addWidget(self.user_avatar_label)

        self.auth_status_label = QtWidgets.QLabel("GitHub: не подключен")
        self.auth_status_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        self.auth_status_label.setWordWrap(True)
        self.auth_status_label.setMinimumWidth(0)
        abl.addWidget(self.auth_status_label, 1)

        self.login_action_btn = QtWidgets.QToolButton()
        self.login_action_btn.setText("Войти 🔑")
        self.login_action_btn.setToolTip("Авторизоваться на GitHub через токен")
        self.login_action_btn.setStyleSheet("color: #58A6FF; font-weight: bold; padding: 2px 6px;")
        self.login_action_btn.clicked.connect(self._handle_auth_action)
        abl.addWidget(self.login_action_btn)
        return self.auth_banner

    def _build_github_card(self) -> QtWidgets.QFrame:
        self.github_card = QtWidgets.QFrame()
        self.github_card.setObjectName("gitRemoteCard")
        gh = QtWidgets.QVBoxLayout(self.github_card)
        gh.setContentsMargins(10, 7, 10, 7)
        self.github_repo_label = QtWidgets.QLabel("github.com/…")
        self.github_repo_label.setObjectName("gitRemoteLabel")
        self.github_repo_label.setWordWrap(True)
        self.github_repo_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        gh.addWidget(self.github_repo_label)
        links = QtWidgets.QHBoxLayout()
        links.setSpacing(4)
        gh.addLayout(links)
        for text, callback in (
            ("Репозиторий", self.open_github_repo),
            ("PR", self.open_github_prs),
            ("Задачи", self.open_github_issues)
        ):
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.clicked.connect(callback)
            links.addWidget(b)
        self.github_card.hide()
        return self.github_card

    def _build_publish_frame(self) -> QtWidgets.QFrame:
        self.publish_frame = QtWidgets.QFrame()
        pfl = QtWidgets.QVBoxLayout(self.publish_frame)
        pfl.setContentsMargins(0, 0, 0, 0)
        self.publish_btn = self._button("Опубликовать на GitHub", self._publish_to_github)
        self.publish_btn.setStyleSheet("background: #238636; color: white; font-weight: bold; padding: 6px;")
        pfl.addWidget(self.publish_btn)
        self.publish_frame.hide()
        return self.publish_frame

    def _build_sync_row(self) -> QtWidgets.QGridLayout:
        """Compact action row (VS Code shows sync/commit buttons, not long labels)."""
        sync = QtWidgets.QGridLayout()
        sync.setSpacing(6)
        for index, (text, tip, icon_name, callback) in enumerate((
            ("Получить", "Получить изменения (Pull)", "arrow-down", self.git_pull),
            ("Отправить", "Отправить изменения (Push)", "arrow-up", self.git_push),
            ("Синхронизировать", "Синхронизировать (Sync)", "sync", self.git_sync),
        )):
            b = self._button(text, callback)
            b.setToolTip(tip)
            sync.addWidget(b, index // 2, index % 2, 1, 2 if index == 2 else 1)
        return sync

    def _build_not_repo_frame(self) -> QtWidgets.QFrame:
        self.not_repo_frame = QtWidgets.QFrame()
        nr = QtWidgets.QVBoxLayout(self.not_repo_frame)
        nr.setContentsMargins(0, 0, 0, 0)
        nr.addWidget(self._button("Создать репозиторий", self.init_repository))
        nr.addWidget(self._button("Клонировать с GitHub…", self.show_clone_dialog))
        self.not_repo_frame.hide()
        return self.not_repo_frame

    def _build_file_list(self, layout):
        self.status = QtWidgets.QLabel("Откройте Git-проект для просмотра изменений.")
        self.status.setObjectName("gitStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.files_label = QtWidgets.QLabel("ИЗМЕНЕНИЯ")
        self.files_label.setObjectName("panelSectionLabel")
        layout.addWidget(self.files_label)

        self.files = QtWidgets.QListWidget()
        self.files.setObjectName("gitFiles")
        self.files.setMinimumHeight(140)
        self.files.setTextElideMode(QtCore.Qt.ElideMiddle)
        self.files.itemDoubleClicked.connect(self._open_item)
        self.files.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self._file_context_menu)
        layout.addWidget(self.files, 1)

    def _build_commit_controls(self, layout):
        self.message = QtWidgets.QLineEdit()
        self.message.setObjectName("gitCommitMessage")
        self.message.setPlaceholderText("Сообщение коммита…")
        self.message.returnPressed.connect(self.commit_all)
        layout.addWidget(self.message)

        # VS Code shows one full-width primary "Commit" button plus compact
        # secondary actions, which stays readable in a 280 px sidebar.
        commit = self._button("Зафиксировать", self.commit_all, object_name="gitCommitButton")
        commit.setToolTip("Зафиксировать все изменения (Commit)")
        layout.addWidget(commit)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(4)
        stage = self._button("Индекс +", self.stage_all)
        stage.setToolTip("Проиндексировать все файлы (Stage All)")
        unstage = self._button("Индекс −", self.unstage_all)
        unstage.setToolTip("Снять индексацию (Unstage All)")
        actions.addWidget(stage)
        actions.addWidget(unstage)
        layout.addLayout(actions)

    def _update_auth_ui(self):
        user = self.github_service.get_user_info()
        if user and user.get("token"):
            login = user.get("login", "user")
            self.user_avatar_label.setText("✓")
            self.user_avatar_label.setStyleSheet("color: #3FB950; font-size: 14px; font-weight: bold;")
            self.auth_status_label.setText(f"@{login}")
            self.auth_status_label.setStyleSheet("color: #E6EDF3; font-weight: bold; font-size: 12px;")
            self.login_action_btn.setText("Меню ▾")
            self.login_action_btn.setToolTip(f"Подключен аккаунт @{login}")
        else:
            self.user_avatar_label.setText("🐙")
            self.user_avatar_label.setStyleSheet("font-size: 16px;")
            self.auth_status_label.setText("GitHub не подключен")
            self.auth_status_label.setStyleSheet("color: #8B949E; font-size: 12px;")
            self.login_action_btn.setText("Войти 🔑")
            self.login_action_btn.setToolTip("Войти через Personal Access Token")

    def _handle_auth_action(self):
        if not self.github_service.is_authenticated():
            dialog = GitHubLoginDialog(self)
            dialog.authenticated.connect(lambda _: self._on_auth_success())
            dialog.exec_()
        else:
            # Menu with options
            menu = QtWidgets.QMenu(self.login_action_btn)
            user = self.github_service.get_user_info()
            login = user.get("login", "") if user else ""
            menu.addAction(f"Профиль @{login}", lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{login}")))
            menu.addAction("Мои репозитории…", self._open_user_repos)
            menu.addSeparator()
            menu.addAction("Выйти из аккаунта", self._logout)
            menu.exec_(self.login_action_btn.mapToGlobal(QtCore.QPoint(0, self.login_action_btn.height())))

    def _on_auth_success(self):
        self._update_auth_ui()
        self.refresh()
        self.status.setText("Аутентификация GitHub завершена успешно!")

    def _logout(self):
        self.github_service.logout()
        self._update_auth_ui()
        self.refresh()
        self.status.setText("Вы вышли из GitHub.")

    def _open_user_repos(self):
        dialog = GitHubReposDialog(self)
        dialog.repo_selected.connect(self._clone_from_url)
        dialog.exec_()

    def _clone_from_url(self, clone_url: str, repo_name: str):
        dialog = CloneGitHubDialog(self.root_path, self)
        dialog.url_edit.setText(clone_url)
        dialog.name_edit.setText(repo_name)
        dialog.exec_()

    def set_root(self, root):
        self.root_path = str(Path(root).resolve()) if root else None
        # Git status runs several ``git`` subprocesses (~0.3 s on a real repo).
        # Doing that while a project is being opened froze the window and every
        # animation in it, so the panel only refreshes once it is actually shown.
        if self.isVisible():
            self.refresh()
        else:
            self._needs_refresh = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._needs_refresh:
            self._needs_refresh = False
            # Let the panel paint first, then query git.
            QtCore.QTimer.singleShot(0, self.refresh)

    def _run(self, args, timeout=15):
        if not self.root_path:
            return False, ""
        env = self.github_service.get_auth_git_env()
        try:
            # run_hidden: без него каждый git-вызов открывает окно консоли.
            p = run_hidden(
                ["git", *args],
                cwd=self.root_path,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                timeout=timeout
            )
            out = p.stdout.strip()
            # Mask token from output for security
            token = self.github_service.get_token()
            if token:
                out = out.replace(token, "***")
            return p.returncode == 0, out
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def _detect_github(self, url: str = None):
        """Fill the GitHub card from the remote URL (already read off-thread)."""
        if url is None:
            ok, url = self._run(["remote", "get-url", "origin"])
            url = url if ok else ""
        if not url:
            self.github_repo = None
            self.github_card.hide()
            # Show publish button if it's a git repo but has no remote origin
            is_git = (Path(self.root_path) / ".git").exists() if self.root_path else False
            if is_git and self.github_service.is_authenticated():
                self.publish_frame.show()
            else:
                self.publish_frame.hide()
            return

        self.publish_frame.hide()
        match = re.search(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", url.strip())
        if not match:
            self.github_repo = None
            self.github_card.hide()
            return

        owner, repo = match.group(1), match.group(2)
        web = f"https://github.com/{owner}/{repo}"
        self.github_repo = (owner, repo, web)
        self.github_repo_label.setText(f"{owner}/{repo}")
        self.github_card.show()

    def _update_branch_menu(self):
        menu = QtWidgets.QMenu(self.branch_btn)
        for name in getattr(self, "_branches", []) or []:
            if name:
                menu.addAction(name, lambda b=name: self._switch_branch(b))
        menu.addSeparator()
        menu.addAction("Создать ветку…", self._create_branch_dialog)
        self.branch_btn.setMenu(menu)

    # ------------------------------------------------------------------
    # Git I/O never runs on the GUI thread
    # ------------------------------------------------------------------
    def _run_background(self, work, on_done, status_text: str) -> bool:
        """Execute a blocking git job on the thread pool.

        Every ``git`` call spawns a process (≈60–90 ms on Windows, much more on
        slow disks or when a hook runs), so doing them on the GUI thread froze
        the whole window — that is what made the Source Control view "lag".
        """
        if getattr(self, "_action_busy", False):
            self.status.setText("Git уже выполняет операцию…")
            return False
        self._action_busy = True
        self.status.setText(status_text)
        from services.background import run_async

        def _done(result):
            self._action_busy = False
            try:
                on_done(result)
            finally:
                self.refresh()

        def _failed(message):
            self._action_busy = False
            self.status.setText(message or "Git: операция не удалась")

        run_async(work, on_done=_done, on_error=_failed)
        return True

    def _switch_branch(self, name):
        def work():
            ok, out = self._run(["switch", name])
            if not ok:
                ok, out = self._run(["checkout", name])
            return out or f"Переключено на ветку {name}"

        self._run_background(work, lambda out: self.status.setText(out),
                             f"Переключение на ветку {name}…")

    def _create_branch_dialog(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Новая ветка", "Имя ветки:")
        if not ok or not name.strip():
            return
        branch = name.strip()

        def work():
            success, out = self._run(["switch", "-c", branch])
            if not success:
                success, out = self._run(["checkout", "-b", branch])
            return out or f"Создана ветка {branch}"

        self._run_background(work, lambda out: self.status.setText(out),
                             f"Создание ветки {branch}…")

    def open_github_repo(self):
        if self.github_repo:
            QDesktopServices.openUrl(QUrl(self.github_repo[2]))

    def open_github_prs(self):
        if self.github_repo:
            QDesktopServices.openUrl(QUrl(f"{self.github_repo[2]}/pulls"))

    def open_github_issues(self):
        if self.github_repo:
            QDesktopServices.openUrl(QUrl(f"{self.github_repo[2]}/issues"))

    def _publish_to_github(self):
        if not self.root_path:
            return
        if not self.github_service.is_authenticated():
            dialog = GitHubLoginDialog(self)
            if dialog.exec_() != QtWidgets.QDialog.Accepted:
                return

        folder_name = Path(self.root_path).name
        dialog = CreateGitHubRepoDialog(folder_name, self)
        dialog.repo_created.connect(self._on_repo_published)
        dialog.exec_()

    def _on_repo_published(self, clone_url: str):
        auth_url = self.github_service.inject_token_into_url(clone_url)
        self._run(["remote", "remove", "origin"])
        ok, out = self._run(["remote", "add", "origin", auth_url])
        if not ok:
            self.status.setText(f"Ошибка привязки remote: {out}")
            QtWidgets.QMessageBox.critical(self, "Ошибка публикации", f"Не удалось привязать удалённый репозиторий origin:\n\n{out}")
            return
        branch = self.current_branch or "main"
        self._run(["branch", "-M", branch])
        ok, out = self._run(["push", "-u", "origin", branch])
        self.refresh()
        if ok:
            QtWidgets.QMessageBox.information(
                self,
                "Публикация на GitHub",
                f"✓ Проект успешно опубликован на GitHub!\n\nВетка: {branch}\nURL: {clone_url}"
            )
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка публикации",
                f"Репозиторий создан, но возникла ошибка при первой отправке (Push):\n\n{out}"
            )

    def init_repository(self):
        ok, out = self._run(["init"])
        self.refresh()
        if ok:
            QtWidgets.QMessageBox.information(
                self,
                "Git инициализация",
                "✓ Git-репозиторий успешно инициализирован в проекте."
            )
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка Git инициализации",
                f"Не удалось инициализировать Git-репозиторий:\n\n{out}"
            )

    def show_clone_dialog(self):
        dialog = CloneGitHubDialog(self.root_path, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.cloned_path:
            win = self.window()
            if hasattr(win, "project_handler"):
                from widgets.ProjectManager import project_manager
                win.project_handler.on_project_opened(project_manager.create_project(dialog.cloned_path))

    def _ensure_authenticated_for_remote(self) -> bool:
        """Prompt user to log in if remote is GitHub and not logged in."""
        url = self._remote_url_or_empty()
        if "github.com" in url and not self.github_service.is_authenticated():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Аутентификация GitHub",
                "Для взаимодействия с GitHub (Push/Pull) требуется авторизация.\nХотите войти сейчас?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes
            )
            if reply == QtWidgets.QMessageBox.Yes:
                dialog = GitHubLoginDialog(self)
                return dialog.exec_() == QtWidgets.QDialog.Accepted
            return False
        return True

    def _remote_url_or_empty(self) -> str:
        """Cached origin URL (filled by refresh), never a GUI-thread git call."""
        url = getattr(self, "_remote_url", "") or ""
        if not url:
            ok, url = self._run(["remote", "get-url", "origin"])
            url = url if ok else ""
            if url:
                self._remote_url = url
        return url

    def git_pull(self):
        if not self._ensure_authenticated_for_remote():
            return
        branch = self.current_branch
        remote = self._remote_url_or_empty()
        authenticated = self.github_service.is_authenticated()

        def work():
            if remote and "github.com" in remote and authenticated:
                auth_url = self.github_service.inject_token_into_url(remote)
                return self._run(["pull", auth_url, branch])
            return self._run(["pull"])

        def done(result):
            ok, out = result
            if ok:
                msg = f"✓ Изменения успешно получены!\n\nВетка: {branch}"
                if out:
                    msg += f"\n\nОтвет Git:\n{out}"
                QtWidgets.QMessageBox.information(self, "Получение с GitHub (Pull)", msg)
                self._notify_window(f"Git: Pull успешно выполнен ({branch})")
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Ошибка получения (Pull)",
                    f"Не удалось получить изменения из удалённого репозитория:\n\n"
                    f"{out or 'Неизвестная ошибка Git.'}")
                self._notify_window("Git: Ошибка выполнения Pull", error=True)

        self._run_background(work, done, "Получение изменений с GitHub (Pull)…")

    def git_push(self):
        if not self._ensure_authenticated_for_remote():
            return
        branch = self.current_branch
        remote = self._remote_url_or_empty()
        authenticated = self.github_service.is_authenticated()

        def work():
            if remote and "github.com" in remote and authenticated:
                auth_url = self.github_service.inject_token_into_url(remote)
                return self._run(["push", auth_url, f"HEAD:{branch}"])
            return self._run(["push"])

        def done(result):
            ok, out = result
            if ok:
                msg = f"✓ Изменения успешно отправлены на GitHub!\n\nВетка: {branch}"
                if out:
                    msg += f"\n\nОтвет Git:\n{out}"
                QtWidgets.QMessageBox.information(self, "Отправка на GitHub (Push)", msg)
                self._notify_window(f"Git: Push успешно выполнен ({branch})")
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Ошибка отправки (Push)",
                    f"Не удалось отправить изменения на GitHub в ветку {branch}:\n\n"
                    f"{out or 'Проверьте токен авторизации и права на запись.'}")
                self._notify_window("Git: Ошибка выполнения Push", error=True)

        self._run_background(work, done, "Отправка изменений на GitHub (Push)…")

    def git_sync(self):
        if not self._ensure_authenticated_for_remote():
            return
        branch = self.current_branch
        remote = self._remote_url_or_empty()
        authenticated = self.github_service.is_authenticated()

        def work():
            if remote and "github.com" in remote and authenticated:
                auth_url = self.github_service.inject_token_into_url(remote)
                pull = self._run(["pull", auth_url, branch])
                push = self._run(["push", auth_url, f"HEAD:{branch}"])
            else:
                pull = self._run(["pull"])
                push = self._run(["push"])
            return pull, push

        def done(result):
            (pull_ok, pull_out), (push_ok, push_out) = result
            lines = []
            lines.append(f"Pull: {'✓' if pull_ok else '✗'}" + (f"\n{pull_out}" if pull_out else ""))
            lines.append(f"Push: {'✓' if push_ok else '✗'}" + (f"\n{push_out}" if push_out else ""))
            text = "\n\n".join(lines)
            if pull_ok and push_ok:
                QtWidgets.QMessageBox.information(
                    self, "Синхронизация с GitHub (Sync)", f"✓ Синхронизация завершена.\n\n{text}")
                self._notify_window(f"Git: Sync выполнен ({branch})")
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Синхронизация с GitHub (Sync)", f"Синхронизация завершилась с ошибкой.\n\n{text}")
                self._notify_window("Git: Ошибка выполнения Sync", error=True)

        self._run_background(work, done, "Синхронизация с GitHub (Sync: Pull → Push)…")

    def _notify_window(self, message: str, error: bool = False):
        try:
            bar = getattr(self.window(), "status_bar", None)
            if bar is not None:
                bar.showMessage(message, 5000)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Repository state (read on the worker thread)
    # ------------------------------------------------------------------
    def _collect_state(self) -> dict:
        """Read branch/status/remote/branches — runs off the GUI thread."""
        root = self.root_path
        state = {"is_dir": bool(root and os.path.isdir(root)), "root": root}
        if not state["is_dir"]:
            return state
        ok_branch, branch = self._run(["branch", "--show-current"])
        state["branch_ok"] = ok_branch
        state["branch"] = branch if ok_branch else ""
        if not ok_branch:
            return state
        ok_status, status = self._run(["status", "--porcelain"])
        state["status_ok"] = ok_status
        state["status"] = status
        ok_remote, remote = self._run(["remote", "get-url", "origin"])
        state["remote"] = remote if ok_remote else ""
        ok_branches, branches = self._run(["branch", "--list"])
        state["branches"] = [
            line.strip().lstrip("* ").strip()
            for line in (branches if ok_branches else "").splitlines()
        ]
        return state

    def refresh(self):
        """Refresh the Source Control view without blocking the window."""
        try:
            self._update_auth_ui()
        except RuntimeError:
            return
        if getattr(self, "_state_busy", False):
            self._state_pending = True
            return
        if not self.root_path or not os.path.isdir(self.root_path):
            self._apply_state({"is_dir": False})
            return
        self._state_busy = True
        self.status.setText("Обновление состояния Git…")
        from services.background import run_async
        run_async(self._collect_state, on_done=self._on_state_ready,
                  on_error=self._on_state_failed)

    def _on_state_ready(self, state):
        self._state_busy = False
        try:
            if state.get("root") and state.get("root") != self.root_path:
                # The project changed while the state was being read.
                self._state_pending = True
            else:
                self._apply_state(state or {})
        except RuntimeError:
            return
        finally:
            self._schedule_pending_refresh()

    def _on_state_failed(self, message):
        self._state_busy = False
        try:
            self.status.setText(message or "Не удалось прочитать состояние Git.")
        except RuntimeError:
            return
        self._schedule_pending_refresh()

    def _schedule_pending_refresh(self):
        if getattr(self, "_state_pending", False):
            self._state_pending = False
            QtCore.QTimer.singleShot(0, self.refresh)

    def _apply_state(self, state):
        """Paint the state collected by :meth:`_collect_state` (GUI thread)."""
        self.files.clear()
        if not state.get("is_dir"):
            self.not_repo_frame.hide()
            self.github_card.hide()
            self.publish_frame.hide()
            self.branch_btn.setText("Нет Git-репозитория")
            self.status.setText("Откройте папку проекта.")
            return
        if not state.get("branch_ok"):
            self.not_repo_frame.show()
            self.github_card.hide()
            self.publish_frame.hide()
            self.branch_btn.setText("Нет Git-репозитория")
            self.status.setText("Это не Git-репозиторий.")
            return

        self.not_repo_frame.hide()
        self.current_branch = state.get("branch") or "HEAD"
        self.branch_btn.setText(self.current_branch)
        self.branch_btn.setToolTip(self.current_branch)
        self._branches = state.get("branches") or []
        self._update_branch_menu()
        self._remote_url = state.get("remote") or ""
        self._detect_github(self._remote_url)

        output = state.get("status") or ""
        if not state.get("status_ok"):
            self.status.setText(output or "Не удалось прочитать Git status.")
            return
        if not output:
            self.status.setText("Рабочее дерево чистое — все изменения зафиксированы.")
            return

        self.files.setUpdatesEnabled(False)
        try:
            for line in output.splitlines():
                if len(line) < 3:
                    continue
                x, y, path = line[0], line[1], line[3:].strip()
                code = x if x != " " else y
                label = {
                    "M": "Изменён",
                    "D": "Удалён",
                    "A": "Добавлен",
                    "R": "Переименован",
                    "?": "Не отслеживается"
                }.get(code, code or "Изменён")
                item = QtWidgets.QListWidgetItem(f"{label}    {path}")
                item.setData(QtCore.Qt.UserRole, path)
                self.files.addItem(item)
        finally:
            self.files.setUpdatesEnabled(True)
        self.status.setText(f"Файлов с изменениями: {self.files.count()} · ветка {self.current_branch}")

    def _file_context_menu(self, pos):
        item = self.files.itemAt(pos)
        menu = QtWidgets.QMenu(self)
        if item:
            path = item.data(QtCore.Qt.UserRole)
            menu.addAction("Открыть файл", lambda: self._open_item(item))
            menu.addAction("Индексировать (git add)", lambda: self._stage_file(path))
            menu.addAction("Снять с индекса (git reset)", lambda: self._unstage_file(path))
            menu.addAction("Отменить локальные изменения…", lambda: self._discard_file_changes(path))
            menu.addSeparator()
            menu.addAction("Копировать относительный путь", lambda: QtWidgets.QApplication.clipboard().setText(path))
            if self.root_path:
                full_path = str(Path(self.root_path) / path.strip('"'))
                menu.addAction("Копировать абсолютный путь", lambda: QtWidgets.QApplication.clipboard().setText(full_path))
            menu.addSeparator()

        menu.addAction("Капсула изменений (История)", lambda: getattr(self.window(), "action_change_capsule", lambda: None)())
        menu.addSeparator()
        menu.addAction("Синхронизировать проект (Sync)", self.git_sync)
        menu.addAction("Отправить (Push)", self.git_push)
        menu.addAction("Получить (Pull)", self.git_pull)
        if self.github_repo:
            menu.addSeparator()
            menu.addAction("Открыть репозиторий на GitHub ↗", self.open_github_repo)
            menu.addAction("Pull Requests на GitHub ↗", self.open_github_prs)
            menu.addAction("Задачи (Issues) на GitHub ↗", self.open_github_issues)

        menu.exec_(self.files.viewport().mapToGlobal(pos))

    def _discard_file_changes(self, path):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Отмена изменений",
            f"Отменить все локальные изменения в файле «{path}»?\nЭто действие необратимо.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        def work():
            self._run(["restore", "--", path])
            return self._run(["checkout", "--", path])

        self._run_background(work, lambda result: self.status.setText(
            result[1] or "Изменения отменены."), f"Отмена изменений в {path}…")

    def stage_all(self):
        self._run_background(
            lambda: self._run(["add", "-A"]),
            lambda result: self.status.setText(
                result[1] or ("Все изменения проиндексированы." if result[0] else "Ошибка индексации.")),
            "Индексация изменений…")

    def unstage_all(self):
        self._run_background(
            lambda: self._run(["reset"]),
            lambda result: self.status.setText(
                result[1] or ("Индекс очищен." if result[0] else "Ошибка очистки индекса.")),
            "Очистка индекса…")

    def commit_all(self):
        message = self.message.text().strip()
        if not message:
            QtWidgets.QMessageBox.information(self, "Коммит", "Введите сообщение коммита перед фиксацией.")
            return

        def work():
            ok_status, out_status = self._run(["status", "--porcelain"])
            if ok_status and not out_status.strip():
                return "empty", ""
            ok_cached, _ = self._run(["diff", "--cached", "--quiet"])
            if ok_cached:
                self._run(["add", "-A"])
            return self._run(["commit", "-m", message])

        def done(result):
            if result == ("empty", ""):
                QtWidgets.QMessageBox.information(
                    self, "Коммит", "Рабочее дерево чистое.\nНет изменений для создания коммита.")
                return
            ok, out = result
            if ok:
                self.message.clear()
                msg = f"✓ Коммит успешно создан!\n\nСообщение: {message}"
                if out:
                    msg += f"\n\nОтвет Git:\n{out}"
                QtWidgets.QMessageBox.information(self, "Коммит Git", msg)
                self._notify_window(f"Git: Коммит создан «{message}»")
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Ошибка коммита",
                    f"Не удалось создать коммит:\n\n{out or 'Неизвестная ошибка Git.'}")
                self._notify_window("Git: Ошибка создания коммита", error=True)

        self._run_background(work, done, "Создание коммита…")

    def _stage_file(self, path: str):
        self._run_background(lambda: self._run(["add", "--", path]),
                             lambda result: self.status.setText(
                                 result[1] or ("Файл проиндексирован." if result[0] else "Ошибка индексации.")),
                             f"Индексация {path}…")

    def _unstage_file(self, path: str):
        self._run_background(lambda: self._run(["reset", "HEAD", "--", path]),
                             lambda result: self.status.setText(
                                 result[1] or ("Файл снят с индекса." if result[0] else "Ошибка снятия с индекса.")),
                             f"Снятие с индекса {path}…")

    def _open_item(self, item):
        path = item.data(QtCore.Qt.UserRole)
        if not path or not self.root_path:
            return
        full = Path(self.root_path) / path.strip('"')
        if full.exists() and full.is_file() and hasattr(self.window(), "file_manager"):
            self.window().file_manager.open_file(str(full))
