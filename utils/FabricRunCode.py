import asyncio
import subprocess
from abc import ABC, abstractmethod
from os import path
from subprocess import PIPE, Popen, check_output, CalledProcessError
from sys import platform
from concurrent.futures import ThreadPoolExecutor
import threading

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
            'gnome-terminal': '--',
            'konsole': '-e',
            'xfce4-terminal': '-e',
            'kitty': '-e',
        }

        for terminal, param in terminals.items():
            try:
                term = check_output(['which', terminal]).decode().strip()
                if terminal == 'gnome-terminal':
                    return f'{term} {param} bash -c "{command}; exec bash"'
                else:
                    return f'{term} {param} bash -c "{command} && read"'
            except (CalledProcessError, FileNotFoundError):
                continue
        return f'xterm -e bash -c "{command} && read"'

class OSXFoundTerminalClass(FabricFoundTerminalClass):
    def get_terminal_command(self, command) -> str:
        return f"osascript -e 'tell app \"Terminal\" to do script \"{command}\"'"

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
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return exe_path
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Compilation failed: {e.stderr}") from e

def compile_program_cpp(path: str) -> str:
    if platform == "win32":
        exe_path = path.rsplit(".", 1)[0] + ".exe"
    elif platform == "linux" or platform == "linux2":
        exe_path = path.rsplit(".", 1)[0] + ".out"
    
    command = ["g++", path, "-o", exe_path]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return exe_path
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Compilation failed: {e.stderr}") from e

class AsyncCodeRunner:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)
    
    async def run_code_async(self, file_path, language, args=""):
        """Асинхронный запуск кода"""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, self._run_code_sync, file_path, language, args
            )
            return result
        except Exception as e:
            return f"Error: {str(e)}"
        
    def run_code_sync(self, file_path, language, args=""):
        """Синхронный запуск кода"""
        return self._run_code_sync(file_path, language, args)
    
    def _run_code_sync(self, file_path, language, args=""):
        """Синхронный запуск кода (выполняется в отдельном потоке)"""
        runner = RunCodeClass(file_path, path.basename(file_path), language, args)
        if runner.command:
            try:
                process = Popen(runner.command, shell=True)
                return f"Process started with PID: {process.pid}"
            except Exception as e:
                return f"Failed to start process: {str(e)}"
        return "No command generated"

class RunCodeClass:
    def __init__(self, pathFile, name, lang, args=""):
        self._path = path.abspath(pathFile)
        self._name = name
        self._args = args
        self.command = ""
        
        lang_commands = {
            "py": f"python {self._path} {args}",
            "rb": f"ruby {self._path} {args}",
            "js": f"node {self._path} {args}",
            "php": f"php {self._path} {args}",
            "lua": f"lua {self._path} {args}",
            "pl": f"perl {self._path} {args}",
            "sh": f"bash {self._path} {args}",
        }
        
        if lang in lang_commands:
            self.command = choice_env(lang_commands[lang])
        elif lang == "c":
            try:
                exe = compile_program_c(self._path)
                self.command = choice_env(f"{exe} {args}")
            except ValueError as e:
                raise e
        elif lang == "cpp":
            try:
                exe = compile_program_cpp(self._path)
                self.command = choice_env(f"{exe} {args}")
            except ValueError as e:
                raise e
        elif lang == "java":
            # Компиляция и запуск Java
            class_dir = path.dirname(self._path)
            class_name = path.basename(self._path).replace('.java', '')
            compile_cmd = f"javac {self._path}"
            run_cmd = f"java -cp {class_dir} {class_name} {args}"
            self.command = choice_env(f"{compile_cmd} && {run_cmd}")
        else:
            self.command = None

    def process(self):
        if self.command:
            Popen(self.command, shell=True)

# Глобальный экземпляр асинхронного раннера
FabricRunCode = AsyncCodeRunner()