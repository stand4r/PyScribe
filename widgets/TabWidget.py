"""Editor group with compact VS Code-like tabs and cross-group drag/drop."""
from uuid import uuid4
from PyQt5 import QtCore, QtGui, QtWidgets


class EditorTabBar(QtWidgets.QTabBar):
    _drag_sources = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        self.setTabsClosable(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setElideMode(QtCore.Qt.ElideRight)
        self.setUsesScrollButtons(True)
        self._press_pos = None
        self._press_index = -1
        self.setAcceptDrops(True)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # Плавное подсвечивание таба под курсором.
        self._hover_index = -1
        self._hover_intensity = 0.0
        self._hover_anim = None
        self.setMouseTracking(True)

    # -- hover animation ------------------------------------------------
    def mouseMoveEvent(self, event):
        index = self.tabAt(event.pos())
        if index != self._hover_index:
            self._hover_index = index
            self._animate_hover()
        if (self._press_pos is not None and self._press_index >= 0 and
                event.buttons() & QtCore.Qt.LeftButton and
                (event.pos() - self._press_pos).manhattanLength() >= QtWidgets.QApplication.startDragDistance()):
            group = self.parentWidget()
            if isinstance(group, TabWidget):
                token = str(uuid4())
                self._drag_sources[token] = (group, self._press_index)
                mime = QtCore.QMimeData()
                mime.setData('application/x-pyscribe-editor-tab', token.encode('ascii'))
                drag = QtGui.QDrag(self)
                drag.setMimeData(mime)
                drag.exec_(QtCore.Qt.MoveAction)
                self._press_pos = None
                self._press_index = -1
                return
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_index = -1
        self._animate_hover()
        super().leaveEvent(event)

    def _animate_hover(self):
        try:
            from widgets.animations import animate_property, DURATION
        except Exception:
            self.update()
            return
        if self._hover_anim is not None:
            try:
                self._hover_anim.stop()
            except RuntimeError:
                pass
        target = 1.0 if self._hover_index >= 0 else 0.0
        self._hover_anim = animate_property(
            self, b"hoverIntensity", float(self._hover_intensity), target,
            duration=DURATION["fast"], owner=self,
        )

    # Qt property so animations can target it.
    def _get_hover_intensity(self):
        return self._hover_intensity

    def _set_hover_intensity(self, value):
        self._hover_intensity = float(value)
        self.update()

    hoverIntensity = QtCore.pyqtProperty(float, _get_hover_intensity, _set_hover_intensity)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover_intensity <= 0.01 or self._hover_index < 0:
            return
        rect = self.tabRect(self._hover_index)
        if rect.isNull():
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtGui.QColor("#00F2FE")
        color.setAlphaF(0.10 * self._hover_intensity)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect.adjusted(1, 2, -1, -2), 6, 6)
        painter.end()

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        self._press_index = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-pyscribe-editor-tab'):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        raw = bytes(event.mimeData().data('application/x-pyscribe-editor-tab')).decode('ascii', 'ignore')
        source_info = self._drag_sources.pop(raw, None)
        target = self.parentWidget()
        if source_info and isinstance(target, TabWidget):
            source, index = source_info
            source.transfer_tab_to(index, target, self.tabAt(event.pos()))
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
        else:
            event.ignore()


class TabWidget(QtWidgets.QTabWidget):
    groupActivated = QtCore.pyqtSignal(object)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setIconSize(QtCore.QSize(20, 20))
        self.setMovable(False)
        self.setTabsClosable(True)
        self.setAcceptDrops(True)
        self.setTabBar(EditorTabBar(self))
        self.setObjectName("editorGroup")

        self.currentChanged.connect(lambda _index: self.groupActivated.emit(self))
        self.tabBar().installEventFilter(self)

    # Compatibility attributes for older callers; toolbar actions were intentionally removed.
    button_run = None
    button_settings = None
    toggle_button = None

    def _watch_page(self, widget):
        if widget is None:
            return
        widget.installEventFilter(self)
        widget.setAcceptDrops(True)
        for child in widget.findChildren(QtCore.QObject):
            child.installEventFilter(self)
            if isinstance(child, QtWidgets.QWidget):
                child.setAcceptDrops(True)

    def addTab(self, *args):
        index = super().addTab(*args)
        if args:
            self._watch_page(args[0])
        return index

    def insertTab(self, *args):
        index = super().insertTab(*args)
        if args:
            self._watch_page(args[1] if len(args) > 1 and isinstance(args[0], int) else args[0])
        return index

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.FocusIn):
            self.groupActivated.emit(self)
        if event.type() in (QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove):
            if event.mimeData().hasFormat('application/x-pyscribe-editor-tab'):
                event.acceptProposedAction()
                return True
        if event.type() == QtCore.QEvent.Drop and event.mimeData().hasFormat('application/x-pyscribe-editor-tab'):
            raw = bytes(event.mimeData().data('application/x-pyscribe-editor-tab')).decode('ascii', 'ignore')
            source_info = EditorTabBar._drag_sources.pop(raw, None)
            if source_info:
                source, index = source_info
                source.transfer_tab_to(index, self, self.count())
                event.acceptProposedAction()
                return True
        return super().eventFilter(watched, event)

    def focusInEvent(self, event):
        self.groupActivated.emit(self)
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self.groupActivated.emit(self)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-pyscribe-editor-tab'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        raw = bytes(event.mimeData().data('application/x-pyscribe-editor-tab')).decode('ascii', 'ignore')
        source_info = EditorTabBar._drag_sources.pop(raw, None)
        if source_info:
            source, index = source_info
            source.transfer_tab_to(index, self, self.count())
            event.acceptProposedAction()
        else:
            event.ignore()

    def transfer_tab_to(self, index, target, target_index=-1):
        if not (0 <= index < self.count()):
            return
        if target is self:
            if 0 <= target_index < self.count() and target_index != index:
                self.tabBar().moveTab(index, target_index)
            return
        widget = self.widget(index)
        title = self.tabText(index)
        icon = self.tabIcon(index)
        tip = self.tabToolTip(index)
        self.removeTab(index)
        if target_index < 0 or target_index > target.count():
            target_index = target.count()
        new_index = target.insertTab(target_index, widget, icon, title)
        target.setTabToolTip(new_index, tip)
        target.setCurrentIndex(new_index)
        target.groupActivated.emit(target)

    def _request_close(self, index):
        if 0 <= index < self.count():
            self.tabCloseRequested.emit(index)

    def set_project_name(self, project_name):
        return
