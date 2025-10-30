# SettingsWidget.py
from functools import partial
from PyQt5 import QtWidgets, QtCore, QtGui
from utils.settings_manager import get_settings_manager

class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, settings, pathSettings, parent=None):
        super().__init__(parent)
        self.path_settings = pathSettings
        self.settings = settings
        self.mode = -2
        self.parent = parent
        self.settings_manager = get_settings_manager()
        self.setupUi()

    def setupUi(self):
        # Применяем текущие настройки темы
        self.apply_theme()
        
        self.layout = QtWidgets.QFormLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок
        title = QtWidgets.QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        self.layout.addRow(title)
        
        # Разделитель
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("background-color: #555555;")
        self.layout.addRow(line)
        
        # Поля настроек
        self.fields = {}
        settings_data = {
            'main_color': ('Main Color', 'Основной цвет интерфейса'),
            'text_color': ('Text Color', 'Цвет текста'),
            'first_color': ('Background 1', 'Основной фон'),
            'second_color': ('Background 2', 'Вторичный фон'),
            'tab_color': ('Tab Color', 'Цвет вкладок'),
            'fontsize': ('Font Size', 'Размер шрифта кода'),
            'font_size_tab': ('Tab Font Size', 'Размер шрифта вкладок')
        }
        
        for key, (label, tooltip) in settings_data.items():
            label_widget = QtWidgets.QLabel(label)
            label_widget.setToolTip(tooltip)
            
            if 'color' in key:
                # Color picker для цветов
                color_widget = QtWidgets.QWidget()
                color_layout = QtWidgets.QHBoxLayout(color_widget)
                color_layout.setContentsMargins(0, 0, 0, 0)
                
                edit = QtWidgets.QLineEdit(str(self.settings_manager.get_setting(key, "")))
                edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #2d2d2d;
                        color: white;
                        border: 1px solid #555555;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QLineEdit:focus {
                        border-color: #0078d4;
                    }
                """)
                
                color_button = QtWidgets.QPushButton("Pick")
                color_button.setFixedWidth(60)
                color_button.setStyleSheet("""
                    QPushButton {
                        background-color: #0078d4;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: #106ebe;
                    }
                """)
                color_button.clicked.connect(partial(self.pick_color, edit))
                
                color_layout.addWidget(edit)
                color_layout.addWidget(color_button)
                
                self.fields[key] = edit
                self.layout.addRow(label_widget, color_widget)
            else:
                # Обычное поле для чисел и текста
                edit = QtWidgets.QLineEdit(str(self.settings_manager.get_setting(key, "")))
                edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #2d2d2d;
                        color: white;
                        border: 1px solid #555555;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QLineEdit:focus {
                        border-color: #0078d4;
                    }
                """)
                
                self.fields[key] = edit
                self.layout.addRow(label_widget, edit)
        
        # Дополнительные настройки
        self.setup_additional_settings()
        
        # Кнопки
        button_layout = QtWidgets.QHBoxLayout()
        
        self.buttonSave = QtWidgets.QPushButton("Save Settings")
        self.buttonSave.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.buttonSave.clicked.connect(self.save_settings)
        
        self.buttonReset = QtWidgets.QPushButton("Reset to Default")
        self.buttonReset.setStyleSheet("""
            QPushButton {
                background-color: #d13438;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b02c30;
            }
        """)
        self.buttonReset.clicked.connect(self.reset_to_default)
        
        self.buttonApply = QtWidgets.QPushButton("Apply")
        self.buttonApply.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
        """)
        self.buttonApply.clicked.connect(self.apply_settings)
        
        button_layout.addWidget(self.buttonSave)
        button_layout.addWidget(self.buttonApply)
        button_layout.addWidget(self.buttonReset)
        button_layout.addStretch()
        
        self.layout.addRow(button_layout)

    def setup_additional_settings(self):
        """Дополнительные настройки"""
        # Автосохранение
        auto_save_label = QtWidgets.QLabel("Auto-save interval (seconds)")
        auto_save_label.setToolTip("Интервал автосохранения в секундах (0 для отключения)")
        
        self.auto_save_edit = QtWidgets.QSpinBox()
        self.auto_save_edit.setRange(0, 3600)
        self.auto_save_edit.setValue(self.settings_manager.get_setting('auto_save_interval', 30))
        self.auto_save_edit.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        self.layout.addRow(auto_save_label, self.auto_save_edit)
        
        # Показ строки номеров
        self.show_line_numbers = QtWidgets.QCheckBox("Show line numbers")
        self.show_line_numbers.setChecked(self.settings_manager.get_setting('show_line_numbers', True))
        self.show_line_numbers.setStyleSheet("color: #ffffff;")
        self.layout.addRow(self.show_line_numbers)
        
        # Включение подсветки синтаксиса
        self.syntax_highlighting = QtWidgets.QCheckBox("Syntax highlighting")
        self.syntax_highlighting.setChecked(self.settings_manager.get_setting('syntax_highlighting', True))
        self.syntax_highlighting.setStyleSheet("color: #ffffff;")
        self.layout.addRow(self.syntax_highlighting)

    def pick_color(self, edit_widget):
        """Открыть диалог выбора цвета"""
        current_color = edit_widget.text()
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current_color), self, "Choose Color")
        if color.isValid():
            edit_widget.setText(color.name())

    def apply_theme(self):
        """Применить текущую тему"""
        first_color = self.settings_manager.get_setting('first_color', '#16171D')
        self.setStyleSheet(f"""
            SettingsWidget {{
                background-color: {first_color};
                color: #ffffff;
            }}
        """)

    def save_settings(self):
        """Сохранить настройки и закрыть"""
        self.apply_settings()
        self.close()

    def apply_settings(self):
        """Применить настройки без закрытия"""
        try:
            # Сохраняем основные настройки
            for key, edit in self.fields.items():
                self.settings_manager.set_setting(key, edit.text())
            
            # Сохраняем дополнительные настройки
            self.settings_manager.set_setting('auto_save_interval', self.auto_save_edit.value())
            self.settings_manager.set_setting('show_line_numbers', self.show_line_numbers.isChecked())
            self.settings_manager.set_setting('syntax_highlighting', self.syntax_highlighting.isChecked())
            
            # Обновляем интервал автосохранения в главном окне
            if hasattr(self.parent, 'auto_save_timer') and self.parent.auto_save_timer:
                interval = self.auto_save_edit.value() * 1000  # в миллисекунды
                if interval > 0:
                    self.parent.auto_save_timer.start(interval)
                else:
                    self.parent.auto_save_timer.stop()
            
            # Применяем тему
            self.apply_theme()
            
            # Обновляем UI родительского окна
            if self.parent:
                if hasattr(self.parent, 'apply_application_theme'):
                    self.parent.apply_application_theme()
                # Обновляем все открытые редакторы
                if hasattr(self.parent, 'tab_widget'):
                    for i in range(self.parent.tab_widget.count()):
                        editor = self.parent.tab_widget.widget(i)
                        if hasattr(editor, 'apply_theme'):
                            editor.apply_theme()
            
            # Показать сообщение об успехе
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText("Settings applied successfully!")
            msg.setWindowTitle("Success")
            msg.exec_()
            
        except Exception as e:
            # Показать сообщение об ошибке
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText(f"Error applying settings: {str(e)}")
            msg.setWindowTitle("Error")
            msg.exec_()

    def reset_to_default(self):
        """Сбросить настройки к значениям по умолчанию"""
        from utils.programs import EditorSettings
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to default values?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            default_settings = EditorSettings()
            
            # Сбрасываем основные поля
            for key, edit in self.fields.items():
                default_value = getattr(default_settings, key, "")
                edit.setText(str(default_value))
            
            # Сбрасываем дополнительные настройки
            self.auto_save_edit.setValue(30)
            self.show_line_numbers.setChecked(True)
            self.syntax_highlighting.setChecked(True)