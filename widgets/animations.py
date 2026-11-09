"""PyScribe animation toolkit: shared, reusable Qt animations for the workbench.

All helpers are defensive: they never raise if the target widget has been
deleted, and they always end in the requested *final* state so that a widget is
never left invisible / transparent because an animation was interrupted.

Public API
----------
``DURATION`` / ``EASING``            tuning constants
``animate_property(widget, prop, start, end, ...)``   generic N-property tween
``fade_in(widget, ...)``             opacity 0 -> 1
``fade_out(widget, ..., on_finished=)``   opacity 1 -> 0, then hides
``slide_reveal(container, height, ...)``  max-height 0 -> N for collapsible bars
``slide_conceal(container, ..., on_finished=)``
``pulse(widget, ...)``               soft scale/glow pulse to draw the eye
``flash(widget, color, ...)``        background flash used for run/finish events
``cross_fade(old, new, ...)``        fade one widget out while another fades in
``stagger(items, delay_ms, fn)``     run ``fn(item)`` staggered for a nice cascade
``AnimatedSplitterHeight``           helper class for splitter-panel animations
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = [
    "DURATION",
    "EASING",
    "safe_call",
    "widget_alive",
    "animate_property",
    "fade_in",
    "fade_out",
    "slide_reveal",
    "slide_conceal",
    "pulse",
    "flash",
    "cross_fade",
    "stagger",
    "fade_opacity",
    "AnimatedSplitterHeight",
]

# Central motion language: fast enough to feel instant, slow enough to read.
DURATION = {
    "fast": 120,
    "normal": 180,
    "slow": 260,
}

EASING = {
    "out": QtCore.QEasingCurve.OutCubic,
    "in": QtCore.QEasingCurve.InCubic,
    "in_out": QtCore.QEasingCurve.InOutCubic,
    "back": QtCore.QEasingCurve.OutBack,
}


def widget_alive(widget) -> bool:
    """Return True when the underlying C++ object still exists.

    Calling a method on a deleted wrapper can raise ``RuntimeError`` *or* crash
    the process with an access violation (notably for QGraphicsEffect objects),
    so ``sip.isdeleted`` is the safe check to use here.
    """
    if widget is None:
        return False
    try:
        import sip
        if sip.isdeleted(widget):
            return False
    except Exception:
        pass
    try:
        widget.objectName()
        return True
    except (RuntimeError, AttributeError):
        return False


def safe_call(fn: Optional[Callable], *args) -> None:
    """Invoke *fn* swallowing errors from already-deleted Qt objects."""
    if fn is None:
        return
    try:
        fn(*args)
    except (RuntimeError, AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Core tweening
# ---------------------------------------------------------------------------

def animate_property(
    widget: QtWidgets.QWidget,
    prop: bytes,
    start,
    end,
    duration: int = DURATION["normal"],
    easing=QtCore.QEasingCurve.OutCubic,
    on_finished: Optional[Callable] = None,
    owner: Optional[QtWidgets.QWidget] = None,
) -> QtCore.QVariantAnimation:
    """Animate a Qt property (``b"opacity"``, ``b"maximumHeight"``, ...).

    The returned animation is parented to *owner* (default *widget*) so it is
    destroyed together with the widget. ``on_finished`` is always invoked,
    even if the interval is zero.
    """
    holder = owner if owner is not None else widget
    anim = QtCore.QVariantAnimation(holder if widget_alive(holder) else None)
    anim.setDuration(max(0, int(duration)))
    anim.setEasingCurve(easing)
    anim.setStartValue(start)
    anim.setEndValue(end)

    def _apply(value):
        if not widget_alive(widget):
            anim.stop()
            return
        try:
            widget.setProperty(prop, value)
            widget.update()
        except (RuntimeError, TypeError):
            anim.stop()
        except Exception:
            # Never let a repaint tween take the application down.
            anim.stop()

    anim.valueChanged.connect(_apply)

    def _finish():
        _apply(end)
        safe_call(on_finished)

    anim.finished.connect(_finish)
    if anim.duration() == 0:
        _apply(end)
        QtCore.QTimer.singleShot(0, _finish)
    else:
        anim.start()
    return anim


# ---------------------------------------------------------------------------
# Opacity helpers
# ---------------------------------------------------------------------------

def _get_opacity_effect(widget: QtWidgets.QWidget) -> QtWidgets.QGraphicsOpacityEffect:
    """Reuse an existing opacity effect when present to avoid stacking effects.

    ``setGraphicsEffect`` hands ownership of the effect to C++. If Python drops
    the only wrapper, the C++ object is destroyed and a still-running animation
    then writes to freed memory (an access violation, not a catchable
    RuntimeError). Keeping a Python reference on the widget prevents that.
    """
    effect = widget.graphicsEffect()
    if isinstance(effect, QtWidgets.QGraphicsOpacityEffect):
        widget._pyscribe_opacity_effect = effect
        return effect
    effect = QtWidgets.QGraphicsOpacityEffect(widget)
    effect.setOpacity(1.0)
    widget.setGraphicsEffect(effect)
    widget._pyscribe_opacity_effect = effect
    return effect


def _release_opacity_effect(widget: QtWidgets.QWidget) -> None:
    """Remove the opacity effect so normal painting / QSS effects are not degraded."""
    if not widget_alive(widget):
        return
    try:
        effect = widget.graphicsEffect()
        if isinstance(effect, QtWidgets.QGraphicsOpacityEffect):
            widget.setGraphicsEffect(None)
    except RuntimeError:
        pass
    try:
        widget._pyscribe_opacity_effect = None
    except RuntimeError:
        pass


class _OpacityRamp(QtCore.QObject):
    """Drives an opacity tween with a Python timer.

    A ``QVariantAnimation`` living inside Qt's animation machinery can still
    fire into an object whose C++ side was already destroyed, which crashes the
    process with an access violation. A Python-side ramp checks every frame that
    both the widget and its effect still exist, so it degrades to "stop" instead
    of taking the application down.
    """

    INTERVAL_MS = 16

    def __init__(self, widget, effect, start: float, end: float,
                 duration: int, easing, on_finished=None):
        super().__init__(widget if widget_alive(widget) else None)
        self._widget = widget
        self._effect = effect
        self._start = float(start)
        self._end = float(end)
        self._duration = max(1, int(duration))
        self._easing = easing
        self._on_finished = on_finished
        self._elapsed = 0
        self._done = False
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def start(self):
        _ACTIVE_OPACITY_RAMPS.add(self)
        self._apply(self._start)
        self._timer.start()

    def stop(self):
        if self._done:
            return
        self._done = True
        try:
            self._timer.stop()
        except RuntimeError:
            pass
        _ACTIVE_OPACITY_RAMPS.discard(self)
        safe_call(self._on_finished)

    def _progress(self, t: float) -> float:
        eased = QtCore.QEasingCurve(self._easing).valueForProgress(
            max(0.0, min(1.0, t)))
        return self._start + (self._end - self._start) * eased

    def _apply(self, value: float):
        if not widget_alive(self._effect):
            return
        try:
            self._effect.setOpacity(max(0.0, min(1.0, float(value))))
        except (RuntimeError, AttributeError):
            pass

    def _tick(self):
        if not widget_alive(self._widget) or not widget_alive(self._effect):
            self.stop()
            return
        self._elapsed += self.INTERVAL_MS
        t = min(1.0, self._elapsed / self._duration)
        self._apply(self._progress(t))
        if t >= 1.0:
            self.stop()


_ACTIVE_OPACITY_RAMPS: set = set()


def fade_opacity(
    widget: QtWidgets.QWidget,
    target: float,
    duration: int = DURATION["normal"],
    on_finished: Optional[Callable] = None,
    easing=QtCore.QEasingCurve.InOutCubic,
    show_first: bool = True,
):
    """Tween the widget opacity towards *target* (0.0 .. 1.0)."""
    if not widget_alive(widget):
        safe_call(on_finished)
        return None
    effect = _get_opacity_effect(widget)
    if show_first and target > 0 and widget.isHidden():
        widget.show()
    start = float(effect.opacity())

    def _done():
        if target >= 0.999:
            _release_opacity_effect(widget)
        safe_call(on_finished)

    ramp = _OpacityRamp(widget, effect, start, float(target), duration, easing, _done)
    ramp.start()
    return ramp


def fade_in(widget: QtWidgets.QWidget, duration: int = DURATION["normal"],
            on_finished: Optional[Callable] = None):
    """Fade a widget in from transparent to fully opaque."""
    if not widget_alive(widget):
        return None
    widget.setVisible(True)
    effect = _get_opacity_effect(widget)
    effect.setOpacity(0.0)
    return fade_opacity(widget, 1.0, duration=duration,
                        on_finished=on_finished, show_first=False)


def fade_out(widget: QtWidgets.QWidget, duration: int = DURATION["normal"],
             on_finished: Optional[Callable] = None, hide_after: bool = True):
    """Fade a widget out and (by default) hide it when the tween ends."""
    if not widget_alive(widget):
        safe_call(on_finished)
        return None
    if widget.isHidden():
        safe_call(on_finished)
        return None

    def _done():
        if hide_after and widget_alive(widget):
            widget.hide()
            _release_opacity_effect(widget)
        safe_call(on_finished)

    return fade_opacity(widget, 0.0, duration=duration, on_finished=_done,
                        show_first=False)


def cross_fade(old: Optional[QtWidgets.QWidget], new: Optional[QtWidgets.QWidget],
               duration: int = DURATION["normal"]) -> None:
    """Fade *old* out while *new* fades in, hiding the former at the end."""
    if widget_alive(new):
        try:
            new.setVisible(True)
            new.raise_()
        except RuntimeError:
            pass
    if widget_alive(old) and old is not new:
        fade_out(old, duration=duration)
    if widget_alive(new):
        fade_in(new, duration=duration)


# ---------------------------------------------------------------------------
# Collapsible bars (find/replace bar, banners, toolbars)
# ---------------------------------------------------------------------------

def slide_reveal(container: QtWidgets.QWidget, target_height: Optional[int] = None,
                 duration: int = DURATION["normal"], on_finished: Optional[Callable] = None):
    """Reveal a collapsible widget by animating ``maximumHeight`` 0 -> target."""
    if not widget_alive(container):
        return None
    if target_height is None:
        target_height = max(container.sizeHint().height(), container.minimumSizeHint().height(), 24)
    container.setMaximumHeight(0)
    container.setVisible(True)
    return animate_property(
        container, b"maximumHeight", 0, int(target_height),
        duration=duration, easing=QtCore.QEasingCurve.OutCubic,
        on_finished=lambda: _finish_reveal(container, on_finished),
    )


def _finish_reveal(container, on_finished):
    if widget_alive(container):
        container.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
    safe_call(on_finished)


def slide_conceal(container: QtWidgets.QWidget, duration: int = DURATION["fast"],
                  on_finished: Optional[Callable] = None):
    """Conceal a collapsible widget by animating ``maximumHeight`` -> 0."""
    if not widget_alive(container):
        safe_call(on_finished)
        return None
    if container.isHidden():
        safe_call(on_finished)
        return None
    start = container.height()

    def _done():
        if widget_alive(container):
            container.hide()
            container.setMaximumHeight(16777215)
        safe_call(on_finished)

    return animate_property(
        container, b"maximumHeight", start, 0,
        duration=duration, easing=QtCore.QEasingCurve.InCubic,
        on_finished=_done,
    )


# ---------------------------------------------------------------------------
# Emphasis effects
# ---------------------------------------------------------------------------

def pulse(widget: QtWidgets.QWidget, times: int = 2, duration: int = DURATION["slow"],
          strength: float = 0.35, on_finished: Optional[Callable] = None):
    """Soft opacity pulse used for terminal command completion and status changes."""
    if not widget_alive(widget):
        safe_call(on_finished)
        return None
    effect = _get_opacity_effect(widget)
    holder = widget
    seq = QtCore.QSequentialAnimationGroup(holder)
    for _ in range(max(1, int(times))):
        down = QtCore.QPropertyAnimation(effect, b"opacity", seq)
        down.setDuration(duration // 2)
        down.setStartValue(1.0)
        down.setEndValue(max(0.05, 1.0 - strength))
        down.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        up = QtCore.QPropertyAnimation(effect, b"opacity", seq)
        up.setDuration(duration // 2)
        up.setStartValue(max(0.05, 1.0 - strength))
        up.setEndValue(1.0)
        up.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        seq.addAnimation(down)
        seq.addAnimation(up)

    def _done():
        if widget_alive(widget):
            _release_opacity_effect(widget)
        safe_call(on_finished)

    seq.finished.connect(_done)
    seq.start()
    return seq


def flash(widget: QtWidgets.QWidget, color: str = "#00F2FE", alpha: int = 70,
          duration: int = 380, on_finished: Optional[Callable] = None):
    """One-shot background flash overlay drawn on top of *widget* (non-intrusive).

    Implemented with a child overlay instead of a stylesheet round-trip so the
    widget's QSS is never clobbered.
    """
    if not widget_alive(widget):
        safe_call(on_finished)
        return None
    overlay = _FlashOverlay(widget, QtGui.QColor(color), alpha)
    overlay.setGeometry(widget.rect())
    overlay.show()
    overlay.raise_()
    anim = QtCore.QVariantAnimation(overlay)
    anim.setDuration(max(1, int(duration)))
    anim.setStartValue(alpha)
    anim.setEndValue(0)
    anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

    def _step(v):
        overlay.set_intensity(int(v))

    def _done():
        overlay.deleteLater()
        safe_call(on_finished)

    anim.valueChanged.connect(_step)
    anim.finished.connect(_done)
    anim.start()
    return anim


class _FlashOverlay(QtWidgets.QWidget):
    """Transparent, mouse-transparent overlay that paints a fading tint."""

    def __init__(self, parent, color: QtGui.QColor, alpha: int):
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self._alpha = alpha
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.installEventFilter(self)

    def set_intensity(self, value: int):
        self._alpha = max(0, min(255, int(value)))
        self.update()

    def paintEvent(self, event):
        if self._alpha <= 0:
            return
        c = QtGui.QColor(self._color)
        c.setAlpha(self._alpha)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), c)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def stagger(items: Sequence, delay_ms: int, fn: Callable, *, reverse: bool = False) -> List[QtCore.QTimer]:
    """Call ``fn(item)`` for each item with an incremental delay (cascade effect)."""
    timers = []
    seq = list(items)
    if reverse:
        seq = list(reversed(seq))
    for i, item in enumerate(seq):
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda it=item: safe_call(fn, it))
        timer.start(max(0, i * delay_ms))
        timers.append(timer)
    return timers


class AnimatedSplitterHeight:
    """Drive a two-pane ``QSplitter`` (editor + bottom panel) with a smooth tween.

    ``total`` is the splitter's full size along its orientation. The manager
    keeps track of the currently running animation so that repeated toggles do
    not fight each other (the previous animation is stopped before a new one
    starts).
    """

    def __init__(self, splitter: QtWidgets.QSplitter, panel_index: int = 1,
                 owner: Optional[QtCore.QObject] = None):
        self.splitter = splitter
        self.panel_index = panel_index
        self.owner = owner or splitter
        self._anim = None

    def stop(self):
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass
            self._anim = None

    def current_height(self) -> int:
        if not widget_alive(self.splitter):
            return 0
        sizes = self.splitter.sizes()
        if 0 <= self.panel_index < len(sizes):
            return max(0, sizes[self.panel_index])
        return 0

    def animate_to(self, target_height: int, duration: int = DURATION["normal"],
                   on_finished: Optional[Callable] = None):
        self.stop()
        if not widget_alive(self.splitter):
            safe_call(on_finished)
            return None
        total = max(
            self.splitter.height() if self.splitter.orientation() == QtCore.Qt.Vertical
            else self.splitter.width(),
            1,
        )
        sizes = self.splitter.sizes()
        if len(sizes) > 1:
            total = sum(sizes) or total
        start = self.current_height()
        target = max(0, int(target_height))
        if start == target:
            self._apply(target, total)
            safe_call(on_finished)
            return None

        anim = QtCore.QVariantAnimation(self.owner)
        anim.setDuration(max(0, int(duration)))
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(target)

        def _step(value):
            self._apply(int(value), total)

        anim.valueChanged.connect(_step)

        def _done():
            self._apply(target, total)
            self._anim = None
            safe_call(on_finished)

        anim.finished.connect(_done)
        self._anim = anim
        anim.start()
        return anim

    def _apply(self, height: int, total: int):
        if not widget_alive(self.splitter):
            return
        height = max(0, min(height, total))
        sizes = [0] * self.splitter.count()
        for i in range(self.splitter.count()):
            sizes[i] = 0
        if self.panel_index < self.splitter.count():
            sizes[self.panel_index] = height
        first = 0 if self.panel_index != 0 else 1
        sizes[first] = max(1, total - height)
        self.splitter.setSizes(sizes)
