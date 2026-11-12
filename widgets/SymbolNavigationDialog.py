"""Modern dialog for choosing between definitions, references, and OpenAPI targets.

Displays candidate locations clearly labeled with:
- Target kind / badge ([LSP Определение], [OpenAPI Спецификация], [OpenAPI Обработчик], [Текстовое совпадение])
- File name and path
- Line number and code preview
- Filter / search box for quickly narrowing large reference lists
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from core.code_analysis.lsp_client import LspLocation


class SymbolNavigationDialog(QtWidgets.QDialog):
    """Interactive navigation popup for jumping to symbols and cross-language links."""

    location_selected = QtCore.pyqtSignal(str, int, int)  # file_path, line, col

    def __init__(self, title: str, locations: List[LspLocation], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 460)
        self._all_locations = list(locations)
        self._filtered_locations: List[LspLocation] = []

        self._build_ui()
        self._apply_filter("")

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: #1e1e1e;
                color: #cccccc;
            }
            QLineEdit#filterInput {
                background: #252526;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10pt;
            }
            QLineEdit#filterInput:focus {
                border-color: #007acc;
            }
            QTreeWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333333;
                border-radius: 4px;
                font-family: "Segoe UI", "Cascadia Code", sans-serif;
                font-size: 10pt;
            }
            QTreeWidget::item {
                padding: 5px 2px;
                border-bottom: 1px solid #282828;
            }
            QTreeWidget::item:hover {
                background: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background: #094771;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #252526;
                color: #858585;
                border: none;
                border-bottom: 1px solid #333333;
                padding: 5px 8px;
                font-weight: bold;
            }
            QPushButton {
                background: #333333;
                color: #cccccc;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: #3a3d41;
                border-color: #007acc;
            }
            QPushButton#jumpBtn {
                background: #007acc;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#jumpBtn:hover {
                background: #0098ff;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Filter input
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setObjectName("filterInput")
        self.filter_edit.setPlaceholderText("Фильтровать по имени файла или коду…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_edit)

        # Candidate Tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Тип / Источник", "Файл", "Стр.", "Фрагмент кода"])
        self.tree.setColumnWidth(0, 240)
        self.tree.setColumnWidth(1, 180)
        self.tree.setColumnWidth(2, 50)
        self.tree.header().setStretchLastSection(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self.tree, 1)

        # Footer buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.count_label = QtWidgets.QLabel(f"Найдено совпадений: {len(self._all_locations)}")
        self.count_label.setStyleSheet("color: #858585; font-size: 9pt;")
        btn_layout.addWidget(self.count_label)
        btn_layout.addStretch()

        self.jump_btn = QtWidgets.QPushButton("Перейти (Enter)")
        self.jump_btn.setObjectName("jumpBtn")
        self.jump_btn.clicked.connect(self._on_jump_clicked)
        btn_layout.addWidget(self.jump_btn)

        self.cancel_btn = QtWidgets.QPushButton("Отмена (Esc)")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _apply_filter(self, query: str):
        q = query.strip().lower()
        self.tree.clear()
        self._filtered_locations = []

        for loc in self._all_locations:
            filename = Path(loc.file_path).name
            match_str = f"{loc.badge} {filename} {loc.file_path} {loc.preview}".lower()
            if not q or q in match_str:
                self._filtered_locations.append(loc)

                item = QtWidgets.QTreeWidgetItem([
                    loc.badge,
                    filename,
                    str(loc.line),
                    loc.preview,
                ])
                item.setToolTip(1, loc.file_path)
                item.setData(0, QtCore.Qt.UserRole, loc)

                # Color-code badges
                if loc.kind == "openapi":
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor("#4EC9B0")))
                elif loc.kind == "semantic":
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor("#00F2FE")))
                elif loc.kind == "syntax":
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor("#DCDCAA")))
                else:  # text
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor("#858585")))

                self.tree.addTopLevelItem(item)

        self.count_label.setText(f"Найдено: {len(self._filtered_locations)} из {len(self._all_locations)}")
        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _on_item_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int):
        loc = item.data(0, QtCore.Qt.UserRole)
        if isinstance(loc, LspLocation):
            self.location_selected.emit(loc.file_path, loc.line, loc.col)
            self.accept()

    def _on_jump_clicked(self):
        curr = self.tree.currentItem()
        if curr:
            self._on_item_activated(curr, 0)


def show_symbol_dialog(parent, title: str, locations: List[LspLocation], on_select=None) -> Optional[SymbolNavigationDialog]:
    """Helper to display the symbol navigation dialog and connect selection callback."""
    if not locations:
        return None
    dlg = SymbolNavigationDialog(title, locations, parent)
    if on_select:
        def _cb(path: str, line: int, col: int):
            for loc in locations:
                if loc.file_path == path and loc.line == line and loc.col == col:
                    on_select(loc)
                    return
            on_select(LspLocation(file_path=path, line=line, col=col))
        dlg.location_selected.connect(_cb)
    dlg.exec_()
    return dlg
