# utils/programs/__init__.py
class EditorSettings:
    def __init__(self):
        # Цвета
        self.main_color = "#25263b"
        self.text_color = "#ffffff"
        self.first_color = "#131313"
        self.second_color = "#1e1e1e"
        self.tab_color = "#0078d4"
        
        # Шрифты
        self.fontsize = "14"
        self.font_size_tab = "12"
        
        # Дополнительные настройки
        self.auto_save_interval = 30
        self.show_line_numbers = True
        self.syntax_highlighting = True
        self.word_wrap = False