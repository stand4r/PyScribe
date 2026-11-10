"""PyScribe application styling and visual design system integration."""
from __future__ import annotations

import os
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette
from PyQt5.QtWidgets import QApplication

from core.logging_config import get_logger
from design.themes import THEMES
from utils.settings_manager import get_settings_manager

logger = get_logger("styling")

# Interface typography. Segoe UI reads as an office application; Bahnschrift
# turned out to be a _condensed_ variable font (≈86 % of Segoe UI's width), so
# the whole interface looked horizontally squeezed. The list is ordered by
# preference and the first installed family wins; a Settings choice overrides it.
UI_FONT_CANDIDATES = (
    "Candara",
    "Corbel",
    "Segoe UI Variable Text",
    "Inter",
    "Segoe UI",
    "Arial",
)
# Kept selectable, but last: its condensed default needs an explicit warning.
UI_FONT_DEPRECATED = ("Bahnschrift",)
MONO_FONT_CANDIDATES = (
    "Cascadia Code",
    "JetBrains Mono",
    "Consolas",
    "Courier New",
)


def is_font_available(family: str) -> bool:
    """True when Windows actually has this family installed."""
    if not family:
        return False
    try:
        return QtGui.QFontInfo(QtGui.QFont(family)).exactMatch()
    except Exception:
        return False


def resolve_ui_font() -> str:
    """Pick the interface font: user choice, else the first installed candidate."""
    try:
        preferred = str(get_settings_manager().get_setting("ui_font", "") or "").strip()
    except Exception:
        preferred = ""
    if preferred and is_font_available(preferred):
        return preferred
    for candidate in UI_FONT_CANDIDATES:
        if is_font_available(candidate):
            return candidate
    return "Segoe UI"


def resolve_mono_font() -> str:
    """Pick the monospace font used by the editor and terminal."""
    for candidate in MONO_FONT_CANDIDATES:
        if is_font_available(candidate):
            return candidate
    return "Consolas"


_ui_font_cache: dict = {"key": None, "value": None}


def ui_font_family() -> str:
    """Cached resolved interface font for painters that build ``QFont`` objects.

    Recomputing ``QFontInfo`` on every repaint would be wasteful, so the result
    is cached and invalidated when the ``ui_font`` setting changes.
    """
    try:
        key = str(get_settings_manager().get_setting("ui_font", "") or "")
    except Exception:
        key = ""
    if _ui_font_cache["value"] is None or _ui_font_cache["key"] != key:
        _ui_font_cache["key"] = key
        _ui_font_cache["value"] = resolve_ui_font()
    return _ui_font_cache["value"]


def ui_qfont(point_size: int = 9, weight=None, bold: bool = False) -> QFont:
    """Interface font as a configured ``QFont``."""
    font = QFont(ui_font_family(), int(point_size))
    font.setStyleStrategy(QFont.PreferAntialias)
    if bold:
        font.setBold(True)
    elif weight is not None:
        font.setWeight(int(weight))
    return font


def _set_windows_app_identity():
    """Give Windows a stable AppUserModelID so the taskbar uses PyScribe identity.

    When running from Python, Windows can otherwise group the window under the
    Python/Qt host and display the generic Python icon.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "PyScribe.PyScribe.1"
        )
    except Exception:
        pass


def _load_design_qss(base_path: Path) -> str:
    """Load the single source of truth for the PyScribe visual system."""
    qss_path = base_path / "design" / "theme.qss"
    try:
        qss = qss_path.read_text(encoding="utf-8")
        close_icon = (base_path / "design" / "icons" / "tab-close.svg").as_posix()
        qss = qss.replace("url(icons/tab-close.svg)", f"url({close_icon})")
        # The base stylesheet uses design tokens rather than hard-coded theme islands.
        # This keeps every widget on the same surface when the user changes theme.
        sm = get_settings_manager()
        settings = sm.get_all_settings()
        preset = THEMES.get(str(settings.get("theme", "dark")), THEMES["dark"])
        colors = {key: settings.get(key, value) for key, value in preset.items()}
        token_map = {
            "#181818": colors.get("app_background", "#181818"),
            "#1E1E1E": colors.get("editor_background", "#1E1E1E"),
            "#242424": colors.get("input_background", "#242424"),
            "#2A2D2E": colors.get("hover_background", "#2A2D2E"),
            "#37373D": colors.get("active_background", "#37373D"),
            "#264F78": colors.get("selection_background", "#264F78"),
            "#2B2B2B": colors.get("border_color", "#2B2B2B"),
            "#0078D4": colors.get("accent_color", "#0078D4"),
            "#D4D4D4": colors.get("text_primary", "#D4D4D4"),
            "#A8A8A8": colors.get("text_secondary", "#A8A8A8"),
        }
        for source, target in token_map.items():
            qss = qss.replace(source, target)
        # Flat surfaces derived from the active palette keep both light and
        # dark themes readable without gradients or decorative highlights.
        surface = QColor(colors.get("panel_background", "#252526"))
        foreground = QColor(colors.get("text_primary", "#D4D4D4"))

        def tint(amount):
            return QColor(*[
                round(a + (b - a) * amount)
                for a, b in zip(surface.getRgb()[:3], foreground.getRgb()[:3])
            ]).name()

        glass_tokens = {
            "@glass_surface@": tint(0.035),
            "@glass_border@": tint(0.18),
            "@glass_hover@": tint(0.14),
            "@glass_menu@": tint(0.025),
            "@glass_text@": foreground.name(),
            "@markdown_paper@": tint(0.075),
            "@markdown_text@": tint(0.83),
            "@glass_focus@": colors.get("accent_color", "#0078D4"),
        }
        for token, value in glass_tokens.items():
            qss = qss.replace(token, value)
        # Typography tokens: the family is resolved once and substituted here so
        # every rule uses the same interface font.
        qss = qss.replace("@ui_font@", resolve_ui_font())
        qss = qss.replace("@mono_font@", resolve_mono_font())
        return qss
    except OSError as exc:
        logger.exception("PyScribe operation failed")
        return ""


def user_appearance_qss(settings: dict, ui_font_size: int) -> str:
    """Appearance overrides a user can change, appended to the design system.

    Only *values* live here; the block must never paint a background on a
    generic ``QWidget``. That selector also matches labels, tool buttons and
    check boxes, and because this block is appended last it would override the
    design's ``background: transparent`` rule: the text would then paint the
    window colour on top of cards, inputs and buttons — visible as rectangles
    whose background does not match the widget they sit on.
    """
    app_background = settings.get('app_background', '#181818')
    text_primary = settings.get('text_primary', '#CCCCCC')
    editor_background = settings.get('editor_background', '#1E1E1E')
    input_background = settings.get('input_background', '#313131')
    editor_font = settings.get('editor_font', 'Cascadia Code')
    editor_font_size = int(settings.get('editor_font_size', 13) or 13)
    terminal_font_size = int(settings.get('terminal_font_size', 11) or 11)
    tab_height = int(settings.get('tab_height', 35) or 35)
    chat_px = max(16, ui_font_size + 2)
    # Keep every chat-related control on the same typographic scale: the input
    # used to fall back to the 9pt editor font (12px) while answers were 16px,
    # and the code viewer inherited that small editor size as well.
    chat_code_pt = max(11, int(round(chat_px * 0.75)))       # 16px → 12pt
    chip_px = max(12, int(round(chat_px * 0.78)))            # context/model chips
    return f"""QWidget {{ font-size: {ui_font_size}px; color: {text_primary}; }}
QMainWindow, QDialog {{ background: {app_background}; }}
QFrame#workbenchTopBar, QFrame#activityBar, QFrame#sidePanel, QFrame#explorerHeader {{ background: {app_background}; }}
QLabel#aiUserBubbleText {{ font-size: {chat_code_pt}pt; }}
QPlainTextEdit#aiInput {{ font-size: {chat_code_pt}pt; padding: 2px 4px; }}
QPlainTextEdit#chatCodeView {{
    font-family: '{editor_font}';
    font-size: {chat_code_pt}pt;
}}
QToolButton#aiAccessMode, QToolButton#aiScopeButton, QToolButton#aiModelButton {{
    font-size: {chip_px}px;
}}
QLabel#aiStatsLine {{ font-size: {max(13, chip_px)}px; }}
QPlainTextEdit, QTextEdit#codeEditor, QTextEdit#terminalScreen {{
    background: {editor_background};
    color: {text_primary};
    font-family: '{editor_font}';
    font-size: {editor_font_size}pt;
}}
QTextEdit#terminalScreen {{ font-family: 'Cascadia Mono', 'Cascadia Code', 'Consolas', monospace; font-size: {terminal_font_size}pt; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {input_background}; color: {text_primary}; }}
QTabWidget#editorGroupPrimary QTabBar::tab, QTabWidget#editorGroupSecondary QTabBar::tab {{
    min-height: {tab_height}px;
    max-height: {tab_height}px;
}}
"""


class _DesignSystemEventFilter(QtCore.QObject):
    """Event filter for central theme integration without destructive stylesheet stripping."""

    def eventFilter(self, watched, event):
        return False


def setup_application_style(app: QApplication, base_path: Path):
    """Apply persisted theme and uniform typography before the first workbench widget is created."""
    app.setStyle("Fusion")
    app_font = ui_qfont(9)
    app.setFont(app_font)
    sm = get_settings_manager()
    settings = sm.get_all_settings()
    preset = THEMES.get(str(settings.get("theme", "dark")), THEMES["dark"])
    colors = {k: settings.get(k, v) for k, v in preset.items()}
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(colors["app_background"]))
    palette.setColor(QPalette.WindowText, QColor(colors["text_primary"]))
    palette.setColor(QPalette.Base, QColor(colors["editor_background"]))
    palette.setColor(QPalette.AlternateBase, QColor(colors["panel_background"]))
    palette.setColor(QPalette.ToolTipBase, QColor(colors["input_background"]))
    palette.setColor(QPalette.ToolTipText, QColor(colors["text_primary"]))
    palette.setColor(QPalette.Text, QColor(colors["text_primary"]))
    palette.setColor(QPalette.Button, QColor(colors["input_background"]))
    palette.setColor(QPalette.ButtonText, QColor(colors["text_primary"]))
    palette.setColor(QPalette.Highlight, QColor(colors["selection_background"]))
    palette.setColor(QPalette.HighlightedText, QColor(colors["text_primary"]))
    app.setPalette(palette)
    app.setStyleSheet(_load_design_qss(base_path))
    app._pyscribe_design_filter = _DesignSystemEventFilter(app)
    app.installEventFilter(app._pyscribe_design_filter)
    # Prefer the official mark (two slashes) for the window/taskbar icon.
    icon_candidates = [
        base_path / "src" / "PyScribe.ico",
        base_path / "src" / "icon_app_256.png",
        base_path / "src" / "icon_app.png",
    ]
    app_icon = next((p for p in icon_candidates if p.exists()), icon_candidates[-1])
    app.setWindowIcon(QIcon(str(app_icon)))
    _set_windows_app_id(app_icon)


def _set_windows_app_id(icon_path=None):
    """Group PyScribe under its own taskbar button on Windows.

    Without an explicit AppUserModelID, Windows attributes the window to
    ``python.exe``/the launcher and shows *their* icon in the taskbar, even
    though ``setWindowIcon`` is set. The ID must be set before the first
    top-level window is shown.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "PyScribe.Workbench.1")
    except Exception:
        get_logger("styling").debug("AppUserModelID not set", exc_info=True)
