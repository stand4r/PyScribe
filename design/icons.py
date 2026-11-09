"""VS Code (codicon) iconography for PyScribe.

PyScribe ships VS Code's official ``codicon.ttf`` (see design/fonts for licenses) so the activity
bar, explorer toolbar, terminal and window controls use exactly the same
monochrome glyphs as VS Code instead of bespoke neon line art.

Public API
----------
``CODICONS``                name -> codepoint mapping
``codicon_font(pixel_size)`` QFont configured for the codicon glyphs
``codicon_icon(name, size, color)`` QIcon from the glyph (retina aware)
``codicon_char(name)``      the glyph as ``str`` (for QSS ``content`` fallbacks)
``font_is_available()``     whether the bundled font could be loaded
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = [
    "CODICONS",
    "codicon_char",
    "codicon_font",
    "codicon_icon",
    "font_is_available",
    "FONT_FAMILY",
]

FONT_FAMILY = "codicon"

# Verified against the bundled ``codicon.ttf`` by rendering each glyph.
CODICONS: Dict[str, int] = {
    # Activity bar (matches VS Code's default activity bar)
    "files": 0xEA83,          # folder glyph (VS Code explorer icon is a folder
                              # silhouette; the "files" codepoint box reads as a
                              # 3D cube which looked wrong here)
    "document": 0xEB60,       # plain document
    "search": 0xEA6D,         # magnifier
    "source-control": 0xEA68, # branch graph
    "run": 0xEB2C,            # play triangle
    "debug": 0xEAD8,          # bug with play badge
    "extensions": 0xEA64,     # connected nodes (blocks)
    "settings-gear": 0xEB51,  # gear
    "terminal": 0xEADF,       # terminal prompt
    "intelligence": 0xEB31,   # pulse / heartbeat
    # Explorer toolbar
    "new-file": 0xEA7F,       # document with plus
    "new-folder": 0xEA80,     # folder with plus
    "refresh": 0xEB37,        # circular arrows
    "collapse-all": 0xEAC5,   # double up-chevron
    "expand-all": 0xEAC4,     # double down-chevron
    # Trees / lists
    "chevron-right": 0xEAB6,
    "chevron-down": 0xEAB4,
    "chevron-up": 0xEAB7,
    "send": 0xEAB7,           # upward chevron used as the chat "send" affordance
    "folder": 0xEA8B,         # simple folder
    "folder-opened": 0xEAF7,  # open folder
    "file": 0xEA7B,           # document
    "file-code": 0xEA85,
    "symbol-file": 0xEB70,
    "symbol-class": 0xEB5B,
    "symbol-method": 0xEAB8,
    # Generic actions
    "close": 0xEA76,          # x
    "add": 0xEAB0,            # plus
    "more": 0xEA7C,           # three vertical dots (kebab)
    "trash": 0xEBE2,          # trash can
    "clear-all": 0xEABF,      # x over lines
    "chrome-minimize": 0xEABA, # underscore
    "chrome-maximize": 0xEAB9, # square outline
    "chrome-restore": 0xEABB,  # two squares
    "chrome-close": 0xEAB8,    # x
    "error": 0xEB47,          # octagon with x
    "stop": 0xEB47,
    "warning": 0xEA6C,        # triangle with !
    "check": 0xEAB2,          # check mark
    "lightbulb": 0xEA61,
    "sparkle": 0xEBF0,
}

_FONT_LOADED: bool = False
_FONT_FAMILY_NAME: str = FONT_FAMILY


def _font_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / "codicon.ttf"


def _ensure_font() -> str:
    """Load the bundled codicon font once and return the usable family name."""
    global _FONT_LOADED, _FONT_FAMILY_NAME
    if _FONT_LOADED:
        return _FONT_FAMILY_NAME
    _FONT_LOADED = True
    path = _font_path()
    if not path.exists():
        return _FONT_FAMILY_NAME
    try:
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _FONT_FAMILY_NAME = families[0]
    except Exception:
        pass
    return _FONT_FAMILY_NAME


def font_is_available() -> bool:
    """True when the bundled codicon font was loaded successfully."""
    family = _ensure_font()
    try:
        return family in QtGui.QFontDatabase().families()
    except Exception:
        return False


def codicon_char(name: str) -> str:
    """Return the glyph character for a codicon name (empty if unknown)."""
    cp = CODICONS.get(name)
    return chr(cp) if cp else ""


def codicon_font(pixel_size: int = 16) -> QtGui.QFont:
    """QFont that renders codicon glyphs at *pixel_size* device-independent px."""
    family = _ensure_font()
    font = QtGui.QFont(family)
    font.setPixelSize(int(pixel_size))
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    return font


def ai_icon(size: int = 16, color: str = "#868686", accent: str = "") -> QtGui.QIcon:
    """The dedicated AI-agent glyph: a four-point spark plus a small companion.

    Drawn as vector paths (not a font glyph) so it stays crisp at any size and
    scale. ``accent`` paints the smaller spark in a second colour; leaving it
    empty keeps the icon monochrome, matching the rest of the activity bar.
    """
    icon = QtGui.QIcon()
    primary = QtGui.QColor(color)
    secondary = QtGui.QColor(accent) if accent else QtGui.QColor(color)

    for scale in (1, 2):
        px = size * scale
        image = QtGui.QImage(px, px, QtGui.QImage.Format_ARGB32)
        image.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        def spark(cx, cy, radius, inner, col, alpha=255):
            """A four-pointed star with concave sides (the classic AI spark)."""
            path = QtGui.QPainterPath()
            import math
            path.moveTo(cx, cy - radius)
            # Concave curve to the right point, then repeat around.
            for angle_from, angle_to, r_from, r_to in (
                (-90, 0, radius, radius),
                (0, 90, radius, radius),
                (90, 180, radius, radius),
                (180, 270, radius, radius),
            ):
                mid = (angle_from + angle_to) / 2.0
                ctrl_r = inner
                mx = cx + math.cos(math.radians(mid)) * ctrl_r
                my = cy + math.sin(math.radians(mid)) * ctrl_r
                ex = cx + math.cos(math.radians(angle_to)) * r_to
                ey = cy + math.sin(math.radians(angle_to)) * r_to
                path.quadTo(mx, my, ex, ey)
            path.closeSubpath()
            painter.setPen(QtCore.Qt.NoPen)
            c = QtGui.QColor(col)
            c.setAlpha(alpha)
            painter.setBrush(c)
            painter.drawPath(path)

        unit = px / 16.0
        # Main spark, optically centred slightly left/up.
        spark(6.4 * unit, 6.2 * unit, 5.6 * unit, 1.5 * unit, primary)
        # Small companion spark to the lower right.
        spark(12.2 * unit, 12.0 * unit, 3.0 * unit, 0.8 * unit, secondary)
        painter.end()

        if scale == 2:
            image.setDevicePixelRatio(2.0)
        icon.addPixmap(QtGui.QPixmap.fromImage(image))
    return icon


def codicon_icon(name: str, size: int = 16, color: str = "#CCCCCC") -> QtGui.QIcon:
    """Build a crisp QIcon (with a 2x variant) from a codicon glyph."""
    char = codicon_char(name)
    icon = QtGui.QIcon()
    if not char:
        return icon
    font = codicon_font(size)
    for scale in (1, 2):
        px = size * scale
        image = QtGui.QImage(px, px, QtGui.QImage.Format_ARGB32)
        image.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        f = QtGui.QFont(font)
        f.setPixelSize(int(size * scale * 0.94))
        painter.setFont(f)
        painter.setPen(QtGui.QColor(color))
        painter.drawText(QtCore.QRect(0, 0, px, px), QtCore.Qt.AlignCenter, char)
        painter.end()
        if scale == 2:
            image.setDevicePixelRatio(2.0)
        icon.addPixmap(QtGui.QPixmap.fromImage(image))
    return icon


def codicon_pixmap(name: str, size: int = 16, color: str = "#CCCCCC") -> QtGui.QPixmap:
    return codicon_icon(name, size, color).pixmap(size, size)


def codicon_label(name: str, size: int = 16, color: str = "#CCCCCC", parent=None) -> QtWidgets.QLabel:
    """A QLabel that draws a single codicon glyph (used where QSS needs text)."""
    label = QtWidgets.QLabel(codicon_char(name), parent)
    label.setFont(codicon_font(size))
    label.setStyleSheet(f"background: transparent; border: none; color: {color};")
    label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setFixedSize(size + 4, size + 4)
    return label
