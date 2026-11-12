"""Level 2: Tree-sitter AST Syntax Engine for PyScribe.

Provides:
- In-memory parsing tolerant to syntax errors and incomplete code.
- Extraction of symbols (functions, methods, classes, structs, interfaces, enums, types).
- Import statement discovery and call expression tracking.
- Fallback regex symbol extractor when grammars are missing.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


@dataclass
class AnalyzedSymbol:
    """Represents a symbol discovered in source code."""
    name: str
    kind: str  # function, method, class, struct, interface, enum, type, import
    line: int  # 1-based start line
    col: int   # 0-based start col
    end_line: int
    end_col: int
    parent: Optional[str] = None
    signature: str = ""
    docstring: str = ""
    file_path: str = ""

    @property
    def parent_name(self) -> Optional[str]:
        return self.parent


@dataclass
class SyntaxParseResult:
    """Result of AST/syntax analysis for a file buffer."""
    lang_id: str
    symbols: List[AnalyzedSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    calls: List[Tuple[str, int, int]] = field(default_factory=list)  # (call_name, line, col)
    syntax_errors: List[Tuple[int, str]] = field(default_factory=list)  # (line, message)
    is_tree_sitter: bool = False


class TreeSitterEngine:
    """Manages grammar loading, parsing and symbol extraction."""

    def __init__(self):
        self._parsers: Dict[str, Any] = {}
        self._languages: Dict[str, Any] = {}

    def _get_parser(self, lang_id: str) -> Optional[Any]:
        if not TREE_SITTER_AVAILABLE:
            return None

        if lang_id in self._parsers:
            return self._parsers[lang_id]

        ts_lang = self._load_language(lang_id)
        if ts_lang is None:
            return None

        try:
            parser = Parser(ts_lang)
            self._parsers[lang_id] = parser
            return parser
        except Exception as exc:
            logger.warning("Failed to construct tree-sitter parser for %s: %s", lang_id, exc)
            return None

    def _load_language(self, lang_id: str) -> Optional[Any]:
        if lang_id in self._languages:
            return self._languages[lang_id]

        lang_obj = None
        try:
            if lang_id == "python":
                import tree_sitter_python
                lang_obj = Language(tree_sitter_python.language())
            elif lang_id == "javascript":
                import tree_sitter_javascript
                lang_obj = Language(tree_sitter_javascript.language())
            elif lang_id == "typescript":
                import tree_sitter_typescript
                lang_obj = Language(tree_sitter_typescript.language_typescript())
            elif lang_id in ("tsx", "jsx"):
                import tree_sitter_typescript
                lang_obj = Language(tree_sitter_typescript.language_tsx())
            elif lang_id == "c":
                import tree_sitter_c
                lang_obj = Language(tree_sitter_c.language())
            elif lang_id == "cpp":
                import tree_sitter_cpp
                lang_obj = Language(tree_sitter_cpp.language())
            elif lang_id in ("c_sharp", "csharp", "cs"):
                import tree_sitter_c_sharp
                lang_obj = Language(tree_sitter_c_sharp.language())
            elif lang_id == "java":
                import tree_sitter_java
                lang_obj = Language(tree_sitter_java.language())
            elif lang_id == "go":
                import tree_sitter_go
                lang_obj = Language(tree_sitter_go.language())
            elif lang_id == "rust":
                import tree_sitter_rust
                lang_obj = Language(tree_sitter_rust.language())
            elif lang_id == "json":
                import tree_sitter_json
                lang_obj = Language(tree_sitter_json.language())
        except Exception as exc:
            logger.debug("Tree-sitter grammar import failed for %s: %s", lang_id, exc)
            return None

        if lang_obj is not None:
            self._languages[lang_id] = lang_obj
        return lang_obj

    def parse(self, code: str, lang_id: str, file_path: str = "") -> SyntaxParseResult:
        """Parse source code in memory and extract symbols, imports, and calls."""
        parser = self._get_parser(lang_id)
        if parser is None:
            return self._fallback_parse(code, lang_id, file_path)

        try:
            source_bytes = code.encode("utf-8", errors="replace")
            tree = parser.parse(source_bytes)
            root = tree.root_node

            result = SyntaxParseResult(lang_id=lang_id, is_tree_sitter=True)
            self._walk_node(root, source_bytes, result, file_path=file_path, parent_name=None)
            return result
        except Exception as exc:
            logger.warning("Tree-sitter parse error for %s (%s): %s", file_path, lang_id, exc)
            return self._fallback_parse(code, lang_id, file_path)

    def _walk_node(
        self,
        node: Any,
        source: bytes,
        result: SyntaxParseResult,
        file_path: str = "",
        parent_name: Optional[str] = None
    ) -> None:
        """Recursively walk tree-sitter AST nodes."""
        node_type = node.type

        # Check for syntax error markers
        if node.is_error or node_type == "ERROR":
            line = node.start_point[0] + 1
            result.syntax_errors.append((line, f"Синтаксическая ошибка на строке {line}"))

        # Function declarations
        if node_type in (
            "function_definition", "function_declaration", "method_declaration",
            "method_definition", "function_item", "arrow_function", "constructor_declaration"
        ):
            name = self._extract_node_name(node, source)
            kind = "method" if parent_name else "function"
            if node_type == "constructor_declaration":
                kind = "constructor"

            if name:
                if "::" in name:
                    parent_part, name = name.rsplit("::", 1)
                    parent_name = parent_name or parent_part
                    kind = "method"
                start_l, start_c = node.start_point[0] + 1, node.start_point[1]
                end_l, end_c = node.end_point[0] + 1, node.end_point[1]
                sig = self._extract_first_line(node, source)
                sym = AnalyzedSymbol(
                    name=name, kind=kind, line=start_l, col=start_c,
                    end_line=end_l, end_col=end_c, parent=parent_name,
                    signature=sig, file_path=file_path
                )
                result.symbols.append(sym)
                parent_name = name

        # Class / Struct / Interface / Enum declarations
        elif node_type in (
            "class_definition", "class_declaration", "class_specifier",
            "struct_specifier", "struct_item", "struct_declaration",
            "interface_declaration", "trait_item", "enum_declaration",
            "enum_specifier", "enum_item", "type_declaration", "type_alias_declaration",
            "type_spec"
        ):
            name = self._extract_node_name(node, source)
            kind = "class"
            type_child = node.child_by_field_name("type")
            type_str = type_child.type if type_child else ""
            if "struct" in node_type or "struct" in type_str:
                kind = "struct"
            elif "interface" in node_type or "trait" in node_type or "interface" in type_str:
                kind = "interface"
            elif "enum" in node_type or "enum" in type_str:
                kind = "enum"
            elif "type" in node_type:
                kind = "type"

            if name:
                start_l, start_c = node.start_point[0] + 1, node.start_point[1]
                end_l, end_c = node.end_point[0] + 1, node.end_point[1]
                sig = self._extract_first_line(node, source)
                sym = AnalyzedSymbol(
                    name=name, kind=kind, line=start_l, col=start_c,
                    end_line=end_l, end_col=end_c, parent=parent_name,
                    signature=sig, file_path=file_path
                )
                result.symbols.append(sym)
                parent_name = name

        # Imports
        elif node_type in (
            "import_statement", "import_from_statement", "import_declaration",
            "using_directive", "use_declaration", "preproc_include", "package_clause"
        ):
            text = self._node_text(node, source)
            result.imports.append(text)

        # Calls
        elif node_type in ("call", "call_expression", "method_invocation", "invocation_expression"):
            call_name = self._extract_call_name(node, source)
            if call_name:
                line, col = node.start_point[0] + 1, node.start_point[1]
                result.calls.append((call_name, line, col))

        # Recurse children
        for child in node.children:
            self._walk_node(child, source, result, file_path=file_path, parent_name=parent_name)

    def _extract_node_name(self, node: Any, source: bytes) -> Optional[str]:
        """Extract declared symbol name from child nodes or field."""
        # Try tree-sitter field name
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._node_text(name_node, source)

        # Try declarator child
        decl = node.child_by_field_name("declarator")
        if decl:
            inner_name = decl.child_by_field_name("declarator") or decl.child_by_field_name("name") or decl
            return self._node_text(inner_name, source)

        # Scan for identifier child
        for c in node.children:
            if c.type in ("identifier", "type_identifier", "property_identifier", "field_identifier", "name"):
                return self._node_text(c, source)

        return None

    def _extract_call_name(self, node: Any, source: bytes) -> Optional[str]:
        fn_node = node.child_by_field_name("function") or node.child_by_field_name("expression")
        if not fn_node and node.children:
            fn_node = node.children[0]
        if fn_node:
            text = self._node_text(fn_node, source)
            # If member access (obj.method), take full or last
            return text.strip()
        return None

    def _node_text(self, node: Any, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()

    def _extract_first_line(self, node: Any, source: bytes) -> str:
        text = self._node_text(node, source)
        return text.splitlines()[0] if text else ""

    def _fallback_parse(self, code: str, lang_id: str, file_path: str = "") -> SyntaxParseResult:
        """Conservative regex extraction fallback for symbols and calls."""
        result = SyntaxParseResult(lang_id=lang_id, is_tree_sitter=False)
        lines = code.splitlines()

        patterns = [
            (r"\bclass\s+([A-Za-z_]\w*)", "class"),
            (r"\b(?:interface|trait)\s+([A-Za-z_]\w*)", "interface"),
            (r"\bstruct\s+([A-Za-z_]\w*)", "struct"),
            (r"\benum\s+([A-Za-z_]\w*)", "enum"),
            (r"\btype\s+([A-Za-z_]\w*)", "type"),
            (r"\b(?:def|func|fn|function|fun)\s+([A-Za-z_]\w*)", "function"),
            (r"\b([A-Za-z_]\w*)\s*=\s*(?:function|\([^\n]*\)\s*=>)", "function"),
        ]

        current_class = None
        for idx, line in enumerate(lines):
            line_num = idx + 1
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*")):
                continue

            for pat, kind in patterns:
                m = re.search(pat, line)
                if m:
                    sym_name = m.group(1)
                    if kind in ("class", "struct", "interface", "enum"):
                        current_class = sym_name
                        parent = None
                    else:
                        parent = current_class
                        if parent:
                            kind = "method"

                    col = m.start(1)
                    sym = AnalyzedSymbol(
                        name=sym_name, kind=kind, line=line_num, col=col,
                        end_line=line_num + 5, end_col=col + len(sym_name),
                        parent=parent, signature=stripped, file_path=file_path
                    )
                    result.symbols.append(sym)
                    break

            # Imports
            if re.match(r"^\s*(?:import|from|using|#include|package)\b", line):
                result.imports.append(stripped)

            # Calls
            for call_m in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", line):
                cname = call_m.group(1)
                if cname not in ("if", "for", "while", "switch", "catch", "return"):
                    result.calls.append((cname, line_num, call_m.start(1)))

        return result


_GLOBAL_TREESITTER: Optional[TreeSitterEngine] = None


def get_treesitter_engine() -> TreeSitterEngine:
    global _GLOBAL_TREESITTER
    if _GLOBAL_TREESITTER is None:
        _GLOBAL_TREESITTER = TreeSitterEngine()
    return _GLOBAL_TREESITTER
