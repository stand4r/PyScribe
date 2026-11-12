"""Extensible Language Analysis Registry for PyScribe.

Defines multi-language configurations covering:
- File extensions & detection
- Tree-sitter grammar specifications
- LSP server discovery, configuration and capabilities
- Toolchain integration and installation hints
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class AnalysisLevel(IntEnum):
    """Levels of code intelligence available for a file or language."""
    TEXT = 1       # Base text matching, token regexes, no parser
    SYNTAX = 2     # Tree-sitter AST, tolerant to incomplete code, symbols & outline
    SEMANTIC = 3   # Full LSP server / semantic toolchain, diagnostics & references


@dataclass
class LanguageSpec:
    """Specification describing analysis capabilities for a language."""
    id: str
    display_name: str
    extensions: Tuple[str, ...]
    tree_sitter_module: str
    symbol_node_types: Dict[str, str] = field(default_factory=dict)
    lsp_candidates: List[str] = field(default_factory=list)
    lsp_args: List[str] = field(default_factory=list)
    lsp_capabilities: Set[str] = field(default_factory=lambda: {"definition", "references", "diagnostics", "documentSymbol"})
    toolchain_key: str = ""
    install_hint: str = ""
    shebang_patterns: Tuple[str, ...] = ()
    filename_patterns: Tuple[str, ...] = ()


class LanguageRegistry:
    """Central registry of language specifications with toolchain discovery."""

    def __init__(self):
        self._specs: Dict[str, LanguageSpec] = {}
        self._ext_map: Dict[str, str] = {}
        self._filename_map: Dict[str, str] = {}
        self._register_builtins()

    def register(self, spec: LanguageSpec) -> None:
        """Register or override a language specification."""
        self._specs[spec.id] = spec
        for ext in spec.extensions:
            self._ext_map[ext.lower()] = spec.id
        for fn in spec.filename_patterns:
            self._filename_map[fn.lower()] = spec.id

    def get_by_id(self, lang_id: str) -> Optional[LanguageSpec]:
        return self._specs.get(lang_id)

    def get(self, lang_id: str, default: Optional[LanguageSpec] = None) -> Optional[LanguageSpec]:
        """Dict-like accessor for language spec by id."""
        return self._specs.get(lang_id, default)

    def get_by_path(self, path: Path | str) -> Optional[LanguageSpec]:
        p = Path(path)
        name_lower = p.name.lower()
        if name_lower in self._filename_map:
            return self._specs.get(self._filename_map[name_lower])

        suffix = p.suffix.lower()
        if suffix in self._ext_map:
            return self._specs.get(self._ext_map[suffix])

        # Check multi-suffix like .d.ts or .tar.gz
        suffixes = "".join(p.suffixes).lower()
        if suffixes in self._ext_map:
            return self._specs.get(self._ext_map[suffixes])

        return None

    def detect_language(self, path: Path | str, content: Optional[str] = None) -> Tuple[str, str]:
        """Return (lang_id, display_name) for a file or fallback to text."""
        spec = self.get_by_path(path)
        if spec:
            return spec.id, spec.display_name

        if content:
            first_line = content.splitlines()[0] if content.splitlines() else ""
            if first_line.startswith("#!"):
                for s in self._specs.values():
                    for pat in s.shebang_patterns:
                        if pat in first_line:
                            return s.id, s.display_name

        return "plaintext", "Текстовый файл"

    def resolve_lsp_server(self, spec: LanguageSpec, configured_path: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        """Find executable LSP server path and arguments.

        Settings override has highest priority, followed by toolchain detection,
        then system PATH and common installation paths.
        """
        # 1. Configured custom path from settings
        if configured_path and str(configured_path).strip():
            candidate = Path(str(configured_path).strip().strip('"')).expanduser()
            if candidate.is_file():
                return str(candidate.resolve()), list(spec.lsp_args)
            which_p = shutil.which(str(candidate))
            if which_p:
                return str(Path(which_p).resolve()), list(spec.lsp_args)
            # Explicit path from settings has highest priority
            return str(candidate), list(spec.lsp_args)

        # 2. Candidate commands across PATH and common environments
        for cmd in spec.lsp_candidates:
            # Check PATH
            which_p = shutil.which(cmd)
            if which_p:
                return str(Path(which_p).resolve()), list(spec.lsp_args)

            # On Windows check npm roaming, local python scripts, go bin, cargo bin
            home = Path.home()
            local_app = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
            roaming = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))

            possible_paths = [
                # Python scripts
                Path(sys.executable).parent / "Scripts" / f"{cmd}.exe",
                Path(sys.executable).parent / "Scripts" / cmd,
                Path(local_app) / "Python" / "pythoncore-3.14-64" / "Scripts" / f"{cmd}.exe",
                # Node / npm global
                Path(roaming) / "npm" / f"{cmd}.cmd",
                Path(roaming) / "npm" / f"{cmd}.ps1",
                Path(roaming) / "npm" / cmd,
                # Go binaries
                home / "go" / "bin" / f"{cmd}.exe",
                home / "go" / "bin" / cmd,
                # Rust cargo binaries
                home / ".cargo" / "bin" / f"{cmd}.exe",
                home / ".cargo" / "bin" / cmd,
                # LLVM / clangd
                Path(r"C:\Program Files\LLVM\bin") / f"{cmd}.exe",
                Path(r"C:\Program Files (x86)\LLVM\bin") / f"{cmd}.exe",
            ]

            for p in possible_paths:
                if p.is_file():
                    return str(p.resolve()), list(spec.lsp_args)

        return None, []

    def all_specs(self) -> List[LanguageSpec]:
        return list(self._specs.values())

    def _register_builtins(self):
        """Register the comprehensive set of supported languages."""
        # 1. Python
        self.register(LanguageSpec(
            id="python",
            display_name="Python",
            extensions=(".py", ".pyw", ".pyi"),
            tree_sitter_module="tree_sitter_python",
            symbol_node_types={
                "function_definition": "function",
                "class_definition": "class",
                "import_statement": "import",
                "import_from_statement": "import",
                "call": "call",
            },
            lsp_candidates=["pylsp", "pyright-langserver", "pyright", "jedi-language-server"],
            lsp_args=[],
            toolchain_key="python",
            install_hint="Установите python-lsp-server (`pip install python-lsp-server`) или pyright (`npm i -g pyright`).",
            shebang_patterns=("python", "python3"),
        ))

        # 2. JavaScript
        self.register(LanguageSpec(
            id="javascript",
            display_name="JavaScript",
            extensions=(".js", ".jsx", ".mjs", ".cjs"),
            tree_sitter_module="tree_sitter_javascript",
            symbol_node_types={
                "function_declaration": "function",
                "function_expression": "function",
                "arrow_function": "function",
                "method_definition": "method",
                "class_declaration": "class",
                "import_statement": "import",
                "call_expression": "call",
            },
            lsp_candidates=["typescript-language-server", "vtsls", "deno"],
            lsp_args=["--stdio"],
            toolchain_key="javascript",
            install_hint="Установите typescript-language-server (`npm install -g typescript-language-server typescript`).",
            shebang_patterns=("node", "deno", "bun"),
        ))

        # 3. TypeScript
        self.register(LanguageSpec(
            id="typescript",
            display_name="TypeScript",
            extensions=(".ts", ".tsx", ".d.ts"),
            tree_sitter_module="tree_sitter_typescript",
            symbol_node_types={
                "function_declaration": "function",
                "arrow_function": "function",
                "method_definition": "method",
                "class_declaration": "class",
                "interface_declaration": "interface",
                "type_alias_declaration": "type",
                "enum_declaration": "enum",
                "import_statement": "import",
                "call_expression": "call",
            },
            lsp_candidates=["typescript-language-server", "vtsls", "deno"],
            lsp_args=["--stdio"],
            toolchain_key="typescript",
            install_hint="Установите typescript-language-server (`npm install -g typescript-language-server typescript`).",
            shebang_patterns=("ts-node", "deno", "bun"),
        ))

        # 4. C
        self.register(LanguageSpec(
            id="c",
            display_name="C",
            extensions=(".c", ".h"),
            tree_sitter_module="tree_sitter_c",
            symbol_node_types={
                "function_definition": "function",
                "function_declarator": "function",
                "struct_specifier": "struct",
                "enum_specifier": "enum",
                "type_definition": "type",
                "preproc_include": "import",
                "call_expression": "call",
            },
            lsp_candidates=["clangd", "ccls"],
            lsp_args=[],
            toolchain_key="c",
            install_hint="Установите LLVM / clangd (https://github.com/clangd/clangd/releases).",
        ))

        # 5. C++
        self.register(LanguageSpec(
            id="cpp",
            display_name="C++",
            extensions=(".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"),
            tree_sitter_module="tree_sitter_cpp",
            symbol_node_types={
                "function_definition": "function",
                "class_specifier": "class",
                "struct_specifier": "struct",
                "enum_specifier": "enum",
                "namespace_definition": "namespace",
                "preproc_include": "import",
                "call_expression": "call",
            },
            lsp_candidates=["clangd", "ccls"],
            lsp_args=[],
            toolchain_key="cpp",
            install_hint="Установите LLVM / clangd (https://github.com/clangd/clangd/releases).",
        ))

        # 6. C#
        self.register(LanguageSpec(
            id="c_sharp",
            display_name="C#",
            extensions=(".cs",),
            tree_sitter_module="tree_sitter_c_sharp",
            symbol_node_types={
                "class_declaration": "class",
                "struct_declaration": "struct",
                "interface_declaration": "interface",
                "enum_declaration": "enum",
                "method_declaration": "method",
                "constructor_declaration": "constructor",
                "property_declaration": "property",
                "using_directive": "import",
                "invocation_expression": "call",
            },
            lsp_candidates=["csharp-ls", "OmniSharp", "omnisharp"],
            lsp_args=[],
            toolchain_key="csharp",
            install_hint="Установите csharp-ls (`dotnet tool install -g csharp-ls`) или OmniSharp.",
        ))

        # 7. Java
        self.register(LanguageSpec(
            id="java",
            display_name="Java",
            extensions=(".java",),
            tree_sitter_module="tree_sitter_java",
            symbol_node_types={
                "class_declaration": "class",
                "interface_declaration": "interface",
                "enum_declaration": "enum",
                "method_declaration": "method",
                "constructor_declaration": "constructor",
                "import_declaration": "import",
                "method_invocation": "call",
            },
            lsp_candidates=["jdtls", "java-language-server"],
            lsp_args=[],
            toolchain_key="java",
            install_hint="Установите Eclipse JDT Language Server (jdtls).",
        ))

        # 8. Go
        self.register(LanguageSpec(
            id="go",
            display_name="Go",
            extensions=(".go",),
            tree_sitter_module="tree_sitter_go",
            symbol_node_types={
                "function_declaration": "function",
                "method_declaration": "method",
                "type_declaration": "type",
                "import_declaration": "import",
                "call_expression": "call",
            },
            lsp_candidates=["gopls"],
            lsp_args=[],
            toolchain_key="go",
            install_hint="Установите gopls (`go install golang.org/x/tools/gopls@latest`).",
        ))

        # 9. Rust
        self.register(LanguageSpec(
            id="rust",
            display_name="Rust",
            extensions=(".rs",),
            tree_sitter_module="tree_sitter_rust",
            symbol_node_types={
                "function_item": "function",
                "struct_item": "struct",
                "enum_item": "enum",
                "trait_item": "interface",
                "impl_item": "class",
                "use_declaration": "import",
                "call_expression": "call",
            },
            lsp_candidates=["rust-analyzer"],
            lsp_args=[],
            toolchain_key="rust",
            install_hint="Установите rust-analyzer (`rustup component add rust-analyzer`).",
        ))

        # 10. JSON (for OpenAPI / specs / config)
        self.register(LanguageSpec(
            id="json",
            display_name="JSON",
            extensions=(".json", ".jsonc"),
            tree_sitter_module="tree_sitter_json",
            symbol_node_types={
                "pair": "property",
            },
            lsp_candidates=["vscode-json-language-server"],
            lsp_args=["--stdio"],
            toolchain_key="json",
            install_hint="",
        ))


_GLOBAL_REGISTRY: Optional[LanguageRegistry] = None


def get_language_registry() -> LanguageRegistry:
    """Singleton getter for the global language registry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = LanguageRegistry()
    return _GLOBAL_REGISTRY
