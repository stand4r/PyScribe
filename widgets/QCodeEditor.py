from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout
import ast
from os import remove
import subprocess
import tempfile


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

patterns = {
    "python": {
            (r"\band\b", "#c77a5a"), (r"\bassert\b", "#c77a5a"), (r"\bbreak\b", "#c77a5a"),
            (r"\bcontinue\b", "#c77a5a"), (r"\bdef\b", "#c77a5a"), (r"\bdel\b", "#c77a5a"), 
            (r"\belif\b", "#c77a5a"),  (r"\belse\b", "#c77a5a"), (r"\bexcept\b", "#c77a5a"), 
            (r"\bexec\b", "#c77a5a"), (r"\bfinally\b", "#c77a5a"), (r"\bfor\b", "#c77a5a"), 
            (r"\bfrom\b", "#c77a5a"), (r"\bglobal\b", "#c77a5a"), (r"\bglobal\b", "#c77a5a"), 
            (r"\bif\b", "#c77a5a"), (r"\bimport\b", "#c77a5a"), (r"\bin\b", "#c77a5a"), 
            (r'\bis\b', "#c77a5a"), (r'\blambda\b', "#c77a5a"), (r'\bnot\b', "#c77a5a"), (r'\bor\b', "#c77a5a"), 
            (r'\bpass\b', "#c77a5a"), (r'\braise\b', "#c77a5a"), (r'\bis\b', "#c77a5a"), (r'\bis\b', "#c77a5a"), 
            (r'\bis\b', "#c77a5a"), (r'\bprint\b', "#c77a5a"), (r'\breturn\b', "#c77a5a"), (r'\btry\b', "#c77a5a"), 
            (r'\bwhile\b', "#c77a5a"), (r'\byield\b', "#c77a5a"), (r'\bNone\b', "#c77a5a"), (r'\bTrue\b', "#c77a5a"), 
            (r'\bFalse\b', "#c77a5a"), (r'\bauto\b', "#c77a5a"), (r'\bbreak\b', "#c77a5a"), (r'\bcase\b', "#c77a5a"), 
            (r'\bchar\b', "#c77a5a"), (r'\bconst\b', "#c77a5a"),
            (r'#.*$', "#FFFF9C"), (rf'"([^"]+)"', "#FFFF9C"), (rf"''", "#FFFF9C"), (rf'""', "#FFFF9C"), 
            (r'class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]', "#7777FF"),
            (r'[A-Za-z_][A-Za-z0-9_]*\s*\('), (r'\b\d+\b', "#00C200"), 
            (r'\b\d+\b', "#7777FF"), (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"), 
            (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"), 
            (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"), 
            (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"), 
            (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"), 
            (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"), 
            (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"), 
            (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
    "c": {
        (r'\b\d+\b', "#7777FF"), (r"\{", "#ffff00"), (r"\}", "#ffff00"), (rf"\(", "#ffff00"), (rf"\)", "#ffff00"), 
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"), 
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"), 
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"), 
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"), 
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"), 
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"), 
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
    "cpp": {
        (r'\b\d+\b', "#7777FF"), (r"\{", "#ffff00"), (r"\}", "#ffff00"), (rf"\(", "#ffff00"), (rf"\)", "#ffff00"), 
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"), 
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"), 
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"), 
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"), 
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"), 
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"), 
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    }
}


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
        self.analyzer = CodeAnalyzer(self.language)
        self.blockCountChanged.connect(self.analyzeCode)
        self.completer = MyCompleter(self.dict, self.first_color, self.font_size)
        self.completer.setWidget(self)
        self.completer.insertText.connect(self.insertCompletion)
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
        if self.language == "python":
            self.textChanged.connect(self.analyzeAndHighlightErrors)
        if self.language == "bin" or self.language == "out" or self.language == "exe":
            self.setReadOnly(True)
            self.setFont(QFont("Courier New", self.font_size)) 

    def analyzeAndHighlightErrors(self):
        code = self.toPlainText()

        # Создаем временный файл для кода
        with open("temp_file.py", "w") as temp_file:
            temp_file.write(code)

        # Запускаем процесс flake8 на временном файле
        try:
            result = subprocess.check_output(["python -m flake8 temp_file.py"], shell=True)
            output = result.stdout
            errors = self.parseFlake8Output(output)
            self.highlightCodeErrors(errors)
        except subprocess.CalledProcessError as e:
            print("Error while running flake8:", e.stderr)
        remove("temp_file.py")

    def parseFlake8Output(self, output):
        errors = []
        for line in output.split('\n'):
            if line:
                parts = line.split(':')
                line_number = int(parts[1])
                column = int(parts[2])
                errors.append((line_number, column))
        return errors

    def highlightCodeErrors(self, errors):
        for (line, _) in errors:
            start_pos = self.document().findBlockByLineNumber(line - 1).position()
            text_cursor = QTextCursor(self.document())
            text_cursor.setPosition(start_pos)
            text_cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            self.error_format = self.text_edit.currentCharFormat()
            self.error_format.setBackground(Qt.red)
            text_cursor.setCharFormat(self.error_format)

    def analyzeCode(self):
        if self.toPlainText() != "":
            self.analyzer.analyze_code(self.toPlainText())
            self.dict = self.analyzer.get_auto_complete_dict()
            self.completer.update(self.dict)

    def insertCompletion(self, completion):
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
        QPlainTextEdit.focusInEvent(self, event)

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
        tc = self.textCursor()
        if event.key() == Qt.Key_Tab:
            if self.completer.popup().isVisible():  # Если виджет автодополнения видим
                inserted_text = self.completer.getSelected()  # Получаем выбранный текст из виджета автодополнения
                if inserted_text:
                    cursor_position = tc.position()  # Получаем начальное положение курсора
                    tc.select(QTextCursor.WordUnderCursor)  # Выбираем слово, над которым находится курсор
                    tc.removeSelectedText()  # Удаляем текст, над которым находится курсор
                    self.setTextCursor(tc)  # Устанавливаем обновленное положение курсора
                    self.insertPlainText(inserted_text)  # Вставляем выбранный текст
                    self.completer.popup().hide()
                    return
            else:
                self.insertPlainText(" "*self.tabWidth)
        

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


        elif event.key() in [Qt.Key_Enter, Qt.Key_Return] and self.language in ["python", "c", "cpp"]:
            self.completer.popup().hide()
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
            if event.key() == Qt.Key_Backspace:
                self.completer.popup().hide()  # Скрываем popup при удалении последнего символа
            tc.select(QTextCursor.WordUnderCursor)
            cr = self.cursorRect()
            if event.text() not in [".", "[", "{", "("]:
                if len(tc.selectedText()) > 0:
                    prefix = tc.selectedText()  # Получаем выбранный текст для установки в качестве префикса автодополнения
                    if "." in prefix:
                        prefix = prefix.split(".")[-1]
                    self.completer.setCompletionPrefix(prefix)
                    popup = self.completer.popup()
                    popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                    cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width()) 
                    self.completer.complete(cr)  # Запускаем автодополнение
            else:
                self.completer.popup().hide()  # Если ничего не выбрано, скрываем всплывающий список
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
            for i in patterns[self.language]:
                self.patterns.append((i[0], QColor(i[1])))
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

    def __init__(self, d=[], backcolor="", fontsize=11, parent=None):
        QCompleter.__init__(self, d, parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)  # Нечувствительность к регистру
        self.setFilterMode(Qt.MatchContains)  # Фильтрация по вхождению
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.popup().setFixedWidth(200)
        self.highlighted.connect(self.setHighlighted)
        self.popup().setStyleSheet(f"font-size: {fontsize-1}pt;"
                                   "QListView { background-color: "+backcolor+"; color: white; padding: 2px; border: 1px solid lightgray;} "
                                   "QFrame {border: 1px solid #ccc; padding: 2px;}"
                                   "QListView::item:selected { background-color: lightgray;}"
                                   "QListView::item {height: 30px;}")

    def update(self, d):
        model = QStringListModel()
        model.setStringList(d)
        self.setModel(model)

    def complete(self, rect):
        # Рассчитываем позицию попапа относительно курсора
        point = QPoint(rect.left(), rect.top() + rect.height())
        global_point = rect.bottomLeft() + point

        # Перемещаем попап QCompleter
        self.popup().move(global_point)

        super().complete(rect)

    def setHighlighted(self, text):
        self.lastSelected = text

    def getSelected(self):
        return self.lastSelected
    
class CodeAnalyzer:
    def __init__(self, lang):
        self._lang = lang
        self.defined_names = keywords[self._lang]

    def analyze_code(self, code):
        if self._lang == "python":
            import re
            self.defined_names = keywords[self._lang]  # Сброс списка определенных имен
            # Анализируем текст кода, чтобы найти определения функций и переменных
            try:
            # Разбираем код в абстрактное синтаксическое дерево (AST)
                tree = ast.parse(code)

                # Обходим AST, чтобы найти все определения и импорты
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Если узел - определение функции, добавляем ее имя в словарь
                        if node.name not in self.defined_names:
                            self.defined_names += node.name
                    elif isinstance(node, ast.ClassDef):
                        # Если узел - определение класса, добавляем его имя в словарь
                        if node.name not in self.defined_names:
                            self.defined_names += node.name
                        for n in node.body:
                            if isinstance(n, ast.FunctionDef):
                                if node.name not in self.defined_names:
                                    self.defined_names += n.name
                    elif isinstance(node, ast.Import):
                        # Если узел - импорт, добавляем имена импортированных модулей в словарь
                        for alias in node.names:
                            if node.name not in self.defined_names:
                                self.defined_names += alias.name.split(".")[0]
            except:
                function_pattern = r'def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(' 
                self.defined_names += re.findall(function_pattern, code)
            variable_pattern = r'\b([A-Za-z_][A-Za-z0-9_]*)\b(?=[^\(]*\))'  # Регулярное выражение для определения переменных
            self.defined_names += re.findall(variable_pattern, code)
        elif self._lang == "c":
            c_language_dictionary = [
                "auto", "double", "int", "struct", "break", "else", "long", "switch",
                "case", "enum", "register", "typedef", "char", "extern", "return", "union",
                "continue", "for", "signed", "void", "do", "if", "static", "while",
                "default", "goto", "sizeof", "volatile", "const", "float", "short", "unsigned"
            ]

            c_standard_library = [
                "assert", "errno", "time", "stdlib", "stdio", "math", "string"  # И другие стандартные библиотеки C
            ]
            
            import ply.lex as lex
            import ply.yacc as yacc
            tokens = (
                'VAR',  # Переменная
                'FUNC',  # Функция
                # Другие токены, такие как INT, FLOAT и т.д.
            )

            # Определение правил для токенов
            def t_VAR(t):
                r'[a-zA-Z_][a-zA-Z0-9_]*'
                # Добавляем переменную в список
                variables.append(t.value)
                return t

            def t_FUNC(t):
                r'[a-zA-Z_][a-zA-Z0-9_]*\('
                # Добавляем имя функции в список
                functions.append(t.value[:-1])
                return t

            # Другие правила для токенов

            # Запуск парсера
            def parse_c_code(code):
                lexer = lex.lex()
                lexer.input(code)
                for token in lexer:
                    pass  # Парсинг всех токенов

            # Пример использования парсера
            variables = []
            functions = []
            parse_c_code(code)
            self.defined_names += variables
            self.defined_names += functions
            self.defined_names += c_language_dictionary
            self.defined_names += c_standard_library
        elif self._lang == "cpp":
            variable_pattern = r'\b\w+\s+\w+\s*=\s*.*;'
            function_pattern = r'\b\w+\s+\w+\(.*\)\s*{'

            # Извлечение переменных
            variables = re.findall(variable_pattern, code)

            # Извлечение функций
            functions = re.findall(function_pattern, code)
            self.defined_names += variables
            self.defined_names += functions
        

    def get_auto_complete_dict(self):
        return list(set([name for name in self.defined_names]))  # Возвращаем словарь для автодополнения
