from PyQt5 import QtCore, QtGui, QtWidgets


class ClickableFrame(QtWidgets.QFrame):
    """Кликабельный фрейм с hover-эффектами"""
    
    clicked = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super(ClickableFrame, self).__init__(parent)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        """Эффект при наведении"""
        self.setStyleSheet(self.styleSheet() + """
            QFrame {
                border: 1px solid #007acc;
            }
        """)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Эффект при уходе курсора"""
        self.setStyleSheet(self.styleSheet().replace(
            "border: 1px solid #007acc;", ""
        ))
        super().leaveEvent(event)


class Ui_Welcome(QtWidgets.QWidget):
    def __init__(self, parent=None, settings={}):
        super(Ui_Welcome, self).__init__(parent)
        QtCore.QMetaObject.connectSlotsByName(self)
        self.settings = settings
        self.welcome = True
        
        # Цвета в стиле VS Code
        self.bg_color = "#1e1e1e"
        self.secondary_bg = "#252526"
        self.accent_color = "#007acc"
        self.text_color = "#cccccc"
        self.text_muted = "#858585"
        self.hover_color = "#2a2d2e"
        self.border_color = "#3e4452"
        
        self.setObjectName("Main")
        
        # Основной layout
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        
        # Контейнер для центрирования контента
        self.content_container = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(40, 60, 40, 60)
        self.content_layout.setSpacing(40)
        self.content_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        # Заголовок и иконка
        self.header_widget = QtWidgets.QWidget()
        self.header_layout = QtWidgets.QVBoxLayout(self.header_widget)
        self.header_layout.setSpacing(30)
        self.header_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        self.IconLabel = QtWidgets.QLabel()
        self.IconLabel.setMaximumSize(QtCore.QSize(120, 120))
        self.IconLabel.setMinimumSize(QtCore.QSize(120, 120))
        self.IconLabel.setText("")
        self.IconLabel.setPixmap(QtGui.QPixmap("./src/icon2.png"))
        self.IconLabel.setScaledContents(True)
        self.IconLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.IconLabel.setObjectName("IconLabel")
        
        self.WelcomLabel = QtWidgets.QLabel()
        font = QtGui.QFont()
        font.setFamily("Segoe UI Light")
        font.setPointSize(28)
        font.setWeight(QtGui.QFont.Light)
        self.WelcomLabel.setFont(font)
        self.WelcomLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.WelcomLabel.setObjectName("WelcomLabel")
        
        self.header_layout.addWidget(self.IconLabel)
        self.header_layout.addWidget(self.WelcomLabel)
        
        # Блок с быстрыми действиями
        self.actions_widget = QtWidgets.QWidget()
        self.actions_layout = QtWidgets.QHBoxLayout(self.actions_widget)
        self.actions_layout.setSpacing(30)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        # Левая колонка - Новый файл
        self.new_file_card = self.create_action_card(
            "New File", 
            "Create a new file", 
            "Ctrl+N"
        )
        
        # Правая колонка - Открыть файл
        self.open_file_card = self.create_action_card(
            "Open File", 
            "Open an existing file", 
            "Ctrl+O"
        )
        
        self.actions_layout.addWidget(self.new_file_card)
        self.actions_layout.addWidget(self.open_file_card)
        
        # Секция недавних файлов
        self.recent_section = self.create_recent_section()
        
        # Добавляем все в основной layout
        self.content_layout.addWidget(self.header_widget)
        self.content_layout.addWidget(self.actions_widget)
        self.content_layout.addWidget(self.recent_section)
        self.content_layout.addStretch()
        
        self.verticalLayout.addWidget(self.content_container)
        
        # Применяем стили
        self.apply_styles()
        self.retranslateUi()

    def create_action_card(self, title, description, shortcut):
        """Создание кликабельной карточки действия"""
        card = ClickableFrame()
        card.setMinimumSize(200, 120)
        card.setMaximumSize(300, 140)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        
        # Заголовок
        title_label = QtWidgets.QLabel(title)
        title_font = QtGui.QFont()
        title_font.setFamily("Segoe UI Semibold")
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        
        # Описание
        desc_label = QtWidgets.QLabel(description)
        desc_font = QtGui.QFont()
        desc_font.setFamily("Segoe UI")
        desc_font.setPointSize(10)
        desc_label.setFont(desc_font)
        
        # Горячие клавиши
        shortcut_label = QtWidgets.QLabel(shortcut)
        shortcut_font = QtGui.QFont()
        shortcut_font.setFamily("Consolas")
        shortcut_font.setPointSize(9)
        shortcut_label.setFont(shortcut_font)
        
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(shortcut_label)
        
        # Сохраняем ссылки для стилизации
        card.title_label = title_label
        card.desc_label = desc_label
        card.shortcut_label = shortcut_label
        
        return card

    def create_recent_section(self):
        """Создание секции недавних файлов"""
        section = QtWidgets.QFrame()
        section_layout = QtWidgets.QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(15)
        
        # Заголовок секции
        section_title = QtWidgets.QLabel("Recent Files")
        title_font = QtGui.QFont()
        title_font.setFamily("Segoe UI Semibold")
        title_font.setPointSize(12)
        section_title.setFont(title_font)
        
        # Контейнер для списка
        recent_list = QtWidgets.QFrame()
        recent_list_layout = QtWidgets.QVBoxLayout(recent_list)
        recent_list_layout.setContentsMargins(0, 0, 0, 0)
        recent_list_layout.setSpacing(5)
        
        # Заглушка для демонстрации
        no_recent_label = QtWidgets.QLabel("No recent files")
        no_recent_font = QtGui.QFont()
        no_recent_font.setFamily("Segoe UI")
        no_recent_font.setPointSize(10)
        no_recent_label.setFont(no_recent_font)
        no_recent_label.setAlignment(QtCore.Qt.AlignCenter)
        no_recent_label.setMinimumHeight(60)
        
        recent_list_layout.addWidget(no_recent_label)
        
        section_layout.addWidget(section_title)
        section_layout.addWidget(recent_list)
        
        # Сохраняем ссылки
        section.section_title = section_title
        section.recent_list = recent_list
        section.no_recent_label = no_recent_label
        
        return section

    def apply_styles(self):
        """Применение стилей"""
        # Основной стиль
        self.setStyleSheet(f"""
            QWidget#Main {{
                background-color: {self.bg_color};
                color: {self.text_color};
            }}
        """)
        
        # Стиль для карточек действий
        action_card_style = f"""
            ClickableFrame {{
                background-color: {self.secondary_bg};
                border: 1px solid {self.border_color};
                border-radius: 6px;
            }}
            ClickableFrame:hover {{
                background-color: {self.hover_color};
                border: 1px solid {self.accent_color};
            }}
            QLabel {{
                background: transparent;
                color: {self.text_color};
            }}
        """
        
        self.new_file_card.setStyleSheet(action_card_style)
        self.open_file_card.setStyleSheet(action_card_style)
        
        # Стиль для заголовков карточек
        self.new_file_card.title_label.setStyleSheet(f"color: {self.accent_color};")
        self.open_file_card.title_label.setStyleSheet(f"color: {self.accent_color};")
        
        # Стиль для описаний
        self.new_file_card.desc_label.setStyleSheet(f"color: {self.text_muted};")
        self.open_file_card.desc_label.setStyleSheet(f"color: {self.text_muted};")
        
        # Стиль для горячих клавиш
        hotkey_style = f"""
            color: {self.text_muted};
            background-color: {self.bg_color};
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid {self.border_color};
        """
        self.new_file_card.shortcut_label.setStyleSheet(hotkey_style)
        self.open_file_card.shortcut_label.setStyleSheet(hotkey_style)
        
        # Стиль для заголовка
        self.WelcomLabel.setStyleSheet(f"""
            color: {self.text_color};
            background: transparent;
            padding: 10px;
        """)
        
        # Стиль для иконки
        self.IconLabel.setStyleSheet("""
            background: transparent;
            border: 3px solid #007acc;
            border-radius: 20px;
            padding: 10px;
        """)
        
        # Стиль для секции недавних файлов
        self.recent_section.setStyleSheet(f"""
            QFrame {{
                background: transparent;
            }}
        """)
        
        self.recent_section.section_title.setStyleSheet(f"""
            color: {self.text_color};
            background: transparent;
            padding: 5px 0px;
        """)
        
        self.recent_section.recent_list.setStyleSheet(f"""
            background: {self.secondary_bg};
            border: 1px solid {self.border_color};
            border-radius: 6px;
        """)
        
        self.recent_section.no_recent_label.setStyleSheet(f"""
            color: {self.text_muted};
            background: transparent;
        """)
        
        # Стиль для контейнера
        self.content_container.setStyleSheet("background: transparent;")

    def retranslateUi(self):
        """Установка текстов"""
        _translate = QtCore.QCoreApplication.translate
        self.WelcomLabel.setText(_translate("Main", "Welcome to PyScribe"))
        
        # Обновляем тексты в карточках
        self.new_file_card.title_label.setText(_translate("Main", "New File"))
        self.new_file_card.desc_label.setText(_translate("Main", "Create a new file"))
        self.new_file_card.shortcut_label.setText(_translate("Main", "Ctrl+N"))
        
        self.open_file_card.title_label.setText(_translate("Main", "Open File"))
        self.open_file_card.desc_label.setText(_translate("Main", "Open an existing file"))
        self.open_file_card.shortcut_label.setText(_translate("Main", "Ctrl+O"))
        
        self.recent_section.section_title.setText(_translate("Main", "Recent Files"))
        self.recent_section.no_recent_label.setText(_translate("Main", "No recent files"))

    def connect_signals(self, new_file_handler, open_file_handler):
        """Подключение сигналов к обработчикам"""
        self.new_file_card.clicked.connect(new_file_handler)
        self.open_file_card.clicked.connect(open_file_handler)

    def get_cards(self):
        """Возвращает карточки для подключения сигналов"""
        return {
            'new_file': self.new_file_card,
            'open_file': self.open_file_card
        }