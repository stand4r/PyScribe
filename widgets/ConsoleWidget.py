"""Bottom Workbench panel: integrated terminal, file-scoped Problems and Output."""
from pathlib import Path
from design.icons import line_icon, set_line_icon
from PyQt5 import QtWidgets, QtCore, QtGui
from .TerminalWidget import TerminalWidget
from design.icons import codicon_icon


class ConsoleWidget(QtWidgets.QWidget):
    """Provide a useful, dark, structured bottom panel for the active file."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consoleWidget")
        self._current_file = None
        # Diagnostics for the active file, keyed by path. Re-analysing the same
        # unchanged file on every tab switch blocked the GUI thread long enough
        # to stall every running animation, so results are reused until the
        # content (or the file on disk) actually changes.
        self._analysis_cache = {}
        self._lsp_diagnostics = {}
        self._build()
        try:
            from core.code_analysis.service import UnifiedCodeAnalysisService
            svc = UnifiedCodeAnalysisService.get_instance()
            svc.diagnostics_updated.connect(self._on_lsp_diagnostics)
            svc.diagnostics_cleared.connect(self._on_lsp_diagnostics_cleared)
        except Exception:
            pass

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setObjectName("consoleTabs")
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.terminal_widget = TerminalWidget(self)
        self.tab_widget.addTab(self.terminal_widget, "Терминал")
        self.problems_widget = self._create_problems()
        self.tab_widget.addTab(self.problems_widget, "Проблемы")
        self.output_widget = self._create_output()
        self.tab_widget.addTab(self.output_widget, "Вывод")
        from .ProjectTaskManager import ProjectTaskManager
        self.task_manager = ProjectTaskManager(self.terminal_widget, self)
        self.tab_widget.addTab(self.task_manager, "Диспетчер задач")

        # Right side of the panel strip: terminal actions + problem counter,
        # mirroring VS Code's panel title bar tool set.
        corner = QtWidgets.QWidget()
        corner.setObjectName("consoleCorner")
        corner_layout = QtWidgets.QHBoxLayout(corner)
        # Vertically centred, with the same 4px breathing room as the tabs.
        corner_layout.setContentsMargins(4, 2, 8, 2)
        corner_layout.setSpacing(2)

        self._toolbar_buttons = {}
        for key, icon_name, tip, slot in (
            ("new_terminal", "add", "Новый терминал (Ctrl+Shift+`)", self._new_terminal),
            ("kill", "stop", "Завершить процесс и перезапустить", self._kill_terminal),
            ("clear", "clear-all", "Очистить панель", self._clear_panel),
            ("collapse", "chevron-down", "Скрыть панель", self._hide_panel),
        ):
            button = QtWidgets.QToolButton()
            button.setObjectName("consoleAction")
            button.setIcon(codicon_icon(icon_name, 16, "#CCCCCC"))
            button.setIconSize(QtCore.QSize(16, 16))
            button.setToolTip(tip)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            # A fixed 28px hit area, vertically centred inside the 36px strip.
            button.setFixedSize(28, 28)
            button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, s=slot: s())
            corner_layout.addWidget(button, 0, QtCore.Qt.AlignVCenter)
            self._toolbar_buttons[key] = button

        self._problem_badge = QtWidgets.QLabel("")
        self._problem_badge.setObjectName("consoleBadge")
        self._problem_badge.setVisible(False)
        corner_layout.addWidget(self._problem_badge, 0, QtCore.Qt.AlignVCenter)

        self.tab_widget.setCornerWidget(corner, QtCore.Qt.TopRightCorner)

        # Problem count badge + busy indicator live in the panel strip.
        self.tab_widget.currentChanged.connect(self._animate_page_change)
        self.terminal_widget.busy_changed.connect(self._set_terminal_busy)
        self.terminal_widget.tab_count_changed.connect(self._refresh_terminal_tab_label)

        layout.addWidget(self.tab_widget)
        self._busy_timer = QtCore.QTimer(self)
        self._busy_timer.setInterval(120)

    # ------------------------------------------------------------------
    # Panel toolbar actions
    # ------------------------------------------------------------------
    def _new_terminal(self):
        self.set_current_tab("Терминал")
        self.terminal_widget.create_new_tab()

    def _kill_terminal(self):
        self.set_current_tab("Терминал")
        self.terminal_widget.kill_current()

    def _clear_panel(self):
        if self.tab_widget.currentIndex() == 1:
            self.clear_problems()
        elif self.tab_widget.currentIndex() == 2:
            self.clear_output()
        else:
            self.terminal_widget.clear_current()

    def _hide_panel(self):
        window = self.window()
        if hasattr(window, "toggle_terminal"):
            window.toggle_terminal()

    def on_ui_scale_changed(self, percent: int):
        """Scale the panel strip buttons with the global UI scale."""
        from app.ui_scale import scale_px
        size = max(24, scale_px(28))
        for button in getattr(self, "_toolbar_buttons", {}).values():
            button.setFixedSize(size, size)
            button.setIconSize(QtCore.QSize(scale_px(16), scale_px(16)))

    # ------------------------------------------------------------------
    # Panel animations
    # ------------------------------------------------------------------
    def _animate_page_change(self, index: int):
        """Soft fade when switching between Терминал / Проблемы / Вывод."""
        widget = self.tab_widget.widget(index)
        if widget is None:
            return
        try:
            from widgets.animations import fade_in, DURATION
            fade_in(widget, duration=DURATION["fast"])
        except Exception:
            pass

    def _set_terminal_busy(self, busy: bool):
        """Animated '● process running' indicator on the Терминал tab."""
        index = self.tab_widget.indexOf(self.terminal_widget)
        if index < 0:
            return
        self.tab_widget.setTabText(index, "Терминал ●" if busy else "Терминал")
        try:
            from widgets.animations import fade_in, fade_out
            if busy:
                fade_in(self.tab_widget.tabBar(), duration=100)
        except Exception:
            pass

    def _refresh_terminal_tab_label(self, count: int):
        index = self.tab_widget.indexOf(self.terminal_widget)
        if index >= 0 and not self.tab_widget.tabText(index).endswith("●"):
            self.tab_widget.setTabText(index, "Терминал")
        if count > 1:
            index = self.tab_widget.indexOf(self.terminal_widget)
            if index >= 0:
                self.tab_widget.setTabToolTip(index, f"Открыто терминалов: {count}")

    def _update_problem_badge(self):
        count = self.problems_list.count() if hasattr(self, "problems_list") else 0
        index = self.tab_widget.indexOf(self.problems_widget)
        if index < 0:
            return
        self.tab_widget.setTabText(index, f"Проблемы ({count})" if count else "Проблемы")
        self._problem_badge.setText(f"{count}" if count else "")
        self._problem_badge.setVisible(bool(count))
        if count:
            try:
                from widgets.animations import flash
                flash(self.problems_widget, color="#F14C4C", alpha=55, duration=420)
            except Exception:
                pass

    def _toolbar(self, title, clear_slot):
        bar = QtWidgets.QFrame(); bar.setObjectName("panelToolbar")
        row = QtWidgets.QHBoxLayout(bar); row.setContentsMargins(10, 5, 10, 5); row.setSpacing(8)
        label = QtWidgets.QLabel(title); label.setObjectName("panelTitle")
        context = QtWidgets.QLabel("Активный файл"); context.setObjectName("panelContext")
        clear = QtWidgets.QPushButton("Очистить"); clear.setObjectName("panelToolButton"); clear.clicked.connect(clear_slot)
        row.addWidget(label); row.addWidget(context); row.addStretch(); row.addWidget(clear)
        return bar, context

    def _create_problems(self):
        widget = QtWidgets.QWidget(); widget.setObjectName("problemsPane")
        layout = QtWidgets.QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        
        bar = QtWidgets.QFrame(); bar.setObjectName("panelToolbar")
        row = QtWidgets.QHBoxLayout(bar); row.setContentsMargins(10, 5, 10, 5); row.setSpacing(8)
        label = QtWidgets.QLabel("Проблемы"); label.setObjectName("panelTitle")
        self.problems_context = QtWidgets.QLabel("Активный файл"); self.problems_context.setObjectName("panelContext")
        
        copy_btn = QtWidgets.QPushButton("Скопировать")
        set_line_icon(copy_btn, "copy")
        copy_btn.setObjectName("panelToolButton")
        copy_btn.setToolTip("Скопировать список проблем в буфер обмена")
        copy_btn.clicked.connect(self.copy_problems)

        save_btn = QtWidgets.QPushButton("Сохранить в файл…")
        set_line_icon(save_btn, "save")
        save_btn.setObjectName("panelToolButton")
        save_btn.setToolTip("Экспортировать проблемы в файл (.txt, .md, .json)")
        save_btn.clicked.connect(self.save_problems_to_file)

        clear = QtWidgets.QPushButton("Очистить")
        clear.setObjectName("panelToolButton")
        clear.clicked.connect(self.clear_problems)

        row.addWidget(label)
        row.addWidget(self.problems_context)
        row.addStretch()
        row.addWidget(copy_btn)
        row.addWidget(save_btn)
        row.addWidget(clear)
        layout.addWidget(bar)

        self.problems_list = QtWidgets.QListWidget(); self.problems_list.setObjectName("problemsList")
        self.problems_list.setAlternatingRowColors(True)
        self.problems_list.itemDoubleClicked.connect(self._open_problem)
        self.problems_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.problems_list.customContextMenuRequested.connect(self._problems_context_menu)
        layout.addWidget(self.problems_list)
        return widget

    def _problems_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        curr = self.problems_list.itemAt(pos)
        if curr:
            act_copy_one = menu.addAction(line_icon("copy"), "Скопировать выбранную проблему")
            act_copy_one.triggered.connect(lambda: self._copy_single_problem(curr))
            act_open = menu.addAction(line_icon("search"), "Перейти к строке")
            act_open.triggered.connect(lambda: self._open_problem(curr))
            menu.addSeparator()

        act_copy_all = menu.addAction(line_icon("copy"), "Скопировать все проблемы")
        act_copy_all.triggered.connect(self.copy_problems)

        act_save = menu.addAction(line_icon("save"), "Сохранить список в файл…")
        act_save.triggered.connect(self.save_problems_to_file)

        menu.addSeparator()
        act_clear = menu.addAction(line_icon("trash"), "Очистить список")
        act_clear.triggered.connect(self.clear_problems)
        menu.exec_(self.problems_list.mapToGlobal(pos))

    def _copy_single_problem(self, item):
        if not item: return
        path = item.data(QtCore.Qt.UserRole) or ""
        line = item.data(QtCore.Qt.UserRole + 1) or 1
        text = f"{item.text()} ({path}:{line})"
        QtWidgets.QApplication.clipboard().setText(text)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Проблема скопирована в буфер")

    def copy_problems(self):
        """Скопировать все проблемы в буфер обмена."""
        if not self.problems_list.count():
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Список проблем пуст")
            return
        lines = []
        for i in range(self.problems_list.count()):
            it = self.problems_list.item(i)
            path = it.data(QtCore.Qt.UserRole) or ""
            line = it.data(QtCore.Qt.UserRole + 1) or 1
            lines.append(f"{it.text()} | {path}:{line}")
        report = "\n".join(lines)
        QtWidgets.QApplication.clipboard().setText(report)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), f"Скопировано {len(lines)} проблем")

    def save_problems_to_file(self):
        """Сохранить список проблем в файл."""
        if not self.problems_list.count():
            QtWidgets.QMessageBox.information(self, "Проблемы", "Список проблем пуст.")
            return

        file_path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт о проблемах в коде",
            "code_problems_report.md",
            "Markdown (*.md);;Текстовый файл (*.txt);;JSON (*.json)"
        )
        if not file_path:
            return

        try:
            items_data = []
            for i in range(self.problems_list.count()):
                it = self.problems_list.item(i)
                items_data.append({
                    "text": it.text(),
                    "file": str(it.data(QtCore.Qt.UserRole) or ""),
                    "line": int(it.data(QtCore.Qt.UserRole + 1) or 1)
                })

            p = Path(file_path)
            ext = p.suffix.lower()
            if ext == ".json":
                import json
                p.write_text(json.dumps(items_data, ensure_ascii=False, indent=2), encoding="utf-8")
            elif ext == ".md":
                md_lines = [
                    f"# Отчёт о проблемах в коде проекта",
                    f"",
                    f"> Сформировано в PyScribe IDE. Всего замечаний: **{len(items_data)}**.",
                    f"",
                    f"| # | Тип и описание | Файл | Строка |",
                    f"| :--- | :--- | :--- | :--- |",
                ]
                for idx, row in enumerate(items_data, 1):
                    fn = Path(row['file']).name if row['file'] else "—"
                    md_lines.append(f"| {idx} | {row['text']} | `{fn}` | {row['line']} |")
                p.write_text("\n".join(md_lines), encoding="utf-8")
            else:
                txt_lines = [f"Отчёт о проблемах в коде проекта ({len(items_data)} замечаний):\n"]
                for idx, row in enumerate(items_data, 1):
                    txt_lines.append(f"{idx}. {row['text']} [{row['file']}:{row['line']}]")
                p.write_text("\n".join(txt_lines), encoding="utf-8")

            QtWidgets.QMessageBox.information(self, "Успешно", f"Отчёт сохранён:\n{p.name}")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Ошибка сохранения", f"Не удалось сохранить отчёт: {exc}")

    def _create_output(self):
        widget = QtWidgets.QWidget(); widget.setObjectName("outputPane")
        layout = QtWidgets.QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        toolbar, self.output_context = self._toolbar("Вывод", self.clear_output)
        layout.addWidget(toolbar)
        self.output_text = QtWidgets.QTextEdit(); self.output_text.setObjectName("outputText"); self.output_text.setReadOnly(True)
        self.output_text.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        layout.addWidget(self.output_text)
        return widget

    def _open_problem(self, item):
        path = item.data(QtCore.Qt.UserRole)
        line = item.data(QtCore.Qt.UserRole + 1) or 1
        if path and self.parent() and hasattr(self.parent(), "open_analysis_location"):
            self.parent().open_analysis_location(path, int(line))

    def add_problem(self, problem_type, file_path, line, description, is_lsp=False):
        type_str = {"error": "ОШИБКА", "warning": "ПРЕДУПРЕЖДЕНИЕ", "info": "ИНФОРМАЦИЯ"}.get(problem_type, str(problem_type).upper())
        item = QtWidgets.QListWidgetItem(f"{type_str}  {description}  ·  строка {line}")
        item.setData(QtCore.Qt.UserRole, str(file_path)); item.setData(QtCore.Qt.UserRole + 1, int(line or 1))
        if is_lsp:
            item.setData(QtCore.Qt.UserRole + 2, "lsp")
        color = {"error":"#F14C4C", "warning":"#CCA700", "info":"#A8A8A8"}.get(problem_type, "#D4D4D4")
        item.setForeground(QtGui.QColor(color)); self.problems_list.addItem(item)
        self._update_problem_badge()

    def _on_lsp_diagnostics(self, file_path: str, diagnostics: list):
        norm = str(Path(file_path).resolve())
        if not hasattr(self, "_lsp_diagnostics"):
            self._lsp_diagnostics = {}
        self._lsp_diagnostics[norm] = diagnostics

        if self._current_file and str(Path(self._current_file).resolve()) == norm:
            self._sync_lsp_problems(norm)

    def _on_lsp_diagnostics_cleared(self, file_path: str):
        norm = str(Path(file_path).resolve())
        if hasattr(self, "_lsp_diagnostics"):
            self._lsp_diagnostics.pop(norm, None)
        if self._current_file and str(Path(self._current_file).resolve()) == norm:
            self._sync_lsp_problems(norm)

    def _sync_lsp_problems(self, norm_path: str):
        # Remove existing LSP items for this file
        for i in reversed(range(self.problems_list.count())):
            it = self.problems_list.item(i)
            if it.data(QtCore.Qt.UserRole + 2) == "lsp":
                self.problems_list.takeItem(i)

        diags = getattr(self, "_lsp_diagnostics", {}).get(norm_path, [])
        for d in diags:
            self.add_problem(
                problem_type=d.severity,
                file_path=norm_path,
                line=d.line,
                description=f"[{d.source or 'LSP'}] {d.message}",
                is_lsp=True
            )
        self._update_problem_badge()

    def append_output(self, text, is_error=False):
        if not text: return
        cursor = self.output_text.textCursor(); cursor.movePosition(QtGui.QTextCursor.End)
        cursor.setCharFormat(QtGui.QTextCharFormat())
        fmt = QtGui.QTextCharFormat(); fmt.setForeground(QtGui.QColor("#F14C4C" if is_error else "#D4D4D4")); cursor.setCharFormat(fmt)
        cursor.insertText(str(text)); self.output_text.setTextCursor(cursor); self.output_text.ensureCursorVisible()

    def clear_problems(self):
        self.problems_list.clear()
        self._update_problem_badge()

    def clear_output(self):
        self.output_text.clear()

    def apply_terminal_settings(self):
        if hasattr(self, 'terminal_widget') and hasattr(self.terminal_widget, 'apply_terminal_settings'):
            self.terminal_widget.apply_terminal_settings()

    @staticmethod
    def _analysis_signature(file_path, content, engine=None):
        """Cheap identity of "this exact file content, analysed this way"."""
        if content is not None:
            fingerprint = f"{len(content)}:{hash(content) & 0xFFFFFFFF:x}"
        else:
            try:
                stat = Path(file_path).stat()
                fingerprint = f"{stat.st_size}:{int(stat.st_mtime_ns)}"
            except OSError:
                fingerprint = "missing"
        analyzers = ""
        if engine is not None:
            try:
                analyzers = ",".join(sorted(getattr(engine, "enabled_analyzers", ()) or ()))
            except TypeError:
                analyzers = ""
        return (fingerprint, analyzers, str(getattr(engine, "root", "") or ""))

    def set_file_context(self, file_path, file_info=None, engine=None, content=None):
        """Show only diagnostics/metrics belonging to the active editor file."""
        self._current_file = str(file_path) if file_path else None
        name = Path(file_path).name if file_path else "Нет открытого файла"
        self.problems_context.setText(name); self.output_context.setText(name)
        self.problems_list.clear(); self.output_text.clear()
        self._update_problem_badge()
        if not file_path:
            self.output_text.setPlainText("Откройте файл, чтобы увидеть его диагностику и вывод.")
            return
        info = file_info
        if info is None and engine is not None and not getattr(engine, "enabled_analyzers", set()):
            self.output_text.setPlainText("Анализ отключен для этого проекта.")
            return
        if info is None and engine is not None:
            signature = self._analysis_signature(file_path, content, engine)
            cached = self._analysis_cache.get(str(file_path))
            if cached is not None and cached[0] == signature:
                info = cached[1]
            else:
                try: info = engine.analyze_file(str(file_path), content)
                except Exception as exc:
                    self.output_text.setPlainText(f"Ошибка анализа файла: {exc}"); return
                if info is not None:
                    self._analysis_cache[str(file_path)] = (signature, info)
                    if len(self._analysis_cache) > 64:
                        # Keep the cache bounded; the active files are few.
                        self._analysis_cache.pop(next(iter(self._analysis_cache)))
        # Always sync LSP diagnostics for active file
        self._sync_lsp_problems(str(Path(file_path).resolve()))

        if info is None:
            if not self.problems_list.count():
                self.output_text.setPlainText("Для этого файла нет активного анализатора.")
            else:
                self.output_text.setPlainText("Диагностика предоставлена языковым сервером LSP.")
            return
        for issue in getattr(info, "issues", []):
            self.add_problem(issue.severity, issue.file, issue.line, f"{issue.code}: {issue.message}")
        metrics = getattr(info, "metrics", {}) or {}
        lines = [f"Файл: {file_path}", f"Язык: {getattr(info, 'language', 'unknown')}", f"Строк: {getattr(info, 'lines', 0)}", f"Функций: {getattr(info, 'functions', 0)}", f"Классов: {getattr(info, 'classes', 0)}", f"Сложность: {getattr(info, 'complexity', 0)}"]
        if metrics:
            lines.append("\nМетрики:")
            for key, value in metrics.items():
                lines.append(f"  {key}: {value}")
        self.output_text.setPlainText("\n".join(lines))
        self._update_problem_badge()
        # Do not steal focus from the terminal when switching files.
        if self.problems_list.count() and self.tab_widget.currentIndex() == 2:
            self.tab_widget.setCurrentIndex(1)

    def set_analysis(self, analysis, engine=None):
        """Compatibility wrapper; display the currently active file only."""
        if self._current_file:
            info = analysis.files.get(str(Path(self._current_file).resolve())) if analysis else None
            self.set_file_context(self._current_file, info, engine)

    def get_terminal(self): return self.terminal_widget

    def set_current_tab(self, tab_name):
        mapping = {
            "Terminal": 0, "Problems": 1, "Output": 2,
            "Терминал": 0, "Проблемы": 1, "Вывод": 2,
        }
        index = mapping.get(tab_name)
        if index is not None: self.tab_widget.setCurrentIndex(index)

    def run_command(self, command, working_dir=None):
        self.set_current_tab("Терминал")
        self.terminal_widget.run_command(command, working_dir)

    def shutdown(self):
        if hasattr(self, 'terminal_widget') and hasattr(self.terminal_widget, 'shutdown'):
            try:
                self.terminal_widget.shutdown()
            except Exception:
                pass

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
