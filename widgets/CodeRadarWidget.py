"""PyScribe widgets/CodeRadarWidget.py.

Deprecated module preserved for backwards compatibility with legacy plugins and configurations.
Active code navigation, AST inspection and Clean Code actions are handled by CodeLensBar.
"""
from __future__ import annotations

from widgets.CodeLensBar import CodeLensBar, CodeSymbol

# Backwards compatibility alias
CodeRadarWidget = CodeLensBar

__all__ = ["CodeRadarWidget", "CodeLensBar", "CodeSymbol"]
