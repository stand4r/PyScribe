from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout
import ast


keywords = {
        "python": [
            'and', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'not', 'or', 'pass', 'print',
            'raise', 'return', 'try', 'while', 'yield',
            'None', 'True', 'False', "auto", 
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
    def __init__(self, parent=None, language="", d=[], settings={}):
        super(CodeTextEdit, self).__init__(parent)
        self.filename = ""
        self.fullfilepath = ""
        self.language = language
        self.settings = settings
        self.welcome = False
        self.main_color = self.settings["settings"]['main_color']#013B81
        self.text_color = self.settings["settings"]["text_color"]#ABB2BF
        self.first_color = self.settings["settings"]['first_color']#16171D
        self.second_color = self.settings["settings"]['second_color']#131313
        self.tab_color = self.settings["settings"]['tab_color']#1F2228
        self.languages = self.settings["languages"]
        self.font_size = int(self.settings["settings"]["fontsize"])
        self.dict = d
        '''self.completer = MyCompleter()
        self.completer.setWidget(self)
        self.completer.insertText.connect(self.insertCompletion)'''
        self.tabWidth = 4
        self.setFont(QFont("Courier New", self.font_size))
        self.setStyleSheet(
            f"background-color: {self.first_color};\n"
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
            self.setFont(QFont("Courier New", self.font_size)) 
    
    '''def insertCompletion(self, completion):
        tc = self.textCursor()
        extra = (len(completion) - len(self.completer.completionPrefix()))
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
        self.completer.popup().hide()

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        QPlainTextEdit.focusInEvent(self, event)'''

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
        '''
        tc = self.textCursor()
        if event.key() == Qt.Key_Tab and self.completer.popup().isVisible():
            self.completer.insertText.emit(self.completer.getSelected())
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            return

        QPlainTextEdit.keyPressEvent(self, event)
        tc.select(QTextCursor.WordUnderCursor)
        cr = self.cursorRect()

        if len(tc.selectedText()) > 0:
            self.completer.setCompletionPrefix(tc.selectedText())
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0,0))

            cr.setWidth(self.completer.popup().sizeHintForColumn(0) 
            + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cr)
        else:
            self.completer.popup().hide()
        '''
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
    def __init__(self, parent=None, language="", d=[],  settings={}):
        super(CodeEdit, self).__init__(parent)
        self.language = language
        self.filename = ""
        self.fullfilepath = ""
        self.settings = settings
        self.welcome = False
        self.fontSize = int(self.settings["settings"]["fontsize"])
        self.first_color = self.settings["settings"]["first_color"]
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.textedit = CodeTextEdit(self, language=language, d=d, settings=self.settings)
        self.labelCount = QPlainTextEdit(self)
        self.labelCount.setReadOnly(True)
        self.labelCount.setStyleSheet(f"padding-left: 12px; color: #ABB2BF; width: 0px;\n padding-top: 10px;\n" 
                                        f"background-color: {self.first_color}; padding-bottom: 20px; letter-spacing:1px; border: 2px solid {self.first_color}; border-right-color: #282C34;")
        self.labelCount.setFixedWidth(70)
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
        self.textedit.verticalScrollBar().setValue(value)
        self.labelCount.verticalScrollBar().setValue(value)

    def changeCount(self, value):
        self.labelCount.setPlainText("")
        self.labelCount.insertPlainText("\n".join([f"{round(i, 2):>3}" for i in range(self.textedit.blockCount())]))
        self.labelCount.verticalScrollBar().setValue(value)

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
                format.setForeground(QColor("#c77a5a"))
                pattern = (rf'\b{word}\b', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            for word in braces:
                format = QTextCharFormat()
                format.setForeground(QColor(Qt.yellow))
                pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            for word in operators:
                format = QTextCharFormat()
                format.setForeground(QColor("#c77a5a"))
                pattern = (rf'{word}', format)  # Use raw f-string for regex patterns
                self.patterns.append(pattern)
            format = QTextCharFormat()
            format.setForeground(QColor("#FFFF9C"))
            self.patterns.append((r'#.*$', format))
            self.patterns.append((rf'"([^"]+)"', format))
            self.patterns.append((rf"'([^']+)'", format))
            self.patterns.append((rf"''", format))
            self.patterns.append((rf'""', format))
            '''format = QTextCharFormat()
            format.setForeground(QColor("#fffdd0"))
            self.patterns.append((r"\bself\b", format))'''
            format = QTextCharFormat()
            format.setForeground(QColor(Qt.yellow))
            self.patterns.append((rf'\b#include\b', format))
            format = QTextCharFormat()
            format.setForeground(QColor("#7777FF"))
            self.patterns.append((r'class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]', format))
            format = QTextCharFormat()
            format.setForeground(QColor("#00C200"))
            self.patterns.append((r'[A-Za-z_][A-Za-z0-9_]*\s*\(', format))
            format = QTextCharFormat()
            format.setForeground(QColor("#7777FF"))
            self.patterns.append((r'\b\d+\b', format))
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

    def __init__(self, parent=None):
        QCompleter.__init__(self, ["test","foo","bar"], parent)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.highlighted.connect(self.setHighlighted)

    def setHighlighted(self, text):
        self.lastSelected = text

    def getSelected(self):
        return self.lastSelected
    
class CodeAnalyzer:
    def __init__(self):
        self.keywords = [
            'and', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'exec', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'not', 'or', 'pass', 'print',
            'raise', 'return', 'try', 'while', 'yield',
            'None', 'True', 'False', 'self', "auto", 
            "break", "case", "char", "const", "continue"
            ]
        self.defined_names = []  # Переменные и функции, определенные в коде

    def analyze_code(self, code):
        self.defined_names = []  # Сброс списка определенных имен
        # Анализируем текст кода, чтобы найти определения функций и переменных
        
        # Разбираем код в абстрактное синтаксическое дерево (AST)
        tree = ast.parse(code)

        # Обходим AST, чтобы найти все определения и импорты
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Если узел - определение функции, добавляем ее имя в словарь
                self.defined_names += node.name
            elif isinstance(node, ast.ClassDef):
                # Если узел - определение класса, добавляем его имя в словарь
                self.defined_names += node.name
            elif isinstance(node, ast.Import):
                # Если узел - импорт, добавляем имена импортированных модулей в словарь
                for alias in node.names:
                    self.defined_names += alias.name.split(".")[0]
        import re
        variable_pattern = r'\b([A-Za-z_][A-Za-z0-9_]*)\b(?=[^\(]*\))'  # Регулярное выражение для определения переменных
        self.defined_names += re.findall(variable_pattern, code)

    def get_auto_complete_dict(self):
        return {name: '' for name in self.defined_names if name not in self.keywords}  # Возвращаем словарь для автодополнения
