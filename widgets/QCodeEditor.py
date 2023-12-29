from PyQt5.QtCore import Qt, QRegExp, pyqtSlot
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont, QTextCursor, QPainter, QFontMetrics, QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QAction, QShortcut
import ast



keywords = [
            'and', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'not', 'or', 'pass', 'print',
            'raise', 'return', 'try', 'while', 'yield',
            'None', 'True', 'False', 'self', "auto", 
            "break", "case", "char", "const", "continue", 
            "default", "do", "double", "else", "enum", "extern", 
            "float", "for", "goto", "if", "int",
            "long", "register", "return", "short", "signed", 
            "sizeof", "static", "struct", "switch", "typedef", 
            "union", "unsigned", "void", "volatile", "while",
            "asm", "auto", "bool", "break", "case", "catch", "char", "class", "const",
            "const_cast", "continue", "default", "delete", "do", "double", "dynamic_cast",
            "else", "enum", "explicit", "export", "extern", "false", "float", "for",
            "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace",
            "new", "operator", "private", "protected", "public", "register", "reinterpret_cast",
            "return", "short", "signed", "sizeof", "static", "static_cast", "struct",
            "switch", "template", "this", "throw", "true", "try", "typedef", "typeid",
            "typename", "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t",
            "while"]

operators = [
            '=',
            # Comparison
            '==', '!=', '<', '<=', '>', '>=',
            # Arithmetic
            '\+', '-', '\*', '/', '//', '\%', '\*\*',
            # In-place
            '\+=', '-=', '\*=', '/=', '\%=',
            # Bitwise
            '\^', '\|', '\&', '\~', '>>', '<<',
        ]

braces = [
            '\{', '\}', '\(', '\)', '\[', '\]',
        ]


class CodeTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super(CodeTextEdit, self).__init__(parent)
        self.fontSize = 14
        self.setFont(QFont("Console", self.fontSize))
        self.highlighter = WordHighlighter(self.document())
        self.filename = ""
        self.fullfilepath = ""
        self.language = ""
        self.tabWidth = 4
        self.setStyleSheet(
            "background-color:#131313;\n"
            "color: #ffffff;\n"
            "padding-top: 20px;\n"
            "padding-bottom: 20px;\n"
            "padding-left: 20px;\n"
            "padding-right:20px;\n"
            "letter-spacing:1px;\n"
            "line-height: 15px;\n"
            )
        self.shortcutAdd = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self.shortcutAdd.activated.connect(self.addFontSize)
        self.shortcutPop = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcutPop.activated.connect(self.popFontSize)
        self.highlighter.rehighlight()

    @pyqtSlot()
    def addFontSize(self):
        self.fontSize+=1
        self.setFont(QFont("Console", self.fontSize))

    @pyqtSlot()
    def popFontSize(self):
        self.fontSize-=1
        self.setFont(QFont("Console", self.fontSize))
        
    def addText(self, text):
        self.insertPlainText(text)
        self.highlighter.rehighlight()
        
    def set_highlight_words(self, words, color):
        self.highlighter.set_patterns(words, color)

    def keyPressEvent(self, event):
        if event.text() in  ["'", '"', "(", "{", "["]:
            if event.text() == '"':
                self.insertPlainText('""')
            elif event.text() == "'":
                self.insertPlainText("''")
            elif event.text() == "(":
                self.insertPlainText("()")
            elif event.text() == "[":
                self.insertPlainText("[]")
            elif event.text() == "{":
                self.insertPlainText("{}")

            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
        elif event.key() == Qt.Key_Tab:
            self.insertPlainText(" "*self.tabWidth)
        elif event.key() in [Qt.Key_Enter, Qt.Key_Return]:
              # Вставляем новую строку
            cursor = self.textCursor()
            line = cursor.block().text()

            # Считаем количество пробелов в начале текущей строки
            spaces = len(line) - len(line.lstrip(' '))
            indentation = ' ' * spaces

            # Проверяем, заканчивается ли предыдущая строка на особые слова
            if line.strip().endswith(('if', 'for', 'while', 'else', 'elif', ':')):
                indentation += ' ' * self.tabWidth  # Добавляем отступ
            self.insertPlainText('\n')
            self.insertPlainText(indentation)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        font = painter.font()
        font.setPointSize(self.fontSize-1)  # Задаем размер шрифта для счетчика строк
        painter.setFont(font)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # Определяем видимые блоки и рисуем номера строк
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#fdfff5"))
                painter.drawText(0, int(top), self.viewport().width(), self.fontMetrics().height(), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def linenumberarea_paint_event(self, event):
        """
        Paint the line number area.
        """
        if self._linenumber_enabled:
            painter = QPainter(self.linenumberarea)
            painter.fillRect(
                event.rect(),
                self._highlighter.get_sideareas_color(),
            )

            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = round(self.blockBoundingGeometry(block).translated(
                self.contentOffset()).top())
            bottom = top + round(self.blockBoundingRect(block).height())

            font = painter.font()
            font.setPointSize(12)
            active_block = self.textCursor().block()
            active_line_number = active_block.blockNumber() + 1

            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    number = block_number + 1

                    if number == active_line_number:
                        font.setWeight(font.Bold)
                        painter.setFont(font)
                        painter.setPen(
                            self._highlighter.get_foreground_color())
                    else:
                        font.setWeight(font.Normal)
                        painter.setFont(font)
                        painter.setPen(QColor(Qt.darkGray))
                    right_padding = self.linenumberarea._right_padding
                    painter.drawText(
                        0,
                        top,
                        self.linenumberarea.width() - right_padding,
                        self.fontMetrics().height(),
                        Qt.AlignRight, str(number),
                    )

                block = block.next()
                top = bottom
                bottom = top + round(self.blockBoundingRect(block).height())
                block_number += 1


class WordHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super(WordHighlighter, self).__init__(parent)
        self.set_patterns()

    def set_patterns(self):
        self.patterns = self.create_patterns()

    def create_patterns(self):
        patterns = []
        for word in keywords:
            format = QTextCharFormat()
            if word == 'self':
                format.setFontItalic(True)
            format.setForeground(QColor(Qt.cyan))
            pattern = (rf'\b{word}\b', format)  # Use raw f-string for regex patterns
            patterns.append(pattern)
        for word in braces:
            format = QTextCharFormat()
            format.setForeground(QColor(Qt.yellow))
            pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
            patterns.append(pattern)
        for word in operators:
            format = QTextCharFormat()
            format.setForeground(QColor("#eedc5b"))
            pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
            patterns.append(pattern)
        format = QTextCharFormat()
        format.setForeground(QColor("#639AC1"))
        patterns.append((rf'"([^"]+)"', format))
        patterns.append((rf"'([^']+)'", format))
        patterns.append((rf"''", format))
        patterns.append((rf'""', format))
        format = QTextCharFormat()
        format.setForeground(QColor(Qt.yellow))
        pattern = (rf'\b#include\b', format)  # Use raw f-string for regex patterns
        patterns.append(pattern)

        return patterns

    def highlightBlock(self, text):
        for pattern, format in self.patterns:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)


def format_code(code):
    tree = ast.parse(code)
    ast.fix_missing_locations(tree)

    class IndentVisitor(ast.NodeVisitor):
        def __init__(self):
            self.indentation_level = 0

        def generic_visit(self, node):
            ast.NodeVisitor.generic_visit(self, node)
            if isinstance(node, (ast.FunctionDef, ast.With)):
                self.indentation_level += 1

        def visit(self, node):
            node.lineno = node.lineno + self.indentation_level
            return ast.NodeVisitor.visit(self, node)

        def depart(self, node):
            if isinstance(node, (ast.FunctionDef, ast.With)):
                self.indentation_level -= 1

    visitor = IndentVisitor()
    visitor.visit(tree)
    formatted_code = ast.unparse(tree)
    
    return formatted_code