"""Adversarial testing — «Адвокат дьявола».

Given a Python module, generate boundary inputs for its functions, execute them
in an isolated subprocess with a timeout, detect crashes and hangs, then
**minimize** every failing input with delta-debugging so the user gets the
smallest reproducing example instead of a 500-element list.

The module has no Qt dependencies, so it can be used and tested headlessly.

Design notes
------------
* Code under test runs in a **separate process**: a crash (segfault, ``sys.exit``)
  or an infinite loop cannot take the IDE down; a hang is caught by the timeout.
* Inputs are generated from type annotations when present and from a generic
  boundary pool otherwise (``None``, ``0``, ``-1``, ``""``, ``[]``, ``{}``, ...).
* Only crash-type findings are reported. "Wrong result" needs an oracle the tool
  does not have, so it is deliberately not guessed.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.subprocess_utils import run_hidden

__all__ = [
    "FunctionSpec",
    "Finding",
    "AdversaryReport",
    "AdversaryRunner",
    "discover_functions",
    "generate_cases",
    "failing_cases_pytest",
]

DEFAULT_TIMEOUT = 8
MAX_CASES_PER_FUNCTION = 24
MAX_MINIMIZE_RUNS = 14
RESULT_MARKER = "###ADVERSARY_RESULT###"

# Values tried for a parameter whose role could not be inferred. Plausible
# values come first: passing None to everything buries real bugs in noise.
GENERIC_POOL: List[Any] = [
    [], "", 0, {}, -1, 1, [1, 2, 3], "a", None, {"a": 1}, True, 10 ** 6,
]

# Values tried when a role was inferred from the function body.
ROLE_POOLS: Dict[str, List[Any]] = {
    "sequence": [[], [0], [None], [1, 2, 3], "", "abc"],
    "number": [0, -1, 1, 10 ** 6, 0.0],
    "string": ["", "a", "юникод", "x" * 500],
    "mapping": [{}, {"a": 1}, {0: None}, {"a": 1, "b": 2}],
}

# Values tried for a known annotation.
TYPE_POOLS: Dict[str, List[Any]] = {
    "int": [0, -1, 1, 10 ** 6, -10 ** 6],
    "float": [0.0, -1.5, 1e6, float("inf")],
    "str": ["", "a", "юникод", "x" * 500],
    "bool": [True, False],
    "bytes": [b"", b"a"],
    "list": [[], [0], [1, 2, 3], [None], [[1], [2]]],
    "dict": [{}, {"a": 1}, {0: None}],
    "set": [set(), {1, 2}],
    "tuple": [(), (0,), (1, 2)],
}

RUNNER_TEMPLATE = '''\
import importlib.util
import json
import sys
import traceback

MARKER = "__RESULT_MARKER__"


def _emit(payload):
    sys.stdout.write("\\n" + MARKER + json.dumps(payload, ensure_ascii=False) + "\\n")
    sys.stdout.flush()


def main():
    module_path, func_name, args_json = sys.argv[1:4]
    args = json.loads(args_json)
    try:
        spec = importlib.util.spec_from_file_location("adversary_target", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["adversary_target"] = module
        spec.loader.exec_module(module)
    except BaseException as exc:
        _emit({"kind": "import_error", "error_type": type(exc).__name__,
               "error": str(exc), "line": None,
               "traceback": traceback.format_exc()[-2000:]})
        return
    func = getattr(module, func_name, None)
    if func is None:
        _emit({"kind": "missing", "error_type": "AttributeError",
               "error": func_name + " not found", "line": None,
               "traceback": ""})
        return
    try:
        func(*args)
    except BaseException as exc:
        line = None
        tb = traceback.format_exc()
        for frame in traceback.extract_tb(sys.exc_info()[2]):
            if frame.filename == module_path or frame.filename.endswith(module_path):
                line = frame.lineno
        _emit({"kind": "error", "error_type": type(exc).__name__,
               "error": str(exc), "line": line, "traceback": tb[-4000:]})
        return
    _emit({"kind": "ok", "error_type": "", "error": "", "line": None,
           "traceback": ""})


main()
'''


@dataclass
class FunctionSpec:
    """A callable found in a module."""

    name: str
    lineno: int
    arg_names: List[str] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)
    roles: Dict[str, str] = field(default_factory=dict)
    is_async: bool = False

    @property
    def label(self) -> str:
        if not self.arg_names:
            return f"{self.name}()"
        return f"{self.name}({', '.join(self.arg_names)})"


@dataclass
class Finding:
    """One executed case."""

    function: str
    args: List[Any]
    kind: str                     # error | hang | ok | import_error | missing
    error_type: str = ""
    error_message: str = ""
    line: Optional[int] = None
    traceback: str = ""
    minimized: bool = False

    @property
    def failed(self) -> bool:
        return self.kind not in ("ok",)

    @property
    def args_literal(self) -> str:
        try:
            return ", ".join(repr(value) for value in self.args)
        except Exception:
            return "?"

    @property
    def summary(self) -> str:
        if self.kind == "hang":
            return "зависание (превышен таймаут)"
        if self.kind == "import_error":
            return f"модуль не импортируется: {self.error_type}: {self.error_message}"
        if self.kind == "missing":
            return "функция не найдена в модуле"
        if self.kind == "ok":
            return "без ошибки"
        location = f", строка {self.line}" if self.line else ""
        return f"{self.error_type}: {self.error_message}{location}"


@dataclass
class AdversaryReport:
    """Result of a whole file run."""

    module_path: str = ""
    findings: List[Finding] = field(default_factory=list)
    cases_run: int = 0
    functions_checked: int = 0
    error: str = ""

    @property
    def failures(self) -> List[Finding]:
        return [f for f in self.findings if f.failed]

    def groups(self) -> List[Tuple[Finding, int]]:
        """Collapse identical errors into one representative plus a count.

        Ten ``TypeError`` variants of the same bug are noise; the user needs one
        minimal example per distinct error.
        """
        buckets: Dict[Tuple[str, str, str], List[Finding]] = {}
        for finding in self.failures:
            key = (finding.function, finding.kind, finding.error_type,
                   finding.error_message[:120])
            buckets.setdefault(key, []).append(finding)
        grouped: List[Tuple[Finding, int]] = []
        for items in buckets.values():
            best = min(items, key=lambda f: len(f.args_literal))
            grouped.append((best, len(items)))
        grouped.sort(key=lambda pair: (pair[0].function, pair[0].kind, pair[0].error_type))
        return grouped

    def to_markdown(self) -> str:
        lines = [f"# Испытания: {Path(self.module_path).name}", ""]
        lines.append(f"Функций проверено: {self.functions_checked} · "
                     f"случаев запущено: {self.cases_run} · "
                     f"найдено проблем: {len(self.groups())}")
        lines.append("")
        if self.error:
            lines.append(f"> {self.error}")
            lines.append("")
        for finding, count in self.groups():
            suffix = f" (и ещё {count - 1} похожих)" if count > 1 else ""
            lines.append(f"## {finding.function}({finding.args_literal}){suffix}")
            lines.append("")
            lines.append(f"- Результат: {finding.summary}")
            if finding.minimized:
                lines.append("- Вход минимизирован (delta-debugging)")
            lines.append("")
        return "\n".join(lines).strip() + "\n"


# ----------------------------------------------------------------------
# Discovery and input generation
# ----------------------------------------------------------------------
_SEQUENCE_CALLS = {"len", "sum", "min", "max", "sorted", "list", "set", "tuple",
                   "enumerate", "any", "all", "reversed", "zip"}
_MAPPING_METHODS = {"items", "keys", "values", "get", "setdefault", "update"}
_STRING_METHODS = {"split", "strip", "lstrip", "rstrip", "upper", "lower",
                   "startswith", "endswith", "replace", "format", "join",
                   "encode", "title", "capitalize", "find"}
_SEQUENCE_METHODS = {"append", "extend", "insert", "pop", "remove", "index",
                     "count", "sort", "reverse"}


def _infer_roles(func: ast.AST, names: Sequence[str]) -> Dict[str, str]:
    """Guess what each parameter is used *as* inside the function body.

    Without this, every unannotated parameter receives ``None`` and unrelated
    values, and real bugs drown in ``TypeError`` noise. A few AST patterns are
    enough to tell a sequence from a number or a string.
    """
    roles: Dict[str, str] = {}
    ranks = {"unknown": 0, "number": 1, "string": 1, "mapping": 2, "sequence": 2}

    def mark(name: str, role: str):
        if name not in names:
            return
        if ranks.get(role, 0) >= ranks.get(roles.get(name, "unknown"), 0):
            roles[name] = role

    for node in ast.walk(func):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            mark(node.value.id, "sequence")
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            mark(node.iter.id, "sequence")
        elif isinstance(node, ast.Compare):
            for side in [node.left] + list(node.comparators):
                if isinstance(side, ast.Name):
                    mark(side.id, "number")
        elif isinstance(node, ast.BinOp):
            for side in (node.left, node.right):
                if isinstance(side, ast.Name):
                    # ``+`` on strings is common, everything else is numeric.
                    mark(side.id, "string" if isinstance(node.op, ast.Add) else "number")
        elif isinstance(node, ast.Call):
            func_node = node.func
            if isinstance(func_node, ast.Name):
                if func_node.id in _SEQUENCE_CALLS and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        mark(arg.id, "sequence")
                elif func_node.id == "str" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        mark(arg.id, "string")
                elif func_node.id in ("int", "float") and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        mark(arg.id, "number")
            elif isinstance(func_node, ast.Attribute) and isinstance(func_node.value, ast.Name):
                method = func_node.attr
                if method in _MAPPING_METHODS:
                    mark(func_node.value.id, "mapping")
                elif method in _STRING_METHODS:
                    mark(func_node.value.id, "string")
                elif method in _SEQUENCE_METHODS:
                    mark(func_node.value.id, "sequence")
    return roles


def _annotation_name(node: Optional[ast.AST]) -> str:
    """Best-effort textual form of an annotation (``int``, ``list[int]``, ...)."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def discover_functions(source: str) -> List[FunctionSpec]:
    """Top-level functions of a module, with their parameter names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    specs: List[FunctionSpec] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = [a.arg for a in node.args.args]
        if args and args[0] in ("self", "cls"):
            args = args[1:]
        annotations = {}
        for argument in list(node.args.args) + list(node.args.kwonlyargs):
            name = _annotation_name(argument.annotation)
            if name:
                annotations[argument.arg] = name
        specs.append(FunctionSpec(
            name=node.name,
            lineno=node.lineno,
            arg_names=args,
            annotations=annotations,
            roles=_infer_roles(node, args),
            is_async=isinstance(node, ast.AsyncFunctionDef),
        ))
    return specs


def _pool_for_annotation(annotation: str) -> List[Any]:
    text = (annotation or "").lower().replace(" ", "")
    if not text:
        return list(GENERIC_POOL)
    # Optional / union: try the non-None part plus None.
    if "none" in text or "optional" in text:
        base = text.replace("none", "").replace("optional", "").strip("[]|,")
        pool = _pool_for_annotation(base) if base else []
        return [None] + pool
    for key, pool in TYPE_POOLS.items():
        if text.startswith(key) or text.startswith(f"typing.{key}"):
            return list(pool)
    return list(GENERIC_POOL)


def _pool_for_parameter(spec: FunctionSpec, name: str) -> List[Any]:
    """Values for one parameter: annotation first, then inferred role."""
    annotation = spec.annotations.get(name, "")
    if annotation:
        pool = _pool_for_annotation(annotation)
        if pool:
            return pool
    role = spec.roles.get(name, "")
    if role in ROLE_POOLS:
        return list(ROLE_POOLS[role])
    return list(GENERIC_POOL)


def generate_cases(spec: FunctionSpec, limit: int = MAX_CASES_PER_FUNCTION) -> List[List[Any]]:
    """Boundary inputs for a function, capped to ``limit`` combinations."""
    if not spec.arg_names:
        return [[]]
    pools = [_pool_for_parameter(spec, name) for name in spec.arg_names]
    cases: List[List[Any]] = []
    # Drive the product by index so the first cases stay short and readable.
    index = 0
    while len(cases) < limit:
        case: List[Any] = []
        remainder = index
        for pool in pools:
            case.append(pool[remainder % len(pool)])
            remainder //= len(pool)
        cases.append(case)
        index += 1
        # All combinations exhausted?
        if index >= _product_size(pools):
            break
    return cases


def _product_size(pools: Sequence[Sequence[Any]]) -> int:
    total = 1
    for pool in pools:
        total *= max(1, len(pool))
    return total


# ----------------------------------------------------------------------
# Execution
# ----------------------------------------------------------------------
class AdversaryRunner:
    """Runs generated cases in a subprocess and minimizes failing inputs."""

    def __init__(self, python_executable: Optional[str] = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.python = python_executable or sys.executable
        self.timeout = timeout
        self._runner_path: Optional[str] = None

    # -- infrastructure ------------------------------------------------
    def _runner(self) -> str:
        if self._runner_path and os.path.exists(self._runner_path):
            return self._runner_path
        handle = tempfile.NamedTemporaryFile(
            "w", suffix="_adversary_runner.py", delete=False, encoding="utf-8")
        handle.write(RUNNER_TEMPLATE.replace("__RESULT_MARKER__", RESULT_MARKER))
        handle.close()
        self._runner_path = handle.name
        return self._runner_path

    def dispose(self):
        """Remove the temporary runner script."""
        if self._runner_path and os.path.exists(self._runner_path):
            try:
                os.unlink(self._runner_path)
            except OSError:
                pass
        self._runner_path = None

    def execute(self, module_path: str, function_name: str,
                args: Sequence[Any]) -> Finding:
        """Run one call and classify the outcome."""
        command = [self.python, self._runner(), str(module_path), function_name,
                   json.dumps(list(args), ensure_ascii=False)]
        try:
            completed = run_hidden(
                command, capture_output=True, text=True, timeout=self.timeout,
                encoding="utf-8", errors="replace",
                cwd=str(Path(module_path).parent),
            )
        except subprocess.TimeoutExpired:
            return Finding(function=function_name, args=list(args), kind="hang")
        except OSError as exc:
            return Finding(function=function_name, args=list(args),
                           kind="import_error", error_type="OSError",
                           error_message=str(exc))

        payload = None
        for line in reversed((completed.stdout or "").splitlines()):
            if line.startswith(RESULT_MARKER):
                try:
                    payload = json.loads(line[len(RESULT_MARKER):])
                except json.JSONDecodeError:
                    payload = None
                break
        if payload is None:
            stderr = (completed.stderr or "").strip().splitlines()
            message = stderr[-1] if stderr else "нет ответа от процесса"
            return Finding(function=function_name, args=list(args),
                           kind="error", error_type="ProcessError",
                           error_message=message[:300])
        return Finding(
            function=function_name,
            args=list(args),
            kind=str(payload.get("kind") or "error"),
            error_type=str(payload.get("error_type") or ""),
            error_message=str(payload.get("error") or ""),
            line=payload.get("line"),
            traceback=str(payload.get("traceback") or ""),
        )

    # -- minimization --------------------------------------------------
    def _shrink_values(self, value: Any) -> List[Any]:
        """Smaller candidates for one argument (delta-debugging step)."""
        if isinstance(value, list) and len(value) > 1:
            half = len(value) // 2
            return [value[:half], value[half:], value[:1]]
        if isinstance(value, str) and len(value) > 1:
            half = len(value) // 2
            return [value[:half], value[:1]]
        if isinstance(value, dict) and len(value) > 1:
            keys = list(value.keys())
            half = len(keys) // 2
            return [{k: value[k] for k in keys[:half]},
                    {k: value[k] for k in keys[:1]}]
        return []

    def minimize(self, module_path: str, finding: Finding) -> Finding:
        """Shrink every argument while the failure reproduces."""
        if not finding.failed:
            return finding
        best = finding
        budget = MAX_MINIMIZE_RUNS
        changed = False
        for position, value in enumerate(list(best.args)):
            candidates = self._shrink_values(value)
            for candidate in candidates:
                if budget <= 0:
                    break
                trial = list(best.args)
                trial[position] = candidate
                budget -= 1
                result = self.execute(module_path, best.function, trial)
                if result.failed and result.kind == best.kind:
                    best = result
                    changed = True
                    break
        if changed:
            best.minimized = True
        return best

    # -- public --------------------------------------------------------
    def run_function(self, module_path: str, spec: FunctionSpec,
                     limit: int = MAX_CASES_PER_FUNCTION) -> Tuple[List[Finding], int]:
        """Run all generated cases for one function."""
        findings: List[Finding] = []
        cases = generate_cases(spec, limit=limit)
        for args in cases:
            findings.append(self.execute(module_path, spec.name, args))
        return findings, len(cases)

    def run_file(self, module_path: str,
                 limit: int = MAX_CASES_PER_FUNCTION) -> AdversaryReport:
        """Check every top-level function of a file."""
        report = AdversaryReport(module_path=str(module_path))
        path = Path(module_path)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            report.error = f"Не удалось прочитать файл: {exc}"
            return report
        specs = discover_functions(source)
        if not specs:
            report.error = "В файле не найдено функций верхнего уровня."
            return report
        report.functions_checked = len(specs)
        for spec in specs:
            if spec.is_async:
                # Awaiting coroutines needs an event loop; out of scope here.
                continue
            findings, count = self.run_function(path, spec, limit=limit)
            report.cases_run += count
            for finding in findings:
                if finding.failed:
                    report.findings.append(
                        self.minimize(str(path), finding))
                else:
                    report.findings.append(finding)
        return report


# ----------------------------------------------------------------------
# Pytest export
# ----------------------------------------------------------------------
def failing_cases_pytest(module_path: str, findings: Sequence[Finding]) -> str:
    """A pytest module that reproduces every failing call."""
    module_name = Path(module_path).stem
    lines = [
        '"""Регрессионные тесты, сгенерированные PyScribe («Адвокат дьявола»)."""',
        "import importlib.util",
        "from pathlib import Path",
        "",
        "import pytest",
        "",
        f'_MODULE_PATH = Path(__file__).with_name({Path(module_path).name!r})',
        "",
        "",
        "def _load():",
        '    spec = importlib.util.spec_from_file_location("adversary_target", _MODULE_PATH)',
        "    module = importlib.util.module_from_spec(spec)",
        "    spec.loader.exec_module(module)",
        "    return module",
        "",
        "",
        "_MODULE = _load()",
        "",
        "",
        "@pytest.mark.parametrize('function,args', [",
    ]
    for finding in findings:
        if not finding.failed:
            continue
        lines.append(f"    ({finding.function!r}, {finding.args!r}),")
    lines.extend([
        "])",
        "def test_no_crash(function, args):",
        '    """Вызов не должен бросать исключение."""',
        "    getattr(_MODULE, function)(*args)",
        "",
    ])
    return "\n".join(lines)
