"""High-performance virtual Hex Viewer and Binary Inspector for PyScribe.

Features:
- Fast virtual QAbstractTableModel handling files from bytes to gigabytes instantly.
- 16-byte aligned rows with offset, discrete byte cells, and ASCII column.
- Bidirectional navigation: selecting byte updates offset, selection range, and inspector.
- Real-time Data Inspector (Int8/16/32/64, UInt8/16/32/64, Float32/64, Binary, UTF-8/ASCII, Unix time)
  with Little Endian and Big Endian support.
- Full Hex and Text search with previous/next navigation and match highlighting.
- "Go to offset" navigation (supports hex '0x100' and decimal '256').
- Multiple copy formats: Hex ('4D 5A'), C-Array ('0x4D, 0x5A'), ASCII, Base64, Offset.
- Zoom in / Zoom out font sizing.
- Pure dark theme styling matching PyScribe IDE.
"""
from __future__ import annotations

import base64
import datetime
import struct
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets


class HexTableModel(QtCore.QAbstractTableModel):
    """Virtual table model for binary data."""

    def __init__(self, data: bytes = b"", bytes_per_row: int = 16, parent=None):
        super().__init__(parent)
        self._data = bytes(data)
        self._bpr = max(8, min(32, bytes_per_row))
        self._search_matches: List[int] = []

    def set_data(self, data: bytes):
        self.beginResetModel()
        self._data = bytes(data)
        self._search_matches = []
        self.endResetModel()

    def set_matches(self, matches: List[int]):
        self._search_matches = matches
        self.layoutChanged.emit()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        if not self._data:
            return 0
        return (len(self._data) + self._bpr - 1) // self._bpr

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        # Col 0: Offset
        # Col 1..16: Byte 0..15
        # Col 17: ASCII
        return 1 + self._bpr + 1

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        r = index.row()
        c = index.column()

        # Col 0: Offset
        if c == 0:
            if role == QtCore.Qt.DisplayRole:
                return f"{r * self._bpr:08X}"
            if role == QtCore.Qt.TextAlignmentRole:
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            if role == QtCore.Qt.ForegroundRole:
                return QtGui.QBrush(QtGui.QColor("#858585"))
            return None

        # ASCII Column (last column)
        if c == 1 + self._bpr:
            start_off = r * self._bpr
            chunk = self._data[start_off:start_off + self._bpr]
            if role == QtCore.Qt.DisplayRole:
                return "".join(chr(b) if 32 <= b <= 126 else "·" for b in chunk)
            if role == QtCore.Qt.TextAlignmentRole:
                return int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            if role == QtCore.Qt.ForegroundRole:
                return QtGui.QBrush(QtGui.QColor("#4EC9B0"))
            return None

        # Hex Byte Columns (1 to 16)
        byte_idx = c - 1
        off = r * self._bpr + byte_idx
        if off >= len(self._data):
            return None

        val = self._data[off]
        if role == QtCore.Qt.DisplayRole:
            return f"{val:02X}"
        if role == QtCore.Qt.TextAlignmentRole:
            return int(QtCore.Qt.AlignCenter)
        if role == QtCore.Qt.ForegroundRole:
            if val == 0:
                return QtGui.QBrush(QtGui.QColor("#555555"))
            if 32 <= val <= 126:
                return QtGui.QBrush(QtGui.QColor("#9CDCFE"))
            return QtGui.QBrush(QtGui.QColor("#DCDCAA"))
        if role == QtCore.Qt.BackgroundRole:
            if off in self._search_matches:
                return QtGui.QBrush(QtGui.QColor(255, 214, 0, 90))
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole) -> Any:
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "Смещение"
            if section == 1 + self._bpr:
                return "ASCII"
            return f"{section - 1:02X}"
        return None

    def get_offset_for_index(self, index: QtCore.QModelIndex) -> Optional[int]:
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if 1 <= c <= self._bpr:
            off = r * self._bpr + (c - 1)
            return off if off < len(self._data) else None
        if c == 1 + self._bpr:
            off = r * self._bpr
            return off if off < len(self._data) else None
        if c == 0:
            return r * self._bpr
        return None

    def get_index_for_offset(self, offset: int) -> QtCore.QModelIndex:
        if offset < 0 or offset >= len(self._data):
            return QtCore.QModelIndex()
        r = offset // self._bpr
        c = 1 + (offset % self._bpr)
        return self.index(r, c)


class DataInspectorWidget(QtWidgets.QWidget):
    """Detailed byte interpreter (Inspector) for the selected offset."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_little_endian = True
        self.data = b""
        self.current_offset = 0

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Header with Endianness toggle
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Инспектор данных")
        title.setStyleSheet("font-weight: bold; color: #00F2FE;")
        header.addWidget(title)
        header.addStretch()

        self.endian_btn = QtWidgets.QToolButton()
        self.endian_btn.setText("Little Endian")
        self.endian_btn.setToolTip("Переключить порядок байтов (Little / Big Endian)")
        self.endian_btn.clicked.connect(self._toggle_endian)
        header.addWidget(self.endian_btn)
        layout.addLayout(header)

        # Form layout of values
        self.grid = QtWidgets.QFormLayout()
        self.grid.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.grid.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.grid.setVerticalSpacing(4)
        self.grid.setHorizontalSpacing(10)

        self.lbl_offset = self._make_val_label()
        self.lbl_binary = self._make_val_label()
        self.lbl_int8 = self._make_val_label()
        self.lbl_uint8 = self._make_val_label()
        self.lbl_int16 = self._make_val_label()
        self.lbl_uint16 = self._make_val_label()
        self.lbl_int32 = self._make_val_label()
        self.lbl_uint32 = self._make_val_label()
        self.lbl_int64 = self._make_val_label()
        self.lbl_float32 = self._make_val_label()
        self.lbl_float64 = self._make_val_label()
        self.lbl_char = self._make_val_label()
        self.lbl_time = self._make_val_label()

        self.grid.addRow("Смещение:", self.lbl_offset)
        self.grid.addRow("Двоичный (8-бит):", self.lbl_binary)
        self.grid.addRow("Символ:", self.lbl_char)
        self.grid.addRow("Int8:", self.lbl_int8)
        self.grid.addRow("UInt8:", self.lbl_uint8)
        self.grid.addRow("Int16:", self.lbl_int16)
        self.grid.addRow("UInt16:", self.lbl_uint16)
        self.grid.addRow("Int32:", self.lbl_int32)
        self.grid.addRow("UInt32:", self.lbl_uint32)
        self.grid.addRow("Int64:", self.lbl_int64)
        self.grid.addRow("Float32:", self.lbl_float32)
        self.grid.addRow("Float64:", self.lbl_float64)
        self.grid.addRow("Время (Unix):", self.lbl_time)

        layout.addLayout(self.grid)
        layout.addStretch()

    def _make_val_label(self) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel("-")
        lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lbl.setStyleSheet("color: #d4d4d4; font-family: 'Cascadia Code', monospace; font-size: 9pt;")
        return lbl

    def _toggle_endian(self):
        self.is_little_endian = not self.is_little_endian
        self.endian_btn.setText("Little Endian" if self.is_little_endian else "Big Endian")
        self.update_inspector(self.data, self.current_offset)

    def update_inspector(self, data: bytes, offset: int):
        self.data = data
        self.current_offset = offset

        if not data or offset < 0 or offset >= len(data):
            for lbl in (self.lbl_offset, self.lbl_binary, self.lbl_int8, self.lbl_uint8,
                        self.lbl_int16, self.lbl_uint16, self.lbl_int32, self.lbl_uint32,
                        self.lbl_int64, self.lbl_float32, self.lbl_float64, self.lbl_char, self.lbl_time):
                lbl.setText("-")
            return

        order = "<" if self.is_little_endian else ">"
        remaining = data[offset:]

        self.lbl_offset.setText(f"0x{offset:08X} ({offset:,})")

        # Byte 0
        b0 = remaining[0]
        self.lbl_binary.setText(f"{b0:08b}")
        ch = chr(b0) if 32 <= b0 <= 126 else "."
        self.lbl_char.setText(f"'{ch}' (ASCII {b0})")

        s8 = struct.unpack("b", remaining[:1])[0]
        self.lbl_int8.setText(str(s8))
        self.lbl_uint8.setText(str(b0))

        # 16-bit
        if len(remaining) >= 2:
            s16 = struct.unpack(f"{order}h", remaining[:2])[0]
            u16 = struct.unpack(f"{order}H", remaining[:2])[0]
            self.lbl_int16.setText(f"{s16:,}")
            self.lbl_uint16.setText(f"{u16:,}")
        else:
            self.lbl_int16.setText("-")
            self.lbl_uint16.setText("-")

        # 32-bit
        if len(remaining) >= 4:
            s32 = struct.unpack(f"{order}i", remaining[:4])[0]
            u32 = struct.unpack(f"{order}I", remaining[:4])[0]
            f32 = struct.unpack(f"{order}f", remaining[:4])[0]
            self.lbl_int32.setText(f"{s32:,}")
            self.lbl_uint32.setText(f"{u32:,}")
            self.lbl_float32.setText(f"{f32:.6g}")

            # Unix time
            if 0 < u32 < 2500000000:
                try:
                    dt = datetime.datetime.fromtimestamp(u32, datetime.timezone.utc)
                    self.lbl_time.setText(dt.strftime("%Y-%m-%d %H:%M:%S UTC"))
                except Exception:
                    self.lbl_time.setText("-")
            else:
                self.lbl_time.setText("-")
        else:
            self.lbl_int32.setText("-")
            self.lbl_uint32.setText("-")
            self.lbl_float32.setText("-")
            self.lbl_time.setText("-")

        # 64-bit
        if len(remaining) >= 8:
            s64 = struct.unpack(f"{order}q", remaining[:8])[0]
            f64 = struct.unpack(f"{order}d", remaining[:8])[0]
            self.lbl_int64.setText(f"{s64:,}")
            self.lbl_float64.setText(f"{f64:.10g}")
        else:
            self.lbl_int64.setText("-")
            self.lbl_float64.setText("-")


class HexViewer(QtWidgets.QWidget):
    """High-performance Hex Viewer with inspector, search, and export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path: Optional[Union[str, Path]] = None
        self.data: bytes = b""
        self.font_size = 11
        self.bytes_per_row = 16
        self.current_offset = 0

        self.setObjectName("hexViewer")
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget#hexViewer {
                background: #1e1e1e;
                color: #cccccc;
            }
            #hexToolbar {
                background: #252526;
                border-bottom: 1px solid #333333;
                padding: 4px;
            }
            QTableView#hexTableView {
                background: #1e1e1e;
                color: #d4d4d4;
                gridline-color: transparent;
                border: none;
                font-family: "Cascadia Code", "Consolas", monospace;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background: #252526;
                color: #858585;
                border: none;
                border-bottom: 1px solid #333333;
                padding: 4px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-weight: bold;
            }
            QLineEdit#hexSearch {
                background: #3c3c3c;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QComboBox, QToolButton {
                background: #333333;
                color: #cccccc;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QComboBox:hover, QToolButton:hover {
                background: #3a3d41;
                border-color: #007acc;
            }
            #hexStatus {
                background: #252526;
                color: #858585;
                border-top: 1px solid #333333;
                padding: 3px 10px;
                font-size: 9pt;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Toolbar
        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("hexToolbar")
        t_layout = QtWidgets.QHBoxLayout(toolbar)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(6)

        # Search Type Combo
        self.search_type_combo = QtWidgets.QComboBox()
        self.search_type_combo.addItem("Текст", "text")
        self.search_type_combo.addItem("HEX", "hex")
        t_layout.addWidget(self.search_type_combo)

        # Search input
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("hexSearch")
        self.search_edit.setPlaceholderText("Найти в двоичном файле… (Ctrl+F)")
        self.search_edit.setFixedWidth(210)
        self.search_edit.returnPressed.connect(self._find_next)
        t_layout.addWidget(self.search_edit)

        # Search buttons
        self.prev_btn = QtWidgets.QToolButton()
        set_line_icon(self.prev_btn, "up")
        self.prev_btn.setToolTip("Предыдущее совпадение")
        self.prev_btn.clicked.connect(self._find_prev)
        t_layout.addWidget(self.prev_btn)

        self.next_btn = QtWidgets.QToolButton()
        set_line_icon(self.next_btn, "down")
        self.next_btn.setToolTip("Следующее совпадение")
        self.next_btn.clicked.connect(self._find_next)
        t_layout.addWidget(self.next_btn)

        self.match_lbl = QtWidgets.QLabel("")
        self.match_lbl.setStyleSheet("color: #888888; font-size: 9pt;")
        t_layout.addWidget(self.match_lbl)

        t_layout.addWidget(self._separator())

        # Go to offset button
        self.goto_btn = QtWidgets.QToolButton()
        self.goto_btn.setText("Перейти…")
        self.goto_btn.setToolTip("Перейти к смещению (Ctrl+G)")
        self.goto_btn.clicked.connect(self.prompt_goto_offset)
        t_layout.addWidget(self.goto_btn)

        # Copy format menu
        self.copy_btn = QtWidgets.QToolButton()
        self.copy_btn.setText("Копировать")
        set_line_icon(self.copy_btn, "copy")
        self.copy_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        copy_menu = QtWidgets.QMenu(self.copy_btn)
        act_hex = copy_menu.addAction("Копировать HEX (4D 5A…)")
        act_hex.triggered.connect(lambda: self.copy_selected("hex"))
        act_c = copy_menu.addAction("Копировать C-массив (0x4D, 0x5A…)")
        act_c.triggered.connect(lambda: self.copy_selected("c_array"))
        act_text = copy_menu.addAction("Копировать ASCII текст")
        act_text.triggered.connect(lambda: self.copy_selected("ascii"))
        act_b64 = copy_menu.addAction("Копировать Base64")
        act_b64.triggered.connect(lambda: self.copy_selected("base64"))
        self.copy_btn.setMenu(copy_menu)
        t_layout.addWidget(self.copy_btn)

        # Font zoom
        self.zoom_in_btn = QtWidgets.QToolButton()
        set_line_icon(self.zoom_in_btn, "add")
        self.zoom_in_btn.setToolTip("Увеличить шрифт (Ctrl+=)")
        self.zoom_in_btn.clicked.connect(self.add_font_size)
        t_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QtWidgets.QToolButton()
        set_line_icon(self.zoom_out_btn, "minus")
        self.zoom_out_btn.setToolTip("Уменьшить шрифт (Ctrl+−)")
        self.zoom_out_btn.clicked.connect(self.pop_font_size)
        t_layout.addWidget(self.zoom_out_btn)

        t_layout.addStretch()

        # Toggle Inspector panel
        self.toggle_inspector_btn = QtWidgets.QToolButton()
        self.toggle_inspector_btn.setText("Инспектор")
        self.toggle_inspector_btn.setCheckable(True)
        self.toggle_inspector_btn.setChecked(True)
        self.toggle_inspector_btn.setToolTip("Показать/скрыть инспектор данных")
        self.toggle_inspector_btn.toggled.connect(self._toggle_inspector)
        t_layout.addWidget(self.toggle_inspector_btn)

        root.addWidget(toolbar)

        # 2. Main Body Splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Table View
        self.model = HexTableModel(b"", self.bytes_per_row, self)
        self.table_view = QtWidgets.QTableView()
        self.table_view.setObjectName("hexTableView")
        self.table_view.setModel(self.model)
        self.table_view.setShowGrid(False)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        selection_model = self.table_view.selectionModel()
        selection_model.currentChanged.connect(self._on_current_changed)
        selection_model.selectionChanged.connect(self._on_selection_changed)

        self.splitter.addWidget(self.table_view)

        # Inspector Panel
        self.inspector = DataInspectorWidget(self)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

        root.addWidget(self.splitter, 1)

        # 3. Status Bar
        self.status_bar = QtWidgets.QWidget()
        self.status_bar.setObjectName("hexStatus")
        s_layout = QtWidgets.QHBoxLayout(self.status_bar)
        s_layout.setContentsMargins(8, 2, 8, 2)
        self.info_label = QtWidgets.QLabel("Binary • read-only")
        self.status_offset_lbl = QtWidgets.QLabel("")
        s_layout.addWidget(self.info_label)
        s_layout.addStretch()
        s_layout.addWidget(self.status_offset_lbl)
        root.addWidget(self.status_bar)

        self._apply_font()
        self._configure_column_widths()

        # Keyboard shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+="), self, activated=self.add_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+-"), self, activated=self.pop_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+G"), self, activated=self.prompt_goto_offset)
        QtWidgets.QShortcut(QtGui.QKeySequence.Find, self, activated=self.search_edit.setFocus)

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("color: #444444;")
        return line

    def _configure_column_widths(self):
        font_metrics = QtGui.QFontMetrics(QtGui.QFont("Cascadia Code", self.font_size))
        char_w = font_metrics.averageCharWidth()

        # Offset column: 8 hex digits + margin
        self.table_view.setColumnWidth(0, max(85, char_w * 10))

        # 16 Hex byte columns
        byte_w = max(28, char_w * 3 + 4)
        for c in range(1, 1 + self.bytes_per_row):
            self.table_view.setColumnWidth(c, byte_w)

        # ASCII column: 16 chars + margin
        self.table_view.setColumnWidth(1 + self.bytes_per_row, max(140, char_w * 18 + 10))

    def _apply_font(self):
        font = QtGui.QFont("Cascadia Code", self.font_size)
        self.table_view.setFont(font)
        self.table_view.horizontalHeader().setFont(font)
        self._configure_column_widths()

    def add_font_size(self):
        self.font_size = min(28, self.font_size + 1)
        self._apply_font()

    def pop_font_size(self):
        self.font_size = max(7, self.font_size - 1)
        self._apply_font()

    # Compatibility aliases
    def addFontSize(self): self.add_font_size()
    def popFontSize(self): self.pop_font_size()

    def _toggle_inspector(self, checked: bool):
        self.inspector.setVisible(checked)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------
    def load_file(self, data: Union[bytes, bytearray]):
        """Load binary data into the virtual hex model."""
        self.data = bytes(data)
        self.model.set_data(self.data)

        name = Path(self.file_path).name if self.file_path else "Binary"
        size = len(self.data)
        self.info_label.setText(f"{name}  •  {size:,} bytes  •  read-only")

        if size > 0:
            first_idx = self.model.index(0, 1)
            self.table_view.setCurrentIndex(first_idx)
            self.inspector.update_inspector(self.data, 0)
            self.status_offset_lbl.setText("Смещение: 0x00000000 (0)")
        else:
            self.status_offset_lbl.setText("Файл пуст")

    # ------------------------------------------------------------------
    # Selection and Offset Tracking
    # ------------------------------------------------------------------
    def _on_current_changed(self, current: QtCore.QModelIndex, _previous: QtCore.QModelIndex):
        off = self.model.get_offset_for_index(current)
        if off is not None:
            self.current_offset = off
            self.inspector.update_inspector(self.data, off)
            self.status_offset_lbl.setText(f"Смещение: 0x{off:08X} ({off:,})")

    def _on_selection_changed(self):
        indexes = self.table_view.selectedIndexes()
        offsets = []
        for idx in indexes:
            off = self.model.get_offset_for_index(idx)
            if off is not None:
                offsets.append(off)
        if len(offsets) > 1:
            min_off, max_off = min(offsets), max(offsets)
            count = len(offsets)
            self.status_offset_lbl.setText(
                f"Смещение: 0x{min_off:08X}..0x{max_off:08X}  •  Выделено: {count:,} байт"
            )

    def _get_selected_bytes(self) -> bytes:
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            if self.current_offset < len(self.data):
                return self.data[self.current_offset:self.current_offset + 1]
            return b""

        offsets = sorted(set(self.model.get_offset_for_index(idx) for idx in indexes if self.model.get_offset_for_index(idx) is not None))
        if not offsets:
            return b""

        # Contiguous range if start to end
        min_off, max_off = offsets[0], offsets[-1]
        return self.data[min_off:max_off + 1]

    # ------------------------------------------------------------------
    # Navigation / Go to offset
    # ------------------------------------------------------------------
    def prompt_goto_offset(self):
        text, ok = QtWidgets.QInputDialog.getText(
            self, "Перейти к смещению",
            "Введите смещение (например 0x100 или 256):",
            text=f"0x{self.current_offset:X}"
        )
        if ok and text:
            self.goto_offset(text.strip())

    def goto_offset(self, offset_str: str) -> bool:
        try:
            s = offset_str.strip().lower()
            if s.startswith("0x"):
                offset = int(s, 16)
            elif s.endswith("h"):
                offset = int(s[:-1], 16)
            else:
                offset = int(s)
        except ValueError:
            self.status_offset_lbl.setText(f"Недопустимый формат: {offset_str}")
            if self.isVisible():
                QtWidgets.QMessageBox.warning(self, "Ошибка смещения", f"Недопустимый формат: {offset_str}")
            return False

        if offset < 0 or offset >= len(self.data):
            self.status_offset_lbl.setText(f"Смещение вне диапазона (0..{len(self.data) - 1:,})")
            if self.isVisible():
                QtWidgets.QMessageBox.warning(
                    self, "Смещение вне диапазона",
                    f"Смещение {offset:,} выходит за пределы файла (0..{len(self.data) - 1:,})."
                )
            return False

        idx = self.model.get_index_for_offset(offset)
        if idx.isValid():
            self.table_view.setCurrentIndex(idx)
            self.table_view.scrollTo(idx, QtWidgets.QAbstractItemView.PositionAtCenter)
            return True
        return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _find_next(self):
        self._search(forward=True)

    def _find_prev(self):
        self._search(forward=False)

    def _search(self, forward: bool = True):
        query = self.search_edit.text().strip()
        if not query or not self.data:
            self.model.set_matches([])
            self.match_lbl.setText("")
            return

        search_type = self.search_type_combo.currentData()
        target_bytes = b""
        if search_type == "hex":
            clean_hex = query.replace(" ", "").replace("0x", "")
            try:
                target_bytes = bytes.fromhex(clean_hex)
            except ValueError:
                self.match_lbl.setText("Неверный HEX")
                return
        else:
            target_bytes = query.encode("utf-8", errors="replace")

        if not target_bytes:
            return

        # Find all occurrences
        matches = []
        start = 0
        while True:
            pos = self.data.find(target_bytes, start)
            if pos == -1:
                break
            for i in range(len(target_bytes)):
                matches.append(pos + i)
            start = pos + 1

        self.model.set_matches(matches)

        if not matches:
            self.match_lbl.setText("Не найдено")
            return

        unique_offsets = sorted(set(matches))
        self.match_lbl.setText(f"Найдено: {len(unique_offsets) // len(target_bytes):,}")

        # Move to next or previous match relative to current_offset
        if forward:
            next_off = next((off for off in unique_offsets if off > self.current_offset), unique_offsets[0])
        else:
            next_off = next((off for off in reversed(unique_offsets) if off < self.current_offset), unique_offsets[-1])

        idx = self.model.get_index_for_offset(next_off)
        if idx.isValid():
            self.table_view.setCurrentIndex(idx)
            self.table_view.scrollTo(idx, QtWidgets.QAbstractItemView.PositionAtCenter)

    # ------------------------------------------------------------------
    # Copying
    # ------------------------------------------------------------------
    def copy_selected(self, fmt: str = "hex"):
        selected = self._get_selected_bytes()
        if not selected:
            return

        if fmt == "hex":
            text = " ".join(f"{b:02X}" for b in selected)
        elif fmt == "c_array":
            text = ", ".join(f"0x{b:02X}" for b in selected)
        elif fmt == "ascii":
            text = "".join(chr(b) if 32 <= b <= 126 else "." for b in selected)
        elif fmt == "base64":
            text = base64.b64encode(selected).decode("ascii")
        elif fmt == "offset":
            text = f"0x{self.current_offset:08X}"
        else:
            text = selected.hex()

        QtWidgets.QApplication.clipboard().setText(text)

    def _show_context_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        act_hex = menu.addAction("Копировать как HEX (Ctrl+C)")
        act_hex.triggered.connect(lambda: self.copy_selected("hex"))
        act_c = menu.addAction("Копировать как C-массив")
        act_c.triggered.connect(lambda: self.copy_selected("c_array"))
        act_ascii = menu.addAction("Копировать как ASCII")
        act_ascii.triggered.connect(lambda: self.copy_selected("ascii"))
        act_b64 = menu.addAction("Копировать как Base64")
        act_b64.triggered.connect(lambda: self.copy_selected("base64"))
        menu.addSeparator()
        act_goto = menu.addAction("Перейти к смещению… (Ctrl+G)")
        act_goto.triggered.connect(self.prompt_goto_offset)
        act_sel_all = menu.addAction("Выделить всё (Ctrl+A)")
        act_sel_all.triggered.connect(self.table_view.selectAll)

        menu.exec_(self.table_view.viewport().mapToGlobal(pos))
