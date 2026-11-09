"""Application-wide UI scaling for accessibility (low-vision support).

The workbench is sized in device-independent pixels (row heights, icon sizes,
fonts), so scaling the *font* alone would not enlarge the chrome. Instead this
module scales Qt's own metric system (``QT_SCALE_FACTOR`` equivalent via
``QApplication.setAttribute`` + a scale-aware stylesheet) and exposes:

``apply_ui_scale(app, percent)``
    Apply ``percent`` (75..200) to the running application: sets Qt's global
    scale factor, re-applies the stylesheet with scaled metrics and returns the
    factor actually used.
``current_scale()`` / ``scale_px(px)``
    Helpers for widgets that need a scaled pixel value at runtime.
``available_scales()``
    Preset percentages shown in Settings.

How it works: Qt reads ``QGUIApplication::setAttribute(Qt::AA_EnableHighDpiScaling)``
only at start-up, so a *runtime* change uses the private-but-stable
``QT_SCALE_FACTOR`` equivalent: we rebuild the app stylesheet with every
``px`` metric multiplied by the factor and bump the default font size. Widgets
that use layout managers (all of the workbench) then reflow automatically.
"""
from __future__ import annotations

import re
from typing import Iterable, List

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = [
    "MIN_SCALE",
    "MAX_SCALE",
    "DEFAULT_SCALE",
    "available_scales",
    "normalize_scale",
    "scale_px",
    "current_scale",
    "apply_ui_scale",
    "scale_stylesheet",
]

MIN_SCALE = 75
MAX_SCALE = 200
DEFAULT_SCALE = 100

# Presets aligned with Windows / VS Code accessibility expectations.
SCALE_PRESETS: List[int] = [75, 80, 90, 100, 110, 125, 150, 175, 200]

_current = DEFAULT_SCALE

# Matches "12px" but not "112px"; leaves "%", "pt", colors and selectors alone.
_PX_RE = re.compile(r"(?<![\w.#-])(\d+(?:\.\d+)?)px\b")


def available_scales() -> List[int]:
    return list(SCALE_PRESETS)


def normalize_scale(percent) -> int:
    """Clamp/round a user supplied scale to the supported range."""
    try:
        value = int(round(float(percent)))
    except (TypeError, ValueError):
        return DEFAULT_SCALE
    return max(MIN_SCALE, min(MAX_SCALE, value))


def current_scale() -> int:
    return _current


def scale_px(px: float) -> int:
    """Scale a raw pixel value with the active UI scale."""
    return max(1, int(round(float(px) * _current / 100.0)))


def scale_stylesheet(qss: str, percent: int) -> str:
    """Multiply every ``Npx`` length in *qss* by ``percent``."""

    def repl(match: re.Match) -> str:
        value = float(match.group(1))
        scaled = value * percent / 100.0
        # Keep sub-pixel borders at >= 1px so hairlines never disappear.
        if value > 0 and scaled < 1:
            scaled = 1
        if abs(scaled - round(scaled)) < 0.01:
            return f"{int(round(scaled))}px"
        return f"{scaled:.1f}px"

    return _PX_RE.sub(repl, qss)


def _base_font(app: QtWidgets.QApplication) -> QtGui.QFont:
    font = getattr(app, "_pyscribe_base_font", None)
    if font is None:
        font = QtGui.QFont(app.font())
        font.setPointSize(9)
        app._pyscribe_base_font = font
    return font


def apply_ui_scale(app: QtWidgets.QApplication, percent, stylesheet_provider=None) -> int:
    """Apply *percent* scaling to *app* and return the value actually applied.

    ``stylesheet_provider`` is an optional callable returning the *unscaled*
    application stylesheet; it is scaled and installed so every pixel metric in
    the design system grows with the factor.
    """
    global _current
    scale = normalize_scale(percent)
    if app is None:
        _current = scale
        return scale

    factor = scale / 100.0
    _current = scale

    # 1. Global font size (all text that is not pinned by the stylesheet).
    base = _base_font(app)
    font = QtGui.QFont(base)
    font.setPointSizeF(max(6.0, base.pointSizeF() * factor))
    app.setFont(font)

    # 2. Stylesheet metrics (row heights, paddings, icon boxes, borders).
    if stylesheet_provider is not None:
        try:
            raw = stylesheet_provider() or ""
        except Exception:
            raw = ""
        if raw:
            app.setStyleSheet(scale_stylesheet(raw, scale))

    # 3. Icon geometry: let every widget that paints a codicon re-render it.
    for widget in app.allWidgets():
        try:
            if hasattr(widget, "on_ui_scale_changed"):
                widget.on_ui_scale_changed(scale)
        except RuntimeError:
            continue

    # 4. Re-layout. Pixel metrics that live in Python (fixed widths of side
    #    panels, splitters, dock columns) are applied by the window itself.
    for top in app.topLevelWidgets():
        try:
            # Nudge style-dependent size hints (fonts changed) before re-layout.
            style = top.style()
            if style is not None:
                style.unpolish(top)
                style.polish(top)
            top.updateGeometry()
        except RuntimeError:
            continue
    return scale
