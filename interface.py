from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QTextCursor, QFont, QIcon
from subprocess import PIPE, Popen
from os import path, remove
from QCodeEditor import CodeTextEdit
from basicInterface import Ui_MainWindow



class UiMainWindow(Ui_MainWindow):
    def setupUiCustom(self, MainWindow):
        self.setupUi(MainWindow)
        
        scriptDir = path.dirname(path.realpath(__file__))
        MainWindow.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png')) 
        self.actionRun.triggered.connect(self.actionRunCode)
       

    def actionRunCode(self):
        self.ResultText.setPlainText("")
        self.ResultText.insertPlainText("~> run output.py\n")
        open("output.py", "w").write(self.CodeEdit.toPlainText())
        process = Popen("python output.py", shell=True, stderr=PIPE, stdout=PIPE, text=True)
        while True:
            output = process.stdout.readline()
            error = process.stderr.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                self.ResultText.insertPlainText(output)
            if error:
                self.ResultText.insertPlainText(+error)
        remove("output.py")


if __name__ == "__main__":
    import sys
    scriptDir = path.dirname(path.realpath(__file__))
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QIcon(scriptDir+path.sep+'src/icon2.png'))
    MainWindow = QtWidgets.QMainWindow()
    ui = UiMainWindow()
    ui.setupUiCustom(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())