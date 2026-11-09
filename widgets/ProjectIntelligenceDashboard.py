"""PyScribe widgets/ProjectIntelligenceWidget.py: application module and reusable component."""
from __future__ import annotations

from pathlib import Path
import math
import json
import time
from datetime import datetime
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from core.logging_config import get_logger
from core.project_intelligence import ProjectAnalysis, ProjectIntelligenceEngine, FileInfo, Issue
from services.code_intelligence_service import CodeIntelligenceService
from widgets.LoadingSpinner import LoadingOverlay
from widgets.Dialog import CustomDialog

logger = get_logger("intelligence")
def _ui_font(point_size: int = 9, weight=None, bold=False):
    """Neutral UI typography for analysis labels, metrics and graph painters."""
    font = QtGui.QFont("Segoe UI", point_size)
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    if bold:
        font.setWeight(QtGui.QFont.DemiBold)
    elif weight is not None:
        font.setWeight(weight)
    return font


def _ui_font_family() -> str:
    return "Segoe UI"


# ----------------------------------------------------------------------
# Unified palette for the analysis view.
# The panel used to mix cyan (#00F2FE), green gradients (#10B981), purple
# (#8E74AA) and a blue-tinted navy (#16202E) that clashed with the neutral
# greys used everywhere else in the workbench. Everything here is now neutral
# grey + a single accent; colour is reserved for genuine severity meaning.
# ----------------------------------------------------------------------
class Palette:
    """Neutral surfaces + one accent, matching the workbench theme."""

    # Surfaces (same family as the rest of the app)
    SURFACE = "#1F1F1F"          # cards / panels
    SURFACE_ALT = "#252526"      # inputs, chips
    TRACK = "#2D2D30"            # gauge track, progress backgrounds
    BORDER = "#2B2B2B"           # hairline borders
    BORDER_STRONG = "#3A3A3C"    # emphasised borders / hover

    # Text
    TEXT = "#D4D4D4"
    TEXT_STRONG = "#EDEDED"
    TEXT_MUTED = "#8B949E"

    # The only accent: VS Code blue
    ACCENT = "#0078D4"
    ACCENT_HOVER = "#1A8BE0"
    ACCENT_TEXT = "#4DA3E8"      # accent used as text on dark surfaces

    # Severity — the only place colour carries meaning
    DANGER = "#E5534B"
    WARNING = "#C9A227"
    OK = "#3FB950"

    @classmethod
    def severity(cls, level: str) -> str:
        return {"high": cls.DANGER, "medium": cls.WARNING,
                "low": cls.TEXT_MUTED}.get(str(level).lower(), cls.TEXT_MUTED)


# Two button styles only: one accent-filled primary, one quiet secondary.
def primary_button_qss(padding: str = "4px 12px", radius: int = 6) -> str:
    return (
        'QToolButton {  font-weight: 600; color: #FFFFFF;'
        f' background: {Palette.ACCENT}; border: 1px solid {Palette.ACCENT};'
        f' border-radius: {radius}px; padding: {padding}; }}'
        f'QToolButton:hover {{ background: {Palette.ACCENT_HOVER};'
        f' border-color: {Palette.ACCENT_HOVER}; }}'
    )


def secondary_button_qss(padding: str = "4px 12px", radius: int = 6) -> str:
    return (
        'QToolButton {  font-weight: 500;'
        f' color: {Palette.TEXT}; background: {Palette.SURFACE_ALT};'
        f' border: 1px solid {Palette.BORDER_STRONG};'
        f' border-radius: {radius}px; padding: {padding}; }}'
        f'QToolButton:hover {{ background: {Palette.TRACK};'
        f' border-color: {Palette.TEXT_MUTED}; }}'
    )


class AnalysisWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int, str)
    finished = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, engine: ProjectIntelligenceEngine):
        super().__init__()
        self.engine = engine

    @QtCore.pyqtSlot()
    def run(self):
        try:
            result = self.engine.analyze(self._progress)
            self._emit(self.finished, result)
        except Exception as exc:
            self._emit(self.failed, str(exc))

    def _emit(self, signal, payload):
        """Emit safely: the worker may already be deleted during shutdown."""
        try:
            signal.emit(payload)
        except RuntimeError:
            pass

    def _progress(self, current, total, name):
        try:
            self.progress.emit(current, total, name)
        except RuntimeError:
            # The dashboard (and this worker) can be gone while the analysis
            # thread is still finishing; that must not abort the thread.
            pass


class AnalysisNavigation(QtWidgets.QWidget):
    """Full-width page buttons that wrap instead of clipping or eliding."""

    def __init__(self, tabs, parent=None):
        super().__init__(parent)
        self.tabs = tabs
        self.setObjectName("analysisNavigation")
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.buttons = []
        self._columns = 0
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        for index in range(tabs.count()):
            button = QtWidgets.QToolButton(self)
            button.setObjectName("analysisPageButton")
            button.setText(tabs.tabText(index))
            button.setCheckable(True)
            button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, i=index: tabs.setCurrentIndex(i))
            group.addButton(button)
            self.buttons.append(button)
        tabs.currentChanged.connect(self._select)
        self._select(tabs.currentIndex())
        self._arrange()

    def _select(self, index):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)

    def _arrange(self):
        if not self.buttons:
            return
        needed = max(button.sizeHint().width() for button in self.buttons)
        gap = self.grid.spacing()
        columns = max(1, min(len(self.buttons), (self.width() + gap) // (needed + gap)))
        # Keep complete, equal rows (six, three, two or one column).
        while len(self.buttons) % columns:
            columns -= 1
        if columns == self._columns:
            return
        for column in range(len(self.buttons)):
            self.grid.setColumnStretch(column, 0)
            self.grid.setColumnMinimumWidth(column, 0)
        for button in self.buttons:
            self.grid.removeWidget(button)
        for index, button in enumerate(self.buttons):
            self.grid.addWidget(button, index // columns, index % columns)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
        self._columns = columns
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange):
            self._columns = 0
            QtCore.QTimer.singleShot(0, self._arrange)


class AdversaryWorker(QtCore.QObject):
    """Runs «Адвокат дьявола» off the UI thread.

    Each case spawns a subprocess with a timeout, so a full run takes a few
    seconds — far too long to block the window.
    """

    finished = QtCore.pyqtSignal(object)

    def __init__(self, path: str, timeout: int = 8):
        super().__init__()
        self.path = str(path)
        self.timeout = timeout

    @QtCore.pyqtSlot()
    def run(self):
        from core.adversary import AdversaryReport, AdversaryRunner
        runner = AdversaryRunner(timeout=self.timeout)
        try:
            report = runner.run_file(self.path)
        except Exception as exc:  # noqa: BLE001 - report instead of crashing
            report = AdversaryReport(module_path=self.path,
                                     error=f"Ошибка испытания: {exc}")
        finally:
            runner.dispose()
        self.finished.emit(report)


class GraphNodeItem(QtWidgets.QGraphicsObject):
    toggled = QtCore.pyqtSignal(str, bool)
    activated = QtCore.pyqtSignal(str)
    moved = QtCore.pyqtSignal(str, object)

    def __init__(self, node, expanded=False, parent=None):
        super().__init__(parent)
        self.node = node
        self.expanded = expanded
        self.w = 190
        self.h = 64
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(2)
        self._hover = False

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.w, self.h)

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        base = self.scene().views()[0] if self.scene() and self.scene().views() else None
        palette = base.palette() if base is not None else QtWidgets.QApplication.palette()
        bg = palette.alternateBase().color()
        border = palette.highlight().color()
        fg = palette.text().color()
        if self._hover:
            bg = palette.mid().color()
        p.setPen(QtGui.QPen(QtGui.QColor(border), 1.4))
        p.setBrush(QtGui.QBrush(QtGui.QColor(bg)))
        p.drawRoundedRect(0, 0, self.w, self.h, 9, 9)

        kind = self.node.kind.upper()
        p.setPen(QtGui.QColor(border))
        p.setFont(_ui_font(8, weight=QtGui.QFont.Medium))
        p.drawText(12, 17, kind)
        p.setPen(QtGui.QColor(fg))
        p.setFont(_ui_font(10, weight=QtGui.QFont.Medium))
        name = self.node.name
        if len(name) > 24:
            name = name[:22] + '…'
        p.drawText(12, 37, name)
        p.setPen(QtGui.QColor(Palette.TEXT_MUTED))
        p.setFont(_ui_font(8))
        p.drawText(12, 53, f'line {self.node.line}' if self.node.line else '')

        if self.node.kind in {'module', 'class', 'function', 'method'}:
            p.setPen(QtGui.QColor(Palette.TEXT_MUTED))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRoundedRect(self.w - 26, 20, 14, 14, 4, 4)
            p.drawLine(self.w - 22, 27, self.w - 16, 27)
            if not self.expanded:
                p.drawLine(self.w - 19, 24, self.w - 19, 30)

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.node.kind in {'module', 'class', 'function', 'method'}:
            if QtCore.QRectF(self.w - 34, 10, 30, 44).contains(event.pos()):
                self.expanded = not self.expanded
                self.toggled.emit(self.node.id, self.expanded)
                event.accept()
                return
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            self.moved.emit(self.node.id, value)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.activated.emit(self.node.file)
        event.accept()


class ProjectGraphView(QtWidgets.QGraphicsView):
    node_activated = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('projectGraphView')
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setRenderHint(QtGui.QPainter.TextAntialiasing)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setBackgroundBrush(QtGui.QColor('#14181D'))
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self._nodes = {}
        self._node_data = []
        self._edge_data = []
        self._expanded = set()
        self._mode = 'modules'
        self._search = ''
        self._layout_positions = {}
        self._did_initial_fit = False
        self._edge_items = []

    def clear_graph(self):
        self.scene().clear()
        self._nodes.clear()
        self._node_data = []
        self._edge_data = []
        self._layout_positions = {}
        self._did_initial_fit = False

    def set_graph(self, nodes, edges, mode='modules'):
        self._mode = mode
        self._node_data = list(nodes)
        self._edge_data = list(edges)
        self._did_initial_fit = False
        self._render()

    def set_search(self, text):
        self._search = (text or '').strip().lower()
        for node_id, item in self._nodes.items():
            item.setOpacity(1.0 if not self._search or self._search in item.node.name.lower() or self._search in item.node.file.lower() else 0.18)

    def _visible_nodes(self):
        nodes = {n.id: n for n in self._node_data}
        roots = [n for n in self._node_data if not n.parent_id or n.parent_id not in nodes]
        visible = []
        def walk(node):
            visible.append(node)
            if node.id in self._expanded:
                for child in self._node_data:
                    if child.parent_id == node.id:
                        walk(child)
        for root in roots:
            walk(root)
        return visible

    def _force_layout(self, visible):
        """Deterministic force layout with strong node repulsion and generous spacing."""
        import math
        n = len(visible)
        if not n:
            return {}
        ids = [x.id for x in visible]
        index = {x: i for i, x in enumerate(ids)}
        # Start on a large spiral so nodes never begin stacked in the same place.
        pos = {}
        radius_step = 250.0
        for i, node_id in enumerate(ids):
            angle = i * 2.3999632297
            radius = 180.0 + radius_step * math.sqrt(i / max(1, n - 1))
            pos[node_id] = [math.cos(angle) * radius, math.sin(angle) * radius]
        edges = [(e.source, e.target) for e in self._edge_data if e.source in index and e.target in index and e.source != e.target]
        area = max(160000.0, n * 30000.0)
        k = max(260.0, math.sqrt(area / max(1, n)))
        for _ in range(min(260, 100 + n * 5)):
            disp = {x: [0.0, 0.0] for x in ids}
            for i, a in enumerate(ids):
                ax, ay = pos[a]
                for b in ids[i+1:]:
                    bx, by = pos[b]
                    dx, dy = ax-bx, ay-by
                    d2 = max(100.0, dx*dx + dy*dy)
                    d = math.sqrt(d2)
                    force = (k*k) / d
                    fx, fy = dx/d*force, dy/d*force
                    disp[a][0] += fx; disp[a][1] += fy
                    disp[b][0] -= fx; disp[b][1] -= fy
            for a, b in edges:
                ax, ay = pos[a]; bx, by = pos[b]
                dx, dy = bx-ax, by-ay
                d = max(1.0, math.sqrt(dx*dx+dy*dy))
                force = (d*d) / k
                fx, fy = dx/d*force, dy/d*force
                disp[a][0] += fx; disp[a][1] += fy
                disp[b][0] -= fx; disp[b][1] -= fy
            for node_id in ids:
                pos[node_id][0] += max(-55.0, min(55.0, disp[node_id][0] * 0.018))
                pos[node_id][1] += max(-55.0, min(55.0, disp[node_id][1] * 0.018))
        minx = min(v[0] for v in pos.values()); miny = min(v[1] for v in pos.values())
        return {node_id: QtCore.QPointF(v[0]-minx+140, v[1]-miny+140) for node_id, v in pos.items()}

    def _render(self):
        self.scene().clear(); self._nodes.clear()
        visible = self._visible_nodes()
        visible_ids = {n.id for n in visible}
        if not visible:
            return
        positions = self._force_layout(visible)
        self._layout_positions = positions

        # All edges share one muted tone; emphasis comes from width, not hue.
        # (Previously each relation kind had its own colour: 5 hues at once.)
        edge_pen_colour = QtGui.QColor(Palette.BORDER_STRONG)
        edge_widths = {'imports': 1.8, 'calls': 1.4, 'inherits': 1.4,
                       'contains': 1.0, 'exports': 1.0}
        self._edge_items = []
        for e in self._edge_data:
            if e.source not in visible_ids or e.target not in visible_ids:
                continue
            pen = QtGui.QPen(edge_pen_colour, edge_widths.get(e.kind, 1.2))
            pen.setCosmetic(True)
            item = self.scene().addPath(QtGui.QPainterPath(), pen)
            item.setZValue(0)
            self._edge_items.append((item, e.source, e.target))
        for n in visible:
            item = GraphNodeItem(n, n.id in self._expanded)
            item.setPos(positions[n.id])
            item.toggled.connect(self._toggle_node)
            item.activated.connect(self.node_activated.emit)
            item.moved.connect(self._node_moved)
            self.scene().addItem(item)
            self._nodes[n.id] = item
        self._update_edges()
        self.set_search(self._search)
        rect = self.scene().itemsBoundingRect().adjusted(-100, -100, 100, 100)
        self.scene().setSceneRect(rect)
        if not self._did_initial_fit:
            self.fitInView(rect, QtCore.Qt.KeepAspectRatio)
            self._did_initial_fit = True

    def _node_moved(self, node_id, position):
        self._layout_positions[node_id] = QtCore.QPointF(position)
        self._update_edges()
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-140, -140, 140, 140))

    def _update_edges(self):
        for item, source, target in self._edge_items:
            a = self._nodes.get(source)
            b = self._nodes.get(target)
            if not a or not b:
                item.setPath(QtGui.QPainterPath())
                continue
            ar = a.sceneBoundingRect()
            br = b.sceneBoundingRect()
            start = QtCore.QPointF(ar.right(), ar.center().y())
            end = QtCore.QPointF(br.left(), br.center().y())
            if end.x() < start.x():
                start, end = QtCore.QPointF(ar.left(), ar.center().y()), QtCore.QPointF(br.right(), br.center().y())
            dx = max(70.0, abs(end.x() - start.x()) * 0.42)
            path = QtGui.QPainterPath(start)
            path.cubicTo(start.x() + dx, start.y(), end.x() - dx, end.y(), end.x(), end.y())
            item.setPath(path)

    def _toggle_node(self, node_id, expanded):
        if expanded: self._expanded.add(node_id)
        else: self._expanded.discard(node_id)
        self._render()

    def expand_all(self):
        self._expanded = {n.id for n in self._node_data if n.kind in {'module','class','function','method','binary'}}
        self._render()

    def collapse_all(self):
        self._expanded.clear(); self._render()

    def zoom_in(self): self.scale(1.18, 1.18)
    def zoom_out(self): self.scale(0.847, 0.847)
    def reset_zoom(self):
        rect = self.scene().sceneRect()
        if rect.isValid(): self.fitInView(rect, QtCore.Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            self.scale(1.15 if event.angleDelta().y() > 0 else 0.87, 1.15 if event.angleDelta().y() > 0 else 0.87)
            event.accept(); return
        super().wheelEvent(event)


class ProjectGraphEditorWidget(QtWidgets.QWidget):
    """Full editor-tab graph workbench.

    The graph deliberately lives in the editor area rather than the narrow
    activity/sidebar column. All graph navigation, filtering and zooming are
    available here without competing with the project tree.
    """
    open_file_requested = QtCore.pyqtSignal(str, int)

    def __init__(self, engine, mode='modules', parent=None):
        super().__init__(parent)
        self.engine = engine
        self.analysis = getattr(engine, 'analysis', None)
        self.mode = mode
        self.setObjectName('projectGraphEditor')

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._build_header())
        root.addWidget(self._build_controls())

        self.graph = ProjectGraphView()
        self.graph.node_activated.connect(self._open_node)
        root.addWidget(self.graph, 1)
        self.loading_overlay = LoadingOverlay(self.graph)
        self._populate()

    def _build_header(self) -> QtWidgets.QFrame:
        header = QtWidgets.QFrame()
        header.setObjectName('graphEditorHeader')
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(8, 4, 8, 4)
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(0)
        self.title = QtWidgets.QLabel('Граф проекта')
        self.title.setObjectName('graphEditorTitle')
        self.subtitle = QtWidgets.QLabel('Связи и зависимости проекта')
        self.subtitle.setObjectName('graphEditorSubtitle')
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        hl.addLayout(title_box)
        hl.addStretch()
        self.status = QtWidgets.QLabel('')
        self.status.setObjectName('graphEditorStatus')
        hl.addWidget(self.status)
        return header

    def _build_controls(self) -> QtWidgets.QFrame:
        controls = QtWidgets.QFrame()
        controls.setObjectName('graphEditorToolbar')
        grid = QtWidgets.QGridLayout(controls)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)

        grid.addWidget(QtWidgets.QLabel('Вид'), 0, 0)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.setMinimumWidth(150)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        grid.addWidget(self.mode_combo, 0, 1)

        grid.addWidget(QtWidgets.QLabel('Файл'), 0, 2)
        self.file_combo = QtWidgets.QComboBox()
        self.file_combo.setMinimumWidth(220)
        self.file_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.file_combo.currentIndexChanged.connect(self._filters_changed)
        grid.addWidget(self.file_combo, 0, 3, 1, 2)

        grid.addWidget(QtWidgets.QLabel('Функция'), 0, 5)
        self.function_combo = QtWidgets.QComboBox()
        self.function_combo.setMinimumWidth(220)
        self.function_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.function_combo.currentIndexChanged.connect(self._filters_changed)
        grid.addWidget(self.function_combo, 0, 6, 1, 2)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Поиск узлов, файлов, символов…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.graph_search)
        grid.addWidget(self.search, 1, 0, 1, 4)

        self.expand = QtWidgets.QToolButton(); self.expand.setText('Развернуть всё'); self.expand.clicked.connect(self.graph_expand)
        self.collapse = QtWidgets.QToolButton(); self.collapse.setText('Свернуть всё'); self.collapse.clicked.connect(self.graph_collapse)
        self.zoom_out_button = QtWidgets.QToolButton(); self.zoom_out_button.setText('−'); self.zoom_out_button.setToolTip('Уменьшить'); self.zoom_out_button.clicked.connect(lambda: self.graph.zoom_out())
        self.zoom_in_button = QtWidgets.QToolButton(); self.zoom_in_button.setText('+'); self.zoom_in_button.setToolTip('Увеличить'); self.zoom_in_button.clicked.connect(lambda: self.graph.zoom_in())
        self.fit_button = QtWidgets.QToolButton(); self.fit_button.setText('По размеру'); self.fit_button.clicked.connect(lambda: self.graph.reset_zoom())
        self.open_button = QtWidgets.QToolButton(); self.open_button.setText('Открыть исходник'); self.open_button.clicked.connect(self._open_selected)
        for col, widget in enumerate((self.expand, self.collapse, self.zoom_out_button, self.zoom_in_button, self.fit_button, self.open_button), start=4):
            grid.addWidget(widget, 1, col)

        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(6, 2)
        return controls

    def _available_modes(self):
        a = self.analysis
        if not a:
            return []
        available = [('Модули', 'modules')] if a.files else []
        kinds = {n.kind for n in a.structure_nodes}
        if any(k in kinds for k in {'class', 'struct', 'interface', 'enum'}):
            available.append(('Классы', 'classes'))
        if any(k in kinds for k in {'function', 'method', 'constructor'}):
            available.append(('Функции', 'functions'))
        if any(k == 'variable' for k in kinds):
            available.append(('Переменные', 'variables'))
        if a.binaries:
            available.append(('Бинарные объекты', 'binaries'))
        if any(e.kind == 'imports' for e in a.structure_edges) or any(f.imports for f in a.files.values()):
            available.append(('Импорты', 'imports'))
        if any(e.kind == 'exports' for e in a.structure_edges) or any(b.exports for b in a.binaries.values()):
            available.append(('Экспорты', 'exports'))
        return available

    def _populate(self):
        if not self.analysis:
            self.status.setText('Нет данных анализа')
            return
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for label, value in self._available_modes():
            self.mode_combo.addItem(label, value)
        idx = self.mode_combo.findData(self.mode)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mode_combo.blockSignals(False)
        self._populate_files()
        self._refresh_graph()

    def _populate_files(self):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItem('Все файлы проекта', '')
        if self.analysis:
            for info in sorted(self.analysis.files.values(), key=lambda x: x.module.lower()):
                self.file_combo.addItem(info.module, info.path)
        self.file_combo.blockSignals(False)
        self._populate_functions()

    def _populate_functions(self):
        self.function_combo.blockSignals(True)
        self.function_combo.clear()
        self.function_combo.addItem('Все функции', '')
        path = self.file_combo.currentData()
        if self.analysis and path:
            for n in sorted(self.analysis.structure_nodes, key=lambda x: (x.line, x.name.lower())):
                if n.file == path and n.kind in {'function', 'method'}:
                    self.function_combo.addItem(n.name, n.id)
        self.function_combo.blockSignals(False)

    def _mode_changed(self):
        self.mode = self.mode_combo.currentData() or 'modules'
        self._refresh_graph()

    def _filters_changed(self):
        self._populate_functions()
        self._refresh_graph()

    def _refresh_graph(self):
        if not self.engine or not self.analysis:
            return
        mode = self.mode_combo.currentData() or self.mode
        file_path = self.file_combo.currentData() or None
        function_id = self.function_combo.currentData() or None
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.start('Построение графа зависимостей...', 'Расчёт связей и расположения узлов...')
            QtWidgets.QApplication.processEvents()
        nodes, edges = self.engine.graph_data(mode, file_path, function_id)
        self.graph.set_graph(nodes, edges, mode)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.stop()
        self.file_combo.setEnabled(mode in {'classes', 'functions', 'variables'})
        self.function_combo.setEnabled(mode == 'variables')
        mode_names = {'modules': 'Модули', 'classes': 'Классы', 'functions': 'Функции', 'variables': 'Переменные', 'binaries': 'Бинарные объекты', 'imports': 'Импорты', 'exports': 'Экспорты'}
        mode_label = mode_names.get(mode, mode.title())
        self.status.setText(f'{len(nodes)} узлов · {len(edges)} связей')
        self.subtitle.setText(f'Вид: {mode_label} · перетаскивайте узлы, колесико мыши для масштабирования')

    def graph_search(self, text):
        self.graph.set_search(text)

    def graph_expand(self):
        self.graph.expand_all()

    def graph_collapse(self):
        self.graph.collapse_all()

    def _open_node(self, file_path):
        if file_path:
            self.open_file_requested.emit(file_path, 1)

    def _open_selected(self):
        items = self.graph.scene().selectedItems()
        if items and hasattr(items[0], 'node'):
            self._open_node(items[0].node.file)

    def set_mode(self, mode):
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

    def refresh(self):
        self.analysis = getattr(self.engine, 'analysis', None)
        self._populate()

class QualityBadgeWidget(QtWidgets.QWidget):
    """Pristine circular quality gauge displaying exact numeric percentage and radial score arc."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(62, 62)
        self._score = 0.0
        self._color = QtGui.QColor(Palette.TEXT_MUTED)
        self._bg_color = QtGui.QColor(Palette.SURFACE_ALT)

    def setText(self, text: str):
        try:
            self._score = float(str(text).replace('%', '').strip())
        except Exception:
            self._score = 0.0
        self.update()

    def setStyleSheet(self, style: str):
        pass  # Painted via antialiased QPainter

    def set_grade(self, letter: str, color_hex: str, bg_hex: str, score: float = 0):
        self._color = QtGui.QColor(color_hex)
        self._bg_color = QtGui.QColor(bg_hex)
        self._score = float(score) if score is not None else 0.0
        self.update()

    def set_score(self, score: float, color_hex: str = None, bg_hex: str = None):
        self._color = QtGui.QColor(color_hex or Palette.ACCENT)
        self._bg_color = QtGui.QColor(bg_hex or Palette.SURFACE_ALT)
        self._score = float(score) if score is not None else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        size = min(self.width(), self.height()) - 8
        rect = QtCore.QRectF(4, 4, size, size)

        # Background circular track
        track_pen = QtGui.QPen(QtGui.QColor(Palette.TRACK), 3.5)
        painter.setPen(track_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(rect)

        # Active circular progress arc
        if self._score > 0:
            arc_pen = QtGui.QPen(self._color, 3.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
            painter.setPen(arc_pen)
            start_angle = 90 * 16  # 12 o'clock
            span_angle = -int((min(100.0, max(0.0, self._score)) / 100.0) * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # Exact numeric metric
        if self._score > 0:
            val_font = _ui_font(14, bold=True)
            val_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
            painter.setFont(val_font)
            painter.setPen(QtGui.QColor('#FFFFFF'))
            score_text = f"{int(round(self._score))}"
            val_rect = QtCore.QRectF(rect.x(), rect.y() + 6, rect.width(), rect.height() * 0.45)
            painter.drawText(val_rect, QtCore.Qt.AlignCenter, score_text)

            sub_font = _ui_font(8, weight=QtGui.QFont.DemiBold)
            sub_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
            painter.setFont(sub_font)
            painter.setPen(self._color)
            sub_rect = QtCore.QRectF(rect.x(), rect.y() + rect.height() * 0.50, rect.width(), rect.height() * 0.35)
            painter.drawText(sub_rect, QtCore.Qt.AlignCenter, "%")
        else:
            font = _ui_font(16, bold=True)
            font.setStyleStrategy(QtGui.QFont.PreferAntialias)
            painter.setFont(font)
            painter.setPen(QtGui.QColor('#8B949E'))
            painter.drawText(rect, QtCore.Qt.AlignCenter, "—")


class ProjectIntelligenceDashboard(QtWidgets.QWidget):
    analysis_ready = QtCore.pyqtSignal(object)
    analysis_failed = QtCore.pyqtSignal(str)
    open_file_requested = QtCore.pyqtSignal(str, int)
    open_graph_editor_requested = QtCore.pyqtSignal(object, str)
    open_defense_guide_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('projectIntelligence')
        self.engine: Optional[ProjectIntelligenceEngine] = None
        self.analysis: Optional[ProjectAnalysis] = None
        self._thread = None
        self._worker = None
        self._analysis_generation = 0
        self._refresh_pending = False
        self._last_progress_at = 0.0
        self.enabled_analyzers = {'structure', 'dependencies', 'health'}
        self.student_tips = []
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.engine or not getattr(self.engine, 'root', None):
            detected = self._resolve_root_path()
            if detected:
                self.set_project(detected)
        # Five tabs need more room than the default sidebar width.
        ensure = getattr(self.window(), "_ensure_intelligence_width", None)
        if callable(ensure):
            QtCore.QTimer.singleShot(0, ensure)

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # Header
        header = QtWidgets.QFrame()
        header.setObjectName('intelligenceHeader')
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.setSpacing(6)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(1)
        title = QtWidgets.QLabel('Анализ проекта')
        title.setObjectName('intelligenceTitle')
        title.setStyleSheet(
            ' font-size: 12px; font-weight: 600;'
            f' color: {Palette.TEXT_STRONG};')
        self.status = QtWidgets.QLabel('Проект не открыт')
        self.status.setObjectName('intelligenceStatus')
        self.status.setStyleSheet(
            ' font-size: 11px;'
            f' color: {Palette.TEXT_MUTED};')
        title_box.addWidget(title)
        title_box.addWidget(self.status)
        hl.addLayout(title_box, 1)

        # Status lines are informative, not width-defining: without this the
        # long "Файлов: N · M мс" text forced the panel to ~800 px.
        for label in (title, self.status):
            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                QtWidgets.QSizePolicy.Preferred)
            label.setMinimumWidth(0)

        self.refresh_button = QtWidgets.QToolButton()
        self.refresh_button.setText('↻')
        self.refresh_button.setToolTip('Повторно проанализировать проект')
        self.refresh_button.setStyleSheet(secondary_button_qss())
        self.refresh_button.clicked.connect(self.refresh)
        hl.addWidget(self.refresh_button)

        self.open_graph_button = QtWidgets.QToolButton()
        self.open_graph_button.setText('Граф')
        self.open_graph_button.setToolTip('Открыть интерактивную карту/граф связей проекта')
        self.open_graph_button.setStyleSheet(secondary_button_qss())
        self.open_graph_button.clicked.connect(self._open_graph_editor)
        hl.addWidget(self.open_graph_button)

        self.defense_guide_button = QtWidgets.QToolButton()
        self.defense_guide_button.setText('Паспорт')
        self.defense_guide_button.setToolTip('Сформировать архитектурный паспорт и сводный отчёт проекта')
        self.defense_guide_button.setStyleSheet(primary_button_qss())
        self.defense_guide_button.clicked.connect(self._open_defense_guide)
        hl.addWidget(self.defense_guide_button)
        root.addWidget(header)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        root.addWidget(self.progress)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName('intelligenceTabs')
        root.addWidget(self.tabs, 1)

        # Tab 1: Overview & Quality
        self.overview_tab = QtWidgets.QWidget()
        self._build_overview_tab()
        self.overview_scroll = QtWidgets.QScrollArea()
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.overview_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.overview_scroll.setWidget(self.overview_tab)
        self.tabs.addTab(self.overview_scroll, 'Сводка')

        # Tab 2: Code Recommendations
        self.tips_tab = QtWidgets.QWidget()
        self._build_tips_tab()
        self.tips_scroll = self._wrap_in_scroll(self.tips_tab)
        self.tabs.addTab(self.tips_scroll, 'Советы')

        # Tab 3: Structure & Files
        self.structure_tab = QtWidgets.QWidget()
        self._build_structure_tab()
        self.tabs.addTab(self._wrap_in_scroll(self.structure_tab), 'Файлы')

        # Tab 4: Impact Analyzer
        self.impact_page = QtWidgets.QWidget()
        self._build_impact_tab()
        self.impact_scroll = self._wrap_in_scroll(self.impact_page)
        self.tabs.addTab(self.impact_scroll, 'Влияние')

        # Tab 5: Adversarial testing («Адвокат дьявола»)
        self._adversary_path: Optional[str] = None
        self._adversary_report = None
        self._adversary_thread: Optional[QtCore.QThread] = None
        self._adversary_worker = None
        self.adversary_page = QtWidgets.QWidget()
        self._build_adversary_tab()
        self.adversary_scroll = self._wrap_in_scroll(self.adversary_page)
        self.tabs.addTab(self.adversary_scroll, 'Тесты')

        # Tab 6: project task board
        from core.project_tasks import TaskStore as ProjectTaskStore
        self._task_store = ProjectTaskStore(None)
        self.tasks_page = QtWidgets.QWidget()
        self._build_tasks_tab()
        self.tabs.addTab(self._wrap_in_scroll(self.tasks_page), 'Задачи')
        self.tabs.tabBar().hide()
        self.navigation = AnalysisNavigation(self.tabs, self)
        root.insertWidget(root.indexOf(self.tabs), self.navigation)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.loading_overlay = LoadingOverlay(self)
        self.apply_interface_font()

    @staticmethod
    def _wrap_in_scroll(page: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        """Let a tab scroll instead of forcing the whole panel wider.

        Recommendation cards and wide tables used to raise the panel's minimum
        width to ~950 px, so on a 400 px sidebar everything was clipped.
        """
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setWidget(page)
        return scroll

    def _build_overview_tab(self):
        layout = QtWidgets.QVBoxLayout(self.overview_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Project Quality Card
        self.grade_card = QtWidgets.QFrame()
        self.grade_card.setObjectName('overviewGradeCard')
        self.grade_card.setStyleSheet(
            f'#overviewGradeCard {{ background: {Palette.SURFACE};'
            f' border: 1px solid {Palette.BORDER}; border-radius: 8px; }}')
        gcl = QtWidgets.QHBoxLayout(self.grade_card)
        gcl.setContentsMargins(14, 12, 14, 12)
        gcl.setSpacing(14)

        self.grade_badge = QualityBadgeWidget()
        gcl.addWidget(self.grade_badge)

        ginfo_layout = QtWidgets.QVBoxLayout()
        ginfo_layout.setSpacing(3)
        self.grade_title = QtWidgets.QLabel('Качество кода: —')
        self.grade_title.setStyleSheet(
            ' font-size: 13px; font-weight: 600;'
            f' color: {Palette.TEXT_STRONG};')
        self.grade_score = QtWidgets.QLabel('Оценка: —')
        self.grade_score.setStyleSheet(
            ' font-size: 12px; font-weight: 600;'
            f' color: {Palette.ACCENT_TEXT};')
        self.grade_desc = QtWidgets.QLabel('Откройте проект — покажем качество кода, структуру и рекомендации.')
        self.grade_desc.setWordWrap(True)
        self.grade_desc.setStyleSheet(
            ' font-size: 11px;'
            f' color: {Palette.TEXT_MUTED};')
        ginfo_layout.addWidget(self.grade_title)
        ginfo_layout.addWidget(self.grade_score)
        ginfo_layout.addWidget(self.grade_desc)

        # Folder change button removed per user request; hidden button kept for API safety
        self.open_folder_btn = QtWidgets.QPushButton()
        self.open_folder_btn.hide()

        gcl.addLayout(ginfo_layout, 1)
        layout.addWidget(self.grade_card)

        # Metrics Grid (with proper top margin/spacing under the title)
        metrics_group = QtWidgets.QGroupBox('Показатели проекта')
        metrics_group.setStyleSheet(f'''
            QGroupBox {{

                font-weight: 600;
                font-size: 12px;
                color: {Palette.TEXT};
                border: 1px solid {Palette.BORDER};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 18px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                color: {Palette.TEXT_MUTED};
            }}
        ''')
        mgl = QtWidgets.QGridLayout(metrics_group)
        mgl.setContentsMargins(10, 18, 10, 10)
        mgl.setHorizontalSpacing(8)
        mgl.setVerticalSpacing(8)

        self.metric_widgets = {}
        cards = [
            ('files', 'Файлов', 'Файлы исходного кода'),
            ('lines', 'Строк кода', 'Всего строк'),
            ('functions', 'Функций', 'Функции и методы'),
            ('classes', 'Классов', 'Классы и структуры'),
            ('complexity', 'Сложность', 'Средняя сложность функций'),
        ]
        for idx, (key, label, desc) in enumerate(cards):
            box = QtWidgets.QFrame()
            box.setObjectName(f'metricBox_{key}')
            box.setStyleSheet(
                f'#metricBox_{key} {{ background: {Palette.SURFACE_ALT};'
                f' border: 1px solid {Palette.BORDER}; border-radius: 6px; }}')
            bl = QtWidgets.QVBoxLayout(box)
            bl.setContentsMargins(8, 6, 8, 6)
            bl.setSpacing(2)
            val = QtWidgets.QLabel('—')
            val.setStyleSheet(
                ' font-size: 15px; font-weight: 600;'
                f' color: {Palette.TEXT_STRONG};')
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(' color: #8B949E; font-size: 11px; font-weight: 500;')
            bl.addWidget(val)
            bl.addWidget(lbl)
            if idx == 4:
                mgl.addWidget(box, 2, 0, 1, 2)
            else:
                mgl.addWidget(box, idx // 2, idx % 2)
            self.metric_widgets[key] = val
        layout.addWidget(metrics_group)

        # Quick Actions Box (with proper top margin/spacing under the title)
        actions_box = QtWidgets.QGroupBox('Быстрые действия')
        actions_box.setStyleSheet(f'''
            QGroupBox {{

                font-weight: 600;
                font-size: 12px;
                color: {Palette.TEXT};
                border: 1px solid {Palette.BORDER};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 18px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                color: {Palette.TEXT_MUTED};
            }}
        ''')
        abl = QtWidgets.QVBoxLayout(actions_box)
        abl.setContentsMargins(10, 18, 10, 10)
        abl.setSpacing(8)

        # One primary (accent) action, the rest quiet — no gradients.
        self.act_defense_btn = QtWidgets.QPushButton('Открыть паспорт проекта')
        self.act_defense_btn.setStyleSheet(primary_button_qss("8px 12px", 6))
        self.act_defense_btn.clicked.connect(self._open_defense_guide)
        abl.addWidget(self.act_defense_btn)

        self.act_graph_btn = QtWidgets.QPushButton('Открыть карту связей')
        self.act_graph_btn.setStyleSheet(secondary_button_qss("8px 12px", 6))
        self.act_graph_btn.clicked.connect(self._open_graph_editor)
        abl.addWidget(self.act_graph_btn)

        self.act_tips_btn = QtWidgets.QPushButton('Посмотреть рекомендации')
        self.act_tips_btn.setStyleSheet(secondary_button_qss("8px 12px", 6))
        self.act_tips_btn.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tips_scroll))
        abl.addWidget(self.act_tips_btn)
        layout.addWidget(actions_box)

        layout.addStretch()

    def _build_tips_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tips_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QtWidgets.QLabel('Что стоит улучшить в коде — по приоритету.')
        hint.setStyleSheet('color: #8B949E; font-size: 11px;')
        layout.addWidget(hint)

        filter_row = QtWidgets.QHBoxLayout()
        self.tips_filter = QtWidgets.QComboBox()
        self.tips_filter.addItems(['Все рекомендации', 'Высокий приоритет', 'Слишком длинные функции', 'Глубокая вложенность'])
        self.tips_filter.currentIndexChanged.connect(self._filter_tips)
        filter_row.addWidget(self.tips_filter)

        self.tips_search = QtWidgets.QLineEdit()
        self.tips_search.setPlaceholderText('Поиск по файлу или описанию…')
        self.tips_search.setClearButtonEnabled(True)
        self.tips_search.textChanged.connect(self._filter_tips)
        filter_row.addWidget(self.tips_search, 1)

        self.copy_tips_btn = QtWidgets.QPushButton('Скопировать')
        self.copy_tips_btn.setToolTip('Скопировать все текущие рекомендации в буфер обмена')
        self.copy_tips_btn.setStyleSheet(secondary_button_qss("4px 10px", 6))
        self.copy_tips_btn.clicked.connect(self._copy_tips)
        filter_row.addWidget(self.copy_tips_btn)

        self.save_tips_btn = QtWidgets.QPushButton('Экспорт в файл…')
        self.save_tips_btn.setToolTip('Сохранить рекомендации и дефекты в файл (.md, .txt, .json)')
        self.save_tips_btn.setStyleSheet(secondary_button_qss("4px 10px", 6))
        self.save_tips_btn.clicked.connect(self._save_tips_to_file)
        filter_row.addWidget(self.save_tips_btn)

        layout.addLayout(filter_row)

        self.tips_tree = QtWidgets.QTreeWidget()
        self.tips_tree.setHeaderLabels(['Замечание', 'Приоритет', 'Файл', 'Строка', 'Рекомендация'])
        self.tips_tree.setAlternatingRowColors(True)
        self.tips_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tips_tree.customContextMenuRequested.connect(self._on_tips_context_menu)
        self.tips_tree.itemDoubleClicked.connect(self._open_tip_item)
        layout.addWidget(self.tips_tree, 1)

    def _collect_tips_data(self, only_selected: bool = False) -> list:
        items = []
        if only_selected:
            selected = self.tips_tree.selectedItems()
            raw_items = selected if selected else ([self.tips_tree.currentItem()] if self.tips_tree.currentItem() else [])
        else:
            raw_items = [self.tips_tree.topLevelItem(i) for i in range(self.tips_tree.topLevelItemCount())]

        for item in raw_items:
            if not item:
                continue
            title = item.text(0)
            priority = item.text(1)
            file_rel = item.text(2)
            line = item.text(3)
            action = item.text(4)
            full_path = item.data(0, QtCore.Qt.UserRole) or file_rel
            explanation = item.toolTip(0) or action
            items.append({
                "title": title,
                "priority": priority,
                "file": file_rel,
                "full_path": str(full_path),
                "line": line,
                "action": action,
                "explanation": explanation
            })
        return items

    def _copy_tips(self):
        tips = self._collect_tips_data(only_selected=False)
        if not tips:
            QtWidgets.QMessageBox.information(self, "Копирование", "Список рекомендаций пуст.")
            return

        lines = [
            f"# Замечания и рекомендации по коду проекта ({len(tips)})",
            f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        for idx, t in enumerate(tips, 1):
            lines.append(f"### {idx}. [{t['priority']}] {t['title']}")
            lines.append(f"- **Файл:** `{t['file']}` (строка {t['line']})")
            if t['action']:
                lines.append(f"- **Рекомендация:** {t['action']}")
            if t['explanation'] and t['explanation'] != t['action']:
                lines.append(f"- **Пояснение:** {t['explanation']}")
            lines.append("")

        text = "\n".join(lines)
        QtWidgets.QApplication.clipboard().setText(text)

        orig_text = self.copy_tips_btn.text()
        self.copy_tips_btn.setText(f"✓ Скопировано ({len(tips)})")
        QtCore.QTimer.singleShot(2000, lambda: self.copy_tips_btn.setText(orig_text))

    def _save_tips_to_file(self):
        tips = self._collect_tips_data(only_selected=False)
        if not tips:
            QtWidgets.QMessageBox.information(self, "Сохранение", "Список рекомендаций пуст.")
            return

        suggested = "project_code_issues.md"
        file_path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Сохранить замечания и дефекты в файл",
            suggested,
            "Markdown (*.md);;Текстовый файл (*.txt);;JSON файл (*.json);;Все файлы (*.*)"
        )
        if not file_path:
            return

        p = Path(file_path)
        ext = p.suffix.lower()

        if ext == ".json" or "JSON" in selected_filter:
            content = json.dumps({
                "generated_at": datetime.now().isoformat(),
                "total_issues": len(tips),
                "issues": tips
            }, indent=2, ensure_ascii=False)
        elif ext == ".txt" or "Текстовый" in selected_filter:
            lines = [
                f"=== ЗАМЕЧАНИЯ И ДЕФЕКТЫ ПРОЕКТА ({len(tips)}) ===",
                f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 50,
                ""
            ]
            for idx, t in enumerate(tips, 1):
                lines.append(f"[{idx}] [{t['priority']}] {t['title']}")
                lines.append(f"    Файл: {t['file']}:{t['line']}")
                lines.append(f"    Рекомендация: {t['action']}")
                if t['explanation'] and t['explanation'] != t['action']:
                    lines.append(f"    Детали: {t['explanation']}")
                lines.append("-" * 40)
            content = "\n".join(lines)
        else:
            lines = [
                f"# Замечания и рекомендации по коду проекта ({len(tips)})",
                f"Экспортировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "| № | Приоритет | Замечание | Файл | Строка | Рекомендация |",
                "|---|-----------|-----------|------|--------|--------------|"
            ]
            for idx, t in enumerate(tips, 1):
                lines.append(f"| {idx} | {t['priority']} | {t['title']} | `{t['file']}` | {t['line']} | {t['action']} |")
            lines.append("")
            lines.append("## Подробный список")
            lines.append("")
            for idx, t in enumerate(tips, 1):
                lines.append(f"### {idx}. {t['title']}")
                lines.append(f"- **Приоритет:** {t['priority']}")
                lines.append(f"- **Файл:** `{t['full_path']}`:{t['line']}")
                lines.append(f"- **Рекомендация:** {t['action']}")
                if t['explanation'] and t['explanation'] != t['action']:
                    lines.append(f"- **Описание:** {t['explanation']}")
                lines.append("")
            content = "\n".join(lines)

        try:
            p.write_text(content, encoding='utf-8')
            QtWidgets.QMessageBox.information(
                self,
                "Файл сохранён",
                f"Список замечаний ({len(tips)}) успешно сохранён в файл:\n{file_path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось записать файл:\n{e}"
            )

    def _on_tips_context_menu(self, pos):
        item = self.tips_tree.itemAt(pos)
        menu = QtWidgets.QMenu(self)

        if item:
            act_copy_one = menu.addAction("📋 Скопировать выбранное замечание")
            act_copy_one.triggered.connect(lambda: self._copy_single_tip(item))
            act_open = menu.addAction("🔍 Перейти к строке в файле")
            act_open.triggered.connect(lambda: self._open_tip_item(item, 0))
            menu.addSeparator()

        total = self.tips_tree.topLevelItemCount()
        act_copy_all = menu.addAction(f"📋 Скопировать все замечания ({total})")
        act_copy_all.triggered.connect(self._copy_tips)

        act_save = menu.addAction("💾 Сохранить список в файл…")
        act_save.triggered.connect(self._save_tips_to_file)

        menu.exec_(self.tips_tree.viewport().mapToGlobal(pos))

    def _copy_single_tip(self, item):
        title = item.text(0)
        prio = item.text(1)
        f = item.text(2)
        line = item.text(3)
        action = item.text(4)
        expl = item.toolTip(0) or action
        text = f"[{prio}] {title}\nФайл: {f}:{line}\nРекомендация: {action}\nПояснение: {expl}"
        QtWidgets.QApplication.clipboard().setText(text)

    def _build_structure_tab(self):
        layout = QtWidgets.QVBoxLayout(self.structure_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.structure_summary = QtWidgets.QLabel('Откройте проект для изучения архитектуры.')
        self.structure_summary.setWordWrap(True)
        self.structure_summary.setStyleSheet('color: #D4D4D4; font-size: 12px; line-height: 1.4;')
        layout.addWidget(self.structure_summary)

        self.structure_search = QtWidgets.QLineEdit()
        self.structure_search.setPlaceholderText('Поиск по классам, функциям и файлам…')
        self.structure_search.setClearButtonEnabled(True)
        self.structure_search.textChanged.connect(self._filter_structure)
        layout.addWidget(self.structure_search)

        self.structure_tree = QtWidgets.QTreeWidget()
        self.structure_tree.setHeaderLabels(['Элемент', 'Тип', 'Файл', 'Строка'])
        self.structure_tree.itemDoubleClicked.connect(self._open_symbol_item)
        self.structure_tree.itemExpanded.connect(self._on_structure_item_expanded)
        layout.addWidget(self.structure_tree, 1)


    def apply_interface_font(self):
        """Keep analysis UI independent of the editor's monospace font."""
        font = _ui_font(9)
        self.setFont(font)
        for child in self.findChildren(QtWidgets.QWidget):
            child.setFont(font)

    def _build_tasks_tab(self):
        """Project task board: analyse once, then work through the list."""
        layout = QtWidgets.QVBoxLayout(self.tasks_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QtWidgets.QLabel(
            'Задачи проекта: добавляйте вручную или из рекомендаций анализатора. '
            'Список хранится в .pyscribe/tasks.json и сохраняется вместе с проектом.')
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {Palette.TEXT_MUTED}; font-size: 11px;')
        layout.addWidget(hint)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)
        self.task_add_btn = QtWidgets.QPushButton('Новая')
        self.task_add_btn.setStyleSheet(primary_button_qss("4px 10px", 6))
        self.task_add_btn.setToolTip('Добавить задачу')
        self.task_add_btn.clicked.connect(self._add_task_dialog)
        row.addWidget(self.task_add_btn)

        self.task_from_tip_btn = QtWidgets.QPushButton('Из рекомендации')
        self.task_from_tip_btn.setStyleSheet(secondary_button_qss("4px 8px", 6))
        self.task_from_tip_btn.setToolTip(
            'Создать задачу из выбранной рекомендации на вкладке «Советы»')
        self.task_from_tip_btn.clicked.connect(self._task_from_recommendation)
        row.addWidget(self.task_from_tip_btn)
        row.addStretch(1)
        layout.addLayout(row)

        filter_row = QtWidgets.QVBoxLayout()
        filter_row.setSpacing(6)
        self.task_filter = QtWidgets.QComboBox()
        for key, label in (("", "Все задачи"), ("todo", "К выполнению"),
                           ("doing", "В работе"), ("done", "Готово")):
            self.task_filter.addItem(label, key)
        self.task_filter.currentIndexChanged.connect(lambda _i: self._refresh_tasks())
        filter_row.addWidget(self.task_filter)
        self.task_summary = QtWidgets.QLabel('Задач пока нет')
        self.task_summary.setStyleSheet(f'color: {Palette.TEXT_MUTED}; font-size: 11px;')
        filter_row.addWidget(self.task_summary)
        layout.addLayout(filter_row)

        self.task_tree = QtWidgets.QTreeWidget()
        self.task_tree.setHeaderLabels(['Задача', 'Статус', 'Приоритет', 'Файл'])
        self.task_tree.setColumnWidth(0, 190)
        self.task_tree.setColumnWidth(1, 90)
        self.task_tree.setColumnWidth(2, 75)
        self.task_tree.header().setStretchLastSection(True)
        self.task_tree.itemDoubleClicked.connect(self._open_task_item)
        self.task_tree.itemChanged.connect(self._on_task_item_changed)
        layout.addWidget(self.task_tree, 1)

        actions = QtWidgets.QGridLayout()
        actions.setSpacing(4)
        for index, (text, tip, slot) in enumerate((
            ('Готово', 'Переключить выбранную задачу', self._toggle_task_done),
            ('В работу', 'Взять задачу в работу', lambda: self._set_task_status('doing')),
            ('Удалить', 'Удалить выбранную задачу', self._remove_task),
            ('Очистить готовые', 'Удалить все выполненные задачи', self._clear_done_tasks),
        )):
            button = QtWidgets.QPushButton(text)
            button.setStyleSheet(secondary_button_qss("4px 8px", 6))
            button.setToolTip(tip)
            button.clicked.connect(slot)
            actions.addWidget(button, index // 2, index % 2)
        layout.addLayout(actions)

        self._loading_tasks = False

    # -- task board ----------------------------------------------------
    def _selected_task(self):
        item = self.task_tree.currentItem() if hasattr(self, "task_tree") else None
        if item is None:
            return None
        task_id = item.data(0, QtCore.Qt.UserRole)
        return self._task_store.find(task_id) if task_id else None

    def _refresh_tasks(self):
        if not hasattr(self, "task_tree"):
            return
        self._loading_tasks = True
        try:
            self.task_tree.clear()
            status = self.task_filter.currentData() if hasattr(self, "task_filter") else ""
            tasks = self._task_store.filtered(status or None)
            colours = {"high": Palette.DANGER, "medium": Palette.WARNING,
                       "low": Palette.TEXT_MUTED}
            for task in tasks:
                item = QtWidgets.QTreeWidgetItem([
                    task.title,
                    "Готово" if task.is_done else "К выполнению",
                    {"high": "Высокий", "medium": "Средний", "low": "Низкий"}.get(task.priority, "Средний"),
                    Path(task.file).name if task.file else "—",
                ])
                item.setData(0, QtCore.Qt.UserRole, task.id)
                item.setData(2, QtCore.Qt.UserRole, task.priority)
                item.setToolTip(0, task.details or task.title)
                item.setForeground(2, QtGui.QBrush(QtGui.QColor(
                    colours.get(task.priority, Palette.TEXT_MUTED))))
                if task.is_done:
                    font = item.font(0)
                    font.setStrikeOut(True)
                    item.setFont(0, font)
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor(Palette.TEXT_MUTED)))
                item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                self.task_tree.addTopLevelItem(item)
        finally:
            self._loading_tasks = False
        stats = self._task_store.stats()
        self.task_summary.setText(
            f'всего {stats["total"]} · в работе {stats["doing"]} · '
            f'готово {stats["done"]}')
        if self._task_store.error:
            self.task_summary.setText(self._task_store.error)

    def _on_task_item_changed(self, item, column):
        """Rename a task by editing its title in place."""
        if getattr(self, "_loading_tasks", False) or column != 0 or item is None:
            return
        task_id = item.data(0, QtCore.Qt.UserRole)
        task = self._task_store.find(task_id) if task_id else None
        if task is None:
            return
        title = item.text(0).strip()
        if title and title != task.title:
            self._task_store.update(task_id, title=title)
            self._refresh_tasks()

    def _add_task_dialog(self):
        from widgets.Dialog import CustomDialog
        try:
            from PyQt5.QtWidgets import QInputDialog
            title, ok = QInputDialog.getText(self, 'Новая задача', 'Что нужно сделать?')
            if not ok or not title.strip():
                return
            self._task_store.add(title.strip())
            self._refresh_tasks()
        except Exception:
            CustomDialog("Не удалось добавить задачу.").exec_()

    def _task_from_recommendation(self):
        item = getattr(self, "tips_tree", None) and self.tips_tree.currentItem()
        if item is None:
            from widgets.Dialog import CustomDialog
            CustomDialog("Выберите рекомендацию на вкладке «Советы».").exec_()
            return
        title = item.text(0)
        file_path = item.data(0, QtCore.Qt.UserRole) or ""
        line = item.data(1, QtCore.Qt.UserRole) or 0
        details = item.toolTip(0) or ""
        self._task_store.add(title, details=details, file=str(file_path),
                             line=int(line or 0), source="analysis",
                             priority="high")
        self._refresh_tasks()
        self.tabs.setCurrentWidget(self._wrap_find_tasks())

    def _wrap_find_tasks(self):
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is self.tasks_page or self.tabs.widget(index).findChild(
                    QtWidgets.QTreeWidget) is self.task_tree:
                return self.tabs.widget(index)
        return self.tasks_page

    def _toggle_task_done(self):
        task = self._selected_task()
        if task is None:
            return
        self._task_store.toggle_done(task.id)
        self._refresh_tasks()

    def _set_task_status(self, status: str):
        task = self._selected_task()
        if task is None:
            return
        self._task_store.set_status(task.id, status)
        self._refresh_tasks()

    def _remove_task(self):
        task = self._selected_task()
        if task is None:
            return
        self._task_store.remove(task.id)
        self._refresh_tasks()

    def _clear_done_tasks(self):
        self._task_store.clear_done()
        self._refresh_tasks()

    def _open_task_item(self, item, _column):
        task = self._selected_task()
        if task is None or not task.file:
            return
        self.open_file_requested.emit(str(task.file), int(task.line or 1))

    def _build_adversary_tab(self):
        """«Адвокат дьявола»: run boundary inputs and prove the crashes."""
        layout = QtWidgets.QVBoxLayout(self.adversary_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QtWidgets.QLabel(
            '«Адвокат дьявола»: подаёт функции граничные входы (пустой список, None, '
            '0, длинные строки) в отдельном процессе, ловит падения и зависания, '
            'сокращает вход до минимального и показывает причину.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #8B949E; font-size: 11px;')
        layout.addWidget(hint)

        row = QtWidgets.QHBoxLayout()
        self.adversary_file_label = QtWidgets.QLabel('Файл не выбран')
        self.adversary_file_label.setStyleSheet(
            f'color: {Palette.TEXT}; font-size: 12px;')
        self.adversary_file_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        row.addWidget(self.adversary_file_label, 1)
        self.adversary_btn = QtWidgets.QPushButton('Испытать')
        self.adversary_btn.setStyleSheet(primary_button_qss("5px 12px", 6))
        self.adversary_btn.clicked.connect(self._run_adversary)
        row.addWidget(self.adversary_btn)
        layout.addLayout(row)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(4)
        self.adversary_test_btn = QtWidgets.QPushButton('Тест')
        self.adversary_test_btn.setStyleSheet(secondary_button_qss("4px 8px", 6))
        self.adversary_test_btn.setToolTip(
            '«Создать тест»: сохранить найденные падения как pytest-тесты')
        self.adversary_test_btn.clicked.connect(self._save_adversary_tests)
        actions.addWidget(self.adversary_test_btn)

        self.adversary_export_btn = QtWidgets.QPushButton('Отчёт')
        self.adversary_export_btn.setStyleSheet(secondary_button_qss("4px 8px", 6))
        self.adversary_export_btn.setToolTip('Экспортировать отчёт в Markdown')
        self.adversary_export_btn.clicked.connect(self._export_adversary)
        actions.addWidget(self.adversary_export_btn)

        self.adversary_ai_btn = QtWidgets.QPushButton('ИИ')
        self.adversary_ai_btn.setStyleSheet(secondary_button_qss("4px 8px", 6))
        self.adversary_ai_btn.setToolTip(
            '«Спросить ИИ»: отправить находку ИИ-агенту на разбор')
        self.adversary_ai_btn.clicked.connect(self._ask_ai_about_adversary)
        actions.addWidget(self.adversary_ai_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.adversary_summary = QtWidgets.QLabel(
            'Откройте файл и нажмите «Испытать».')
        self.adversary_summary.setStyleSheet(
            f'color: {Palette.TEXT_MUTED}; font-size: 12px;')
        self.adversary_summary.setWordWrap(True)
        layout.addWidget(self.adversary_summary)

        self.adversary_progress = QtWidgets.QProgressBar()
        self.adversary_progress.setRange(0, 0)
        self.adversary_progress.setFixedHeight(4)
        self.adversary_progress.setTextVisible(False)
        self.adversary_progress.hide()
        layout.addWidget(self.adversary_progress)

        self.adversary_tree = QtWidgets.QTreeWidget()
        self.adversary_tree.setHeaderLabels(['Функция (вход)', 'Результат'])
        self.adversary_tree.setColumnWidth(0, 120)
        self.adversary_tree.header().setStretchLastSection(True)
        self.adversary_tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.adversary_tree.setWordWrap(True)
        self.adversary_tree.itemDoubleClicked.connect(self._open_adversary_item)
        layout.addWidget(self.adversary_tree, 1)

        self._set_adversary_buttons(False)

    def _set_adversary_buttons(self, enabled: bool):
        has_report = self._adversary_report is not None and bool(
            getattr(self._adversary_report, "failures", []))
        self.adversary_test_btn.setEnabled(bool(enabled and has_report))
        self.adversary_export_btn.setEnabled(bool(enabled and has_report))
        self.adversary_ai_btn.setEnabled(bool(enabled and has_report))

    def set_adversary_file(self, path: Optional[str]):
        """Point the «Испытания» tab at the file opened in the editor."""
        self._adversary_path = str(path) if path else None
        if path:
            self.adversary_file_label.setText(Path(str(path)).name)
            self.adversary_file_label.setToolTip(str(path))
            self.tabs.setCurrentWidget(self.adversary_scroll)
        else:
            self.adversary_file_label.setText('Файл не выбран')

    def _current_editor_path(self) -> Optional[str]:
        """Path of the file open in the editor, if any."""
        win = self.window()
        getter = getattr(win, "get_current_editor", None)
        if not callable(getter):
            return None
        try:
            editor = getter()
        except Exception:
            return None
        path = getattr(editor, "file_path", None) if editor else None
        return str(path) if path else None

    def _sync_adversary_file(self) -> Optional[str]:
        """Pick up the editor's file automatically.

        The tab used to demand a file chosen through a separate command, so
        pressing «Испытать» only produced a "open a file first" warning even
        with a file open right next to it.
        """
        if self._adversary_thread is not None and self._adversary_thread.isRunning():
            return self._adversary_path
        current = self._current_editor_path()
        if not current:
            return self._adversary_path
        if current != self._adversary_path:
            self._adversary_path = current
            # Results belong to the previous file: drop them instead of
            # showing them next to a different file name.
            self._adversary_report = None
            self.adversary_tree.clear()
            self._set_adversary_buttons(False)
            self.adversary_summary.setText(
                'Нажмите «Испытать», чтобы проверить этот файл.')
            self.adversary_summary.setStyleSheet(
                f'color: {Palette.TEXT_MUTED}; font-size: 12px;')
        self.adversary_file_label.setText(Path(current).name)
        self.adversary_file_label.setToolTip(current)
        return self._adversary_path

    def _on_tab_changed(self, index: int):
        page = self.tabs.widget(index)
        if page is getattr(self, "adversary_scroll", None):
            self._sync_adversary_file()

    def _run_adversary(self):
        if self._adversary_thread is not None and self._adversary_thread.isRunning():
            return
        if not self._sync_adversary_file():
            CustomDialog("Сначала откройте файл, который нужно испытать.").exec_()
            return
        path = Path(self._adversary_path)
        if path.suffix.lower() != ".py":
            CustomDialog(
                f"«Адвокат дьявола» работает с Python-файлами, "
                f"а открыт «{path.name}».").exec_()
            return
        self.adversary_tree.clear()
        self._adversary_report = None
        self._set_adversary_buttons(False)
        self.adversary_summary.setText('Испытание выполняется…')
        self.adversary_progress.show()
        self.adversary_btn.setEnabled(False)

        worker = AdversaryWorker(self._adversary_path)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_adversary_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._adversary_thread = thread
        self._adversary_worker = worker
        thread.start()

    def _on_adversary_finished(self, report):
        self.adversary_progress.hide()
        self.adversary_btn.setEnabled(True)
        self._adversary_report = report
        if report is None:
            self.adversary_summary.setText('Испытание не удалось.')
            return
        if getattr(report, "error", ""):
            self.adversary_summary.setText(report.error)
            self._set_adversary_buttons(True)
            return
        groups = report.groups() if hasattr(report, "groups") else []
        failures = len(groups)
        if not failures:
            self.adversary_summary.setText(
                f'Проблем не найдено: {report.functions_checked} функций, '
                f'{report.cases_run} случаев.')
            self.adversary_summary.setStyleSheet(
                f'color: {Palette.OK}; font-size: 12px;')
            self._set_adversary_buttons(True)
            return
        self.adversary_summary.setText(
            f'Найдено проблем: {failures} · проверено функций: '
            f'{report.functions_checked} · запущено случаев: {report.cases_run}')
        self.adversary_summary.setStyleSheet(
            f'color: {Palette.DANGER}; font-size: 12px;')
        for finding, count in groups:
            suffix = f'  (+{count - 1})' if count > 1 else ''
            item = QtWidgets.QTreeWidgetItem([
                f"{finding.function}({finding.args_literal})",
                finding.summary + suffix,
            ])
            item.setToolTip(0, f"{finding.function}({finding.args_literal})")
            item.setToolTip(1, (finding.traceback or finding.summary)[:1500])
            item.setData(0, QtCore.Qt.UserRole, finding)
            self.adversary_tree.addTopLevelItem(item)
        self._set_adversary_buttons(True)

    def _open_adversary_item(self, item, _column):
        finding = item.data(0, QtCore.Qt.UserRole) if item else None
        if finding is None or not self._adversary_path:
            return
        line = finding.line or 1
        self.open_file_requested.emit(str(self._adversary_path), int(line))

    def _save_adversary_tests(self):
        from core.adversary import failing_cases_pytest
        if not self._adversary_report or not self._adversary_path:
            return
        target = Path(self._adversary_path)
        suggested = target.with_name(f"test_{target.stem}_adversary.py")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Сохранить тесты', str(suggested), 'Python (*.py)')
        if not path:
            return
        try:
            content = failing_cases_pytest(self._adversary_path,
                                           self._adversary_report.failures)
            Path(path).write_text(content, encoding="utf-8")
            self.adversary_summary.setText(f'Тесты сохранены: {Path(path).name}')
        except Exception as exc:  # noqa: BLE001
            CustomDialog(f"Не удалось сохранить тесты: {exc}").exec_()

    def _export_adversary(self):
        if not self._adversary_report:
            return
        report = self._adversary_report
        suggested = Path(report.module_path or "report").with_suffix(".md")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Экспорт отчёта', str(suggested), 'Markdown (*.md)')
        if not path:
            return
        try:
            Path(path).write_text(report.to_markdown(), encoding="utf-8")
            self.adversary_summary.setText(f'Отчёт сохранён: {Path(path).name}')
        except Exception as exc:  # noqa: BLE001
            CustomDialog(f"Не удалось сохранить отчёт: {exc}").exec_()

    def _ask_ai_about_adversary(self):
        """Send the selected finding to the AI panel for an explanation."""
        if not self._adversary_report:
            return
        item = self.adversary_tree.currentItem()
        finding = item.data(0, QtCore.Qt.UserRole) if item else None
        if finding is None:
            groups = self._adversary_report.groups()
            finding = groups[0][0] if groups else None
        if finding is None:
            return
        prompt = (
            "«Адвокат дьявола» нашёл падение:\n"
            f"Функция: {finding.function}({finding.args_literal})\n"
            f"Ошибка: {finding.summary}\n\n"
            "Объясни причину и предложи минимальное исправление.")
        win = self.window()
        panel = getattr(win, "ai_panel", None)
        if panel is None:
            return
        try:
            win.show_ai_agent()
            panel.input.setPlainText(prompt)
            panel.input.setFocus()
        except Exception:
            pass

    def _build_impact_tab(self):
        layout = QtWidgets.QVBoxLayout(self.impact_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QtWidgets.QLabel('Что сломается, если изменить этот файл: зависимые модули, файлы и сложность.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #8B949E; font-size: 11px;')
        layout.addWidget(hint)

        row = QtWidgets.QHBoxLayout()
        self.impact_combo = QtWidgets.QComboBox()
        self.impact_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        row.addWidget(self.impact_combo, 1)
        self.impact_btn = QtWidgets.QPushButton('Проверить влияние')
        self.impact_btn.setStyleSheet(primary_button_qss("5px 12px", 6))
        self.impact_btn.clicked.connect(self._run_impact_analysis)
        row.addWidget(self.impact_btn)
        layout.addLayout(row)

        self.impact_status_label = QtWidgets.QLabel('Выберите файл, чтобы увидеть зависимости.')
        self.impact_status_label.setStyleSheet(
            f'color: {Palette.TEXT_MUTED}; font-size: 12px;')
        layout.addWidget(self.impact_status_label)

        self.impact_tree = QtWidgets.QTreeWidget()
        self.impact_tree.setHeaderLabels(['Модуль', 'Файл', 'Сложность'])
        self.impact_tree.itemDoubleClicked.connect(self._open_impact_item)
        layout.addWidget(self.impact_tree, 1)

    def _resolve_root_path(self) -> Optional[str]:
        """Auto-detect active project/workspace directory from surrounding workbench state."""
        if self.engine and self.engine.root and Path(str(self.engine.root)).is_dir():
            return str(Path(self.engine.root).resolve())

        win = self.window()
        if not hasattr(win, 'current_project') and hasattr(self, 'parent') and self.parent():
            p = self.parent()
            if hasattr(p, 'current_project'):
                win = p
            elif hasattr(p, 'window'):
                win = p.window()

        # 1. Project config
        if hasattr(win, 'current_project') and win.current_project:
            cp = win.current_project
            p_root = cp.get('root_path') if isinstance(cp, dict) else getattr(cp, 'root_path', None)
            if p_root and Path(str(p_root)).is_dir():
                return str(Path(str(p_root)).resolve())

        # 1b. Project manager current project
        if hasattr(win, 'project_manager') and getattr(win.project_manager, 'current_project', None):
            cp = win.project_manager.current_project
            p_root = cp.get('root_path') if isinstance(cp, dict) else getattr(cp, 'root_path', None)
            if p_root and Path(str(p_root)).is_dir():
                return str(Path(str(p_root)).resolve())

        # 2. Window workspace path
        if hasattr(win, 'workspace_path') and win.workspace_path:
            w_root = str(win.workspace_path)
            if Path(w_root).is_dir():
                return str(Path(w_root).resolve())

        # 3. Current active file's folder
        if hasattr(win, 'get_current_editor'):
            ed = win.get_current_editor()
            if ed and getattr(ed, 'file_path', None):
                f_dir = Path(ed.file_path).parent
                if f_dir.is_dir():
                    return str(f_dir.resolve())

        # 4. File explorer root
        if hasattr(win, 'file_explorer') and win.file_explorer:
            try:
                rp = win.file_explorer.model.rootPath()
                if rp and rp not in ('', 'C:/', 'C:\\') and Path(rp).is_dir():
                    return str(Path(rp).resolve())
            except Exception:
                pass

        # 5. Fallback to process cwd
        cwd = Path.cwd()
        if cwd.is_dir():
            return str(cwd.resolve())

        return None

    def choose_and_analyze_folder(self):
        start_dir = self._resolve_root_path() or str(Path.cwd())
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку для анализа", start_dir)
        if folder and Path(folder).is_dir():
            self.set_project(str(Path(folder).resolve()))

    def set_project(self, root: Optional[str], analyzers=None):
        self.enabled_analyzers = set({'structure', 'dependencies', 'health'} if analyzers is None else analyzers)
        # Invalidate any analysis still running for the previous project: its
        # result must never be painted for the newly opened one.
        self._analysis_generation += 1
        self._relative_root = None
        self.engine = ProjectIntelligenceEngine(root, self.enabled_analyzers) if root else None
        self.analysis = None
        # The task board belongs to the project that is open right now.
        try:
            self._task_store.set_root(root)
            self._refresh_tasks()
        except Exception:
            logger.exception("Не удалось загрузить задачи проекта")
        self._clear_views()
        if not root:
            self.status.setText('Проект не открыт')
        elif not self.enabled_analyzers:
            self.status.setText('Анализ отключён')
            # Nothing will finish the animation if no analysis starts.
            try:
                self.loading_overlay.stop()
                self.progress.hide()
                self.refresh_button.setEnabled(True)
            except RuntimeError:
                pass
        else:
            self.status.setText(f'Анализ: {Path(root).name}…')
            self.refresh()

    def _clear_views(self):
        for label in self.metric_widgets.values():
            label.setText('—')
        self.grade_badge.set_grade('—', Palette.TEXT_MUTED, Palette.SURFACE_ALT, 0)
        if hasattr(self, 'grade_title'):
            self.grade_title.setText('Качество кода: —')
        if hasattr(self, 'grade_score'):
            self.grade_score.setText('Оценка: —')
        if hasattr(self, 'grade_desc'):
            self.grade_desc.setText('Откройте проект — покажем качество кода, структуру и рекомендации.')
        if hasattr(self, 'open_folder_btn'):
            self.open_folder_btn.hide()
        self.tips_tree.clear()
        self.structure_tree.clear()
        self.impact_tree.clear()
        self.impact_combo.clear()
        self.open_graph_button.setEnabled(True)

    def refresh(self):
        if not self.engine or not self.engine.root:
            discovered = self._resolve_root_path()
            if discovered:
                self.set_project(discovered)
                return
            else:
                self.choose_and_analyze_folder()
                return

        if self._thread is not None and self._thread.isRunning():
            # A different project was opened while the previous analysis was
            # still running: remember the request and start it once the
            # current thread finishes instead of silently showing stale data.
            self._refresh_pending = True
            return

        root = str(self.engine.root)
        self._analysis_generation += 1
        generation = self._analysis_generation
        worker_engine = ProjectIntelligenceEngine(root, self.enabled_analyzers)

        self.status.setText('Анализируем проект…')
        self.loading_overlay.start('Анализ проекта…', 'Готовим анализатор…', show_progress=True)
        self.progress.setValue(0)
        self.progress.show()
        self.refresh_button.setEnabled(False)

        thread = QtCore.QThread(self)
        worker = AnalysisWorker(worker_engine)
        worker.moveToThread(thread)
        self._thread = thread
        self._worker = worker

        thread.started.connect(worker.run)
        worker.progress.connect(
            lambda current, total, name, gen=generation:
            self._on_progress(current, total, name, gen))
        worker.finished.connect(
            lambda result, gen=generation: self._on_finished(result, gen))
        worker.failed.connect(
            lambda message, gen=generation: self._on_failed(message, gen))
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._analysis_thread_finished)
        thread.start()

    def _is_stale(self, generation) -> bool:
        """True for results that belong to a project the user already left."""
        return generation is not None and generation != self._analysis_generation

    def _on_progress(self, current, total, name, generation=None):
        if self._is_stale(generation):
            return
        # The engine reports every file; repainting the panel (overlay + status
        # text + progress bar) 600+ times made the window stutter. Two updates
        # per second are enough for a progress indicator.
        now = time.monotonic()
        if current < total and (now - self._last_progress_at) < 0.12:
            return
        self._last_progress_at = now
        self.progress.setValue(int(current * 100 / max(1, total)))
        self.loading_overlay.update_progress(current, total, f"Файл: {name}")
        self.status.setText(f'Анализ: {name}…')

    def _analysis_thread_finished(self):
        sender = self.sender()
        if sender is self._thread:
            self._thread = None
            self._worker = None
            if getattr(self, "_refresh_pending", False) and self.engine:
                # A newer project was requested while this analysis was running.
                self._refresh_pending = False
                QtCore.QTimer.singleShot(0, self.refresh)

    def shutdown(self):
        """Stop background threads before the window is destroyed.

        Without this the analysis/adversary workers could be deleted while
        their threads were still running, which ends in a hard crash.
        """
        for attr in ("_thread", "_adversary_thread"):
            thread = getattr(self, attr, None)
            if thread is None:
                continue
            try:
                if thread.isRunning():
                    thread.requestInterruption()
                    thread.quit()
                    thread.wait(3000)
            except RuntimeError:
                pass
            setattr(self, attr, None)
        self._worker = None
        self._adversary_worker = None

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def _on_finished(self, analysis, generation=None):
        if self._is_stale(generation):
            return
        self.analysis = analysis
        if self.engine:
            self.engine.analysis = analysis
        self.loading_overlay.stop()
        self.progress.hide()
        self.refresh_button.setEnabled(True)
        status = f'Файлов: {len(analysis.files)} · {analysis.duration_ms} мс'
        if getattr(analysis, 'scan_truncated', False):
            status += ' · часть файлов пропущена (лимит)'
        self.status.setText(status)
        skipped_dirs = int(getattr(analysis, 'skipped_dirs', 0) or 0)
        skipped_files = int(getattr(analysis, 'skipped_files', 0) or 0)
        skipped_names = list(getattr(analysis, 'skipped_dir_names', []) or [])
        hint = (f'Пропущено служебных каталогов: {skipped_dirs}, файлов: '
                f'{skipped_files}.\nНе анализируются node_modules, .git, '
                'виртуальные окружения, каталоги сборки и файлы больше 2 МБ.')
        if skipped_names:
            hint += '\nПропущены: ' + ', '.join(skipped_names[:10])
            if len(skipped_names) > 10:
                hint += f' и ещё {len(skipped_names) - 10}'
        self.status.setToolTip(hint)
        self._populate(analysis)
        self.analysis_ready.emit(analysis)

    def _on_failed(self, message, generation=None):
        if self._is_stale(generation):
            return
        self.loading_overlay.stop()
        self.progress.hide()
        self.refresh_button.setEnabled(True)
        self.status.setText('Ошибка анализа')
        self.grade_desc.setText(message or 'Не удалось проанализировать проект.')
        # Actions that wait for the analysis must not wait forever.
        try:
            self.analysis_failed.emit(str(message or ''))
        except RuntimeError:
            pass

    def _populate(self, a: ProjectAnalysis):
        metrics = self.engine.metrics() if self.engine else {}
        
        # 1. Update Project Quality Score (Safe parsing)
        health_score = 85.0
        if hasattr(a, 'health_score') and isinstance(a.health_score, (int, float)):
            health_score = float(a.health_score)
        else:
            raw_val = metrics.get('health_score', getattr(a, 'health_score', 85))
            import re
            m = re.search(r'(\d+(?:\.\d+)?)', str(raw_val))
            if m:
                health_score = float(m.group(1))

        grade_info = CodeIntelligenceService.calculate_health_grade(health_score)
        
        self.grade_badge.set_grade(grade_info['letter'], grade_info['color'], grade_info['badge_bg'], health_score)
        if hasattr(self, 'grade_title'):
            self.grade_title.setText(f"Качество кода: {grade_info['label'].lower()}")
        if hasattr(self, 'grade_score'):
            self.grade_score.setText(f"Оценка {int(round(health_score))} из 100")
        if hasattr(self, 'grade_desc'):
            self.grade_desc.setText(grade_info['summary'])
        if hasattr(self, 'open_folder_btn'):
            self.open_folder_btn.hide()

        # 2. Update Metric cards
        self.metric_widgets['files'].setText(str(len(a.files)))
        self.metric_widgets['lines'].setText(str(metrics.get('lines', sum(f.lines for f in a.files.values()))))
        
        funcs_count = len([s for s in a.symbols if s.kind in {'function', 'method'}])
        classes_count = len([s for s in a.symbols if s.kind in {'class', 'struct', 'interface'}])
        self.metric_widgets['functions'].setText(str(funcs_count))
        self.metric_widgets['classes'].setText(str(classes_count))

        avg_comp = float(metrics.get('average_complexity', 3.0))
        comp_str = "Низкая (легко)" if avg_comp <= 5 else "Средняя (норма)" if avg_comp <= 10 else "Высокая (сложно)"
        self.metric_widgets['complexity'].setText(comp_str)

        if 'todo' in self.metric_widgets:
            health_debt = getattr(a, 'health_debt_items', []) or []
            todo_count = len([d for d in health_debt if d.get('kind') == 'Debt']) or len(getattr(a, 'debt', []))
            self.metric_widgets['todo'].setText(str(todo_count))
            if todo_count > 0:
                self.metric_widgets['todo'].setStyleSheet(
            f'font-size: 16px; font-weight: 600; color: {Palette.WARNING};')

        # 3. Populate Recommendations
        self.student_tips = CodeIntelligenceService.extract_code_recommendations(a)
        self._filter_tips()

        # 4. Populate Structure & Files
        langs = ', '.join(sorted({f.language for f in a.files.values()})) or 'Python'
        self.structure_summary.setText(
            f"В проекте {len(a.files)} файлов ({langs}): {classes_count} классов и {funcs_count} функций.\n"
            f"Двойной щелчок по символу открывает его в редакторе."
        )
        self._populate_structure_tree(a)

        # 5. Populate Impact files dropdown
        self.impact_combo.blockSignals(True)
        self.impact_combo.clear()
        for fpath in sorted(a.files.keys()):
            self.impact_combo.addItem(self._relative(fpath), fpath)
        self.impact_combo.blockSignals(False)

        self.open_graph_button.setEnabled(True)
        self.defense_guide_button.setEnabled(True)

    def _filter_tips(self):
        filter_mode = self.tips_filter.currentText()
        query = self.tips_search.text().strip().lower()

        self.tips_tree.clear()
        sev_colors = {
            'high': Palette.severity('high'),
            'medium': Palette.severity('medium'),
            'low': Palette.severity('low'),
        }

        for tip in self.student_tips:
            cat = tip.get('category', '')
            prio = tip.get('priority', 'low')
            file_path = tip.get('file', '')
            line = tip.get('line', 1)
            title = tip.get('title', '')
            explanation = tip.get('explanation', '')
            action = tip.get('action', '')

            if filter_mode == 'Высокий приоритет' and prio != 'high':
                continue
            elif filter_mode == 'Технический долг (TODO/FIXME)' and 'TODO' not in cat and 'FIXME' not in cat and 'BUG' not in cat:
                continue
            elif filter_mode == 'Слишком длинные функции' and 'длинная' not in cat.lower():
                continue
            elif filter_mode == 'Глубокая вложенность' and 'вложенность' not in cat.lower():
                continue

            if query:
                full_text = f"{cat} {file_path} {title} {explanation}".lower()
                if query not in full_text:
                    continue

            prio_label = "Высокая" if prio == "high" else "Средняя" if prio == "medium" else "Низкая"
            item = QtWidgets.QTreeWidgetItem([
                title,
                prio_label,
                self._relative(file_path),
                str(line),
                action
            ])
            item.setData(0, QtCore.Qt.UserRole, file_path)
            item.setData(1, QtCore.Qt.UserRole, line)
            item.setToolTip(0, explanation)
            item.setToolTip(4, explanation)

            c = QtGui.QColor(sev_colors.get(prio, Palette.TEXT_MUTED))
            item.setForeground(1, QtGui.QBrush(c))
            self.tips_tree.addTopLevelItem(item)

        # Resizing every column for hundreds of rows is itself several hundred
        # milliseconds; fixed widths are cheaper and stable while scrolling.
        self.tips_tree.setColumnWidth(0, 300)
        self.tips_tree.setColumnWidth(1, 80)
        self.tips_tree.setColumnWidth(2, 180)
        self.tips_tree.setColumnWidth(3, 60)

    def _populate_structure_tree(self, a: ProjectAnalysis):
        # Creating a tree item for every symbol froze the panel for seconds on a
        # large project. Only file nodes are built now; a file's symbols are
        # added the first time the node is expanded.
        self.structure_tree.setUpdatesEnabled(False)
        try:
            self.structure_tree.clear()
            symbols_by_file = {}
            for s in a.symbols:
                symbols_by_file.setdefault(s.file, []).append(s)
            self._structure_symbols = symbols_by_file
            self._structure_populated = set()

            top_items = []
            for fpath, finfo in sorted(a.files.items(), key=lambda x: self._relative(x[0])):
                rel_path = self._relative(fpath)
                file_item = QtWidgets.QTreeWidgetItem([rel_path, f"{finfo.language}", rel_path, f"{finfo.lines} стр."])
                file_item.setData(0, QtCore.Qt.UserRole, fpath)
                file_item.setData(1, QtCore.Qt.UserRole, 1)
                count = len(symbols_by_file.get(fpath, []))
                if count:
                    # A disabled item still shows the expander, and gives the
                    # user a placeholder until the children are built.
                    file_item.setChildIndicatorPolicy(
                        QtWidgets.QTreeWidgetItem.ShowIndicator)
                top_items.append(file_item)
            self.structure_tree.addTopLevelItems(top_items)
        finally:
            self.structure_tree.setUpdatesEnabled(True)

    def _populate_file_symbols(self, file_item, max_children: int = 200):
        """Build the symbol children of one file node on demand."""
        if file_item is None:
            return
        fpath = file_item.data(0, QtCore.Qt.UserRole)
        if not fpath or fpath in self._structure_populated:
            return
        self._structure_populated.add(fpath)
        rel_path = self._relative(fpath)
        symbols = sorted(self._structure_symbols.get(fpath, []),
                         key=lambda x: (x.line, x.name))
        children = []
        for s in symbols[:max_children]:
            sym_item = QtWidgets.QTreeWidgetItem([s.name, s.kind, rel_path, str(s.line)])
            sym_item.setData(0, QtCore.Qt.UserRole, s.file)
            sym_item.setData(1, QtCore.Qt.UserRole, s.line)
            children.append(sym_item)
        if symbols:
            file_item.addChildren(children)
        if len(symbols) > max_children:
            file_item.addChild(QtWidgets.QTreeWidgetItem(
                [f"…ещё {len(symbols) - max_children}", "", rel_path, ""]))

    def _on_structure_item_expanded(self, item):
        if item is not None and not item.parent():
            self._populate_file_symbols(item)

    def _filter_structure(self, text):
        query = text.strip().lower()
        for i in range(self.structure_tree.topLevelItemCount()):
            file_item = self.structure_tree.topLevelItem(i)
            match_file = query in file_item.text(0).lower()
            any_child_match = False
            for j in range(file_item.childCount()):
                child = file_item.child(j)
                match_child = query in child.text(0).lower() or query in child.text(1).lower()
                child.setHidden(not (match_child or not query))
                if match_child:
                    any_child_match = True
            file_item.setHidden(not (match_file or any_child_match or not query))
            if any_child_match and query:
                file_item.setExpanded(True)

    def _run_impact_analysis(self):
        if not self.engine:
            return
        path = self.impact_combo.currentData()
        if not path:
            return

        impacted = self.engine.impacted_by(path)
        self.impact_tree.clear()
        file_name = Path(path).name
        if impacted:
            self.impact_status_label.setText(f"При изменении '{file_name}' затронуто {len(impacted)} модуль(ей):")
            self.impact_status_label.setStyleSheet(
                f"color: {Palette.WARNING}; font-weight: 600;")
        else:
            self.impact_status_label.setText(f"Модуль '{file_name}' независим: другие файлы от него не зависят.")
            self.impact_status_label.setStyleSheet(
                f"color: {Palette.OK}; font-weight: 600;")

        for info in impacted:
            item = QtWidgets.QTreeWidgetItem([info.module, self._relative(info.path), f"Сложность: {info.complexity}"])
            item.setData(0, QtCore.Qt.UserRole, info.path)
            item.setData(1, QtCore.Qt.UserRole, 1)
            self.impact_tree.addTopLevelItem(item)

    def _open_graph_editor(self):
        self.open_graph_editor_requested.emit(self.engine, 'modules')

    def _open_defense_guide(self):
        self.open_defense_guide_requested.emit()

    def _relative(self, path):
        # ``Path.resolve()`` on every call is a filesystem round-trip; on a
        # OneDrive project it cost ~2 s while filling the tables. The root is
        # resolved once, and paths coming from the scan are already absolute.
        try:
            root = getattr(self, "_relative_root", None)
            if root is None:
                if self.analysis and self.analysis.root:
                    root = str(Path(self.analysis.root).resolve())
                else:
                    root = ""
                self._relative_root = root
            if root:
                candidate = Path(path)
                try:
                    return str(candidate.relative_to(root))
                except ValueError:
                    return str(Path(path).resolve().relative_to(Path(root)))
        except Exception:
            pass
        return Path(path).name

    def _open_tip_item(self, item, _column):
        path = item.data(0, QtCore.Qt.UserRole)
        line = item.data(1, QtCore.Qt.UserRole)
        if path:
            self.open_file_requested.emit(str(path), int(line or 1))

    def _open_symbol_item(self, item, _column):
        path = item.data(0, QtCore.Qt.UserRole)
        line = item.data(1, QtCore.Qt.UserRole)
        if path:
            self.open_file_requested.emit(str(path), int(line or 1))

    def _open_impact_item(self, item, _column):
        path = item.data(0, QtCore.Qt.UserRole)
        if path:
            self.open_file_requested.emit(str(path), 1)

    def set_impact_file(self, path: Optional[str]):
        if path:
            idx = self.impact_combo.findData(path)
            if idx >= 0:
                self.impact_combo.setCurrentIndex(idx)
            self.tabs.setCurrentWidget(self.impact_scroll)
            self._run_impact_analysis()


ProjectIntelligenceWidget = ProjectIntelligenceDashboard

