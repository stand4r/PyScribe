from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont, QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit


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
        self.setFont(QFont("Times", 12))
        self.highlighter = WordHighlighter(self.document())
        self.filename = ""
        self.fullfilepath = ""
        self.language = ""
        self.highlighter.rehighlight()
        
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
            self.insertPlainText("  ")
        else:
            super().keyPressEvent(event)



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
            format.setForeground(QColor(Qt.white))
            pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
            patterns.append(pattern)
        format = QTextCharFormat()
        format.setForeground(QColor("#755651"))
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
