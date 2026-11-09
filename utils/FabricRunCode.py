"""Safe process runner compatibility layer.

The editor executes programs through the integrated terminal. This module is kept
for older callers, but never invokes a command through a shell.
"""
import os
import shlex
import sys
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from core.subprocess_utils import popen_hidden, run_hidden


def safe_path(file_path):
    return str(Path(file_path).resolve())


def _args(value):
    if not value:
        return []
    return shlex.split(str(value), posix=(os.name != "nt"))


def _build(file_path, language, args=""):
    path = safe_path(file_path)
    runners = {
        "py": [sys.executable], "python": [sys.executable], "rb": ["ruby"],
        "js": ["node"], "php": ["php"], "lua": ["lua"], "pl": ["perl"],
        "ts": ["ts-node"], "sh": ["bash"], "bash": ["bash"],
    }
    if language not in runners:
        return None
    return runners[language] + [path] + _args(args)


def compile_program_c(file_path):
    path = safe_path(file_path)
    exe = str(Path(path).with_suffix(".exe" if os.name == "nt" else ".out"))
    run_hidden(["gcc", path, "-o", exe], check=True, capture_output=True, text=True, shell=False)
    return exe


def compile_program_cpp(file_path):
    path = safe_path(file_path)
    exe = str(Path(path).with_suffix(".exe" if os.name == "nt" else ".out"))
    run_hidden(["g++", path, "-o", exe], check=True, capture_output=True, text=True, shell=False)
    return exe


class RunCodeClass:
    def __init__(self, pathFile, name=None, lang="py", args=""):
        self._path = safe_path(pathFile)
        self._args = args
        self.argv = _build(self._path, lang, args)
        self.command = self.argv  # compatibility: command is now argv, never a shell string

    def process(self, cwd=None):
        if not self.argv:
            return None
        return popen_hidden(self.argv, cwd=cwd, shell=False)


class AsyncCodeRunner:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)

    async def run_code_async(self, file_path, language, args=""):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.run_code_sync, file_path, language, args)

    def run_code_sync(self, file_path, language, args=""):
        runner = RunCodeClass(file_path, Path(file_path).name, language, args)
        if not runner.argv:
            return "Unsupported language"
        process = runner.process(cwd=str(Path(file_path).parent))
        return f"Process started with PID: {process.pid}"


FabricRunCode = AsyncCodeRunner()
