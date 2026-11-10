"""Scale the workbench in logical pixels on top of Qt's per-monitor DPI."""
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
    "effective_scale",
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

_LENGTH_RE = re.compile(r"(?<![\w.#-])(\d+(?:\.\d+)?)(px|pt)\b")


def available_scales() -> List[int]:
    return list(SCALE_PRESETS)


def normalize_scale(percent) -> int:
    """Clamp/round a user supplied scale to the supported range."""
    try:
        value = int(round(float(percent)))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_SCALE
    return max(MIN_SCALE, min(MAX_SCALE, value))


def effective_scale(screen: QtGui.QScreen | None, percent=DEFAULT_SCALE) -> int:
    """Use the 1920×1080 layout as a base and enlarge it when both axes allow."""
    if screen is None:
        return normalize_scale(percent)
    size = screen.geometry().size()
    # Qt has already applied Windows display scaling to this geometry.
    fit = min(size.width() / 1920, size.height() / 1080)
    baseline = max(1.0, min(1.5, fit))
    return normalize_scale(normalize_scale(percent) * baseline)


def current_scale() -> int:
    return _current


def scale_px(px: float) -> int:
    """Scale a raw pixel value with the active UI scale."""
    return max(1, int(round(float(px) * _current / 100.0)))


def scale_stylesheet(qss: str, percent: int) -> str:
    """Scale stylesheet lengths while retaining their units."""

    def repl(match: re.Match) -> str:
        value = float(match.group(1))
        unit = match.group(2)
        scaled = value * percent / 100.0
        # Keep sub-pixel borders at >= 1px so hairlines never disappear.
        if unit == "px" and value > 0 and scaled < 1:
            scaled = 1
        if abs(scaled - round(scaled)) < 0.01:
            return f"{int(round(scaled))}{unit}"
        return f"{scaled:.1f}{unit}"

    return _LENGTH_RE.sub(repl, qss)


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
