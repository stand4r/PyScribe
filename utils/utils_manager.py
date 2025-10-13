from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt


class ThemeManager:
    def __init__(self):
        self.themes = {
            'dark': self.dark_theme,
            'light': self.light_theme,
            'blue': self.blue_theme,
        }
    
    @property
    def dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        return palette
    
    @property
    def light_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, Qt.black)
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(233, 231, 227))
        palette.setColor(QPalette.ToolTipBase, Qt.black)
        palette.setColor(QPalette.ToolTipText, Qt.black)
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, Qt.black)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(0, 0, 255))
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        return palette
    
    @property
    def blue_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 35, 45))
        palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.Base, QColor(20, 25, 35))
        palette.setColor(QPalette.AlternateBase, QColor(40, 45, 55))
        palette.setColor(QPalette.ToolTipBase, QColor(50, 55, 65))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(40, 45, 55))
        palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(100, 150, 255))
        palette.setColor(QPalette.Highlight, QColor(100, 150, 255))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        return palette
    
    def apply_theme(self, app, theme_name):
        theme = self.themes.get(theme_name, self.dark_theme)
        app.setPalette(theme)

# Глобальный экземпляр
theme_manager = ThemeManager()