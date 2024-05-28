from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QTabWidget, QStyleOptionTab, QStyle, QTabBar, QStylePainter
from PyQt5.QtGui import QIcon, QColor, QCursor
from PyQt5.QtCore import Qt, QSize


class TabWidget(QTabWidget):
    def __init__(self, parent=None, settings={}):
        super(TabWidget, self).__init__(parent)
        
        # Первоначальная настройка
        self.setTabsClosable(True)
        self.setObjectName("tabWidget")
        self.setDocumentMode(True)
        
        # Настройки
        self.main_color = settings["settings"]["main_color"]  # 013B81
        self.text_color = settings["settings"]["text_color"]  # ABB2BF
        self.first_color = settings["settings"]["first_color"]  # 16171D
        self.second_color = settings["settings"]["second_color"]  # 131313
        self.tab_color = settings["settings"]["tab_color"]  # 1F2228
        self.languages = settings["languages"]
        self.languages_type = settings["languages_type"]
        self.font_size = int(settings["settings"]["fontsize"])
        self.font_size_tab = settings["settings"]["font_size_tab"]
        
        #Топ-сайд
        self.right_tab_widget = QWidget(self)
        self.right_tab_layout = QHBoxLayout()
        self.right_tab_layout.setContentsMargins(5, 0, 0, 0)
        self.right_tab_layout.setSpacing(0)
        self.right_tab_layout.addStretch()

        self.spacinglayout = QVBoxLayout(self.right_tab_widget)  # Устанавливаем нулевые отступы
        self.spacinglayout.setSpacing(0)  # Устанавливаем нулевой интервал
        self.spacinglayout.addStretch()
        self.spacinglayout.addLayout(self.right_tab_layout)
        
        self.setCornerWidget(self.right_tab_widget)
        
        self.button_run = QPushButton("")
        self.button_settings = QPushButton("")
        self.toggle_button = QPushButton("")
        
        self.right_tab_layout.addWidget(self.toggle_button)
        self.right_tab_layout.addWidget(self.button_run)
        self.right_tab_layout.addWidget(self.button_settings)
        self.right_tab_widget.setLayout(self.spacinglayout)
        
        #self.setTabBar(CustomTabBar())
        
        # Стили
        self.button_run.setStyleSheet(
            "border:none; padding-right:5px; padding-left:10px;"
        )
        self.button_run.setIcon(QIcon("src/iconRun.png"))
        self.button_run.setIconSize(QSize(20, 20))
        
        self.button_settings.setStyleSheet(
            "border:none;padding-right:15px;"
        )
        self.button_settings.setIcon(QIcon("src/iconSettings.png"))
        self.button_settings.setIconSize(QSize(20, 20))
        
        self.toggle_button.setIcon(QIcon("src/explorer.png"))
        self.toggle_button.setStyleSheet(
            "border: none; padding-right: 10px; margin-left: 5px;"
        )
        self.toggle_button.setIconSize(QSize(20, 30))
        
        self.right_tab_widget.setStyleSheet(
            "border: none; background-color: #1b1c2e; padding-left: 10px; padding-right: 10px;"
        )
        
        self.setStyleSheet(
            "QTabBar::close-button {image: url(src/close.png);}"
            "QTabBar::tab {padding: 1px; background-color: "
            + "#1b1c2e"
            + "; height: 28px; font-size:"
            + self.font_size_tab
            + "px; border: 1px solid"
            + self.second_color
            + "; border-bottom-color:"
            + self.second_color
            + ";}"
            "QTabBar::tab:selected {background-color:"
            + self.second_color
            + "; color: #ffffff; border-top-color: #00FFFF; padding:1px;}"
            "QTabWidget {border-top: 0px;position: absolute;top: 0;left: 0;right: 0;bottom: 0; border: none;}"
        )


class CustomTabBar(QTabBar):
    def __init__(self, parent=None):
        super(CustomTabBar, self).__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.fillRect(self.rect(), QColor("#2E3440"))

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            
            tab_rect = self.tabRect(index)
            if self.currentIndex() == index:
                option.palette.setColor(option.palette.Button, QColor("#5E81AC"))
            elif tab_rect.contains(self.mapFromGlobal(QCursor.pos())):
                option.palette.setColor(option.palette.Button, QColor("#4C566A"))
            else:
                option.palette.setColor(option.palette.Button, QColor("#16171D"))
                
            painter.drawControl(QStyle.CE_TabBarTab, option)

