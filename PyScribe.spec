# -*- mode: python ; coding: utf-8 -*-
# PyScribe PyInstaller Specification
# Builds a self-contained, windowless Windows desktop IDE executable and bundle.

from pathlib import Path

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "src"), "src"),
    (str(ROOT / "design" / "theme.qss"), "design"),
    (str(ROOT / "design" / "fonts"), "design/fonts"),
    (str(ROOT / "design" / "icons"), "design/icons"),
    (str(ROOT / "config" / "settings.default.json"), "config"),
    (str(ROOT / "USER_GUIDE.md"), "."),
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "third_party" / "assembly" / "nasm"), "third_party/assembly/nasm"),
    (str(ROOT / "third_party" / "assembly" / "fasm"), "third_party/assembly/fasm"),
]

hiddenimports = [
    # PyQt5 Core and GUI
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
    "PyQt5.QtPrintSupport",
    "PyQt5.QtWebEngineWidgets",
    "PyQt5.sip",
    # System and Process inspection
    "psutil",
    "pyte",
    # Syntax highlighting & themes
    "pygments",
    "pygments.lexers",
    "pygments.styles",
    "pygments.formatters",
    # Application modular subsystems
    "app.application",
    "app.main_window",
    "app.controller",
    "app.top_bar",
    "app.ui_manager",
    "app.file_manager",
    "app.project_handler",
    "app.code_runner",
    "app.styling",
    # Core analyzers & services
    "core.logging_config",
    "core.single_instance",
    "core.project_intelligence",
    "core.workspace_index",
    "core.security",
    "core.analyzers.registry",
    "core.analyzers.polyglot",
    "core.analyzers.binary",
    "services.code_intelligence_service",
    "services.github_service",
    "services.process_runner",
    "services.state_store",
    # Widgets
    "widgets.ActivityBar",
    "widgets.GitPanel",
    "widgets.ProjectIntelligenceDashboard",
    "widgets.ChangeCapsuleDialog",
    "widgets.HexViewer",
    "widgets.PDFViewerWidget",
    "widgets.MarkdownViewerWidget",
    "widgets.DocumentViewerWidget",
    "widgets.ConsoleWidget",
    "widgets.TerminalWidget",
    "widgets.Explorer",
    "widgets.QCodeEditor",
    "widgets.AboutDialog",
    "widgets.SettingsWidget",
    "widgets.FindReplaceBar",
    "widgets.QuickOpenDialog",
    "widgets.CommandPalette",
    "widgets.KeyboardShortcutsDialog",
    "widgets.AnalysisProfilesDialog",
    "widgets.ProjectManager",
    "widgets.ProjectDialog",
    "widgets.RunDebugPanel",
    "widgets.SearchPanel",
    "widgets.TabWidget",
    "widgets.WelcomeWidget",
    # Utilities
    "utils.programs",
    "utils.settings_manager",
    "utils.toolchain_detector",
]


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyScribe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "src" / "PyScribe.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PyScribe",
)
