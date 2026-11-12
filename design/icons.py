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

from functools import lru_cache
from pathlib import Path
from typing import Dict

from PyQt5 import QtCore, QtGui, QtSvg, QtWidgets

__all__ = [
    "CODICONS",
    "codicon_char",
    "codicon_font",
    "codicon_icon",
    "font_is_available",
    "FONT_FAMILY",
    "line_icon",
    "set_line_icon",
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
    "checklist": 0xEB79,      # checklist / tasks
    "tasklist": 0xEB79,
    "tag": 0xEA85,
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


# Shared stroke icons, in a 20 × 20 view box. These are rendered at paint
# time so the same outline stays crisp at different zoom levels and DPIs.
_LINE_PATHS = {
    "back": "M12 5 7 10l5 5 M7 10h9",
    "forward": "M8 5l5 5-5 5 M4 10h9",
    "first": "M5 5v10 M13 5l-5 5 5 5 M8 10h8",
    "last": "M15 5v10 M7 5l5 5-5 5 M4 10h8",
    "up": "M5 12l5-5 5 5",
    "down": "M5 8l5 5 5-5",
    "add": "M4.5 10h11 M10 4.5v11",
    "minus": "M4.5 10h11",
    "close": "M5 5l10 10 M15 5 5 15",
    "reload": "M15.5 8a6 6 0 1 0 .4 4 M15.5 4v4h-4",
    "refresh": "M15.5 8a6 6 0 1 0 .4 4 M15.5 4v4h-4",
    "home": "M3 9l7-5.5L17 9 M5 8v8h3.5v-4h3v4H15V8",
    "bookmark": "M5.5 3.5h9V16L10 13l-4.5 3z",
    "external": "M9 5H4v11h11v-5 M11 3.5h5.5V9 M9 11l7.5-7.5",
    "profile": "M7 6a3 3 0 1 0 6 0 3 3 0 0 0-6 0 M4 16c0-6 12-6 12 0",
    "private": "M10 3l6 2.5-.5 6L13 15l-3 2-3-2-2.5-3.5L4 5.5z M7.5 10l1.5 1.5L12.5 8",
    "search": "M4 8a4 4 0 1 0 8 0 4 4 0 0 0-8 0m7 3 5 5",
    "replace": "M4 7h12l-3-3 M16 13H4l3 3",
    "outline": "M7 5h9 M7 10h9 M7 15h9 M4 5h.1 M4 10h.1 M4 15h.1",
    "fit-width": "M3 4v12 M17 4v12 M5 10h10 M7 8l-2 2 2 2 M13 8l2 2-2 2",
    "fit-page": "M8 4H4v4 M12 4h4v4 M16 12v4h-4 M8 16H4v-4",
    "rotate": "M13.5 6.5 10 3l-3.5 3.5 M10 3v5 M15.5 9a6 6 0 1 1-11 0",
    "moon": "M12 3.7A6.7 6.7 0 1 0 16.4 13 6 6 0 0 1 12 3.7z",
    "document": "M5 3h7l3 3v11H5z M12 3v4h3 M8 10h4 M8 13h4",
    "code": "M7 6l-4 4 4 4 M13 6l4 4-4 4 M11 5l-2 10",
    "copy": "M7 7h9v10H7z M4 13H3V3h9v1",
    "save": "M4 3h10l2 2v12H4z M7 3v5h6V3 M7 17v-5h6v5",
    "trash": "M4 5h12 M6 5l1 12h6l1-12 M8 5V3h4v2 M9 8v6 M11 8v6",
    "eye": "M2.5 10c2-4 5-5.5 7.5-5.5s5.5 1.5 7.5 5.5c-2 4-5 5.5-7.5 5.5S4.5 14 2.5 10z M8 10a2 2 0 1 0 4 0 2 2 0 0 0-4 0",
    "key": "M4 7a3.5 3.5 0 1 0 7 0 3.5 3.5 0 0 0-7 0m6 2.5 6 6m-1.5-1.5 1.5-1.5",
    "send": "M5 10l5-5 5 5 M10 5v11",
    "stop": "M6 6h8v8H6z",
    "play": "M6 4.5v11l9-5.5z",
    "more": "M4.5 10h.1 M10 10h.1 M15.5 10h.1",
    "info": "M3 10a7 7 0 1 0 14 0 7 7 0 0 0-14 0 M10 9v5 M10 6h.1",
    "warning": "M10 3l7 13H3z M10 8v3.5 M10 14h.1",
    "check": "M4 10l4 4 8-8",
    "checklist": "M3 4h3v3H3z M8 5.5h9 M3 9h3v3H3z M8 10.5h9 M3 14h3v3H3z M8 15.5h9",
    "tasklist": "M3 4h3v3H3z M8 5.5h9 M3 9h3v3H3z M8 10.5h9 M3 14h3v3H3z M8 15.5h9",
    "tag": "M3 10l7-7h7v7l-7 7z M14 6h.1",
    "star": "M10 2.5l2.4 5.3 5.8.6-4.3 3.9 1.2 5.7L10 15l-5.1 3 1.2-5.7-4.3-3.9 5.8-.6z",
    "circle": "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14z",
    "chevron-right": "M8 5l5 5-5 5",
    "chevron-down": "M5 8l5 5 5-5",
    "chevron-up": "M5 12l5-5 5 5",
    "split-right": "M3 4h14v12H3z M10 4v12",
    "split-down": "M3 4h14v12H3z M3 10h14",
    "unsplit": "M3 4h14v12H3z",

}


@lru_cache(maxsize=96)
def _line_renderer(name, color):
    path = _LINE_PATHS.get(name)
    if not path:
        if name in ("refresh", "reload"):
            path = _LINE_PATHS.get("reload") or _LINE_PATHS.get("refresh")
        else:
            path = _LINE_PATHS.get("info", "M5 5l10 10 M15 5 5 15")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.55" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("ascii")))


class _LineIconEngine(QtGui.QIconEngine):
    def __init__(self, name, color):
        super().__init__()
        self.name = name
        self.color = color

    def clone(self):
        return _LineIconEngine(self.name, self.color)

    def paint(self, painter, rect, mode, state):
        color = self.color or QtWidgets.QApplication.palette().buttonText().color().name()
        painter.save()
        if mode == QtGui.QIcon.Disabled:
            painter.setOpacity(painter.opacity() * 0.42)
        _line_renderer(self.name, color).render(painter, QtCore.QRectF(rect))
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def line_icon(name, color=None):
    """Return a scalable line icon; default strokes follow the UI palette."""
    return QtGui.QIcon(_LineIconEngine(name, QtGui.QColor(color).name() if color else None))


def set_line_icon(control, name, size=16):
    control.setIcon(line_icon(name))
    if isinstance(control, QtWidgets.QToolButton) and control.text():
        control.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
    if hasattr(control, "setIconSize"):
        control.setIconSize(QtCore.QSize(size, size))
