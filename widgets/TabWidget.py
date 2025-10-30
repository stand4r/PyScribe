from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QTabWidget, QStyleOptionTab, QStyle, QTabBar, QStylePainter, QLabel
from PyQt5.QtGui import QIcon, QColor, QCursor, QFont, QPainter, QPainterPath
from PyQt5.QtCore import Qt, QSize, QPoint, QRect, QRectF


class TabWidget(QTabWidget):
    def __init__(self, parent=None, settings={}):
        super(TabWidget, self).__init__(parent)
        
        # Первоначальная настройка
        self.setTabsClosable(False)
        self.setMovable(True)
        self.setObjectName("tabWidget")
        self.setDocumentMode(True)
    
        # Топ-сайд - компактная правая панель с кнопками
        self.right_tab_widget = QWidget(self)
        self.right_tab_layout = QHBoxLayout(self.right_tab_widget)
        self.right_tab_layout.setContentsMargins(8, 4, 8, 4)  # Уменьшаем отступы
        self.right_tab_layout.setSpacing(4)  # Уменьшаем расстояние между кнопками
        self.right_tab_layout.addStretch()

        # Создаем компактные кнопки с эмодзи
        self.button_run = QPushButton("🚀")
        self.button_settings = QPushButton("⚙️")
        self.toggle_button = QPushButton("📁")
        
        self.right_tab_layout.addWidget(self.toggle_button)
        self.right_tab_layout.addWidget(self.button_run)
        self.right_tab_layout.addWidget(self.button_settings)
        
        self.setCornerWidget(self.right_tab_widget)
        
        # Устанавливаем кастомный TabBar в стиле Clean Glass
        self.custom_tab_bar = CleanGlassTabBar(self)
        self.setTabBar(self.custom_tab_bar)
        
        # Компактный Clean Glass стиль для кнопок
        button_style = """
            QPushButton { 
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px;
                padding-bottom: 0px;
                padding-top: 0px;
                color: rgba(255, 255, 255, 0.95);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 14px;
                font-weight: 500;
                min-width: 32px;
                min-height: 32px;
                max-width: 32px;
                max-height: 32px;
            }
            QPushButton:hover { 
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            QPushButton:pressed { 
                background-color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.35);
            }
        """
        
        self.button_run.setStyleSheet(button_style)
        self.button_run.setToolTip("Run Code (Ctrl+R)")
        self.button_run.setCursor(Qt.PointingHandCursor)
        
        self.button_settings.setStyleSheet(button_style)
        self.button_settings.setToolTip("Settings")
        self.button_settings.setCursor(Qt.PointingHandCursor)
        
        self.toggle_button.setStyleSheet(button_style)
        self.toggle_button.setToolTip("Toggle Explorer")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        
        # Компактный стиль для правого виджета
        self.right_tab_widget.setStyleSheet("""
            QWidget {
                background-color: #25263b;
                border: none;
            }
        """)
        
        # Устанавливаем фиксированную высоту для правого виджета
        self.right_tab_widget.setFixedHeight(38)
        
        # Основной стиль TabWidget в стиле Clean Glass
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: rgba(20, 20, 20, 0.9);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            QTabWidget::tab-bar {
                alignment: left;
                background: transparent;
            }
        """)
        
        # Подключаем сигналы
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self.custom_tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        
    def on_tab_close_requested(self, index):
        if index >= 0 and index < self.count():
            self.removeTab(index)
            
    def set_project_name(self, project_name):
        """Установка имени проекта для отображения"""
        if project_name:
            pass


class CleanGlassTabBar(QTabBar):
    def __init__(self, parent=None):
        super(CleanGlassTabBar, self).__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setElideMode(Qt.ElideRight)
        
        # Цвета в стиле Clean Glass
        self.active_bg_color = QColor(40, 40, 40, 200)
        self.inactive_bg_color = QColor(30, 30, 30, 150)
        self.hover_bg_color = QColor(50, 50, 50, 180)
        self.border_color = QColor(255, 255, 255, 40)
        self.active_text_color = QColor(255, 255, 255, 230)
        self.inactive_text_color = QColor(255, 255, 255, 150)
        self.close_button_hover = QColor(255, 90, 90, 200)
        self.close_button_normal = QColor(255, 255, 255, 120)
        self.accent_color = QColor(0, 122, 204, 200)
        
        self.setFont(QFont("Segoe UI", 10))
        
    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        size.setWidth(min(size.width() + 50, 280))
        size.setHeight(34)  # Немного уменьшаем высоту для компактности
        return size
        
    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        
        # Рисуем фон всей панели вкладок
        gradient = QColor(25, 25, 25, 180)
        painter.fillRect(self.rect(), gradient)
        
        # Рисуем каждую вкладку
        for index in range(self.count()):
            self.initStyleOption(option, index)
            tab_rect = self.tabRect(index)
            mouse_pos = self.mapFromGlobal(QCursor.pos())
            is_hovered = tab_rect.contains(mouse_pos)
            
            # Определяем цвета для текущей вкладки
            if index == self.currentIndex():
                bg_color = self.active_bg_color
                text_color = self.active_text_color
                border_color = self.accent_color
            elif is_hovered:
                bg_color = self.hover_bg_color
                text_color = self.active_text_color
                border_color = self.border_color
            else:
                bg_color = self.inactive_bg_color
                text_color = self.inactive_text_color
                border_color = self.border_color
            
            # Рисуем фон вкладки со скругленными углами
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_color)
            
            # Преобразуем QRect в QRectF для addRoundedRect
            tab_rect_f = QRectF(tab_rect)
            path = QPainterPath()
            path.addRoundedRect(tab_rect_f, 6, 6)  # Уменьшаем радиус для компактности
            painter.drawPath(path)
            
            # Рисуем акцентную линию для активной вкладки
            if index == self.currentIndex():
                painter.setPen(border_color)
                painter.setBrush(border_color)
                accent_rect = QRect(tab_rect.left(), tab_rect.top(), tab_rect.width(), 2)  # Тонкая линия
                painter.drawRect(accent_rect)
            
            # Рисуем правую границу
            painter.setPen(self.border_color)
            painter.drawLine(tab_rect.topRight(), tab_rect.bottomRight())
            
            # Рисуем текст
            painter.setPen(text_color)
            font = painter.font()
            font.setPointSize(10)  # Уменьшаем размер шрифта
            font.setFamily("Segoe UI")
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            
            # Текст с отступами
            text_rect = tab_rect.adjusted(12, 0, -30, 0)  # Уменьшаем отступы
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, option.text)
            
            # Рисуем крестик закрытия
            close_rect = self.closeButtonRect(index)
            close_hovered = close_rect.contains(mouse_pos)
            
            # Фон кнопки закрытия при наведении
            if close_hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.close_button_hover)
                painter.drawEllipse(close_rect)
                painter.setPen(QColor(255, 255, 255, 255))
            else:
                painter.setPen(self.close_button_normal)
            
            # Рисуем крестик
            center = close_rect.center()
            offset = 5  # Уменьшаем крестик
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.drawLine(center.x() - offset, center.y() - offset, 
                            center.x() + offset, center.y() + offset)
            painter.drawLine(center.x() - offset, center.y() + offset, 
                            center.x() + offset, center.y() - offset)
    
    def closeButtonRect(self, index):
        tab_rect = self.tabRect(index)
        close_button_size = QSize(16, 16)  # Уменьшаем размер кнопки
        close_rect = QRect(
            tab_rect.right() - close_button_size.width() - 8,  # Уменьшаем отступ
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
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        self.update()
        super().mouseMoveEvent(event)
