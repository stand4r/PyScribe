"""Tests for app package architecture and problem export features."""
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path for local module resolution
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication

# Ensure offscreen Qt environment for headless tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_main_reexports():
    """Verify that main.py remains backwards-compatible with all public symbols."""
    import main
    expected_symbols = [
        "main",
        "ApplicationManager",
        "ModernMainWindow",
        "WorkbenchController",
        "WorkbenchTopBar",
        "ExplorerHeader",
        "TITLE_BAR_HEIGHT",
        "UIManager",
        "FileManager",
        "ProjectHandler",
        "CodeRunner",
        "setup_application_style",
        "_load_design_qss",
    ]
    for sym in expected_symbols:
        assert hasattr(main, sym), f"Symbol {sym} missing from main.py"


def test_app_submodules_import():
    """Verify clean imports of all modular app packages."""
    from app import (
        ApplicationManager,
        ModernMainWindow,
        WorkbenchController,
        WorkbenchTopBar,
        ExplorerHeader,
        UIManager,
        FileManager,
        ProjectHandler,
        CodeRunner,
        setup_application_style,
        main,
    )
    from app.styling import _load_design_qss, setup_application_style
    from app.top_bar import TITLE_BAR_HEIGHT

    assert TITLE_BAR_HEIGHT > 0
    assert callable(main)
    assert callable(setup_application_style)


def test_ui_font_resolution():
    """The interface font must resolve to a family the system really has."""
    app = QApplication.instance() or QApplication([])
    from app.styling import (UI_FONT_CANDIDATES, is_font_available, resolve_mono_font,
                             resolve_ui_font, ui_font_family)

    assert is_font_available("NoSuchFont12345") is False
    family = resolve_ui_font()
    assert family, "resolve_ui_font должен вернуть имя семейства"
    # Whatever is returned must be a real installed family (or the final fallback).
    assert family == "Segoe UI" or is_font_available(family)
    assert ui_font_family() == family
    assert resolve_mono_font()
    # Candara is the default: a normal-width face, unlike Bahnschrift, whose
    # condensed variable instance made the whole UI look squeezed.
    assert UI_FONT_CANDIDATES[0] == "Candara"
    assert "Bahnschrift" not in UI_FONT_CANDIDATES


def test_theme_uses_font_tokens():
    """The interface font is set by QApplication, not per-rule in the stylesheet.

    A `font-family` rule in QSS replaces the widget font and dropped the width
    settings, which is what made Bahnschrift look condensed. Only monospace
    families remain in the stylesheet (as tokens), everything else inherits the
    application font.
    """
    theme = (ROOT / "design" / "theme.qss").read_text(encoding="utf-8")
    assert "@mono_font@" in theme
    declarations = [line.split("font-family:", 1)[1] for line in theme.splitlines()
                    if "font-family:" in line]
    assert declarations, "в theme.qss не найдено ни одного font-family"
    for declaration in declarations:
        first = declaration.split(",")[0].strip().strip(";").strip()
        assert "@mono_font@" in first, declaration
    # The UI family must come from application code only.
    assert "@ui_font@" not in theme


def test_ui_titlebar_facade():
    """Verify ui/titlebar.py re-exports properly."""
    from ui.titlebar import WorkbenchTopBar, ExplorerHeader, TITLE_BAR_HEIGHT
    # 40 px is the value fixed by the visual system (ARCHITECTURE.md,
    # "Menu strip (title bar) | 40 px"); the old 48 px strip was replaced when
    # the chrome was aligned with VS Code metrics.
    assert TITLE_BAR_HEIGHT == 40


def test_console_widget_problems_export():
    """Verify ConsoleWidget problem formatting and export capabilities."""
    app = QApplication.instance() or QApplication([])
    from widgets.ConsoleWidget import ConsoleWidget
    cw = ConsoleWidget()

    # Add sample problems
    cw.add_problem("error", "main.py", 42, "SyntaxError: invalid syntax")
    cw.add_problem("warning", "app.py", 3, "Unused import 'sys'")

    assert cw.problems_list.count() == 2

    # Check copy_problems
    cw.copy_problems()
    clip_text = QApplication.clipboard().text()
    assert "SyntaxError: invalid syntax" in clip_text
    assert "main.py:42" in clip_text

    # Verify methods exist
    assert hasattr(cw, "save_problems_to_file")
    assert hasattr(cw, "_copy_single_problem")


def test_project_intelligence_tips_export():
    """Verify ProjectIntelligenceDashboard tips data collection and formatting."""
    app = QApplication.instance() or QApplication([])
    from widgets.ProjectIntelligenceDashboard import ProjectIntelligenceDashboard
    pid = ProjectIntelligenceDashboard()

    # Tips tree methods exist
    assert hasattr(pid, "_copy_tips")
    assert hasattr(pid, "_save_tips_to_file")
    assert hasattr(pid, "_collect_tips_data")
    assert hasattr(pid, "copy_tips_btn")
    assert hasattr(pid, "save_tips_btn")


def test_project_handler_normalize_root():
    """Verify ProjectHandler _normalize_root handles configs, dicts, and paths."""
    from app.project_handler import ProjectHandler
    handler = ProjectHandler(None)
    assert hasattr(handler, "_normalize_root")
    assert hasattr(handler, "on_project_opened")

    class DummyCfg:
        root_path = "."

    assert handler._normalize_root(DummyCfg()) == str(Path(".").resolve())
    assert handler._normalize_root({"root": "."}) == str(Path(".").resolve())
    assert handler._normalize_root(".") == str(Path(".").resolve())
    assert handler._normalize_root(None) == ""


def test_user_overrides_never_paint_text_surfaces():
    """User overrides must not give text widgets an opaque background.

    The block is appended to ``design/theme.qss`` and therefore wins against
    equal-specificity rules. A blanket ``QWidget { background: ... }`` repaints
    every label and tool button with the window colour, which showed up as
    rectangles whose background did not match the card they sat on (Git panel,
    AI bubbles, analysis cards).
    """
    from app.styling import user_appearance_qss
    qss = user_appearance_qss({'app_background': '#17191C',
                               'text_primary': '#CCCCCC',
                               'editor_background': '#1E1E1E'}, 13)
    text_selectors = {"QWidget", "QLabel", "QToolButton", "QCheckBox",
                      "QRadioButton", "QGroupBox", "QAbstractButton"}
    checked = 0
    for block in qss.split("}"):
        if "{" not in block:
            continue
        selectors, declarations = block.split("{", 1)
        names = {part.strip().split(":")[0].strip()
                 for part in selectors.replace("\n", " ").split(",")}
        if names & text_selectors:
            checked += 1
            assert "background" not in declarations, block.strip()
    assert checked, "не найдено ни одного правила, управляющего текстовыми виджетами"


if __name__ == "__main__":
    test_main_reexports()
    print("test_main_reexports: PASS")
    test_app_submodules_import()
    print("test_app_submodules_import: PASS")
    test_ui_titlebar_facade()
    print("test_ui_titlebar_facade: PASS")
    test_ui_font_resolution()
    print("test_ui_font_resolution: PASS")
    test_theme_uses_font_tokens()
    print("test_theme_uses_font_tokens: PASS")
    test_console_widget_problems_export()
    print("test_console_widget_problems_export: PASS")
    test_project_intelligence_tips_export()
    print("test_project_intelligence_tips_export: PASS")
    test_project_handler_normalize_root()
    print("test_project_handler_normalize_root: PASS")
    test_user_overrides_never_paint_text_surfaces()
    print("test_user_overrides_never_paint_text_surfaces: PASS")
    print("\nALL ARCHITECTURE AND EXPORT TESTS PASSED SUCCESSFULLY!")
