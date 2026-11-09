"""PyScribe widgets/CodeExplainerDialog.py: Professional Code Intelligence & Complexity Inspector."""
from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Dict, Any


class CodeExplainerDialog(QtWidgets.QDialog):
    """Visual dialog providing code explanation, complexity analysis, and architectural review questions."""

    def __init__(self, data: Dict[str, Any], snippet: str, parent=None):
        super().__init__(parent)
        self.data = data or {}
        self.snippet = snippet or ""
        self.setWindowTitle("PyScribe — Интеллектуальный анализ кода")
        self.resize(760, 580)
        self.setMinimumSize(620, 460)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header Box
        header_frame = QtWidgets.QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        hl = QtWidgets.QHBoxLayout(header_frame)
        hl.setContentsMargins(14, 12, 14, 12)
        hl.setSpacing(14)

        title_vbox = QtWidgets.QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QtWidgets.QLabel(self.data.get("title", "Фрагмент кода"))
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #58A6FF;")
        sub_lbl = QtWidgets.QLabel("Алгоритмическая декомпозиция, вычислительная сложность и вопросы для Code Review")
        sub_lbl.setStyleSheet("font-size: 11px; color: #8B949E;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        hl.addLayout(title_vbox, 1)

        complexity = self.data.get("complexity", "O(1)")
        comp_badge = QtWidgets.QLabel(f"{complexity}")
        comp_badge.setStyleSheet("""
            background: #21262D;
            color: #7EE787;
            font-size: 11px;
            font-weight: bold;
            padding: 6px 12px;
            border: 1px solid #3FB950;
            border-radius: 14px;
        """)
        hl.addWidget(comp_badge)
        layout.addWidget(header_frame)

        # Tab Widget for sections
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #30363D;
                background: #0D1117;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #161B22;
                color: #8B949E;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #21262D;
                color: #FFFFFF;
                border-bottom: 2px solid #58A6FF;
            }
        """)

        # Tab 1: Explanation
        expl_tab = QtWidgets.QWidget()
        expl_layout = QtWidgets.QVBoxLayout(expl_tab)
        expl_layout.setContentsMargins(16, 16, 16, 16)
        expl_layout.setSpacing(12)

        summary_box = QtWidgets.QTextBrowser()
        summary_box.setReadOnly(True)
        summary_box.setStyleSheet("background: transparent; border: none; font-size: 13px; color: #E6EDF3; line-height: 1.5;")

        args_text = ""
        if self.data.get("arguments"):
            args_list = ", ".join(f"`{a}`" for a in self.data["arguments"])
            args_text = f"<p><b>Принимаемые параметры:</b> {args_list}</p>"

        tips_html = ""
        tips = self.data.get("tips", [])
        if tips:
            items = "".join(f"<li style='margin-bottom: 6px;'>{tip}</li>" for tip in tips)
            tips_html = f"<div style='margin-top: 14px;'><b>Рекомендации по чистоте и оптимизации:</b><ul style='margin-top: 6px; padding-left: 20px;'>{items}</ul></div>"

        html_content = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'>
            <p style='font-size: 14px; color: #FFFFFF;'><b>Назначение и логика работы:</b></p>
            <p style='color: #C9D1D9; font-size: 13px;'>{self.data.get('summary', '')}</p>
            {args_text}
            {tips_html}
        </div>
        """
        summary_box.setHtml(html_content)
        expl_layout.addWidget(summary_box)
        tabs.addTab(expl_tab, "Анализ логики и сигнатуры")

        # Tab 2: Review Questions
        q_tab = QtWidgets.QWidget()
        q_layout = QtWidgets.QVBoxLayout(q_tab)
        q_layout.setContentsMargins(16, 16, 16, 16)
        q_layout.setSpacing(12)

        q_browser = QtWidgets.QTextBrowser()
        q_browser.setReadOnly(True)
        q_browser.setStyleSheet("background: transparent; border: none; font-size: 13px; color: #E6EDF3;")

        questions = self.data.get("review_questions") or self.data.get("teacher_questions", [])
        q_cards_html = ""
        for i, qa in enumerate(questions, 1):
            q_cards_html += f"""
            <div style='background: #161B22; border: 1px solid #30363D; border-left: 4px solid #58A6FF; border-radius: 6px; padding: 12px 14px; margin-bottom: 12px;'>
                <div style='font-weight: bold; color: #79C0FF; font-size: 13px; margin-bottom: 6px;'>Вопрос {i}: {qa.get('q', '')}</div>
                <div style='color: #C9D1D9; font-size: 12.5px; line-height: 1.4; background: #0D1117; padding: 8px 12px; border-radius: 4px; border: 1px dashed #30363D;'>
                    <b style='color: #7EE787;'>Ответ / Пояснение:</b> <i>"{qa.get('a', '')}"</i>
                </div>
            </div>
            """

        q_tab_html = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'>
            <p style='color: #8B949E; font-size: 12px; margin-bottom: 12px;'>
                Ключевые вопросы по алгоритмам и реализации, актуальные для Code Review и технических собеседований:
            </p>
            {q_cards_html if q_cards_html else '<p>Вопросов по данному фрагменту не сформировано.</p>'}
        </div>
        """
        q_browser.setHtml(q_tab_html)
        q_layout.addWidget(q_browser)
        tabs.addTab(q_tab, f"Вопросы на Code Review ({len(questions)})")

        layout.addWidget(tabs, 1)

        # Bottom Bar
        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(0, 4, 0, 0)

        copy_btn = QtWidgets.QPushButton("Скопировать разбор в буфер")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #30363D;
                color: #FFFFFF;
            }
        """)
        copy_btn.clicked.connect(self._copy_to_clipboard)
        bottom_bar.addWidget(copy_btn)

        bottom_bar.addStretch()

        close_btn = QtWidgets.QPushButton("Закрыть")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #238636;
                color: white;
                border: none;
                padding: 6px 18px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2EA043;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

    def _copy_to_clipboard(self):
        text_parts = [
            f"=== {self.data.get('title', 'Код')} ===",
            f"Сложность: {self.data.get('complexity', '—')}",
            f"\nЛогика работы:\n{self.data.get('summary', '')}\n",
        ]
        questions = self.data.get("review_questions") or self.data.get("teacher_questions", [])
        if questions:
            text_parts.append("Вопросы и ответы для Code Review:")
            for i, qa in enumerate(questions, 1):
                text_parts.append(f"{i}. В: {qa.get('q', '')}\n   О: {qa.get('a', '')}\n")

        full_text = "\n".join(text_parts)
        QtGui.QGuiApplication.clipboard().setText(full_text)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Анализ кода скопирован в буфер обмена!")
