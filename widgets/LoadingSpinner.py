"""PyScribe widgets/LoadingSpinner.py: Reusable animated spinners and loading overlays."""
import math
from PyQt5 import QtCore, QtGui, QtWidgets


class LoadingSpinner(QtWidgets.QWidget):
    """Smooth, high-fps circular arc spinner with antialiased rendering."""

    def __init__(self, parent=None, radius=18, stroke_width=3.5, color="#58A6FF", speed_ms=16):
        super().__init__(parent)
        self.radius = radius
        self.stroke_width = stroke_width
        self.color = QtGui.QColor(color)
        self.angle = 0
        self.arc_length = 80
        self.growing = True

        size = int((radius + stroke_width) * 2 + 4)
        self.setFixedSize(size, size)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(speed_ms)
        self._timer.timeout.connect(self._rotate)
        self._timer.start()

    def set_color(self, color):
        self.color = QtGui.QColor(color)
        self.update()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self.angle = (self.angle + 7) % 360
        # Gentle dynamic pulse for the arc length
        if self.growing:
            self.arc_length += 1.5
            if self.arc_length >= 130:
                self.growing = False
        else:
            self.arc_length -= 1.5
            if self.arc_length <= 50:
                self.growing = True
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        r = self.radius

        # Draw subtle track
        track_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 25), self.stroke_width)
        track_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(QtCore.QPointF(w / 2.0, h / 2.0), r, r)

        # Draw animated spinning arc
        arc_pen = QtGui.QPen(self.color, self.stroke_width)
        arc_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(arc_pen)

        rect = QtCore.QRectF(w / 2.0 - r, h / 2.0 - r, r * 2.0, r * 2.0)
        start_angle = int(-self.angle * 16)
        span_angle = int(-self.arc_length * 16)
        painter.drawArc(rect, start_angle, span_angle)


class MiniSpinner(QtWidgets.QWidget):
    """Compact 16x16 spinner ideal for status bars and toolbars."""

    def __init__(self, parent=None, color="#58A6FF"):
        super().__init__(parent)
        self.color = QtGui.QColor(color)
        self.angle = 0
        self.setFixedSize(16, 16)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._rotate)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        r = 5.5
        w, h = self.width(), self.height()

        pen_track = QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 2.0)
        painter.setPen(pen_track)
        painter.drawEllipse(QtCore.QPointF(w / 2.0, h / 2.0), r, r)

        pen = QtGui.QPen(self.color, 2.0)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        rect = QtCore.QRectF(w / 2.0 - r, h / 2.0 - r, r * 2.0, r * 2.0)
        painter.drawArc(rect, int(-self.angle * 16), int(-100 * 16))


class LoadingOverlay(QtWidgets.QWidget):
    """Modern translucent overlay displaying an animated spinner, title, details, and progress."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setObjectName("loadingOverlay")
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.hide()

        # Track parent geometry
        if parent:
            parent.installEventFilter(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)

        # Centered card
        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName("loadingCard")
        self.card.setStyleSheet("""
            QFrame#loadingCard {
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 16px 24px;
            }
        """)
        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setAlignment(QtCore.Qt.AlignCenter)
        card_layout.setSpacing(10)

        self.spinner = LoadingSpinner(self.card, radius=16, stroke_width=3.5, color="#58A6FF")
        card_layout.addWidget(self.spinner, 0, QtCore.Qt.AlignCenter)

        self.title_label = QtWidgets.QLabel("Загрузка...")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; background: transparent;")
        card_layout.addWidget(self.title_label)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 11px; color: #8B949E; background: transparent;")
        self.status_label.setWordWrap(True)
        self.status_label.setMaximumWidth(280)
        card_layout.addWidget(self.status_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #21262D;
                border: 1px solid #30363D;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #58A6FF;
                border-radius: 2px;
            }
        """)
        self.progress_bar.hide()
        card_layout.addWidget(self.progress_bar, 0, QtCore.Qt.AlignCenter)

        layout.addWidget(self.card)

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Move):
            self.setGeometry(self.parent().rect())
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        # Semi-transparent dark glassmorphism backdrop
        painter.fillRect(self.rect(), QtGui.QColor(18, 22, 28, 215))

    def start(self, title="Загрузка...", status="", show_progress=False):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.title_label.setText(title)
        self.status_label.setText(status)
        self.status_label.setVisible(bool(status))
        self.progress_bar.setVisible(show_progress)
        if show_progress:
            self.progress_bar.setValue(0)
        self.spinner.start()
        self.show()
        self.raise_()

    def update_progress(self, current: int, total: int, status=""):
        if total > 0:
            pct = int(current * 100 / max(1, total))
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(pct)
        if status:
            self.status_label.setText(status)
            self.status_label.show()

    def stop(self):
        self.spinner.stop()
        self.hide()
