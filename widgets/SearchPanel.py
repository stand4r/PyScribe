"""PyScribe widgets/SearchPanel.py: application module and reusable component."""
from pathlib import Path
import re
from PyQt5 import QtCore, QtWidgets, QtGui


class SearchPanel(QtWidgets.QWidget):
    open_file_requested = QtCore.pyqtSignal(str)
    open_match_requested = QtCore.pyqtSignal(str, int)

    SKIP_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', 'dist', 'build'}
    BINARY_SUFFIXES = {
        '.bin', '.exe', '.out', '.dll', '.so', '.dylib', '.elf', '.hex', '.rom',
        '.img', '.iso', '.dat', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp',
        '.ico', '.pyc', '.pyd', '.class', '.jar', '.zip', '.7z', '.rar', '.gz',
        '.mp3', '.mp4', '.wav', '.woff', '.woff2', '.ttf', '.otf'
    }
    MAX_FILE_BYTES = 2 * 1024 * 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self.root_path = Path.cwd()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('ПОИСК')
        title.setObjectName('sideTitle')
        title.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E; letter-spacing: 1px;")
        title_row.addWidget(title)
        title_row.addStretch()
        self.result_count = QtWidgets.QLabel('')
        self.result_count.setStyleSheet('color:#858585; font-size:11px;')
        title_row.addWidget(self.result_count)
        layout.addLayout(title_row)

        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText('Поиск по файлам')
        self.query.setMinimumHeight(32)
        self.query.setClearButtonEnabled(True)
        self.query.setObjectName('searchQuery')
        self.query.returnPressed.connect(self.search)
        layout.addWidget(self.query)

        options = QtWidgets.QHBoxLayout()
        options.setSpacing(4)
        self.case_sensitive = QtWidgets.QToolButton()
        self.case_sensitive.setText('Aa')
        self.case_sensitive.setToolTip('Учитывать регистр (Aa)')
        self.case_sensitive.setCheckable(True)
        self.whole_word = QtWidgets.QToolButton()
        self.whole_word.setText('ab')
        self.whole_word.setToolTip('Слово целиком (ab)')
        self.whole_word.setCheckable(True)
        self.regex = QtWidgets.QToolButton()
        self.regex.setText('.*')
        self.regex.setToolTip('Регулярное выражение (.*)')
        self.regex.setCheckable(True)
        for button in (self.case_sensitive, self.whole_word, self.regex):
            button.setMinimumSize(32, 28)
            button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            options.addWidget(button)
        options.addStretch()
        self.search_button = QtWidgets.QToolButton()
        self.search_button.setText('⌕ Искать')
        self.search_button.setToolTip('Искать по проекту')
        self.search_button.setMinimumHeight(30)
        self.search_button.setMinimumWidth(72)
        self.search_button.clicked.connect(self.search)
        options.addWidget(self.search_button)
        layout.addLayout(options)

        layout.addSpacing(2)

        self.replace = QtWidgets.QLineEdit()
        self.replace.setPlaceholderText('Заменить на…')
        self.replace.setMinimumHeight(32)
        self.replace.setClearButtonEnabled(True)
        layout.addWidget(self.replace)

        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setContentsMargins(0, 2, 0, 4)
        replace_row.addStretch()
        self.replace_button = QtWidgets.QPushButton('Заменить всё')
        self.replace_button.setMinimumHeight(30)
        self.replace_button.clicked.connect(self.replace_all)
        replace_row.addWidget(self.replace_button)
        layout.addLayout(replace_row)

        self.results = QtWidgets.QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.setRootIsDecorated(True)
        self.results.setUniformRowHeights(True)
        self.results.setIndentation(14)
        self.results.setAnimated(False)
        self.results.itemDoubleClicked.connect(self._open_item)
        self.results.setObjectName("searchResults")
        self.results.setTextElideMode(QtCore.Qt.ElideMiddle)
        layout.addWidget(self.results, 1)

    def set_root(self, path):
        if path:
            self.root_path = Path(path)

    def _compile_pattern(self, query):
        if self.regex.isChecked():
            pattern = query
        else:
            pattern = re.escape(query)
            if self.whole_word.isChecked():
                pattern = r'\b' + pattern + r'\b'
        return re.compile(pattern, 0 if self.case_sensitive.isChecked() else re.IGNORECASE)

    def _iter_text_files(self):
        try:
            from core.ignore_rules import walk_files
            # Pruned walk so a search never descends into node_modules/.git.
            scan = walk_files(self.root_path, extensions=None,
                              max_files=None, max_bytes=self.MAX_FILE_BYTES)
            for path in scan.files:
                if path.suffix.lower() in self.BINARY_SUFFIXES:
                    continue
                try:
                    data = path.read_bytes()
                    if b'\x00' in data[:8192]:
                        continue
                    # Remember the real encoding so ``replace_all`` can write the
                    # file back without corrupting non-UTF-8 sources.
                    bom = b''
                    encoding = 'utf-8'
                    if data.startswith(b'\xef\xbb\xbf'):
                        text = data.decode('utf-8-sig')
                        bom = b'\xef\xbb\xbf'
                    else:
                        try:
                            text = data.decode('utf-8')
                        except UnicodeDecodeError:
                            text = data.decode('cp1251')
                            encoding = 'cp1251'
                except (OSError, UnicodeDecodeError, ValueError):
                    continue
                yield path, text, encoding, bom
        except OSError:
            return

    def search(self):
        self.results.clear()
        query = self.query.text()
        if not query.strip() or not self.root_path.exists():
            self.result_count.setText('')
            return
        try:
            pattern = self._compile_pattern(query)
        except re.error as exc:
            self.result_count.setText('Неверное рег. выражение')
            self.results.addTopLevelItem(QtWidgets.QTreeWidgetItem([str(exc)]))
            return

        total_matches = 0
        file_count = 0
        for path, text, _encoding, _bom in self._iter_text_files():
            file_item = None
            for line_no, line in enumerate(text.splitlines(), 1):
                matches = list(pattern.finditer(line))
                if not matches:
                    continue
                if file_item is None:
                    relative = str(path.relative_to(self.root_path))
                    file_item = QtWidgets.QTreeWidgetItem([f'{path.name}  ·  {relative}'])
                    file_item.setData(0, QtCore.Qt.UserRole, str(path))
                    file_item.setToolTip(0, str(path))
                    self.results.addTopLevelItem(file_item)
                    file_count += 1
                snippet = line.strip()
                if len(snippet) > 180:
                    snippet = snippet[:177] + '…'
                child = QtWidgets.QTreeWidgetItem([f'{line_no}:  {snippet}'])
                child.setData(0, QtCore.Qt.UserRole, str(path))
                child.setData(0, QtCore.Qt.UserRole + 1, line_no)
                child.setToolTip(0, f'{path}:{line_no}\n{line.strip()}')
                file_item.addChild(child)
                total_matches += len(matches)
                if total_matches >= 5000:
                    break
            if total_matches >= 5000:
                break
        self.result_count.setText(f'Совпадений: {total_matches} в {file_count} файлах')
        self.results.expandAll()
        if total_matches == 0:
            self.results.addTopLevelItem(QtWidgets.QTreeWidgetItem(['Ничего не найдено']))

    def _open_editor_paths(self) -> set:
        """Absolute paths of files currently open in editor tabs (skip them on replace)."""
        open_paths = set()
        window = self.window()
        getter = getattr(window, 'get_open_file_paths', None)
        if callable(getter):
            try:
                for p in getter() or []:
                    open_paths.add(str(Path(p).resolve()).lower())
            except Exception:
                pass
        return open_paths

    def replace_all(self):
        query = self.query.text()
        if not query.strip():
            return
        try:
            pattern = self._compile_pattern(query)
        except re.error as exc:
            QtWidgets.QMessageBox.warning(self, 'Неверный шаблон поиска', str(exc))
            return
        replacement = self.replace.text()
        changes = 0
        skipped_open = []
        for path, text, encoding, bom in self._iter_text_files():
            new_text, count = pattern.subn(replacement, text)
            if not count:
                continue
            try:
                resolved = str(path.resolve()).lower()
            except OSError:
                resolved = str(path).lower()
            if resolved in self._open_editor_paths():
                # Не перезаписываем буфер открытого файла на диске — иначе
                # последующее автосохранение затрёт замены.
                skipped_open.append(path.name)
                continue
            try:
                # Сохраняем исходную кодировку и BOM, чтобы не разрушить файл.
                payload = new_text.encode(encoding, errors='replace')
                path.write_bytes(bom + payload)
                changes += count
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, 'Ошибка замены', f'{path}: {exc}')
        self.search()
        message = f'Заменено совпадений: {changes}.'
        if skipped_open:
            preview = ', '.join(sorted(set(skipped_open))[:5])
            message += (f'\n\nПропущено файлов, открытых в редакторе: {len(set(skipped_open))}'
                        f' ({preview}). Сохраните и закройте их, затем повторите замену.')
        QtWidgets.QMessageBox.information(self, 'Заменить всё', message)

    def _open_item(self, item, column):
        path = item.data(0, QtCore.Qt.UserRole)
        if not path:
            return
        line = item.data(0, QtCore.Qt.UserRole + 1)
        if line is not None:
            self.open_match_requested.emit(path, int(line))
        else:
            self.open_file_requested.emit(path)
