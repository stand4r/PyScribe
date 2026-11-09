"""Single-instance IPC for PyScribe.

A second launch forwards file/directory arguments to the existing process and exits.
Uses QtLocalServer/QtLocalSocket so no third-party dependency is required.
"""
import json
from pathlib import Path
from PyQt5 import QtCore, QtNetwork


class SingleInstance(QtCore.QObject):
    message_received = QtCore.pyqtSignal(list)

    def __init__(self, name="PyScribe", parent=None):
        super().__init__(parent)
        safe_name = "_".join(ch if ch.isalnum() else "_" for ch in name)
        self.server_name = f"{safe_name}_single_instance_v1"
        self.server = QtNetwork.QLocalServer(self)
        self.server.newConnection.connect(self._on_connection)
        self.is_primary = False

    def acquire(self, arguments=None) -> bool:
        arguments = [str(Path(a).resolve()) for a in (arguments or []) if a]
        socket = QtNetwork.QLocalSocket()
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(350):
            payload = json.dumps(arguments, ensure_ascii=False).encode("utf-8")
            socket.write(payload)
            socket.flush()
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return False

        # A stale local-server name can survive a crash.
        QtNetwork.QLocalServer.removeServer(self.server_name)
        if not self.server.listen(self.server_name):
            # If another process won the race, forward once more.
            socket.connectToServer(self.server_name)
            if socket.waitForConnected(350):
                socket.write(json.dumps(arguments).encode("utf-8"))
                socket.flush()
                socket.waitForBytesWritten(500)
                return False
            return False

        self.is_primary = True
        return True

    def _on_connection(self):
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda s=socket: self._read_socket(s))
        socket.disconnected.connect(socket.deleteLater)

    def _read_socket(self, socket):
        try:
            data = bytes(socket.readAll()).decode("utf-8")
            arguments = json.loads(data) if data else []
            if isinstance(arguments, list):
                self.message_received.emit([str(x) for x in arguments])
        except (ValueError, TypeError):
            pass
