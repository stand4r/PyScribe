"""Read-only viewer for diagrams.net files."""
import base64
from html import unescape
from pathlib import Path
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zlib

from design.icons import set_line_icon
from PyQt5 import QtCore, QtGui, QtWidgets

MAX_XML_BYTES = 16 * 1024 * 1024
DIAGRAM_EXTENSIONS = {".drawio", ".dio"}


def _xml(data):
    if len(data) > MAX_XML_BYTES or b"\x00" in data or re.search(br"<!\s*(DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("Слишком большой файл или неподдерживаемый XML.")
    return ET.fromstring(data)


def read_pages(path):
    with Path(path).open("rb") as file:
        document = _xml(file.read(MAX_XML_BYTES + 1))
    if document.tag == "mxGraphModel":
        return [("Страница 1", document)]
    if document.tag != "mxfile":
        raise ValueError("Ожидается файл diagrams.net (.drawio).")
    pages = []
    budget = MAX_XML_BYTES
    for page in document.findall("diagram"):
        model = page.find("mxGraphModel")
        if model is None and page.text:
            text = page.text.strip()
            if text.startswith("<"):
                model = _xml(text.encode())
            elif text:
                decoder = zlib.decompressobj(-zlib.MAX_WBITS)
                data = decoder.decompress(base64.b64decode(text), budget + 1)
                if not decoder.eof or len(data) > budget:
                    raise ValueError("Повреждённая или слишком большая страница.")
                budget -= len(data)
                model = _xml(unquote(data.decode("ascii")).encode())
        if model is not None and model.tag == "mxGraphModel":
            pages.append((page.get("name") or f"Страница {len(pages) + 1}", model))
    if not pages:
        raise ValueError("В файле нет страниц с диаграммами.")
    return pages


def _label(value):
    value = re.sub(r"<(?:br\b[^>]*|/div|/p)>", "\n", value, flags=re.I)
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _number(element, key, default=0):
    try:
        value = float(element.get(key, default))
        return value if -1e7 <= value <= 1e7 else default
    except (TypeError, ValueError):
        return default


class _DiagramCanvas(QtWidgets.QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.viewport().grabGesture(QtCore.Qt.PinchGesture)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

    def zoom(self, factor):
        if factor <= 0:
            return
        current = self.transform().m11()
        target = max(0.02, min(16.0, current * factor))
        self.scale(target / current, target / current)

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.NativeGesture:
            if event.gestureType() == QtCore.Qt.ZoomNativeGesture:
                self.zoom(1 + event.value())
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.Gesture:
            pinch = event.gesture(QtCore.Qt.PinchGesture)
            if pinch is not None:
                if pinch.changeFlags() & QtWidgets.QPinchGesture.ScaleFactorChanged:
                    previous = pinch.lastScaleFactor()
                    self.zoom(pinch.scaleFactor() / previous if previous > 0 else pinch.scaleFactor())
                event.accept(pinch)
                return True
        return super().viewportEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            self.zoom(1.2 ** (delta / 120))
            event.accept()
            return
        super().wheelEvent(event)


class DiagramViewerWidget(QtWidgets.QWidget):
    open_editor_requested = QtCore.pyqtSignal(str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._pages = []
        layout = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        self.pages = QtWidgets.QComboBox()
        self.pages.currentIndexChanged.connect(self._render_page)
        self.pages.setAccessibleName("Страница диаграммы")
        row.addWidget(self.pages, 1)
        for label, icon, callback in (
            ("−", "minus", lambda: self.view.zoom(0.8)),
            ("+", "add", lambda: self.view.zoom(1.25)),
            ("Вписать", "fit-page", self._fit),
            ("Обновить", "reload", self.reload),
            ("Исходник", "code", lambda: self.open_editor_requested.emit(self.file_path)),
        ):
            button = QtWidgets.QToolButton()
            if icon not in {"minus", "add"}:
                button.setText(label)
            set_line_icon(button, icon)
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = _DiagramCanvas(self.scene)
        self.view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.view.setToolTip("Щипок или Ctrl + прокрутка — масштаб")
        layout.addWidget(self.view, 1)
        self.reload()

    def reload(self):
        page_index = max(0, self.pages.currentIndex())
        try:
            self._pages = read_pages(self.file_path)
        except (OSError, ValueError, ET.ParseError, zlib.error) as error:
            self._pages = []
            self.pages.clear()
            self.scene.clear()
            self.status.setText(f"Не удалось прочитать диаграмму: {error}")
            self.status.show()
            return
        with QtCore.QSignalBlocker(self.pages):
            self.pages.clear()
            self.pages.addItems([name for name, _ in self._pages])
            self.pages.setCurrentIndex(min(page_index, len(self._pages) - 1))
        self._render_page(self.pages.currentIndex())

    def _fit(self):
        if not self.scene.sceneRect().isEmpty():
            self.view.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def _render_page(self, index):
        if not 0 <= index < len(self._pages):
            return
        self.scene.clear()
        model = self._pages[index][1]
        palette = self.palette()
        paper = palette.base().color()
        ink = palette.text().color()
        neutral = QtGui.QColor("#8897a8")
        self.scene.setBackgroundBrush(paper)
        pen = QtGui.QPen(neutral, 1.4)
        boxes = {}
        cells = []
        for element in model.findall("./root/*"):
            cell = element if element.tag == "mxCell" else element.find("mxCell")
            if cell is None:
                continue
            geometry = cell.find("mxGeometry")
            if geometry is None:
                continue
            value = element.get("label", cell.get("value", ""))
            key = cell.get("id") or element.get("id")
            cells.append((cell, geometry, key, value))
        vertices = {key: (cell, geometry) for cell, geometry, key, _ in cells
                    if cell.get("vertex") == "1" and key}

        def box_for(key):
            if key in boxes:
                return boxes[key]
            chain = []
            seen = set()
            current = key
            while current in vertices and current not in boxes and current not in seen:
                seen.add(current)
                cell, geo = vertices[current]
                chain.append((current, geo))
                current = cell.get("parent")
            origin = boxes.get(current, QtCore.QRectF()).topLeft()
            for current, geo in reversed(chain):
                origin += QtCore.QPointF(_number(geo, "x"), _number(geo, "y"))
                boxes[current] = QtCore.QRectF(origin.x(), origin.y(),
                                              max(1, _number(geo, "width", 100)),
                                              max(1, _number(geo, "height", 50)))
            return boxes[key]

        for cell, geometry, key, value in cells:
            if key not in vertices:
                continue
            rect = box_for(key)
            style = dict(part.split("=", 1) for part in cell.get("style", "").split(";") if "=" in part)
            fill = QtGui.QColor(style.get("fillColor", palette.alternateBase().color().name()))
            brush = QtGui.QBrush(fill) if fill.isValid() else QtGui.QBrush(QtCore.Qt.NoBrush)
            path = QtGui.QPainterPath()
            tokens = cell.get("style", "").split(";")
            shape = style.get("shape", "")
            if shape == "ellipse" or "ellipse" in tokens:
                path.addEllipse(rect)
            elif shape == "rhombus" or "rhombus" in tokens:
                path.addPolygon(QtGui.QPolygonF([
                    QtCore.QPointF(rect.center().x(), rect.top()),
                    QtCore.QPointF(rect.right(), rect.center().y()),
                    QtCore.QPointF(rect.center().x(), rect.bottom()),
                    QtCore.QPointF(rect.left(), rect.center().y()),
                ]))
                path.closeSubpath()
            else:
                radius = 8 if style.get("rounded") == "1" else 0
                path.addRoundedRect(rect, radius, radius)
            if "text" not in tokens and shape != "text":
                self.scene.addPath(path, pen, brush)
            text = _label(value)
            if text:
                item = self.scene.addText(text)
                item.setDefaultTextColor(
                    QtGui.QColor("#252a32" if fill.lightness() > 140 else "#e2e8ef")
                    if fill.isValid() else ink
                )
                item.setTextWidth(max(1, rect.width() - 10))
                option = item.document().defaultTextOption()
                option.setAlignment(QtCore.Qt.AlignCenter)
                item.document().setDefaultTextOption(option)
                item.setPos(rect.left() + 5, rect.center().y() - item.boundingRect().height() / 2)
                item.setZValue(1)

        for cell, geometry, _, value in cells:
            if cell.get("edge") != "1":
                continue
            source = boxes.get(cell.get("source"))
            target = boxes.get(cell.get("target"))
            start = self._point(geometry, "sourcePoint")
            end = self._point(geometry, "targetPoint")
            bends = [QtCore.QPointF(_number(p, "x"), _number(p, "y"))
                     for p in geometry.findall("./Array[@as='points']/mxPoint")]
            if source is not None:
                start = self._boundary(source, bends[0] if bends else target.center() if target else end)
            if target is not None:
                end = self._boundary(target, bends[-1] if bends else source.center() if source else start)
            if start is None or end is None:
                continue
            path = QtGui.QPainterPath(start)
            for point in [*bends, end]:
                path.lineTo(point)
            edge = self.scene.addPath(path, pen)
            edge.setZValue(-1)
            line = QtCore.QLineF(bends[-1] if bends else start, end)
            if line.length() > 0 and "endArrow=none" not in cell.get("style", ""):
                dx, dy = line.dx() / line.length(), line.dy() / line.length()
                back = end - QtCore.QPointF(dx * 9, dy * 9)
                wing = QtCore.QPointF(-dy * 4, dx * 4)
                self.scene.addPolygon(QtGui.QPolygonF([end, back + wing, back - wing]), pen, QtGui.QBrush(neutral))
            if value:
                item = self.scene.addSimpleText(_label(value))
                item.setBrush(QtGui.QBrush(ink))
                item.setPos(path.pointAtPercent(0.5) + QtCore.QPointF(4, 3))
        self.status.setText("На этой странице нет видимых элементов.")
        self.status.setVisible(not self.scene.items())
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30))
        QtCore.QTimer.singleShot(0, self._fit)

    @staticmethod
    def _point(geometry, role):
        point = geometry.find(f"./mxPoint[@as='{role}']")
        return QtCore.QPointF(_number(point, "x"), _number(point, "y")) if point is not None else None

    @staticmethod
    def _boundary(rect, toward):
        center = rect.center()
        if toward is None:
            return center
        delta = toward - center
        factor = max(abs(delta.x()) / (rect.width() / 2), abs(delta.y()) / (rect.height() / 2))
        return center + delta / factor if factor else center
