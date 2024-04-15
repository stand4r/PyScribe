from abc import ABC, abstractmethod
from os import path
from subprocess import PIPE, Popen, check_output, CalledProcessError
from sys import platform


class FabricFoundTerminalClass(ABC):
    @abstractmethod
    def get_terminal_command(self, command):
        pass


class WindowsFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        return f'start cmd /k "{command}"'


class LinuxFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        terminals = {
            'alacritty': '-e',
            'xterm': '-e',
            'gnome-terminal': '--command',
            'konsole': '-e',
            'xfce4-terminal': '-e',
            'kitty': '-e',
        }

        for terminal, param in terminals.items():
            try:
                term = str(check_output(['which', terminal]))
                return f'{term} {param} bash -c "{command} && read"'
            except CalledProcessError:
                pass
        return None


class OSXFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        return " "


def choice_env(command):
    if platform == "win32":
        return WindowsFoundTerminalClass().get_terminal_command(command)
    elif platform == "linux" or platform == "linux2":
        return LinuxFoundTerminalClass().get_terminal_command(command)
    elif platform == "darwin":
        return OSXFoundTerminalClass().get_terminal_command(command)
    else:
        return ""


def compile_program_c(path: str) -> str:
    if platform == "win32":
        exe_path = path.rsplit(".", 1)[0] + ".exe"
    elif platform == "linux" or platform == "linux2":
        exe_path = path.rsplit(".", 1)[0] + ".out"
    command = ["gcc", path, "-o", exe_path]
    print(*command)

    compile_process = Popen(command, stderr=PIPE, stdout=PIPE, universal_newlines=True, shell=True)
    stdout, stderr = compile_process.communicate()
    if compile_process.returncode != 0:
        raise ValueError(f"Compilation completed with error {compile_process.returncode}")
    else:
        return exe_path


def compile_program_cpp(path: str) -> str:
    if platform == "win32":
        exe_path = path.rsplit(".", 1)[0] + ".exe"
    elif platform == "linux" or platform == "linux2":
        exe_path = path.rsplit(".", 1)[0] + ".out"
    command = ["g++", path, "-o", exe_path]

    compile_process = Popen(command, stderr=PIPE, stdout=PIPE, universal_newlines=True)
    if compile_process.returncode != 0:
        raise ValueError(f"Compilation completed with error {compile_process.returncode}")
    else:
        return exe_path


class RunCodeClass:
    def __init__(self, pathFile, name, lang, args=""):
        self._path = path.abspath(pathFile)
        self._name = name
        self._args = args
        self.command = ""
        if lang == "rb":
            self.command = choice_env(rf"python {self._path}")
        if lang == "rb":
            try:
                exe = compile_program_c(self._path)
                self.command = choice_env(exe)
            except ValueError:
                raise ValueError
        if lang == "rb":
            try:
                exe = compile_program_cpp(self._path)
                self.command = choice_env(exe)
            except ValueError:
                raise ValueError
        if lang == "rb":
            self.command = choice_env(rf"ruby {self._path}")
        else:
            self.command = None

    def process(self):
        Popen(self.command, shell=True)
