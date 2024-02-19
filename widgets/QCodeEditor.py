from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont, QTextCursor, QPainter, QKeySequence
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QTextEdit,QWidget, QHBoxLayout, QLabel
import ast



keywords = {
        "python": [
            'and', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'not', 'or', 'pass', 'print',
            'raise', 'return', 'try', 'while', 'yield',
            'None', 'True', 'False', 'self', "auto", 
            "break", "case", "char", "const", "continue"
            ],

        "cpp": [
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
            "while"
            ],

        "c": [
            'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do', 
            'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'int', 'long',
            'register', 'return', 'short', 'signed', 'sizeof', 'static', 'struct', 'switch',
            'typedef', 'union', 'unsigned', 'void', 'volatile', 'while'
    ]}

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
    def __init__(self, parent=None, language="", d=[]):
        super(CodeTextEdit, self).__init__(parent)
        self.fontSize = 14
        self.setFont(QFont("Courier New", self.fontSize))
        self.filename = ""
        self.fullfilepath = ""
        self.language = language
        self.dict = d
        self.tabWidth = 4
        self.setStyleSheet(
            "background-color: #16171D;\n"
            "color: #ffffff;\n"
            "padding: 20px;\n"
            "padding-top: 10px;\n"
            "letter-spacing:1px;\n"
            "width: 0px;\n"
            "border: none"
            )
        self.highlighter = WordHighlighter(self.document(), self.language)
        self.highlighter.rehighlight()
        if self.language == "bin" or self.language == "out" or self.language == "exe":
            self.setReadOnly(True)
            self.setFont(QFont("Courier New", self.fontSize))    

    def convert_to_hex(self, content):
        hex_string = ""
        ascii_string = ""
        content_length = len(content)
        padding_space = "  " * 16

        for i, byte in enumerate(content):
            if i % 16 == 0:
                if i > 0:
                    hex_string += f"   {ascii_string}\n"
                hex_string += "{:08X}   ".format(i)
                ascii_string = ""
            ascii_string += chr(byte) if 32 <= byte <= 126 else "."
            hex_string += f"{byte:02X} "
        return hex_string.strip()

    def addText(self, text):
        try:
            self.insertPlainText(text)
        except TypeError:
            hex_content = self.convert_to_hex(text)
            self.setPlainText(hex_content)
        
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
            elif event.text() == "<":
                self.insertPlainText("<>")

            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
            self.setTextCursor(cursor)
        elif event.key() == Qt.Key_Tab:
            self.insertPlainText(" "*self.tabWidth)
        elif event.key() in [Qt.Key_Enter, Qt.Key_Return] and self.language in ["python", "c", "cpp"]:
            if self.language == "python":
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
            elif self.language in ["c", "cpp"]:
                cursor = self.textCursor()
                line = cursor.block().text()

                # Считаем количество пробелов в начале текущей строки
                spaces = len(line) - len(line.lstrip(' '))
                indentation = ' ' * spaces
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)

                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)

                symbol = cursor.selectedText()
                if symbol == "{":
                    indentation += ' ' * self.tabWidth
                    self.insertPlainText("\n\n")  # Добавляем отступ
                    cursor.movePosition(QTextCursor.Up)
                    self.setTextCursor(cursor)
                    self.insertPlainText(indentation)
                else:
                    self.insertPlainText("\n"+indentation)
        else:
            super().keyPressEvent(event)


class CodeEdit(QWidget):
    def __init__(self, parent=None, language="", d=[]):
        super(CodeEdit, self).__init__(parent)
        self.language = language
        self.fontSize = 14
        self.filename = ""
        self.fullfilepath = ""
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.textedit = CodeTextEdit(self, language=language, d=d)
        self.labelCount = QPlainTextEdit(self)
        self.labelCount.setReadOnly(True)
        self.labelCount.setStyleSheet("padding-left: 12px; color: #ABB2BF; width: 0px;\n padding-top: 10px;\n" 
                                        "background-color: #16171D; padding-bottom: 20px; letter-spacing:1px; border: 2px solid #16171D; border-right-color: #282C34;")
        self.labelCount.setFixedWidth(90)
        self.labelCount.setFont(QFont("Courier New", self.fontSize))
        self.textedit.blockCountChanged.connect(self.changeCount)
        self.textedit.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.labelCount.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.layout.addWidget(self.labelCount, 1)
        self.layout.addWidget(self.textedit, 10) 
        self.setLayout(self.layout)
        self.shortcutAdd = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self.shortcutAdd.activated.connect(self.addFontSize)
        self.shortcutPop = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcutPop.activated.connect(self.popFontSize)
        self.shortcutEnd = QShortcut(QKeySequence("Ctrl+Down"), self)
        self.shortcutEnd.activated.connect(self.moveCursorToEnd)
        self.shortcutStart = QShortcut(QKeySequence("Ctrl+Up"), self)
        self.shortcutStart.activated.connect(self.moveCursorToStart)

    def sync_scroll(self, value):
        self.labelCount.verticalScrollBar().setValue(value)
        self.textedit.verticalScrollBar().setValue(value)

    def changeCount(self):
        self.labelCount.setPlainText("")
        self.labelCount.insertPlainText("\n".join([str(i+1) for i in range(self.textedit.blockCount())]))

    def addText(self, text):
        self.textedit.addText(text)
    
    def setPlainText(self, text):
        self.textedit.setPlainText(text)

    def toPlainText(self):
        return self.textedit.toPlainText()

    @pyqtSlot()
    def addFontSize(self):
        self.fontSize += 1
        self.textedit.setFont(QFont("Courier New", self.fontSize))
        self.labelCount.setFont(QFont("Courier New", self.fontSize))

    @pyqtSlot()
    def popFontSize(self):
        if self.fontSize > 1:
            self.fontSize -= 1
            self.textedit.setFont(QFont("Courier New", self.fontSize))
            self.labelCount.setFont(QFont("Courier New", self.fontSize))

    @pyqtSlot()
    def moveCursorToEnd(self):
        self.textedit.moveCursor(QTextCursor.End)
        self.labelCount.moveCursor(QTextCursor.End)
    
    @pyqtSlot()
    def moveCursorToStart(self):
        self.labelCount.moveCursor(QTextCursor.Start)
        self.textedit.moveCursor(QTextCursor.Start)


class WordHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, language):
        super(WordHighlighter, self).__init__(parent)
        self.language = language
        self.patterns = []
        self.set_patterns()

    def set_patterns(self):
        self.create_patterns()

    def create_patterns(self):
        try:
            for word in keywords[self.language]:
                format = QTextCharFormat()
                if word == 'self':
                    format.setFontItalic(True)
                format.setForeground(QColor(Qt.cyan))
                pattern = (rf'\b{word}\b', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            for word in braces:
                format = QTextCharFormat()
                format.setForeground(QColor(Qt.yellow))
                pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            for word in operators:
                format = QTextCharFormat()
                format.setForeground(QColor("#eedc5b"))
                pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            format = QTextCharFormat()
            format.setForeground(QColor("#639AC1"))
            self.patterns.append((rf'"([^"]+)"', format))
            self.patterns.append((rf"'([^']+)'", format))
            self.patterns.append((rf"''", format))
            self.patterns.append((rf'""', format))
            format = QTextCharFormat()
            format.setForeground(QColor(Qt.yellow))
            pattern = (rf'\b#include\b', format)  # Use raw f-string for regex patterns
            self.patterns.append(pattern)

            return self.patterns
        except:
            return []

    def highlightBlock(self, text):
        if self.patterns != []:
            for pattern, format in self.patterns:
                expression = QRegExp(pattern)
                index = expression.indexIn(text)
                while index >= 0:
                    length = expression.matchedLength()
                    self.setFormat(index, length, format)
                    index = expression.indexIn(text, index + length)


class MyCompleter(QCompleter):
    insertText = pyqtSignal(str)

    def __init__(self, d=[], parent=None):
        QCompleter.__init__(self, d, parent)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.highlighted.connect(self.setHighlighted)

    def setHighlighted(self, text):
        self.lastSelected = text

    def getSelected(self):
        return self.lastSelected