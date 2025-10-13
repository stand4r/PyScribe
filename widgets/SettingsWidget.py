from functools import partial
from PyQt5 import QtWidgets, QtCore, QtGui
from utils.programs import settings_manager

class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, settings, pathSettings):
        super().__init__()
        self.path_settings = pathSettings
        self.settings = settings
        self.mode = -2
        self.setupUi()

    def setupUi(self):
        self.setStyleSheet(f"background-color: {settings_manager.get_setting('first_color')};\n"
                           "color: #ffffff;")
        
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
            
            edit = QtWidgets.QLineEdit(str(settings_manager.get_setting(key)))
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
        
        button_layout.addWidget(self.buttonSave)
        button_layout.addWidget(self.buttonReset)
        button_layout.addStretch()
        
        self.layout.addRow(button_layout)

    def save_settings(self):
        """Сохранить настройки"""
        for key, edit in self.fields.items():
            settings_manager.set_setting(key, edit.text())
        
        # Показать сообщение об успехе
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText("Settings saved successfully!")
        msg.setWindowTitle("Success")
        msg.exec_()
        
        # Закрыть виджет
        self.close()

    def reset_to_default(self):
        """Сбросить настройки к значениям по умолчанию"""
        from utils.programs import EditorSettings
        default_settings = EditorSettings()
        
        for key, edit in self.fields.items():
            default_value = getattr(default_settings, key)
            edit.setText(str(default_value))