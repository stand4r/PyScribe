"""PyScribe widgets/ProjectDialog.py: application module and reusable component."""
from core.logging_config import get_logger
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFileDialog, QTextEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
                             QWidget, QFormLayout, QComboBox, QFrame, QScrollArea, QMenu)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette
from pathlib import Path
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import datetime
from widgets.ProjectManager import ProjectConfig, project_manager

# Стили для современного дизайна
MODERN_STYLES = """
QDialog#projectManager { background: #181818; color: #D4D4D4; border-radius: 10px; }
QLabel { background: transparent; color: #D4D4D4; }
QLineEdit, QTextEdit, QComboBox { background: #242424; color: #D4D4D4; border: 1px solid #2B2B2B; border-radius: 6px; padding: 5px 8px; min-height: 28px; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #0078D4; }
QPushButton { background: #2A2D2E; color: #D4D4D4; border: 1px solid #3A3A3A; border-radius: 6px; padding: 5px 12px; min-height: 28px; }
QPushButton:hover, QPushButton:checked { background: #37373D; color: #FFFFFF; border-color: #0078D4; }
QPushButton:pressed { background: #264F78; color: #FFFFFF; }
QPushButton#open-button, QPushButton[primary="true"] {
    background-color: #0078D4;
    color: #FFFFFF !important;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #0078D4;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton#open-button:hover, QPushButton[primary="true"]:hover {
    background-color: #1A8AD8;
    color: #FFFFFF !important;
    border-color: #1A8AD8;
}
QPushButton#open-button:pressed, QPushButton[primary="true"]:pressed {
    background-color: #005A9E;
    color: #FFFFFF !important;
}
QPushButton#new-project-btn {
    background-color: #0078D4;
    color: #FFFFFF !important;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #0078D4;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton#new-project-btn:hover {
    background-color: #1A8AD8;
    color: #FFFFFF !important;
}
QPushButton#configure-button, QPushButton[secondary="true"] {
    background-color: #2A2D2E;
    color: #E3ECF7;
    border: 1px solid #3A3A3A;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#configure-button:hover {
    background-color: #37373D;
    color: #FFFFFF;
    border-color: #0078D4;
}
QPushButton#delete-button, QPushButton[danger="true"] {
    background-color: #2A2D2E;
    color: #F87171;
    border: 1px solid #4A2828;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#delete-button:hover {
    background-color: #7F1D1D;
    color: #FFFFFF;
    border-color: #EF4444;
}
QTabBar::tab { background: #181818; color: #A8A8A8; padding: 8px 14px; min-height: 28px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:hover { background: #2A2D2E; color: #D4D4D4; }
QTabBar::tab:selected { background: #1E1E1E; color: #FFFFFF; border-bottom: 2px solid #0078D4; }
QListWidget, QScrollArea { background: #181818; color: #D4D4D4; border: 1px solid #2B2B2B; border-radius: 8px; }
QFrame#project-card { background: #1E1E1E; border: 1px solid #2B2B2B; border-radius: 8px; }
QFrame#project-card:hover { background: #242424; border-color: #0078D4; }
QFrame#project-card QLabel,
QLabel#projectName,
QLabel#projectPath,
QLabel#projectTime,
QLabel#projectCommandText { background: transparent; background-color: transparent; }
"""


class ModernProjectCard(QFrame):
    """Современная карточка проекта"""
    
    def __init__(self, project: ProjectConfig, parent=None):
        super().__init__(parent)
        self.project = project
        self.parent_dialog = parent
        self.is_selected = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setObjectName("project-card")
        self.setCursor(Qt.PointingHandCursor)
        self.update_card_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # Заголовок проекта
        title_layout = QHBoxLayout()
        title_info_layout = QVBoxLayout()
        title_info_layout.setSpacing(2)
        name_label = QLabel(self.project.get_display_name())
        name_label.setObjectName("projectName")
        name_label.setStyleSheet("background: transparent; background-color: transparent; border: none; font-size: 14px; font-weight: 600; color: #E3ECF7;")
        path_label = QLabel(self.project.root_path)
        path_label.setObjectName("projectPath")
        path_label.setStyleSheet("background: transparent; background-color: transparent; border: none; font-size: 12px; color: #858585;")
        path_label.setWordWrap(False)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_info_layout.addWidget(name_label)
        title_info_layout.addWidget(path_label)
        title_layout.addLayout(title_info_layout, 1)
        time_label = QLabel(self.project.get_last_opened_display())
        time_label.setObjectName("projectTime")
        time_label.setStyleSheet("background: transparent; background-color: transparent; border: none; font-size: 12px; color: #858585;")
        title_layout.addWidget(time_label)
        title_layout.addStretch()

        layout.addLayout(title_layout)
        
        # Команда запуска (если есть)
        if self.project.launch_command:
            command_frame = QFrame()
            command_frame.setObjectName("projectCommand")
            command_frame.setStyleSheet("background: #181818; border: 1px solid #2B2B2B; border-radius: 4px;")
            command_layout = QHBoxLayout(command_frame)
            command_layout.setContentsMargins(8, 8, 8, 8)
            
            command_text = QLabel(self.project.launch_command)
            command_text.setObjectName("projectCommandText")
            command_text.setStyleSheet("background: transparent; background-color: transparent; color: #75BEFF;")
            command_text.setWordWrap(True)
            command_layout.addWidget(command_text, 1)
            
            layout.addWidget(command_frame)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #2B2B2B; max-height: 1px;")
        layout.addWidget(separator)
        
        # Кнопки действий
        actions_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Открыть")
        self.open_button.setObjectName("open-button")
        self.open_button.setProperty("primary", True)
        self.open_button.setStyleSheet(
            "QPushButton#open-button { background-color: #0078D4; color: #FFFFFF; font-weight: 600; font-size: 13px; border: 1px solid #0078D4; border-radius: 6px; padding: 6px 16px; min-height: 28px; }"
            "QPushButton#open-button:hover { background-color: #1A8AD8; color: #FFFFFF; border-color: #1A8AD8; }"
            "QPushButton#open-button:pressed { background-color: #005A9E; color: #FFFFFF; }"
        )
        
        self.configure_button = QPushButton("Настроить")
        self.configure_button.setObjectName("configure-button")
        self.configure_button.setProperty("secondary", True)
        
        self.delete_button = QPushButton("Удалить")
        self.delete_button.setObjectName("delete-button")
        self.delete_button.setProperty("danger", True)
        self.delete_button.setStyleSheet(
            "QPushButton#delete-button { background-color: #3A2326; color: #F87171; border: 1px solid #5C2B2E; border-radius: 6px; padding: 6px 14px; min-height: 28px; }"
            "QPushButton#delete-button:hover { background-color: #E81123; color: #FFFFFF; border-color: #E81123; }"
        )
        
        actions_layout.addWidget(self.open_button)
        actions_layout.addWidget(self.configure_button)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        self.open_button.clicked.connect(self.on_open_clicked)
        self.configure_button.clicked.connect(self.on_configure_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_card_style()

    def update_card_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                QFrame#project-card { background: #1F2836; border: 2px solid #0078D4; border-radius: 8px; }
                QLabel { background: transparent; background-color: transparent; border: none; }
            """)
        else:
            self.setStyleSheet("""
                QFrame#project-card { background: #1E1E1E; border: 1px solid #2B2B2B; border-radius: 8px; }
                QFrame#project-card:hover { background: #242424; border-color: #0078D4; }
                QLabel { background: transparent; background-color: transparent; border: none; }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.parent_dialog and hasattr(self.parent_dialog, 'select_card'):
                self.parent_dialog.select_card(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.parent_dialog:
            self.parent_dialog.open_project(self.project)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.parent_dialog and hasattr(self.parent_dialog, 'select_card'):
            self.parent_dialog.select_card(self)
        menu = QMenu(self)
        open_action = menu.addAction("Открыть проект")
        config_action = menu.addAction("Настроить...")
        menu.addSeparator()
        delete_action = menu.addAction("Удалить из списка")
        chosen = menu.exec_(event.globalPos())
        if chosen == open_action:
            self.on_open_clicked()
        elif chosen == config_action:
            self.on_configure_clicked()
        elif chosen == delete_action:
            self.on_delete_clicked()

    def on_open_clicked(self):
        """Обработчик клика на кнопку Open"""
        if self.parent_dialog:
            self.parent_dialog.open_project(self.project)
        
    def on_delete_clicked(self):
        """Обработчик клика на кнопку Delete"""
        reply = QMessageBox.question(
            self.parent_dialog or self,
            "Удалить проект",
            f"Вы уверены, что хотите удалить проект «{self.project.name}» из списка?\n\n"
            "Примечание: проект будет удален только из списка PyScribe, файлы на диске останутся нетронутыми.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from widgets.ProjectManager import project_manager
            if project_manager.delete_project(self.project.root_path):
                if self.parent_dialog:
                    if getattr(self.parent_dialog, 'selected_card', None) == self:
                        self.parent_dialog.selected_card = None
                        self.parent_dialog.selected_project = None
                    if hasattr(self.parent_dialog, 'load_recent_projects') and getattr(self.parent_dialog, 'recent_layout', None) is not None:
                        self.parent_dialog.load_recent_projects()
                    if hasattr(self.parent_dialog, 'load_all_projects'):
                        self.parent_dialog.load_all_projects()
                    if hasattr(self.parent_dialog, 'status_bar') and self.parent_dialog.status_bar:
                        self.parent_dialog.status_bar.setText(f"Проект «{self.project.name}» удален из списка")
                else:
                    self.deleteLater()
            else:
                QMessageBox.warning(
                    self.parent_dialog or self,
                    "Не удалось удалить",
                    f"Не удалось удалить проект «{self.project.name}»."
                )
    
    def on_configure_clicked(self):
        """Обработчик клика на кнопку Configure"""
        if self.parent_dialog:
            self.parent_dialog.configure_project(self.project)

class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owner = parent
        self.selected_project = None
        self.selected_card = None
        self.recent_layout = None
        self.setWindowTitle("Управление проектами")
        self.setObjectName("projectManager")
        self.setMinimumSize(700, 600)
        self.setup_ui()

    
    def setup_ui(self):
        self.setStyleSheet(MODERN_STYLES)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        #Empty Label
        self.recent_empty_label = QLabel("Недавние проекты не найдены.\nСоздайте новый проект или откройте существующую папку.")

        # Заголовок
        header_layout = QHBoxLayout()
        title_label = QLabel("Управление проектами")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #E3ECF7;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Кнопка создания нового проекта
        new_project_btn = QPushButton("＋ Новый проект")
        new_project_btn.setObjectName("new-project-btn")
        new_project_btn.clicked.connect(self.show_new_project_dialog)
        header_layout.addWidget(new_project_btn)
        
        layout.addLayout(header_layout)
        
        # Вкладки проекта: без отдельного списка недавно открытых проектов.
        self.tabs = QTabWidget()
        self.all_tab = self.create_all_tab()
        self.tabs.addTab(self.all_tab, "Проекты")
        self.quick_tab = self.create_quick_tab()
        self.tabs.addTab(self.quick_tab, "Открыть папку")
        
        layout.addWidget(self.tabs)
        
        # Статус бар
        self.status_bar = QLabel("Готово")
        layout.addWidget(self.status_bar)

    
    def create_recent_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        recent_label = QLabel("Недавние проекты")
        layout.addWidget(recent_label)
        
        # Область прокрутки для карточек
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        self.recent_layout = QVBoxLayout(scroll_widget)
        self.recent_layout.setSpacing(10)
        
        self.load_recent_projects()
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Сообщение если нет проектов
        
        self.recent_empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.recent_empty_label)
        
        self.update_empty_state()
        
        return widget
    
    def create_all_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Поиск
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        search_label.setStyleSheet("color: #CCCCCC;")
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск проекта по названию…")
        self.search_edit.textChanged.connect(self.filter_projects)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        
        layout.addLayout(search_layout)
        
        # Область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.all_scroll_widget = QWidget()
        self.all_layout = QVBoxLayout(self.all_scroll_widget)
        self.all_layout.setSpacing(10)
        
        self.load_all_projects()
        
        scroll_area.setWidget(self.all_scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_quick_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Быстрое открытие папки
        quick_folder_frame = QFrame()
        quick_folder_frame.setStyleSheet("""
            QFrame {
                background-color: #3E3E42;
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 25px;
            }
        """)
        quick_folder_layout = QVBoxLayout(quick_folder_frame)
        
        folder_icon = QLabel("📂")
        folder_icon.setStyleSheet("font-size: 48px; text-align: center;")
        folder_icon.setAlignment(Qt.AlignCenter)
        
        folder_title = QLabel("Открыть папку как проект")
        folder_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; text-align: center;")
        
        folder_desc = QLabel("Быстро откройте любую папку и начните разработку.\nPyScribe автоматически определит структуру проекта.")
        folder_desc.setStyleSheet("color: #CCCCCC; text-align: center; line-height: 1.4;")
        folder_desc.setAlignment(Qt.AlignCenter)
        folder_desc.setWordWrap(True)
        
        open_folder_btn = QPushButton("Выбрать папку…")
        open_folder_btn.setStyleSheet(
            "QPushButton { background-color: #0078D4; color: #FFFFFF; font-weight: 600; font-size: 13px; border: 1px solid #0078D4; border-radius: 6px; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #1A8AD8; color: #FFFFFF; }"
        )
        open_folder_btn.clicked.connect(self.quick_open_folder)
        
        quick_folder_layout.addWidget(folder_icon)
        quick_folder_layout.addWidget(folder_title)
        quick_folder_layout.addSpacing(10)
        quick_folder_layout.addWidget(folder_desc)
        quick_folder_layout.addSpacing(15)
        quick_folder_layout.addWidget(open_folder_btn)
        
        layout.addWidget(quick_folder_frame)
        layout.addStretch()
        
        return widget
    
    def select_card(self, card):
        """Выбор карточки проекта"""
        if hasattr(self, 'selected_card') and self.selected_card and self.selected_card != card:
            try:
                self.selected_card.set_selected(False)
            except Exception:
                pass
        self.selected_card = card
        if card:
            card.set_selected(True)
            self.selected_project = card.project
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.setText(f"Выбран проект: {card.project.get_display_name()} ({card.project.root_path})")

    def keyPressEvent(self, event):
        """Удаление выбранного проекта по клавише Delete/Backspace"""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and getattr(self, 'selected_card', None):
            self.selected_card.on_delete_clicked()
            return
        super().keyPressEvent(event)

    def load_recent_projects(self):
        """Загрузка недавних проектов"""
        if not getattr(self, 'recent_layout', None):
            return
        # Очищаем layout
        for i in reversed(range(self.recent_layout.count())):
            widget = self.recent_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        recent_projects = project_manager.get_recent_projects(5)
        
        for project in recent_projects:
            card = ModernProjectCard(project, self)
            self.recent_layout.addWidget(card)
        
        self.update_empty_state()

    def load_all_projects(self):
        """Загрузка всех проектов"""
        for i in reversed(range(self.all_layout.count())):
            widget = self.all_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        all_projects = project_manager.get_sorted_projects()
        
        for project in all_projects:
            card = ModernProjectCard(project, self)
            self.all_layout.addWidget(card)
        
        if not all_projects:
            empty_label = QLabel("Проекты не найдены.\nСоздайте новый проект, чтобы начать работу.")
            empty_label.setStyleSheet("color: #666666; font-size: 14px; text-align: center; padding: 40px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.all_layout.addWidget(empty_label)
    
    def update_empty_state(self):
        """Обновление состояния пустого списка"""
        if not getattr(self, 'recent_layout', None) or not getattr(self, 'recent_empty_label', None):
            return
        has_recent = self.recent_layout.count() > 0
        self.recent_empty_label.setVisible(not has_recent)

    
    def filter_projects(self, text):
        """Фильтрация проектов по поисковому запросу"""
        for i in range(self.all_layout.count()):
            widget = self.all_layout.itemAt(i).widget()
            if isinstance(widget, ModernProjectCard):
                project_name = widget.project.get_display_name().lower()
                matches = text.lower() in project_name
                widget.setVisible(matches)
    
    def show_new_project_dialog(self):
        """Показать диалог создания нового проекта"""
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if getattr(dialog, 'created_project', None):
                self.selected_project = dialog.created_project
                self.accept()
                return
            self.load_recent_projects()
            self.load_all_projects()
    
    def quick_open_folder(self):
        """Быстрое открытие папки"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Выберите папку проекта",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            folder = str(Path(folder).resolve())
            project = project_manager.open_project(folder)
            if not project:
                project = project_manager.create_project(folder)
            
            self.selected_project = project
            self.accept()
    
    def open_project(self, project):
        """Select a project and close the dialog.

        Project activation is deliberately handled by the owner after
        exec_() returns.  Calling the main window from inside a modal dialog
        can re-enter the event loop while the dialog is still unwinding and
        was the source of the RecursionОшибка seen when opening projects.
        """
        if project is None:
            return

        opened_project = project_manager.open_project(project.root_path)
        if opened_project is None:
            return

        self.selected_project = opened_project
        self.accept()
    
    def configure_project(self, project):
        """Настройка проекта"""
        dialog = ProjectConfigDialog(project, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_recent_projects()
            self.load_all_projects()

class NewProjectDialog(QDialog):
    """Диалог создания нового проекта"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создание нового проекта")
        self.setMinimumSize(500, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Заголовок
        title_label = QLabel("Создание нового проекта")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)
        
        # Форма
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Название проекта
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Мой проект")
        form_layout.addRow("Название проекта:", self.name_edit)
        
        # Папка проекта
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Выберите папку проекта…")
        browse_btn = QPushButton("Обзор…")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_edit, 1)
        folder_layout.addWidget(browse_btn)
        form_layout.addRow("Папка проекта:", folder_layout)
        
        # Команда запуска
        self.command_combo = QComboBox()
        self.command_combo.addItems([
            "Определить автоматически",
            "python main.py",
            "npm start",
            "node index.js", 
            "cargo run",
            "go run main.go",
            "Своя команда…"
        ])
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        form_layout.addRow("Команда запуска:", self.command_combo)
        
        # Кастомная команда (скрыта по умолчанию)
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText("Введите команду запуска…")
        self.custom_command_edit.setVisible(False)
        form_layout.addRow("Своя команда:", self.custom_command_edit)
        
        # Описание
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Описание проекта (необязательно)…")
        form_layout.addRow("Описание:", self.description_edit)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        
        self.create_btn = QPushButton("Создать проект")
        self.create_btn.setObjectName("create-btn")
        self.create_btn.clicked.connect(self.create_project)
        self.create_btn.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)
        
        # Подключаем проверку валидности
        self.name_edit.textChanged.connect(self.validate_form)
        self.folder_edit.textChanged.connect(self.validate_form)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку проекта")
        if folder:
            self.folder_edit.setText(folder)
            # Автозаполнение имени проекта если не заполнено
            if not self.name_edit.text():
                self.name_edit.setText(Path(folder).name)
    
    def on_command_changed(self, text):
        """Обработчик изменения команды запуска"""
        self.custom_command_edit.setVisible(text == "Своя команда…")
    
    def validate_form(self):
        """Проверка валидности формы"""
        has_name = bool(self.name_edit.text().strip())
        has_folder = bool(self.folder_edit.text().strip()) and Path(self.folder_edit.text()).exists()
        self.create_btn.setEnabled(has_name and has_folder)
    
    def create_project(self):
        """Создание проекта"""
        name = self.name_edit.text().strip()
        folder = self.folder_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        # Определяем команду запуска
        command_text = self.command_combo.currentText()
        if command_text == "Определить автоматически":
            launch_command = self.auto_detect_command(folder)
        elif command_text == "Своя команда…":
            launch_command = self.custom_command_edit.text().strip()
        else:
            launch_command = command_text
        
        # Создаем проект
        project = project_manager.create_project(
            root_path=folder,
            name=name,
            launch_command=launch_command,
            description=description
        )
        
        # Создаем базовую структуру если папка пустая
        if not any(Path(folder).iterdir()):
            self.create_project_structure(folder)
        
        self.created_project = project
        self.accept()
    
    def auto_detect_command(self, folder_path):
        """Автоматическое определение команды запуска"""
        path = Path(folder_path)
        
        if (path / "package.json").exists():
            return "npm start"
        elif (path / "main.py").exists():
            return "python main.py"
        elif (path / "index.js").exists():
            return "node index.js"
        elif (path / "Cargo.toml").exists():
            return "cargo run"
        elif (path / "go.mod").exists():
            return "go run main.go"
        elif (path / "pom.xml").exists():
            return "mvn exec:java"
        elif (path / "build.gradle").exists():
            return "./gradlew run" if (path / "gradlew").exists() else "gradle run"
        
        return ""
    
    def create_project_structure(self, folder_path):
        """Создание базовой структуры проекта"""
        try:
            path = Path(folder_path)
            
            # Создаем README
            readme_content = f"""# {self.name_edit.text()}

## Описание
{self.description_edit.toPlainText() or 'Add your project description here.'}

## Getting Started
Follow these instructions to get the project up and running.

## Installation
Add installation instructions here.

## Usage
Explain how to use your project.
"""
            (path / "README.md").write_text(readme_content, encoding='utf-8')
            
            # Создаем gitignore если нет
            if not (path / ".gitignore").exists():
                gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
"""
                (path / ".gitignore").write_text(gitignore_content, encoding='utf-8')
                
        except Exception as e:
            logger.exception("Ошибка creating project structure: ")


class ProjectConfigDialog(QDialog):
    def __init__(self, project_config, parent=None):
        super().__init__(parent)
        self.project_config = project_config
        self.setWindowTitle(f"Настроить проект: {project_config.name}")
        self.setMinimumSize(500, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Заголовок
        title_label = QLabel("Project Configuration")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)
        
        # Информация о проекте
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #3E3E42;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        
        info_title = QLabel("Project Information")
        info_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; margin-bottom: 10px;")
        info_layout.addWidget(info_title)
        
        # Путь проекта
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Расположение:"))
        path_label = QLabel(self.project_config.root_path)
        path_label.setStyleSheet("color: #CCCCCC; font-family: 'Consolas', monospace;")
        path_label.setWordWrap(True)
        path_layout.addWidget(path_label, 1)
        info_layout.addLayout(path_layout)
        
        # Дата создания
        created_layout = QHBoxLayout()
        created_layout.addWidget(QLabel("Создан:"))
        try:
            created_date = datetime.datetime.fromisoformat(
                self.project_config.created_at.replace('Z', '+00:00')
            ).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_date = "Неизвестно"
        created_label = QLabel(created_date)
        created_label.setStyleSheet("color: #CCCCCC;")
        created_layout.addWidget(created_label)
        info_layout.addLayout(created_layout)
        
        layout.addWidget(info_frame)
        
        # Форма настроек
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Название проекта
        self.name_edit = QLineEdit(self.project_config.name)
        self.name_edit.setPlaceholderText("Введите название проекта…")
        form_layout.addRow("Название проекта:", self.name_edit)
        
        # Команда запуска
        command_layout = QVBoxLayout()
        
        self.command_combo = QComboBox()
        self.command_combo.addItems([
            "Своя команда…",
            "python main.py",
            "npm start", 
            "node index.js",
            "java Main",
            "cargo run",
            "go run main.go",
            "./gradlew run",
            "mvn exec:java"
        ])
        
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText("Введите команду запуска…")
        self.custom_command_edit.setText(self.project_config.launch_command)
        
        # Устанавливаем правильный выбор в комбобоксе
        if self.project_config.launch_command in [self.command_combo.itemText(i) for i in range(1, self.command_combo.count())]:
            self.command_combo.setCurrentText(self.project_config.launch_command)
            self.custom_command_edit.setVisible(False)
        else:
            self.command_combo.setCurrentText("Своя команда…")
            self.custom_command_edit.setVisible(True)
        
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        
        command_layout.addWidget(self.command_combo)
        command_layout.addWidget(self.custom_command_edit)
        form_layout.addRow("Команда запуска:", command_layout)
        
        # Описание проекта
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlainText(self.project_config.description)
        self.description_edit.setPlaceholderText("Описание проекта...")
        form_layout.addRow("Описание:", self.description_edit)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        # Кнопка тестирования команды
        test_btn = QPushButton("Проверить команду")
        test_btn.setObjectName("secondary")
        test_btn.clicked.connect(self.test_command)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Сохранить изменения")
        save_btn.setObjectName("save-btn")
        save_btn.clicked.connect(self.save_config)
        
        button_layout.addWidget(test_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def on_command_changed(self, text):
        """Обработчик изменения команды запуска"""
        is_custom = text == "Своя команда…"
        self.custom_command_edit.setVisible(is_custom)
        
        if not is_custom and text != "Своя команда…":
            self.custom_command_edit.setText(text)
    
    def test_command(self):
        """Тестирование команды запуска"""
        command = self.get_launch_command()
        if not command:
            QMessageBox.information(self, "Проверить команду", "Команда запуска не указана")
            return
        
        try:
            import platform
            from core.subprocess_utils import run_hidden

            # Проверяем существование команды
            if platform.system() == "Windows":
                result = run_hidden(["where", command.split()[0]], capture_output=True, text=True)
            else:
                result = run_hidden(["which", command.split()[0]], capture_output=True, text=True)
            
            if result.returncode == 0:
                QMessageBox.information(self, "Проверить команду", 
                                      f"✅ Команда найдена:\n{command}\n\nГотово к запуску!")
            else:
                QMessageBox.warning(self, "Проверить команду",
                                  f"⚠️ Команда не найдена:\n{command}\n\n"
                                  f"Убедитесь, что команда доступна в системной переменной PATH.")
                
        except Exception as e:
            QMessageBox.critical(self, "Проверить команду Ошибка", 
                               f"Ошибка при проверке команды:\n{str(e)}")
    
    def get_launch_command(self):
        """Получение команды запуска из формы"""
        if self.command_combo.currentText() == "Своя команда…":
            return self.custom_command_edit.text().strip()
        else:
            return self.command_combo.currentText()
    
    def get_config(self):
        """Получение конфигурации проекта"""
        self.project_config.name = self.name_edit.text().strip()
        self.project_config.launch_command = self.get_launch_command()
        self.project_config.description = self.description_edit.toPlainText().strip()
        return self.project_config
    
    def save_config(self):
        """Сохранение конфигурации"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка проверки", "Название проекта не может быть пустым")
            return
        
        self.accept()


logger = get_logger("ProjectDialog")
