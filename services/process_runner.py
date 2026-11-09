"""Process execution policy. User-supplied arguments are kept as argv, not shell strings."""
import os
import shlex
import sys
from pathlib import Path

from core.subprocess_utils import popen_hidden

class ProcessRunner:
    COMMANDS = {"py": [sys.executable], "js": ["node"], "rb": ["ruby"], "php": ["php"], "lua": ["lua"], "pl": ["perl"], "ts": ["ts-node"]}
    def build(self, file_path, language, args=""):
        path = str(Path(file_path).resolve())
        argv = list(self.COMMANDS.get(language, []))
        if language in {"sh", "bash"}: argv = ["bash"]
        if not argv: return None
        argv.append(path)
        if args:
            argv.extend(shlex.split(args, posix=os.name != "nt"))
        return argv
    def run(self, file_path, language, args="", cwd=None):
        argv = self.build(file_path, language, args)
        if not argv: raise ValueError(f"Unsupported language: {language}")
        return popen_hidden(argv, cwd=str(cwd) if cwd else None, shell=False)
