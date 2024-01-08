from PyQt5 import QtCore, QtGui, QtWidgets
from sys import argv
import time


class QSplashScreen(QtWidgets.QWidget):
    def setupUi(self):
        self.setObjectName("Form")
        self.setFixedSize(600, 300)
        self.setWindowTitle("")
        self.setWindowOpacity(0.5)
        self.setStyleSheet("background-color: #eff5f5;")
        self.label = QtWidgets.QLabel(self)
        self.label.setGeometry(QtCore.QRect(200, 0, 200, 200))
        self.label.setText("")
        self.label.setPixmap(QtGui.QPixmap("src/logo.jpg"))
        self.label.setScaledContents(True)
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self)
        self.label_2.setGeometry(QtCore.QRect(40, 220, 221, 31))
        font = QtGui.QFont()
        font.setPointSize(20)
        self.label_2.setFont(font)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setGeometry(QtCore.QRect(250, 220, 261, 23))
        self.progressBar.setProperty("value", 0)
        self.progressBar.setTextVisible(False)
        self.progressBar.setInvertedAppearance(False)
        self.progressBar.setTextDirection(QtWidgets.QProgressBar.BottomToTop)
        self.progressBar.setFormat("")
        self.progressBar.setObjectName("progressBar")
        self.timer = QtCore.QTimer()        
        self.timer.timeout.connect(self.handleTimer)
        self.timer.start(25)
        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def handleTimer(self):
        value = self.progressBar.value()
        if value < 100:
            value = value + 1
            self.progressBar.setValue(value)
        else:
            self.timer.stop()

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.label_2.setText(_translate("Form", "Loading"))

if __name__ == "__main__":
    app = QtWidgets.QApplication(argv)
    MainWindow = QSplashScreen()
    MainWindow.setupUi()
    MainWindow.show()
    exit(app.exec_())