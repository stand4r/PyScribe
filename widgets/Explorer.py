from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon, QDesktopServices

class Explorer(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super(Explorer, self).__init__(parent=parent)

        self.setHeaderHidden(True)
        self.setColumnWidth(0, 200)
        self.setFixedWidth(300)

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.model.setIconProvider(CustomIconProvider())
        self.setModel(self.model)
        self.setRootIndex(self.model.index(QtCore.QDir.rootPath()))
        self.hide()

        # Скрытие столбцов "Дата изменения" и "Тип"
        self.setColumnHidden(1, True)  # Размер
        self.setColumnHidden(2, True)  # Тип
        self.setColumnHidden(3, True)  # Дата изменения

        self.setStyleSheet(
            """
            QTreeView {
                background-color: #1b1c2e;
                color: #D8DEE9;
                border: none;
                font-size: 14px;
                padding-top: 5px;
                border: 1px solid #2E3440;
                border-right-color: #282C34;
            }
            QTreeView::item {
                height: 30px;
                padding: 2px;
                padding-right: 10px;
            }
            QTreeView::item:hover {
                background-color: #4C566A;
            }
            QTreeView::item:selected {
                background-color: #5E81AC;
                color: #ECEFF4;
            }
        """
        )

        # Контекстное меню
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def go_up(self):
        current_index = self.currentIndex()
        parent_index = self.model.parent(current_index)
        if parent_index.isValid():
            self.collapse(current_index)
            self.setRootIndex(parent_index)
            self.setCurrentIndex(parent_index)



    def open_context_menu(self, position):
        menu = QtWidgets.QMenu()

        open_action = menu.addAction("Open")
        open_action.triggered.connect(self.open_item)

        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copy_item)

        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self.paste_item)

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_item)

        menu.exec_(self.viewport().mapToGlobal(position))

    def open_item(self):
        index = self.currentIndex()
        if not self.model.isDir(index):
            file_path = self.model.filePath(index)
            QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))

    def copy_item(self):
        index = self.currentIndex()
        file_path = self.model.filePath(index)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(file_path)

    def paste_item(self):
        clipboard = QtWidgets.QApplication.clipboard()
        dest_dir = self.model.filePath(self.currentIndex())
        file_path = clipboard.text()
        if QtCore.QFile.exists(file_path):
            file_name = QtCore.QFileInfo(file_path).fileName()
            QtCore.QFile.copy(file_path, QtCore.QDir(dest_dir).filePath(file_name))

    def delete_item(self):
        index = self.currentIndex()
        file_path = self.model.filePath(index)
        if self.model.isDir(index):
            QtCore.QDir(file_path).removeRecursively()
        else:
            QtCore.QFile.remove(file_path)

class CustomIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, type):
        if type == QtWidgets.QFileIconProvider.Folder:
            return QIcon("src/explorer.png")
        return super().icon(type)

#TEST
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("Explorer")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout(self.central_widget)

        self.explorer = Explorer()
        self.layout.addWidget(self.explorer)

        self.nav_bar = QtWidgets.QHBoxLayout()

        self.up_button = QtWidgets.QPushButton("Up")
        self.up_button.clicked.connect(self.explorer.go_up)
        self.nav_bar.addWidget(self.up_button)

        self.layout.addLayout(self.nav_bar)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

