from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QTabWidget, QStyleOptionTab, QStyle, QTabBar, QStylePainter, QLabel
from PyQt5.QtGui import QIcon, QColor, QCursor, QFont
from PyQt5.QtCore import Qt, QSize, QPoint, QRect


class TabWidget(QTabWidget):
    def __init__(self, parent=None, settings={}):
        super(TabWidget, self).__init__(parent)
        
        # Первоначальная настройка
        self.setTabsClosable(False)  # Отключаем стандартные кнопки закрытия
        self.setMovable(True)
        self.setObjectName("tabWidget")
        self.setDocumentMode(True)
    
        
        # Топ-сайд - правая панель с кнопками
        self.right_tab_widget = QWidget(self)
        self.right_tab_layout = QHBoxLayout(self.right_tab_widget)
        self.right_tab_layout.setContentsMargins(0, 0, 10, 0)
        self.right_tab_layout.setSpacing(5)
        self.right_tab_layout.addStretch()

        self.button_run = QPushButton("")
        self.button_settings = QPushButton("")
        self.toggle_button = QPushButton("")
        
        self.right_tab_layout.addWidget(self.toggle_button)
        self.right_tab_layout.addWidget(self.button_run)
        self.right_tab_layout.addWidget(self.button_settings)
        
        self.setCornerWidget(self.right_tab_widget)
        
        # Устанавливаем кастомный TabBar
        self.custom_tab_bar = VSCodeTabBar(self)
        self.setTabBar(self.custom_tab_bar)
        
        # Стили для кнопок
        button_style = """
            QPushButton { 
                border: none; 
                padding: 8px; 
                border-radius: 4px; 
                background: transparent;
            }
            QPushButton:hover { 
                background-color: #2a2d2e; 
            }
            QPushButton:pressed { 
                background-color: #3a3d3e; 
            }
        """
        
        self.button_run.setStyleSheet(button_style)
        self.button_run.setIcon(QIcon("src/iconRun.png"))
        self.button_run.setIconSize(QSize(18, 18))
        self.button_run.setToolTip("Run")
        
        self.button_settings.setStyleSheet(button_style)
        self.button_settings.setIcon(QIcon("src/iconSettings.png"))
        self.button_settings.setIconSize(QSize(18, 18))
        self.button_settings.setToolTip("Settings")
        
        self.toggle_button.setStyleSheet(button_style)
        self.toggle_button.setIcon(QIcon("src/explorer.png"))
        self.toggle_button.setIconSize(QSize(18, 18))
        self.toggle_button.setToolTip("Toggle Explorer")
        
        self.right_tab_widget.setStyleSheet(
            "background-color: #2d2d2d; border: none; border-left: 1px solid #3e4452;"
        )
        
        # Основной стиль TabWidget
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
                border-top: 1px solid #3e4452;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
        """)
        
        # Подключаем сигналы
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        # Подключаем сигнал от кастомного TabBar
        self.custom_tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        
    def on_tab_close_requested(self, index):
        if index >= 0 and index < self.count():
            self.removeTab(index)
            
    def set_project_name(self, project_name):
        """Установка имени проекта для отображения"""
        if project_name:
            # Можно добавить визуальное отображение проекта в будущем
            pass


class VSCodeTabBar(QTabBar):
    def __init__(self, parent=None):
        super(VSCodeTabBar, self).__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setElideMode(Qt.ElideRight)
        
        # Настройки цветов как в VS Code
        self.active_bg_color = QColor("#1e1e1e")
        self.inactive_bg_color = QColor("#2d2d2d")
        self.hover_bg_color = QColor("#2a2d2e")
        self.border_color = QColor("#3e4452")
        self.active_text_color = QColor("#ffffff")
        self.inactive_text_color = QColor("#858585")
        self.close_button_hover = QColor("#c74e39")
        self.close_button_normal = QColor("#cccccc")
        
    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        # Увеличиваем ширину вкладок
        size.setWidth(min(size.width() + 40, 300))  # Увеличиваем минимальную ширину и максимальную до 300
        size.setHeight(32)  # Немного увеличиваем высоту
        return size
        
    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        
        # Рисуем фон всей панели вкладок
        painter.fillRect(self.rect(), self.inactive_bg_color)
        
        # Рисуем каждую вкладку с границами
        for index in range(self.count()):
            self.initStyleOption(option, index)
            tab_rect = self.tabRect(index)
            mouse_pos = self.mapFromGlobal(QCursor.pos())
            is_hovered = tab_rect.contains(mouse_pos)
            
            # Определяем цвета для текущей вкладки
            if index == self.currentIndex():
                # Активная вкладка
                bg_color = self.active_bg_color
                text_color = self.active_text_color
            elif is_hovered:
                # Вкладка при наведении
                bg_color = self.hover_bg_color
                text_color = self.active_text_color
            else:
                # Неактивная вкладка
                bg_color = self.inactive_bg_color
                text_color = self.inactive_text_color
            
            # Рисуем фон вкладки
            painter.fillRect(tab_rect, bg_color)
            
            # Рисуем правую границу для всех вкладок кроме последней
            if index < self.count() - 1:
                painter.setPen(self.border_color)
                painter.drawLine(tab_rect.topRight(), tab_rect.bottomRight())
            
            # Для активной вкладки рисуем верхнюю границу другим цветом
            if index == self.currentIndex():
                painter.setPen(QColor("#007acc"))
                painter.drawLine(tab_rect.topLeft(), tab_rect.topRight())
                
                # Также рисуем нижнюю границу того же цвета, что и фон контента
                painter.setPen(self.active_bg_color)
                painter.drawLine(tab_rect.bottomLeft(), tab_rect.bottomRight())
            else:
                # Для неактивных вкладок рисуем нижнюю границу
                painter.setPen(self.border_color)
                painter.drawLine(tab_rect.bottomLeft(), tab_rect.bottomRight())
            
            # Рисуем текст
            painter.setPen(text_color)
            font = painter.font()
            font.setPointSize(10)
            font.setFamily("Segoe UI")
            painter.setFont(font)
            
            # Текст с отступами (увеличиваем отступы для больших вкладок)
            text_rect = tab_rect.adjusted(15, 0, -35, 0)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, option.text)
            
            # Всегда рисуем крестик закрытия (только наш кастомный)
            close_rect = self.closeButtonRect(index)
            close_hovered = close_rect.contains(mouse_pos)
            
            # Фон кнопки закрытия при наведении
            if close_hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.close_button_hover)
                painter.drawRoundedRect(close_rect, 2, 2)
                
                # Рисуем белый крестик
                painter.setPen(QColor("#ffffff"))
            else:
                # Серый крестик когда не наведено
                painter.setPen(self.close_button_normal)
            
            # Рисуем крестик
            center = close_rect.center()
            offset = 4  # Немного увеличиваем крестик
            painter.drawLine(center.x() - offset, center.y() - offset, 
                            center.x() + offset, center.y() + offset)
            painter.drawLine(center.x() - offset, center.y() + offset, 
                            center.x() + offset, center.y() - offset)
    
    def closeButtonRect(self, index):
        tab_rect = self.tabRect(index)
        close_button_size = QSize(18, 18)  # Увеличиваем размер кнопки закрытия
        close_rect = QRect(
            tab_rect.right() - close_button_size.width() - 10,  # Увеличиваем отступ
            tab_rect.center().y() - close_button_size.height() // 2,
            close_button_size.width(),
            close_button_size.height()
        )
        return close_rect
    
    def mousePressEvent(self, event):
        pos = event.pos()
        
        # Проверяем, не нажали ли на кнопку закрытия
        for index in range(self.count()):
            close_rect = self.closeButtonRect(index)
            if close_rect.contains(pos):
                self.tabCloseRequested.emit(index)
                return
        
        # Проверяем закрытие средней кнопкой мыши
        if event.button() == Qt.MiddleButton:
            for index in range(self.count()):
                if self.tabRect(index).contains(pos):
                    self.tabCloseRequested.emit(index)
                    return
        
        # Если не нажали на кнопку закрытия, передаем событие родителю
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        # Обновляем отрисовку при движении мыши для hover-эффектов
        self.update()
        super().mouseMoveEvent(event)