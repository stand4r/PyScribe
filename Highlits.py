from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter
from pygments import lexers, formatters, highlight

class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lang):
        super().__init__(document)
        self.format = QTextCharFormat()
        self.format.setForeground(QColor(50, 50, 50))  # устанавливаем цвет текста
        self.format.setFontWeight(QFont.Bold)  # делаем текст жирным

        lexer = lexers.get_lexer_by_name(lang)  # создаем лексер для языка Python
        formatter = formatters.get_formatter_by_name("html")  # создаем форматтер для HTML

        self.highlighter = lambda text: highlight(text, lexer, formatter)  # создаем функцию для подсветки синтаксиса

    def highlightBlock(self, text):
        highlighted_code = self.highlighter(text)  # подсвечиваем текущий блок текста
        self.document().blockSignals(True)  # блокируем сигналы документа
        self.setFormat(0, len(text), self.format)  # устанавливаем формат для всего блока
        self.document().setHtml(highlighted_code)  # устанавливаем HTML с подсвеченным кодом в документ
        self.document().blockSignals(False)  # разблокируем сигналы документа