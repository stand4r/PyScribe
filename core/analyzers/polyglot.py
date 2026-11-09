"""PyScribe core/analyzers/polyglot.py: application module and reusable component."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.project_intelligence import Issue, StructureEdge, StructureNode, SymbolInfo


LANGUAGE_BY_EXT = {
    ".py": "python", ".pyw": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".java": "java", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp", ".go": "go", ".rs": "rust",
    ".cs": "c_sharp", ".php": "php", ".rb": "ruby", ".swift": "swift", ".kt": "kotlin",
    ".kts": "kotlin", ".scala": "scala", ".dart": "dart", ".lua": "lua", ".sh": "bash",
    ".bash": "bash", ".zsh": "bash", ".sql": "sql", ".r": "r", ".R": "r", ".fs": "fsharp", ".fsx": "fsharp", ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".hrl": "erlang", ".hs": "haskell", ".lhs": "haskell", ".jl": "julia", ".m": "objective-c", ".mm": "objective-cpp", ".zig": "zig", ".v": "verilog", ".sol": "solidity", ".asm": "asm", ".s": "asm",
}

LANGUAGE_NAMES = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript", "tsx": "TSX",
    "java": "Java", "c": "C", "cpp": "C++", "go": "Go", "rust": "Rust", "c_sharp": "C#",
    "php": "PHP", "ruby": "Ruby", "swift": "Swift", "kotlin": "Kotlin", "scala": "Scala",
    "dart": "Dart", "lua": "Lua", "bash": "Bash", "sql": "SQL", "r": "R", "fsharp": "F#", "elixir": "Elixir", "erlang": "Erlang", "haskell": "Haskell", "julia": "Julia", "objective-c": "Objective-C", "objective-cpp": "Objective-C++", "zig": "Zig", "verilog": "Verilog", "solidity": "Solidity", "asm": "Assembly",
}


def language_for_path(path: Path) -> Optional[str]:
    return LANGUAGE_BY_EXT.get(path.suffix.lower())


@dataclass
class GenericResult:
    language: str
    symbols: List[SymbolInfo]
    imports: List[str]
    issues: List[Issue]
    nodes: List[StructureNode]
    edges: List[StructureEdge]
    metrics: Dict[str, Any]


class _PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, symbols: List[SymbolInfo], imports: List[str],
                 issues: List[Issue], nodes: List[StructureNode], edges: List[StructureEdge]):
        self.path = path
        self.symbols = symbols
        self.imports = imports
        self.issues = issues
        self.nodes = nodes
        self.edges = edges
        self.stack: List[str] = []
        self.classes: List[str] = []
        self.functions: List[str] = []
        self.complexity = 1

    def _add(self, kind: str, name: str, node: ast.AST, detail: str = "") -> str:
        lineno = getattr(node, 'lineno', 1)
        ident = f"{self.path}:{kind}:{lineno}:{name}"
        parent = self.stack[-1] if self.stack else ""
        scope = ".".join(self.classes + self.functions)
        self.nodes.append(StructureNode(ident, name, kind, str(self.path), lineno, parent, scope, detail))
        if parent:
            self.edges.append(StructureEdge(parent, ident, "contains"))
        return ident

    def visit_Import(self, node):
        self.imports.extend(a.name for a in node.names)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.imports.append("." * node.level + (node.module or ""))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        parent_class = self.classes[-1] if self.classes else ""
        self.symbols.append(SymbolInfo(node.name, "class", str(self.path), node.lineno, parent_class))
        ident = self._add("class", node.name, node, "class")
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.edges.append(StructureEdge(ident, f"ref:{base.id}", "inherits"))
        self.stack.append(ident)
        self.classes.append(node.name)
        self.generic_visit(node)
        self.classes.pop()
        self.stack.pop()

    def visit_FunctionDef(self, node):
        parent = self.classes[-1] if self.classes else (self.functions[-1] if self.functions else "")
        args = [a.arg for a in node.args.args]
        sig = f"def {node.name}({', '.join(args)})"
        kind = "method" if self.classes else "function"
        self.symbols.append(SymbolInfo(node.name, kind, str(self.path), node.lineno, parent, sig))
        ident = self._add(kind, node.name, node, sig)
        self.stack.append(ident)
        self.functions.append(node.name)
        if len(node.args.args) > 7:
            self.issues.append(Issue("warning", "PY021", "Function has more than 7 parameters.", str(self.path), node.lineno, node.name))
        if len(node.body) > 80:
            self.issues.append(Issue("warning", "PY020", "Function has more than 80 top-level statements.", str(self.path), node.lineno, node.name))
        self.generic_visit(node)
        self.functions.pop()
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node):
        self.complexity += 1 + len(node.handlers)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Call(self, node):
        if self.stack:
            target = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if target:
                self.edges.append(StructureEdge(self.stack[-1], f"call:{target}", "calls"))
        if isinstance(node.func, ast.Name):
            if node.func.id == "eval":
                self.issues.append(Issue("error", "PY001", "Dynamic eval() execution requires review.", str(self.path), node.lineno))
            elif node.func.id == "exec":
                self.issues.append(Issue("error", "PY002", "Dynamic exec() execution requires review.", str(self.path), node.lineno))
            elif node.func.id == "compile":
                self.issues.append(Issue("warning", "PY003", "Dynamic compile() reduces static analyzability.", str(self.path), node.lineno))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.issues.append(Issue("warning", "PY010", "Bare except catches every exception.", str(self.path), node.lineno))
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and self.stack:
                self._add("variable", target.id, node, "assignment")
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    if target.id.lower() in {"password", "passwd", "secret", "api_key", "token"}:
                        self.issues.append(Issue("warning", "PY030", f"Possible hard-coded secret in {target.id}.", str(self.path), node.lineno))
        self.generic_visit(node)


class PolyglotSourceAnalyzer:
    """Tree-sitter based structural analyzer with conservative fallbacks.

    Tree-sitter is used when installed; the fallback keeps PyScribe useful on a
    minimal installation and never executes project code.
    """

    def __init__(self, root: Path):
        self.root = root
        self._pack = None
        self._parsers: Dict[str, Any] = {}
        try:
            from tree_sitter_language_pack import get_parser
            self._pack = get_parser
        except Exception:
            self._pack = None

    @property
    def available(self) -> bool:
        return self._pack is not None

    def analyze(self, path: Path, text: str) -> GenericResult:
        language = language_for_path(path) or "text"
        if language == "python":
            return self._python(path, text)
        if self._pack:
            try:
                return self._tree_sitter(path, text, language)
            except Exception as exc:
                return self._fallback(path, text, language, f"Tree-sitter backend: {exc}")
        return self._fallback(path, text, language, "Install tree-sitter-language-pack for full parsing.")

    def _python(self, path: Path, text: str) -> GenericResult:
        symbols: List[SymbolInfo] = []
        imports: List[str] = []
        issues: List[Issue] = []
        nodes: List[StructureNode] = []
        edges: List[StructureEdge] = []
        module = self._module_name(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            issues.append(Issue("error", "PY100", f"Syntax error: {exc.msg}", str(path), exc.lineno or 1))
            return GenericResult("python", symbols, imports, issues, nodes, edges, {"parse_ok": False})

        visitor = _PythonASTVisitor(path, symbols, imports, issues, nodes, edges)
        visitor.visit(tree)
        return GenericResult("python", symbols, imports, issues, nodes, edges, {"parse_ok": True, "complexity": visitor.complexity})

    def _tree_sitter(self, path: Path, text: str, language: str) -> GenericResult:
        parser = self._parsers.get(language)
        if parser is None:
            parser = self._pack(language)
            self._parsers[language] = parser
        tree = parser.parse(text.encode("utf-8", errors="replace"))
        root = tree.root_node
        symbols: List[SymbolInfo] = []
        imports: List[str] = []
        issues: List[Issue] = []
        nodes: List[StructureNode] = []
        edges: List[StructureEdge] = []
        stack: List[str] = []
        complexity = 1
        source = text.encode("utf-8", errors="replace")

        symbol_kinds = {
            "class_declaration": "class", "class_definition": "class", "class_specifier": "class",
            "struct_specifier": "struct", "interface_declaration": "interface", "enum_declaration": "enum",
            "function_declaration": "function", "function_definition": "function", "method_declaration": "method",
            "method_definition": "method", "function_item": "function", "function_item_declaration": "function",
            "arrow_function": "function", "lambda_expression": "function", "constructor_declaration": "constructor",
        }
        import_types = {"import_statement", "import_declaration", "preproc_include", "use_declaration", "using_directive", "package_clause", "require_call"}

        def text_of(n):
            return source[n.start_byte:n.end_byte].decode("utf-8", errors="replace").strip()

        def name_of(n):
            target_types = {"identifier", "type_identifier", "property_identifier", "field_identifier", "name", "simple_identifier"}
            m = next((c for c in n.children if c.type in target_types), None)
            if m:
                return text_of(m)
            try:
                c = n.child_by_field_name("name")
                if c:
                    return text_of(c)
            except Exception:
                pass
            return text_of(n).split("(", 1)[0].split()[-1][:80]

        def walk(n):
            nonlocal complexity
            kind = symbol_kinds.get(n.type)
            if kind:
                name = name_of(n) or n.type
                ident = f"{path}:{kind}:{n.start_point[0]+1}:{name}"
                parent = stack[-1] if stack else ""
                nodes.append(StructureNode(ident, name, kind, str(path), n.start_point[0]+1, parent, "", n.type))
                symbols.append(SymbolInfo(name, kind, str(path), n.start_point[0]+1, parent, text_of(n).split("{", 1)[0].split("=", 1)[0].strip()[:180]))
                if parent:
                    edges.append(StructureEdge(parent, ident, "contains"))
                stack.append(ident)
            if n.type in import_types:
                imports.append(text_of(n)[:240])
            if n.type in {"if_statement", "for_statement", "while_statement", "switch_statement", "catch_clause", "conditional_expression", "case_clause"}:
                complexity += 1
            if n.type in {"call_expression", "call", "function_call_expression"} and stack:
                c_node = None
                try:
                    c_node = n.child_by_field_name("function") or n.child_by_field_name("name")
                except Exception:
                    pass
                if c_node:
                    callee = text_of(c_node).split(".")[-1]
                    edges.append(StructureEdge(stack[-1], f"call:{callee}", "calls"))
            for child in n.children:
                walk(child)
            if kind:
                stack.pop()

        walk(root)
        if root.has_error:
            issues.append(Issue("warning", "TS001", "Parser recovered from one or more syntax errors.", str(path), 1))
        issues.extend(self._generic_security(path, text, language))
        metrics = {"parse_ok": not root.has_error, "complexity": complexity, "ast_nodes": self._count_nodes(root), "parser": "tree-sitter"}
        return GenericResult(language, symbols, imports, issues, nodes, edges, metrics)

    def _fallback(self, path: Path, text: str, language: str, note: str) -> GenericResult:
        symbols: List[SymbolInfo] = []
        nodes: List[StructureNode] = []
        edges: List[StructureEdge] = []
        imports: List[str] = []
        # The C/C++ patterns used to start with `(?:[A-Za-z_]\w*\s+)+`, a nested
        # quantifier that backtracks exponentially on macro-heavy headers: one
        # 615 KB CMSIS header (`stm32f10x.h`) took **85 seconds** to reject.
        # Anchoring the return-type part to a single line keeps it linear
        # (same file: 0.05 s).
        _c_function = (r"^[ \t]*(?:[A-Za-z_][\w \t*&:<>,]*?)?"
                       r"\b([A-Za-z_]\w*)\s*\([^;{}\n]*\)\s*\{")
        patterns = {
            "javascript": r"(?:function|class)\s+([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
            "typescript": r"(?:function|class|interface)\s+([A-Za-z_$][\w$]*)",
            "java": r"(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)|(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+([A-Za-z_$][\w$]*)\s*\(",
            "c": r"\b(?:struct|enum)\s+([A-Za-z_]\w*)|" + _c_function,
            "cpp": (r"\b(?:class|struct|namespace)\s+([A-Za-z_]\w*)|"
                    + _c_function),
            "go": r"(?:type\s+([A-Za-z_]\w*)\s+struct|func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*))",
            "rust": r"(?:struct|enum|trait)\s+([A-Za-z_]\w*)|fn\s+([A-Za-z_]\w*)",
        }
        pat = patterns.get(language)
        if pat:
            for m in re.finditer(pat, text, re.M):
                name = next((x for x in m.groups() if x), "")
                if not name: continue
                line = text.count("\n", 0, m.start()) + 1
                kind = "class" if re.match(r"\s*(class|struct|enum|interface|trait|namespace|type)", m.group(0)) else "function"
                ident = f"{path}:{kind}:{line}:{name}"
                nodes.append(StructureNode(ident, name, kind, str(path), line, "", "", "regex-fallback"))
                symbols.append(SymbolInfo(name, kind, str(path), line))
        for line in text.splitlines():
            if re.search(r"\b(?:import|include|use|require)\b", line): imports.append(line.strip()[:240])
        issues = self._generic_security(path, text, language)
        issues.append(Issue("info", "PI000", note, str(path), 1))
        return GenericResult(language, symbols, imports, issues, nodes, edges, {"parse_ok": True, "parser": "fallback", "complexity": 1})

    def _generic_security(self, path: Path, text: str, language: str) -> List[Issue]:
        # `.+` before an optional `+` backtracks quadratically: on a generated
        # single-line Python file it hung for minutes (same class of bug as the
        # C function pattern above). The bounded character classes keep every
        # rule linear in the line length.
        rules = [
            (r"\beval\s*\(", "SEC001", "Dynamic eval-like execution requires review.", "warning"),
            (r"\b(?:system|popen)\s*\(", "SEC002", "Process execution API detected; review command construction.", "warning"),
            (r"\b(?:password|passwd|secret|api[_-]?key|token)\s*=\s*['\"]", "SEC003", "Possible hard-coded credential detected.", "warning"),
            (r"(?:SELECT|UPDATE|DELETE|INSERT)\s+[^\n]{0,200}?\+[^\n]{0,200}", "SEC004", "Possible string-built SQL query; prefer parameterized queries.", "warning"),
        ]
        # Hard guard: a rule must never scan an unbounded amount of text.
        if len(text) > 400_000:
            text = text[:400_000]
        out: List[Issue] = []
        for pattern, code, msg, sev in rules:
            for m in re.finditer(pattern, text, re.I | re.M):
                out.append(Issue(sev, code, msg, str(path), text.count("\n", 0, m.start()) + 1))
        return out[:200]

    @staticmethod
    def _count_nodes(root) -> int:
        count = 1
        for child in root.children:
            count += PolyglotSourceAnalyzer._count_nodes(child)
        return count

    def _module_name(self, path: Path) -> str:
        try:
            rel = path.relative_to(self.root)
            return ".".join(rel.with_suffix("").parts)
        except Exception:
            return path.stem
