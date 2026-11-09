"""PyScribe core/project_intelligence.py: application module and reusable component."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.subprocess_utils import run_hidden

SKIP_DIRS = {
    '.git', '.hg', '.svn', '__pycache__', '.venv', 'venv', 'env', 'node_modules',
    'dist', 'build', '.idea', '.vscode', '.mypy_cache', '.pytest_cache',
    'target', 'vendor', '.gradle', '.tox', '.ruff_cache',
}

@dataclass
class SymbolInfo:
    name: str
    kind: str
    file: str
    line: int
    parent: str = ''
    signature: str = ''
    language: str = ''

@dataclass
class StructureNode:
    id: str
    name: str
    kind: str
    file: str
    line: int
    parent_id: str = ''
    scope: str = ''
    detail: str = ''

@dataclass
class StructureEdge:
    source: str
    target: str
    kind: str = 'contains'

@dataclass
class Issue:
    severity: str
    code: str
    message: str
    file: str
    line: int
    symbol: str = ''
    language: str = ''

@dataclass
class FileInfo:
    path: str
    module: str
    lines: int = 0
    functions: int = 0
    classes: int = 0
    imports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    complexity: int = 1
    issues: List[Issue] = field(default_factory=list)
    language: str = 'unknown'
    parser: str = ''
    metrics: Dict[str, Any] = field(default_factory=dict)
    kind: str = 'source'

@dataclass
class BinaryInfo:
    path: str
    format: str = 'unknown'
    architecture: str = 'unknown'
    bits: int = 0
    entrypoint: int = 0
    size: int = 0
    sha256: str = ''
    sections: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProjectAnalysis:
    root: str
    files: Dict[str, FileInfo] = field(default_factory=dict)
    binaries: Dict[str, BinaryInfo] = field(default_factory=dict)
    symbols: List[SymbolInfo] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    dependencies: List[Tuple[str, str]] = field(default_factory=list)
    reverse_dependencies: Dict[str, Set[str]] = field(default_factory=dict)
    structure_nodes: List[StructureNode] = field(default_factory=list)
    structure_edges: List[StructureEdge] = field(default_factory=list)
    duration_ms: int = 0
    backend_status: Dict[str, str] = field(default_factory=dict)
    health_score: int = 100
    health_grade: str = 'A'
    health_debt_items: List[Dict[str, Any]] = field(default_factory=list)
    health_summary: Dict[str, Any] = field(default_factory=dict)
    # Scan limits: what was cut or skipped, so the UI can be honest about it.
    scan_truncated: bool = False
    skipped_dirs: int = 0
    skipped_files: int = 0
    skipped_dir_names: List[str] = field(default_factory=list)

    @property
    def python_files(self):
        return [f for f in self.files.values() if f.language == 'python']

    @property
    def source_files(self):
        return list(self.files.values())

    @property
    def total_lines(self):
        return sum(f.lines for f in self.files.values())

    @property
    def average_complexity(self):
        files = [f for f in self.files.values() if f.kind == 'source']
        return sum(f.complexity for f in files) / len(files) if files else 0.0


class ProjectIntelligenceEngine:
    """Polyglot static project intelligence engine.

    It never executes project source or inspected binaries. Source parsing uses
    Python AST for Python and Tree-sitter for other supported languages when the
    optional parser pack is installed. Executables are inspected with LIEF when
    available, with a read-only raw fallback otherwise.
    """

    SOURCE_EXTENSIONS = {
        '.py', '.pyw', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.java', '.c', '.h',
        '.cc', '.cpp', '.cxx', '.hpp', '.hh', '.hxx', '.go', '.rs', '.cs', '.php', '.rb',
        '.swift', '.kt', '.kts', '.scala', '.dart', '.lua', '.sh', '.bash', '.zsh', '.sql', '.r', '.fs', '.fsx', '.ex', '.exs', '.erl', '.hrl', '.hs', '.lhs', '.jl', '.m', '.mm', '.zig', '.v', '.sol', '.asm', '.s'
    }

    DEFAULT_ANALYZERS = {'structure', 'dependencies', 'health'}

    def __init__(self, root: Optional[str] = None, enabled_analyzers=None):
        self.root: Optional[Path] = None
        # None means defaults; an explicit empty set means analysis is disabled.
        self.enabled_analyzers = set(self.DEFAULT_ANALYZERS if enabled_analyzers is None else enabled_analyzers)
        self.analysis = ProjectAnalysis('')
        # Scan limits: large projects must stay openable.
        from core.ignore_rules import MAX_FILES_DEFAULT, MAX_SOURCE_BYTES
        self.max_files = MAX_FILES_DEFAULT
        self.max_source_bytes = MAX_SOURCE_BYTES
        # Hard time budget: one pathological file must never freeze the app.
        self.time_budget_sec = 25.0
        # Breathing room between files so the UI keeps its share of disk I/O.
        self.io_pause_sec = 0.002
        self.last_scan = None
        self.scan_truncated = False
        self.skipped_dirs = 0
        self.skipped_files = 0
        if root:
            self.set_root(root)

    def set_root(self, root: Optional[str]):
        self.root = Path(root).resolve() if root else None
        self.analysis = ProjectAnalysis(str(self.root) if self.root else '')

    def iter_source_files(self) -> List[Path]:
        """Project source files, ignoring vendored, generated and build output.

        The walk prunes ignored directories *during* traversal (see
        ``core.ignore_rules``): ``Path.rglob`` used to descend into
        ``node_modules``/``.git`` and only filter afterwards, which made large
        projects slow to open and could exhaust memory.
        """
        if not self.root or not self.root.exists():
            return []
        from core.ignore_rules import MAX_FILES_DEFAULT, MAX_SOURCE_BYTES, walk_files
        scan = walk_files(self.root, extensions=self.SOURCE_EXTENSIONS,
                          max_files=self.max_files,
                          max_bytes=MAX_SOURCE_BYTES)
        self.last_scan = scan
        self.scan_truncated = bool(scan.truncated)
        self.skipped_dirs = scan.skipped_dirs
        self.skipped_files = scan.skipped_files
        return list(scan.files)

    def iter_project_files(self) -> List[Path]:
        """Source files plus, when enabled, recognized binaries."""
        if not self.root or not self.root.exists():
            return []
        files = self.iter_source_files()
        if 'binaries' not in self.enabled_analyzers:
            return sorted(set(files), key=lambda p: str(p).lower())
        from core.analyzers.binary import BinaryAnalyzer
        from core.ignore_rules import walk_files
        # One more pruned pass, but only for files the source scan skipped by
        # extension: never read every data file in the tree.
        scan = walk_files(self.root, extensions=None, max_files=self.max_files,
                          max_bytes=32 * 1024 * 1024)
        binaries = []
        for path in scan.files:
            if path.suffix.lower() in self.SOURCE_EXTENSIONS:
                continue
            try:
                if BinaryAnalyzer.looks_like_binary(path):
                    binaries.append(path)
            except OSError:
                continue
        return sorted(set(files) | set(binaries), key=lambda p: str(p).lower())

    def _read(self, path: Path) -> str:
        try:
            if path.stat().st_size > self.max_source_bytes:
                # Generated/minified data: parsing it would cost memory and
                # produce noise rather than structure.
                return ''
        except OSError:
            return ''
        try:
            return path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ''

    def _module_name(self, path: Path) -> str:
        try:
            rel = path.relative_to(self.root)
            parts = list(rel.with_suffix('').parts)
            if parts and parts[-1] in {'__init__', 'mod'}:
                parts.pop()
            return '.'.join(parts) or rel.stem
        except Exception:
            return path.stem

    @staticmethod
    def _resolve_import(current_module: str, imported: str) -> str:
        if not imported.startswith('.'):
            return imported
        level = len(imported) - len(imported.lstrip('.'))
        tail = imported[level:]
        parts = current_module.split('.') if current_module else []
        base = parts[:-1]
        if level > 1:
            base = base[:max(0, len(base) - (level - 1))]
        return '.'.join([*base, *([tail] if tail else [])])

    def analyze(self, progress=None) -> ProjectAnalysis:
        started = time.perf_counter()
        analysis = ProjectAnalysis(str(self.root) if self.root else '')
        if not self.root or not self.root.exists():
            return analysis

        # No enabled analyzers means a deliberate no-op. Do not walk the project.
        if not self.enabled_analyzers:
            analysis.duration_ms = int((time.perf_counter() - started) * 1000)
            self.analysis = analysis
            return analysis

        from core.analyzers.polyglot import PolyglotSourceAnalyzer
        from core.analyzers.binary import BinaryAnalyzer
        source_analyzer = PolyglotSourceAnalyzer(self.root) if ('structure' in self.enabled_analyzers or 'dependencies' in self.enabled_analyzers or 'metrics' in self.enabled_analyzers or 'security' in self.enabled_analyzers) else None
        binary_analyzer = BinaryAnalyzer(self.root) if 'binaries' in self.enabled_analyzers else None
        if source_analyzer is not None:
            analysis.backend_status['tree_sitter'] = 'available' if source_analyzer.available else 'fallback'
        if 'binaries' in self.enabled_analyzers:
            try:
                import lief  # noqa: F401
                analysis.backend_status['lief'] = 'available'
            except Exception:
                analysis.backend_status['lief'] = 'fallback'
        if 'metrics' in self.enabled_analyzers:
            try:
                import radon  # noqa: F401
                analysis.backend_status['radon'] = 'available'
            except Exception:
                analysis.backend_status['radon'] = 'not installed'
        if 'security' in self.enabled_analyzers:
            try:
                import bandit  # noqa: F401
                analysis.backend_status['bandit'] = 'available'
            except Exception:
                analysis.backend_status['bandit'] = 'not installed'
        if 'dependencies' in self.enabled_analyzers:
            try:
                import networkx  # noqa: F401
                analysis.backend_status['networkx'] = 'available'
            except Exception:
                analysis.backend_status['networkx'] = 'fallback'

        paths = self.iter_project_files()
        # Record what the scan skipped so the panel can explain a smaller count.
        analysis.scan_truncated = bool(self.scan_truncated)
        analysis.skipped_dirs = int(self.skipped_dirs)
        analysis.skipped_files = int(self.skipped_files)
        if self.last_scan is not None:
            analysis.skipped_dir_names = list(self.last_scan.skipped_dir_names)
        if self.scan_truncated:
            analysis.issues.append(Issue(
                severity='warning', code='SCAN_LIMIT',
                message=(f'Проект слишком большой: проанализировано '
                         f'{len(paths)} файлов (лимит {self.max_files}). '
                         f'Исключены служебные каталоги и крупные файлы.'),
                file=str(self.root), line=0))
        total = len(paths)
        module_by_file = {}
        for p in paths:
            if p.suffix.lower() in self.SOURCE_EXTENSIONS:
                module_by_file[str(p)] = self._module_name(p)
        module_to_file = {m: p for p, m in module_by_file.items()}

        for index, path in enumerate(paths, 1):
            if (self.time_budget_sec and
                    time.perf_counter() - started > self.time_budget_sec):
                remaining = len(paths) - index + 1
                analysis.scan_truncated = True
                analysis.issues.append(Issue(
                    severity='warning', code='ANALYSIS_LIMIT',
                    message=(f'Анализ остановлен по лимиту времени '
                             f'({int(self.time_budget_sec)} с): пропущено '
                             f'{remaining} файлов.'),
                    file=str(self.root), line=0))
                break
            # Cooperative yield: analysis is a background job. Reading hundreds
            # of files from a cloud-synced folder saturates disk I/O and makes
            # the window stutter, so the loop deliberately gives the UI thread
            # time between files.
            time.sleep(self.io_pause_sec)
            if path.suffix.lower() in self.SOURCE_EXTENSIONS and source_analyzer is not None:
                text = self._read(path)
                try:
                    result = source_analyzer.analyze(path, text)
                except (RecursionError, MemoryError, ValueError, UnicodeError) as exc:
                    # One pathological file must not abort the whole project.
                    analysis.issues.append(Issue(
                        severity='warning', code='PARSE_SKIPPED',
                        message=f'Файл пропущен при разборе: {type(exc).__name__}',
                        file=str(path), line=0))
                    if progress:
                        progress(index, total, path.name)
                    continue
                info = FileInfo(
                    path=str(path), module=module_by_file.get(str(path), self._module_name(path)),
                    lines=text.count('\n') + (1 if text else 0), language=result.language,
                    parser=result.metrics.get('parser', 'ast' if result.language == 'python' else 'fallback'),
                    metrics=dict(result.metrics),
                )
                info.symbols = result.symbols
                info.imports = result.imports
                info.issues = result.issues
                info.functions = sum(1 for s in result.symbols if s.kind in {'function', 'method', 'constructor'})
                info.classes = sum(1 for s in result.symbols if s.kind in {'class', 'struct', 'interface', 'enum'})
                info.complexity = int(result.metrics.get('complexity', 1) or 1)
                analysis.files[str(path)] = info
                analysis.symbols.extend(result.symbols)
                analysis.issues.extend(result.issues)
                analysis.structure_nodes.extend(result.nodes)
                analysis.structure_edges.extend(result.edges)
            elif binary_analyzer is not None:
                try:
                    result = binary_analyzer.analyze(path)
                    b = BinaryInfo(
                        path=str(path), format=result.format, architecture=result.architecture, bits=result.bits,
                        entrypoint=result.entrypoint, size=result.metrics.get('size', path.stat().st_size),
                        sha256=result.metrics.get('sha256', ''), sections=result.sections, imports=result.imports,
                        exports=result.exports, symbols=result.symbols, issues=result.issues, metrics=result.metrics,
                    )
                    analysis.binaries[str(path)] = b
                    analysis.symbols.extend(result.symbols)
                    analysis.issues.extend(result.issues)
                    analysis.structure_nodes.extend(result.nodes)
                    analysis.structure_edges.extend(result.edges)
                except Exception as exc:
                    issue = Issue('warning', 'BIN999', f'Binary analysis failed: {exc}', str(path), 1)
                    analysis.issues.append(issue)
            if progress:
                progress(index, total, path.name)

        if 'dependencies' in self.enabled_analyzers:
            self._resolve_source_dependencies(analysis, module_to_file)
            self._add_generic_dependency_edges(analysis)
        if 'metrics' in self.enabled_analyzers:
            self._enrich_python_metrics(analysis)
        if 'security' in self.enabled_analyzers:
            self._run_bandit(analysis)
        if 'health' in self.enabled_analyzers:
            self._analyze_health_and_debt(analysis)
        analysis.dependencies = sorted(set(analysis.dependencies))
        analysis.duration_ms = int((time.perf_counter() - started) * 1000)
        self.analysis = analysis
        return analysis

    def _resolve_source_dependencies(self, analysis: ProjectAnalysis, module_to_file: Dict[str, str]):
        known = set(module_to_file)
        for info in analysis.files.values():
            for imported in info.imports:
                raw = imported.strip()
                # Python imports can be plain names; other parsers return source lines.
                base = self._resolve_import(info.module, raw) if raw.startswith('.') else raw.split()[0] if raw else ''
                base = base.strip('"\' ;(){}')
                candidates = [base]
                if '.' in base: candidates.extend(base.rsplit('.', i)[0] for i in range(1, base.count('.') + 1))
                for candidate in candidates:
                    if candidate in known and candidate != info.module:
                        analysis.dependencies.append((info.module, candidate))
                        analysis.reverse_dependencies.setdefault(candidate, set()).add(info.module)
                        break

    def _add_generic_dependency_edges(self, analysis: ProjectAnalysis):
        # Module graph edges are derived from parsed imports. Add source-file containment.
        file_to_module = {f.path: f.module for f in analysis.files.values()}
        for node in analysis.structure_nodes:
            if node.file in file_to_module and node.kind in {'class', 'struct', 'interface', 'enum', 'function', 'method'} and not node.parent_id:
                module_id = f'module:{file_to_module[node.file]}'
                analysis.structure_edges.append(StructureEdge(module_id, node.id, 'contains'))
        for info in analysis.files.values():
            module_id = f'module:{info.module}'
            analysis.structure_nodes.append(StructureNode(module_id, info.module, 'module', info.path, 1, '', info.language, info.parser))
        for src, dst in analysis.dependencies:
            analysis.structure_edges.append(StructureEdge(f'module:{src}', f'module:{dst}', 'imports'))

    def _enrich_python_metrics(self, analysis: ProjectAnalysis):
        try:
            from radon.complexity import cc_visit
            from radon.metrics import mi_visit
            from radon.raw import analyze as raw_analyze
        except Exception:
            return
        for info in analysis.files.values():
            if info.language != 'python': continue
            text = self._read(Path(info.path))
            try:
                blocks = cc_visit(text)
                raw = raw_analyze(text)
                mi = mi_visit(text, multi=True)
                info.metrics.update({
                    'radon_complexity': round(sum(getattr(b, 'complexity', 1) for b in blocks) / max(1, len(blocks)), 2),
                    'maintainability_index': round(float(mi), 2),
                    'sloc': int(raw.sloc), 'lloc': int(raw.lloc), 'comments': int(raw.comments), 'blank': int(raw.blank),
                })
            except Exception:
                pass

    def _run_bandit(self, analysis: ProjectAnalysis):
        """Optionally enrich Python diagnostics with Bandit without executing project code."""
        if not analysis.python_files:
            return
        try:
            import bandit  # noqa: F401
        except Exception:
            return
        try:
            proc = run_hidden(
                [sys.executable, '-m', 'bandit', '-r', str(self.root), '-f', 'json', '-q',
                 '-x', ','.join(SKIP_DIRS)],
                capture_output=True, text=True, timeout=90, cwd=str(self.root), check=False,
            )
            if not proc.stdout.strip():
                return
            payload = json.loads(proc.stdout)
            existing = {(i.file, i.line, i.code) for i in analysis.issues}
            for item in payload.get('results', []):
                filename = str(Path(item.get('filename', '')).resolve())
                line = int(item.get('line_number') or 1)
                code = str(item.get('test_id') or 'BANDIT')
                key = (filename, line, code)
                if key in existing:
                    continue
                severity = str(item.get('issue_severity', 'LOW')).lower()
                severity = 'error' if severity == 'high' else 'warning' if severity == 'medium' else 'info'
                analysis.issues.append(Issue(severity, code, str(item.get('issue_text') or 'Bandit finding'), filename, line, language='python'))
                existing.add(key)
            analysis.backend_status['bandit'] = 'available + executed'
        except Exception:
            # A third-party analyzer must never make the primary index fail.
            return

    def analyze_file(self, path: str, content: Optional[str] = None):
        p = Path(path).resolve()
        if not self.root or not self.enabled_analyzers:
            return None
        from core.analyzers.polyglot import PolyglotSourceAnalyzer
        text = content if content is not None else self._read(p)
        result = PolyglotSourceAnalyzer(self.root).analyze(p, text)
        info = FileInfo(str(p), self._module_name(p), text.count('\n') + (1 if text else 0), language=result.language,
                        parser=result.metrics.get('parser', ''), metrics=result.metrics)
        info.symbols, info.imports, info.issues = result.symbols, result.imports, result.issues
        info.functions = sum(1 for s in result.symbols if s.kind in {'function', 'method', 'constructor'})
        info.classes = sum(1 for s in result.symbols if s.kind in {'class', 'struct', 'interface', 'enum'})
        info.complexity = int(result.metrics.get('complexity', 1) or 1)
        return info

    def impacted_by(self, path: str) -> List[FileInfo]:
        p = Path(path).resolve()
        info = self.analysis.files.get(str(p))
        if not info: return []
        seen, queue = set(), [info.module]
        while queue:
            module = queue.pop(0)
            for dependent in self.analysis.reverse_dependencies.get(module, set()):
                if dependent not in seen:
                    seen.add(dependent); queue.append(dependent)
        return sorted((f for f in self.analysis.files.values() if f.module in seen), key=lambda f: f.module)

    def dependencies_for(self, path: str) -> List[FileInfo]:
        p = Path(path).resolve(); info = self.analysis.files.get(str(p))
        if not info: return []
        targets = {b for a, b in self.analysis.dependencies if a == info.module}
        return sorted((f for f in self.analysis.files.values() if f.module in targets), key=lambda f: f.module)

    def hotspots(self, limit=30):
        """Rank source files by structural risk/complexity for the diploma UI."""
        rows = []
        for f in self.analysis.files.values():
            issue_weight = sum(5 if i.severity == 'error' else 2 if i.severity == 'warning' else 1 for i in f.issues)
            score = (f.complexity * 2.0) + (f.lines / 120.0) + issue_weight
            rows.append({'file': f.path, 'module': f.module, 'language': f.language,
                         'lines': f.lines, 'complexity': f.complexity, 'issues': len(f.issues),
                         'score': round(score, 2)})
        return sorted(rows, key=lambda x: (-x['score'], x['module'].lower()))[:limit]

    def dependency_cycles(self):
        """Return module dependency cycles, using NetworkX when available."""
        if 'dependencies' not in self.enabled_analyzers:
            return []
        edges = list(self.analysis.dependencies)
        try:
            import networkx as nx
            g = nx.DiGraph(); g.add_edges_from(edges)
            return [list(c) for c in nx.simple_cycles(g)]
        except Exception:
            graph = {}
            for a, b in edges: graph.setdefault(a, []).append(b)
            cycles, stack, active = [], [], set()
            def dfs(u):
                stack.append(u); active.add(u)
                for v in graph.get(u, []):
                    if v in active:
                        try: cycles.append(stack[stack.index(v):] + [v])
                        except ValueError: pass
                    elif v not in stack: dfs(v)
                active.discard(u); stack.pop()
            for u in graph: dfs(u)
            unique=[]; seen=set()
            for c in cycles:
                key=tuple(sorted(c))
                if key not in seen: seen.add(key); unique.append(c)
            return unique

    def security_findings(self):
        return sorted([i for i in self.analysis.issues if i.code.startswith(('PY0', 'B', 'BIN', 'PE'))],
                      key=lambda i: (i.severity, i.file, i.line))

    def dead_code_candidates(self, limit=50):
        """Conservative candidates: private/local functions with no resolved incoming call."""
        incoming = set()
        call_names = set()
        for e in self.analysis.structure_edges:
            if e.kind == 'calls' and e.target.startswith('call:'):
                call_names.add(e.target[5:])
        for n in self.analysis.structure_nodes:
            if n.kind in {'function', 'method'} and n.name in call_names:
                incoming.add(n.id)
        candidates=[]
        for n in self.analysis.structure_nodes:
            if n.kind not in {'function', 'method'} or n.id in incoming: continue
            if n.name.startswith('_') or n.name in {'main', '__init__'}:
                candidates.append({'name': n.name, 'file': n.file, 'line': n.line, 'kind': n.kind})
        return candidates[:limit]

    def graph_data(self, mode='modules', file_path=None, function_id=None):
        a = self.analysis
        if not a:
            return [], []
        mode = mode if mode in {'modules', 'classes', 'functions', 'variables', 'binaries', 'imports', 'exports'} else 'modules'
        nodes, edges = a.structure_nodes, a.structure_edges
        if mode == 'modules':
            modules = [n for n in nodes if n.kind == 'module']
            module_ids = {n.id for n in modules}
            selected = list(modules)
            selected_ids = set(module_ids)
            # Include top-level declarations under each module so modules can be
            # expanded into classes/functions without losing the high-level view.
            for n in nodes:
                if n.parent_id in module_ids and n.kind in {'class','struct','interface','enum','function','method'}:
                    selected.append(n); selected_ids.add(n.id)
            return selected, [e for e in edges if e.source in selected_ids and e.target in selected_ids]
        if mode == 'binaries':
            selected = [n for n in nodes if n.kind in {'binary', 'section', 'import', 'export'}]
        elif mode == 'imports':
            selected = [n for n in nodes if n.kind in {'module', 'import'}]
        elif mode == 'exports':
            selected = [n for n in nodes if n.kind in {'binary', 'export'}]
        else:
            selected = list(nodes)
            if file_path:
                fp = str(Path(file_path).resolve())
                selected = [n for n in selected if str(Path(n.file).resolve()) == fp]
            if mode == 'classes': selected = [n for n in selected if n.kind in {'class','struct','interface','enum','method'}]
            elif mode == 'functions': selected = [n for n in selected if n.kind in {'function','method','constructor'}]
            elif mode == 'variables':
                selected = [n for n in selected if n.kind == 'variable' or (function_id and n.id == function_id)]
                if function_id:
                    selected = [n for n in nodes if n.id == function_id or (n.kind == 'variable' and self._descends_from(n.id, function_id, edges))]
        ids = {n.id for n in selected}
        resolved = []
        by_name = {}
        for n in selected:
            by_name.setdefault(n.name, []).append(n)
        for e in edges:
            if e.source not in ids: continue
            if e.target in ids: resolved.append(e); continue
            if e.kind == 'calls' and e.target.startswith('call:'):
                for n in by_name.get(e.target[5:], []): resolved.append(StructureEdge(e.source, n.id, 'calls'))
            elif e.kind == 'inherits' and e.target.startswith('ref:'):
                for n in by_name.get(e.target[4:], []): resolved.append(StructureEdge(e.source, n.id, 'inherits'))
        return selected, resolved

    @staticmethod
    def _descends_from(node_id, parent_id, edges):
        parents = {e.target: e.source for e in edges if e.kind == 'contains'}
        seen = set()
        cur = node_id
        while cur and cur not in seen:
            if cur == parent_id: return True
            seen.add(cur); cur = parents.get(cur, '')
        return False

    def _analyze_health_and_debt(self, analysis: ProjectAnalysis):
        """Audit codebase technical debt (TODO/FIXME/HACK) and code smells, calculating Health Score (0-100%)."""
        debt_items = []
        todo_count = 0
        fixme_count = 0
        hack_count = 0
        god_functions = 0
        deep_nesting = 0
        long_files = 0

        # Pattern for debt markers in source code comments (#, //, /*, *, --, ;)
        marker_pattern = re.compile(
            r'(?:#|//|/\*|\*|--|;)\s*(TODO|FIXME|HACK|BUG|XXX|OPTIMIZE|TEMP)(?:\s*[:(]|\s+)(.*)$',
            re.IGNORECASE
        )

        for path_str, file_info in analysis.files.items():
            if file_info.kind != 'source':
                continue
            p = Path(path_str)
            text = self._read(p)
            lines = text.splitlines()
            total_lines = len(lines)

            # 1. Large File Smell (> 500 lines)
            if total_lines > 500:
                long_files += 1
                debt_items.append({
                    'file': path_str,
                    'line': 1,
                    'kind': 'Smell',
                    'tag': 'Large File',
                    'severity': 'LOW',
                    'description': f'File contains {total_lines} lines (> 500 lines). Consider modularizing.'
                })

            for line_idx, line in enumerate(lines, 1):
                # 2. Debt markers in comments
                m = marker_pattern.search(line)
                if m:
                    tag = m.group(1).upper()
                    desc = m.group(2).strip().rstrip('*/').strip() or tag
                    if tag in {'FIXME', 'BUG'}:
                        sev = 'HIGH'
                        fixme_count += 1
                        analysis.issues.append(Issue('warning', f'DEBT_{tag}', f'[{tag}] {desc}', path_str, line_idx))
                    elif tag in {'HACK', 'XXX'}:
                        sev = 'MEDIUM'
                        hack_count += 1
                    else:
                        sev = 'LOW'
                        todo_count += 1

                    debt_items.append({
                        'file': path_str,
                        'line': line_idx,
                        'kind': 'Debt',
                        'tag': tag,
                        'severity': sev,
                        'description': desc
                    })

                # 3. Deep nesting smell (indentation >= 20 spaces)
                indent = len(line) - len(line.lstrip(' '))
                if line.startswith('\t'):
                    indent = (len(line) - len(line.lstrip('\t'))) * 4
                if indent >= 20 and line.strip() and not line.strip().startswith(('/**', '*', '//', '#')):
                    deep_nesting += 1
                    if deep_nesting <= 25:
                        debt_items.append({
                            'file': path_str,
                            'line': line_idx,
                            'kind': 'Smell',
                            'tag': 'Deep Nesting',
                            'severity': 'LOW',
                            'description': f'Deep control nesting ({indent // 4} levels). Extract inner logic into functions.'
                        })

            # 4. God functions (> 60 lines)
            for sym in file_info.symbols:
                if sym.kind in {'function', 'method'}:
                    # Estimate based on symbol or complexity
                    if getattr(sym, 'line', 0) and file_info.lines > 120 and file_info.functions <= 2:
                        god_functions += 1
                        debt_items.append({
                            'file': path_str,
                            'line': sym.line,
                            'kind': 'Smell',
                            'tag': 'God Function',
                            'severity': 'MEDIUM',
                            'description': f'Large function \'{sym.name}\' dominates module ({file_info.lines} lines).'
                        })

        # Calculate Health Score (0-100)
        score = 100.0
        score -= (fixme_count * 3.5)
        score -= (hack_count * 2.0)
        score -= (todo_count * 0.5)
        score -= (min(god_functions, 10) * 2.0)
        score -= (min(deep_nesting, 20) * 0.5)
        score -= (min(long_files, 5) * 1.5)

        avg_cc = analysis.average_complexity
        if avg_cc > 8.0:
            score -= min(15.0, (avg_cc - 8.0) * 2.0)

        final_score = max(10, min(100, int(round(score))))
        if final_score >= 90:
            grade = 'A'
        elif final_score >= 80:
            grade = 'B'
        elif final_score >= 70:
            grade = 'C'
        elif final_score >= 60:
            grade = 'D'
        else:
            grade = 'F'

        analysis.health_score = final_score
        analysis.health_grade = grade
        analysis.health_debt_items = debt_items
        analysis.health_summary = {
            'score': final_score,
            'grade': grade,
            'todo_count': todo_count,
            'fixme_count': fixme_count,
            'hack_count': hack_count,
            'total_debt': todo_count + fixme_count + hack_count,
            'deep_nesting': deep_nesting,
            'long_files': long_files,
            'god_functions': god_functions,
            'total_smells': deep_nesting + long_files + god_functions,
        }

    def metrics(self) -> Dict[str, Any]:
        a = self.analysis
        return {
            'files': len(a.files), 'binaries': len(a.binaries), 'lines': a.total_lines,
            'symbols': len(a.symbols), 'functions': sum(f.functions for f in a.files.values()),
            'classes': sum(f.classes for f in a.files.values()), 'dependencies': len(a.dependencies),
            'issues': len(a.issues), 'errors': sum(i.severity == 'error' for i in a.issues),
            'warnings': sum(i.severity == 'warning' for i in a.issues),
            'average_complexity': round(a.average_complexity, 2),
            'languages': len({f.language for f in a.files.values()}),
            'binary_formats': len({b.format for b in a.binaries.values()}),
            'health_score': f"{a.health_score}% ({a.health_grade})",
        }
