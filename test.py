from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Создаем виджет вкладок
        self.tabWidget = QTabWidget()
        self.setCentralWidget(self.tabWidget)

        # Добавляем вкладки
        self.tab1 = QWidget()
        self.tabWidget.addTab(self.tab1, "Вкладка 1")

        self.tab2 = QWidget()
        self.tabWidget.addTab(self.tab2, "Вкладка 2")

        # Устанавливаем стиль для вкладок
        self.tabWidget.setStyleSheet(
            """
            QTabBar::tab {
                width: 100px; /* Ширина вкладок */
                height: 30px; /* Высота вкладок */
                background-color: #ccc; /* Цвет фона вкладок */
                color: #333; /* Цвет текста */
                padding: 5px; /* Отступы внутри вкладок */
                border: 1px solid #999; /* Граница вокруг вкладок */
            }
            QTabBar::tab:selected {
                background-color: #ddd; /* Цвет фона выбранной вкладки */
            }
            """
        )

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
