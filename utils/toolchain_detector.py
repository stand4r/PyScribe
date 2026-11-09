"""PyScribe system toolchain detector.

Scans the operating system environment (PATH, common installation paths,
registry/framework directories) to locate compilers and interpreters for all supported
programming languages.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _first_existing(candidates: list[str]) -> Optional[str]:
    """Return the first candidate path that exists as a file or is in PATH."""
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser()
        if p.is_file():
            return str(p.resolve())
        which_path = shutil.which(c)
        if which_path:
            return str(Path(which_path).resolve())
    return None


def detect_all_toolchains() -> Dict[str, Dict[str, Any]]:
    """Scan the system for compilers and interpreters across all supported languages.

    Returns a mapping of language_key -> {
        'name': str,
        'command': str,
        'path': Optional[str],
        'found': bool,
        'kind': 'compiler' | 'interpreter' | 'runtime'
    }
    """
    home = Path.home()
    local_app_data = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")

    definitions = {
        "python": {
            "name": "Python",
            "kind": "interpreter",
            "candidates": [
                sys.executable,
                "python",
                "python3",
                "py",
                str(Path(local_app_data) / "Programs" / "Python" / "Python312" / "python.exe"),
                str(Path(local_app_data) / "Programs" / "Python" / "Python311" / "python.exe"),
            ],
        },
        "javascript": {
            "name": "JavaScript (Node.js)",
            "kind": "runtime",
            "candidates": [
                "node",
                str(Path(program_files) / "nodejs" / "node.exe"),
                str(Path(program_files_x86) / "nodejs" / "node.exe"),
            ],
        },
        "typescript": {
            "name": "TypeScript",
            "kind": "compiler",
            "candidates": [
                "tsc",
                "ts-node",
                str(Path(local_app_data) / "npm" / "tsc.cmd"),
                str(Path(local_app_data) / "npm" / "ts-node.cmd"),
                str(Path(home) / "AppData" / "Roaming" / "npm" / "tsc.cmd"),
            ],
        },
        "c": {
            "name": "C Compiler (GCC/Clang)",
            "kind": "compiler",
            "candidates": [
                "gcc",
                "clang",
                "cl",
                r"C:\msys64\ucrt64\bin\gcc.exe",
                r"C:\msys64\mingw64\bin\gcc.exe",
                r"C:\MinGW\bin\gcc.exe",
                r"C:\TDM-GCC-64\bin\gcc.exe",
            ],
        },
        "cpp": {
            "name": "C++ Compiler (G++/Clang++)",
            "kind": "compiler",
            "candidates": [
                "g++",
                "clang++",
                "cl",
                r"C:\msys64\ucrt64\bin\g++.exe",
                r"C:\msys64\mingw64\bin\g++.exe",
                r"C:\MinGW\bin\g++.exe",
                r"C:\TDM-GCC-64\bin\g++.exe",
            ],
        },
        "csharp": {
            "name": "C# (.NET / Roslyn)",
            "kind": "compiler",
            "candidates": [
                "dotnet",
                str(Path(sys_root) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"),
                str(Path(sys_root) / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe"),
                str(Path(program_files) / "dotnet" / "dotnet.exe"),
                "csc",
            ],
        },
        "go": {
            "name": "Go",
            "kind": "compiler",
            "candidates": [
                "go",
                str(Path(program_files) / "Go" / "bin" / "go.exe"),
                str(Path(home) / "go" / "bin" / "go.exe"),
            ],
        },
        "rust": {
            "name": "Rust (rustc / cargo)",
            "kind": "compiler",
            "candidates": [
                "rustc",
                "cargo",
                str(Path(home) / ".cargo" / "bin" / "rustc.exe"),
                str(Path(home) / ".cargo" / "bin" / "cargo.exe"),
            ],
        },
        "java": {
            "name": "Java (JDK / JRE)",
            "kind": "compiler",
            "candidates": [
                "javac",
                "java",
                str(Path(program_files) / "Common Files" / "Oracle" / "Java" / "javapath" / "javac.exe"),
                str(Path(program_files) / "Common Files" / "Oracle" / "Java" / "javapath" / "java.exe"),
                str(Path(program_files) / "Java" / "jdk-21" / "bin" / "javac.exe"),
                str(Path(program_files) / "Java" / "jdk-17" / "bin" / "javac.exe"),
            ],
        },
        "php": {
            "name": "PHP",
            "kind": "interpreter",
            "candidates": [
                "php",
                r"C:\php\php.exe",
                r"C:\tools\php\php.exe",
            ],
        },
        "ruby": {
            "name": "Ruby",
            "kind": "interpreter",
            "candidates": [
                "ruby",
                r"C:\Ruby32-x64\bin\ruby.exe",
                r"C:\Ruby31-x64\bin\ruby.exe",
            ],
        },
        "lua": {
            "name": "Lua",
            "kind": "interpreter",
            "candidates": [
                "lua",
                "luajit",
            ],
        },
        "shell": {
            "name": "Shell (Bash)",
            "kind": "runtime",
            "candidates": [
                "bash",
                str(Path(program_files) / "Git" / "bin" / "bash.exe"),
                str(Path(program_files) / "Git" / "usr" / "bin" / "bash.exe"),
                str(Path(program_files_x86) / "Git" / "bin" / "bash.exe"),
                str(Path(sys_root) / "System32" / "wsl.exe"),
            ],
        },
    }

    results = {}
    for lang_key, meta in definitions.items():
        found_path = _first_existing(meta["candidates"])
        results[lang_key] = {
            "name": meta["name"],
            "kind": meta["kind"],
            "command": found_path or "",
            "path": found_path,
            "found": found_path is not None,
        }

    return results


def build_run_command_for_file(
    file_path: str,
    args: str = "",
    custom_toolchains: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Build an execution command for the target file.

    Returns (command_string, failure_reason).
    """
    abs_path = os.path.abspath(file_path)
    suffix = os.path.splitext(abs_path)[1].lower()
    quoted_path = f'"{abs_path}"' if os.name == "nt" else f"'{abs_path}'"
    args_str = f" {args}".rstrip() if args else ""

    # Map file extensions to toolchain keys
    ext_map = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".php": "php",
        ".rb": "ruby",
        ".lua": "lua",
        ".sh": "shell",
        ".bash": "shell",
        ".bat": "batch",
        ".cmd": "batch",
    }

    if suffix in (".bat", ".cmd"):
        return f"call {quoted_path}{args_str}".strip(), None

    lang_key = ext_map.get(suffix)
    toolchains = custom_toolchains or {}

    def get_cmd(key: str) -> Optional[str]:
        configured = (toolchains.get(key) or {}).get("command") if isinstance(toolchains.get(key), dict) else toolchains.get(key)
        if configured and str(configured).strip():
            return str(configured).strip()
        detected = detect_all_toolchains().get(key)
        if detected and detected.get("found") and detected.get("path"):
            return detected["path"]
        return None

    if lang_key == "python":
        py_cmd = get_cmd("python") or sys.executable
        return f'"{py_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "javascript":
        node_cmd = get_cmd("javascript") or "node"
        return f'"{node_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "typescript":
        ts_cmd = get_cmd("typescript")
        if ts_cmd and "ts-node" in ts_cmd.lower():
            return f'"{ts_cmd}" {quoted_path}{args_str}'.strip(), None
        # fallback to ts-node or npx ts-node
        if shutil.which("ts-node"):
            return f'ts-node {quoted_path}{args_str}'.strip(), None
        if shutil.which("npx"):
            return f'npx ts-node {quoted_path}{args_str}'.strip(), None
        return f'tsc {quoted_path} && node {os.path.splitext(quoted_path)[0]}.js{args_str}'.strip(), None

    if lang_key == "go":
        go_cmd = get_cmd("go") or "go"
        return f'"{go_cmd}" run {quoted_path}{args_str}'.strip(), None

    if lang_key == "c":
        c_cmd = get_cmd("c") or "gcc"
        exe_path = str(Path(abs_path).with_suffix(".exe" if os.name == "nt" else ""))
        quoted_exe = f'"{exe_path}"' if os.name == "nt" else f"'{exe_path}'"
        return f'"{c_cmd}" {quoted_path} -o {quoted_exe} && {quoted_exe}{args_str}'.strip(), None

    if lang_key == "cpp":
        cpp_cmd = get_cmd("cpp") or "g++"
        exe_path = str(Path(abs_path).with_suffix(".exe" if os.name == "nt" else ""))
        quoted_exe = f'"{exe_path}"' if os.name == "nt" else f"'{exe_path}'"
        return f'"{cpp_cmd}" {quoted_path} -o {quoted_exe} && {quoted_exe}{args_str}'.strip(), None

    if lang_key == "csharp":
        cs_cmd = get_cmd("csharp")
        if cs_cmd and "csc" in cs_cmd.lower():
            exe_path = str(Path(abs_path).with_suffix(".exe"))
            quoted_exe = f'"{exe_path}"'
            return f'"{cs_cmd}" /out:{quoted_exe} {quoted_path} && {quoted_exe}{args_str}'.strip(), None
        dotnet_cmd = cs_cmd or "dotnet"
        return f'"{dotnet_cmd}" run{args_str}'.strip(), None

    if lang_key == "rust":
        rust_cmd = get_cmd("rust")
        if rust_cmd and "cargo" in rust_cmd.lower():
            return f'"{rust_cmd}" run{args_str}'.strip(), None
        rustc_cmd = rust_cmd or "rustc"
        exe_path = str(Path(abs_path).with_suffix(".exe" if os.name == "nt" else ""))
        quoted_exe = f'"{exe_path}"' if os.name == "nt" else f"'{exe_path}'"
        return f'"{rustc_cmd}" {quoted_path} -o {quoted_exe} && {quoted_exe}{args_str}'.strip(), None

    if lang_key == "java":
        java_cmd = get_cmd("java") or "java"
        # Java 11+ directly runs single-source-file programs with `java Source.java`
        return f'"{java_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "php":
        php_cmd = get_cmd("php") or "php"
        return f'"{php_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "ruby":
        rb_cmd = get_cmd("ruby") or "ruby"
        return f'"{rb_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "lua":
        lua_cmd = get_cmd("lua") or "lua"
        return f'"{lua_cmd}" {quoted_path}{args_str}'.strip(), None

    if lang_key == "shell":
        sh_cmd = get_cmd("shell") or "bash"
        return f'"{sh_cmd}" {quoted_path}{args_str}'.strip(), None

    # Generic executable or unknown script
    return f"{quoted_path}{args_str}".strip(), None
