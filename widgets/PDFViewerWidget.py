import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import fitz

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QSlider, QComboBox, QProgressBar,
                            QMessageBox, QFileDialog, QToolBar, QAction)

from widgets.Dialog import CustomDialog


class PDFViewerWidget(QWidget):
    """Виджет для просмотра PDF файлов"""
    
    page_changed = pyqtSignal(int, int)
    document_loaded = pyqtSignal(str)
    document_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 300
        self.pdf_document = None
        self.use_fitz = False
        self.use_pdf2image = False
        
        self.setup_ui()
        self.setup_connections()
        self.check_dependencies()
        
    def check_dependencies(self):
        """Проверка доступных зависимостей"""
        try:
            import fitz
            self.use_fitz = True
            print("DEBUG: PyMuPDF (fitz) доступен")
        except ImportError:
            print("DEBUG: PyMuPDF не установлен")
        
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.setup_toolbar()
        main_layout.addWidget(self.toolbar)
        
        self.setup_viewer_area()
        main_layout.addWidget(self.viewer_widget)
        
        self.setup_status_bar()
        main_layout.addWidget(self.status_bar)
        
    def setup_toolbar(self):
        """Настройка панели инструментов"""
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d30;
                border: none;
                padding: 4px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px 8px;
                color: #cccccc;
            }
            QToolButton:hover {
                background-color: #3e3e42;
                border: 1px solid #0078d4;
            }
            QToolButton:pressed {
                background-color: #0078d4;
            }
        """)
        
        self.actions = {}
        
        # Открыть файл
        self.actions['open'] = QAction("📁 Open PDF", self)
        self.actions['open'].setShortcut("Ctrl+O")
        
        # Навигация по страницам
        self.actions['first_page'] = QAction("⏮ First", self)
        self.actions['prev_page'] = QAction("◀ Prev", self)
        self.actions['next_page'] = QAction("Next ▶", self)
        self.actions['last_page'] = QAction("Last ⏭", self)
        
        # Масштаб
        self.actions['zoom_in'] = QAction("🔍+ Zoom In", self)
        self.actions['zoom_out'] = QAction("🔍- Zoom Out", self)
        self.actions['zoom_fit'] = QAction("📐 Fit Width", self)
        
        # Добавление действий на панель
        self.toolbar.addAction(self.actions['open'])
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.actions['first_page'])
        self.toolbar.addAction(self.actions['prev_page'])
        
        # Комбо-бокс для навигации по страницам
        self.page_combo = QComboBox()
        self.page_combo.setFixedWidth(80)
        self.page_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 2px 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
        """)
        self.toolbar.addWidget(self.page_combo)
        
        self.toolbar.addAction(self.actions['next_page'])
        self.toolbar.addAction(self.actions['last_page'])
        self.toolbar.addSeparator()
        
        # Слайдер масштаба
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 4px;
                background: #1e1e1e;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #005a9e;
                width: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }
        """)
        
        self.zoom_label = QLabel("300%")
        self.zoom_label.setFixedWidth(40)
        self.zoom_label.setStyleSheet("color: #cccccc;")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        
        self.toolbar.addWidget(QLabel("Zoom:"))
        self.toolbar.addAction(self.actions['zoom_out'])
        self.toolbar.addWidget(self.zoom_slider)
        self.toolbar.addAction(self.actions['zoom_in'])
        self.toolbar.addWidget(self.zoom_label)
        self.toolbar.addAction(self.actions['zoom_fit'])
        
    def setup_viewer_area(self):
        """Настройка области просмотра"""
        self.viewer_widget = QWidget()
        self.viewer_layout = QVBoxLayout(self.viewer_widget)
        self.viewer_layout.setContentsMargins(10, 10, 10, 10)
        
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.pdf_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #cccccc;
                padding: 20px;
            }
        """)
        self.pdf_label.setText("No PDF document loaded\n\nSupported libraries:\n• PyMuPDF (recommended)\n• pdf2image + poppler")
        self.pdf_label.setMinimumSize(400, 500)
        
        self.viewer_layout.addWidget(self.pdf_label)
        
    def setup_status_bar(self):
        """Настройка статус бара"""
        self.status_bar = QWidget()
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                background-color: #1e1e1e;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
        """)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        
        self.status_bar.setStyleSheet("background-color: #2d2d30;")
        self.status_bar.setFixedHeight(25)
        
    def setup_connections(self):
        """Настройка соединений сигналов"""
        self.actions['open'].triggered.connect(self.open_pdf)
        self.actions['first_page'].triggered.connect(self.first_page)
        self.actions['prev_page'].triggered.connect(self.previous_page)
        self.actions['next_page'].triggered.connect(self.next_page)
        self.actions['last_page'].triggered.connect(self.last_page)
        self.actions['zoom_in'].triggered.connect(self.zoom_in)
        self.actions['zoom_out'].triggered.connect(self.zoom_out)
        self.actions['zoom_fit'].triggered.connect(self.zoom_fit)
        
        self.page_combo.currentTextChanged.connect(self.on_page_combo_changed)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
    def open_pdf(self, file_path: str = None):
        """Открыть PDF файл"""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open PDF File", "", "PDF Files (*.pdf)"
            )
            
        if file_path and os.path.exists(file_path):
            try:
                self.load_pdf(file_path)
            except Exception as e:
                CustomDialog(f"Error opening PDF file: {str(e)}").exec()
                
    def load_pdf(self, file_path: str):
        """Загрузить PDF файл"""
        self.current_file_path = file_path
        self.current_page = 0
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        try:
            # Пробуем PyMuPDF сначала
            if self.use_fitz:
                self.load_with_fitz(file_path)
                return
                
            # Если ничего не доступно
            self.show_install_instructions()
            
        except Exception as e:
            CustomDialog(f"Error loading PDF: {str(e)}").exec()
        finally:
            self.progress_bar.setVisible(False)
            
    def load_with_fitz(self, file_path: str):
        """Загрузка PDF с использованием PyMuPDF"""
        import fitz
        
        try:
            self.pdf_document = fitz.open(file_path)
            self.total_pages = len(self.pdf_document)
            
            # Заполнение комбо-бокса страницами
            self.page_combo.clear()
            for i in range(self.total_pages):
                self.page_combo.addItem(f"{i + 1}")
                
            self.update_page_display()
            self.update_status(f"Loaded with PyMuPDF: {Path(file_path).name} - {self.total_pages} pages")
            self.document_loaded.emit(file_path)
            
        except Exception as e:
            raise Exception(f"PyMuPDF error: {str(e)}")

    def update_page_display(self):
        """Обновить отображение текущей страницы (PyMuPDF)"""
        if not self.pdf_document:
            return
            
        try:
            import fitz
            
            page = self.pdf_document.load_page(self.current_page)
            mat = fitz.Matrix(self.zoom_level / 100, self.zoom_level / 100)
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("ppm")
            qimage = QtGui.QImage()
            qimage.loadFromData(img_data)
            
            pixmap = QtGui.QPixmap.fromImage(qimage)
            self.display_pixmap(pixmap)
            
            self.page_combo.setCurrentText(f"{self.current_page + 1}")
            self.page_changed.emit(self.current_page + 1, self.total_pages)
            self.update_status(f"Page {self.current_page + 1} of {self.total_pages}")
            
        except Exception as e:
            self.pdf_label.setText(f"Error displaying page: {str(e)}")
            
    def display_pixmap(self, pixmap: QtGui.QPixmap):
        """Отобразить pixmap с сохранением пропорций"""
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.pdf_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.pdf_label.setPixmap(scaled_pixmap)
        else:
            self.pdf_label.setText("Error loading page image")
            
    def show_install_instructions(self):
        """Показать инструкции по установке необходимых библиотек"""
        message = (
            "PDF viewing requires additional libraries.\n\n"
            "Recommended: Install PyMuPDF (no external dependencies):\n"
            "  pip install PyMuPDF\n\n"
            "Alternative: Install pdf2image and poppler-utils:\n"
            "  pip install pdf2image pillow\n"
            "  And install poppler-utils for your system:\n"
            "    Windows: Download from http://blog.alivate.com.au/poppler-windows/\n"
            "    Linux: sudo apt-get install poppler-utils\n"
            "    macOS: brew install poppler"
        )
        
        CustomDialog(message).exec()
        self.pdf_label.setText("PDF libraries not installed\n\nClick 'Open PDF' for installation instructions")
        
    # Остальные методы остаются без изменений...
    def first_page(self):
        if self.total_pages > 0:
            self.current_page = 0
            self.update_page_display_method()
            
    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page_display_method()
            
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_page_display_method()
            
    def last_page(self):
        if self.total_pages > 0:
            self.current_page = self.total_pages - 1
            self.update_page_display_method()
            
    def update_page_display_method(self):
        """Выбор метода обновления в зависимости от доступной библиотеки"""
        if self.use_fitz:
            self.update_page_display()
        elif self.use_pdf2image:
            self.update_page_display_pdf2image()
            
    def on_page_combo_changed(self, text: str):
        if text and self.total_pages > 0:
            try:
                page_num = int(text) - 1
                if 0 <= page_num < self.total_pages and page_num != self.current_page:
                    self.current_page = page_num
                    self.update_page_display_method()
            except ValueError:
                pass
                
    def zoom_in(self):
        if self.zoom_level < 400:
            self.zoom_level = min(self.zoom_level + 25, 400)
            self.zoom_slider.setValue(self.zoom_level)
            self.update_page_display_method()
            
    def zoom_out(self):
        if self.zoom_level > 25:
            self.zoom_level = max(self.zoom_level - 25, 25)
            self.zoom_slider.setValue(self.zoom_level)
            self.update_page_display_method()
            
    def zoom_fit(self):
        self.zoom_level = 300
        self.zoom_slider.setValue(self.zoom_level)
        self.update_page_display_method()
        
    def on_zoom_changed(self, value: int):
        self.zoom_level = value
        self.zoom_label.setText(f"{value}%")
        self.update_page_display_method()
        
    def update_status(self, message: str):
        self.status_label.setText(message)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_file_path:
            QtCore.QTimer.singleShot(50, self.update_page_display_method)