"""Unified Code Analysis Service for PyScribe.

Coordinates:
- Level 1: Base text matching (TextCodeAnalyzer)
- Level 2: Tree-sitter syntax structure (TreeSitterEngine)
- Level 3: LSP semantic servers (LspClient instances per active language)
- Cross-language: OpenAPI contracts bridge (OpenApiBridge)

Provides background debouncing, cancellation of stale queries, and graceful
project lifecycle cleanup.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from PyQt5 import QtCore

from core.code_analysis.lsp_client import LspCallItem, LspClient, LspDiagnostic, LspLocation
from core.code_analysis.openapi_bridge import OpenApiBridge
from core.code_analysis.registry import AnalysisLevel, LanguageRegistry, LanguageSpec, get_language_registry
from core.code_analysis.syntax_treesitter import AnalyzedSymbol, TreeSitterEngine, get_treesitter_engine
from core.code_analysis.text_analyzer import TextCodeAnalyzer

logger = logging.getLogger(__name__)


class UnifiedCodeAnalysisService(QtCore.QObject):
    """Unified coordinator of multi-language analysis for PyScribe."""

    diagnostics_updated = QtCore.pyqtSignal(str, list)   # (file_path, List[LspDiagnostic])
    diagnostics_cleared = QtCore.pyqtSignal(str)         # (file_path)
    status_changed = QtCore.pyqtSignal(str, dict)        # (file_path, status_dict)

    def __init__(self, root_path: Optional[str] = None, parent: Optional[QtCore.QObject] = None, settings: Optional[dict] = None):
        if isinstance(root_path, QtCore.QObject) and parent is None:
            parent = root_path
            root_path = None
        super().__init__(parent)
        self.registry: LanguageRegistry = get_language_registry()
        self.treesitter: TreeSitterEngine = get_treesitter_engine()
        self.text_analyzer: TextCodeAnalyzer = TextCodeAnalyzer()
        self.openapi_bridge: OpenApiBridge = OpenApiBridge()

        self.root_path: Optional[str] = None
        self._lsp_clients: Dict[str, LspClient] = {}     # lang_id -> LspClient
        self._lsp_lock = threading.Lock()
        self._file_buffers: Dict[str, Tuple[int, str]] = {}  # file_path -> (version, text)
        self._debounce_timers: Dict[str, QtCore.QTimer] = {}
        self._diagnostics_cache: Dict[str, List[LspDiagnostic]] = {}
        self._query_generation = 0

        if root_path:
            self.set_project_root(root_path)

    @classmethod
    def get_instance(cls, root_path: Optional[str] = None) -> UnifiedCodeAnalysisService:
        """Return the singleton instance of the unified analysis service."""
        svc = get_code_analysis_service()
        if root_path:
            svc.set_project_root(root_path)
        return svc

    # ------------------------------------------------------------------
    # Project Lifecycle
    # ------------------------------------------------------------------
    def set_project_root(self, root_path: Optional[str]) -> None:
        """Switch workspace project: cancels requests, terminates LSP servers, and re-indexes."""
        norm_path = str(Path(root_path).resolve()) if root_path else None
        if norm_path == self.root_path:
            return

        logger.info("Switching project root to: %s", norm_path)
        self.root_path = norm_path
        self._query_generation += 1

        # Stop debounce timers
        for timer in self._debounce_timers.values():
            timer.stop()
        self._debounce_timers.clear()

        # Shutdown active LSP servers
        self._shutdown_all_lsp_servers()

        # Reset caches
        self._file_buffers.clear()
        self._diagnostics_cache.clear()

        # Update analyzers
        self.text_analyzer.set_root(self.root_path)
        self.openapi_bridge.set_root(self.root_path)

        if self.root_path:
            # Rebuild OpenAPI index in background
            threading.Thread(target=self.openapi_bridge.rebuild_index, name="openapi-indexer", daemon=True).start()

    def close_project(self) -> None:
        self.set_project_root(None)

    def _shutdown_all_lsp_servers(self) -> None:
        with self._lsp_lock:
            for lang_id, client in list(self._lsp_clients.items()):
                try:
                    logger.info("Stopping LSP client for %s", lang_id)
                    client.shutdown_and_exit()
                except Exception as exc:
                    logger.debug("Error shutting down LSP %s: %s", lang_id, exc)
            self._lsp_clients.clear()

    # ------------------------------------------------------------------
    # LSP Server Management
    # ------------------------------------------------------------------
    def _get_or_start_lsp(self, spec: LanguageSpec) -> Optional[LspClient]:
        if not self.root_path or not spec.lsp_candidates:
            return None

        with self._lsp_lock:
            client = self._lsp_clients.get(spec.id)
            if client and client.is_alive and client.is_initialized:
                return client

            # Check if custom path is configured in PyScribe settings
            configured_path = None
            try:
                from utils.settings_manager import get_settings_manager
                sm = get_settings_manager()
                configured_path = sm.get_setting(f"lsp_{spec.id}_path") or sm.get_setting(f"toolchain_{spec.toolchain_key}_path")
            except Exception:
                pass

            server_exe, server_args = self.registry.resolve_lsp_server(spec, configured_path=configured_path)
            if not server_exe:
                return None

            logger.info("Starting LSP server for %s: %s %s", spec.id, server_exe, server_args)
            client = LspClient(
                lang_id=spec.id,
                server_path=server_exe,
                server_args=server_args,
                root_path=self.root_path,
                on_diagnostics=self._on_lsp_diagnostics,
                on_exit=self._on_lsp_exit,
            )

            ok = client.start(timeout=6.0)
            if ok:
                self._lsp_clients[spec.id] = client
                return client
            return None

    def _on_lsp_diagnostics(self, file_path: str, diagnostics: List[LspDiagnostic]) -> None:
        """Callback from background thread when server publishes diagnostics."""
        self._diagnostics_cache[file_path] = diagnostics
        QtCore.QMetaObject.invokeMethod(
            self,
            "_emit_diagnostics",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, file_path),
            QtCore.Q_ARG(list, diagnostics),
        )

    @QtCore.pyqtSlot(str, list)
    def _emit_diagnostics(self, file_path: str, diagnostics: list):
        self.diagnostics_updated.emit(file_path, diagnostics)

    def _on_lsp_exit(self, lang_id: str, exit_code: int) -> None:
        logger.info("LSP server %s exited with code %s", lang_id, exit_code)
        with self._lsp_lock:
            self._lsp_clients.pop(lang_id, None)

    # ------------------------------------------------------------------
    # Document Change & In-Memory Synchronization
    # ------------------------------------------------------------------
    def on_document_opened(self, file_path: str, text: str) -> None:
        """Notify analysis service of document opening in an editor tab."""
        norm_path = str(Path(file_path).resolve())
        self._file_buffers[norm_path] = (1, text)

        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._get_or_start_lsp(spec)
            if client:
                client.did_open(norm_path, spec.id, text, version=1)

    def on_document_changed(self, file_path: str, text: str) -> None:
        """Called on text edits. Debounces notifications to avoid freezing/flooding."""
        norm_path = str(Path(file_path).resolve())
        curr_ver, _ = self._file_buffers.get(norm_path, (0, ""))
        new_ver = curr_ver + 1
        self._file_buffers[norm_path] = (new_ver, text)

        timer = self._debounce_timers.get(norm_path)
        if timer is None:
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(320)  # 320ms debounce
            timer.timeout.connect(lambda p=norm_path: self._dispatch_document_change(p))
            self._debounce_timers[norm_path] = timer

        timer.start()

    def _dispatch_document_change(self, file_path: str) -> None:
        buf = self._file_buffers.get(file_path)
        if not buf:
            return
        version, text = buf

        spec = self.registry.get_by_path(file_path)
        if spec:
            client = self._get_or_start_lsp(spec)
            if client:
                client.did_change(file_path, text, version=version)

    def on_document_saved(self, file_path: str) -> None:
        norm_path = str(Path(file_path).resolve())
        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._lsp_clients.get(spec.id)
            if client and client.is_alive:
                client.did_save(norm_path)

    def on_document_closed(self, file_path: str) -> None:
        norm_path = str(Path(file_path).resolve())
        self._file_buffers.pop(norm_path, None)
        timer = self._debounce_timers.pop(norm_path, None)
        if timer:
            timer.stop()

        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._lsp_clients.get(spec.id)
            if client and client.is_alive:
                client.did_close(norm_path)

    # ------------------------------------------------------------------
    # Query: File Structure (Tree-sitter Level 2)
    # ------------------------------------------------------------------
    def get_file_structure(self, file_path: str, text: Optional[str] = None) -> List[AnalyzedSymbol]:
        """Extract classes, functions, methods, and structure even with syntax errors."""
        norm_path = str(Path(file_path).resolve())
        if text is None:
            buf = self._file_buffers.get(norm_path)
            if buf:
                text = buf[1]
            elif Path(norm_path).is_file():
                try:
                    text = Path(norm_path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    text = ""
            else:
                text = ""

        spec = self.registry.get_by_path(norm_path)
        lang_id = spec.id if spec else "plaintext"

        parse_res = self.treesitter.parse(text, lang_id, file_path=norm_path)
        return parse_res.symbols

    def get_syntax_result(self, file_path: str, text: Optional[str] = None):
        """Extract full syntax result including symbols and syntax error markers."""
        norm_path = str(Path(file_path).resolve())
        if text is None:
            buf = self._file_buffers.get(norm_path)
            if buf:
                text = buf[1]
            elif Path(norm_path).is_file():
                try:
                    text = Path(norm_path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    text = ""
            else:
                text = ""

        spec = self.registry.get_by_path(norm_path)
        lang_id = spec.id if spec else "plaintext"
        return self.treesitter.parse(text, lang_id, file_path=norm_path)

    # ------------------------------------------------------------------
    # Query: Go to Definition
    # ------------------------------------------------------------------
    def resolve_openapi(self, file_path: str, line: int, col: int, current_line_text: str = "") -> List[LspLocation]:
        """Resolve OpenAPI cross-language contract links for given position."""
        norm_path = str(Path(file_path).resolve())
        return self.openapi_bridge.find_cross_language_links(norm_path, line, col, current_line_text)

    def goto_definition(
        self,
        file_path: str,
        line: int,
        col: int,
        current_line_text: str = "",
        symbol_name: str = "",
    ) -> List[LspLocation]:
        """Resolve definition with fallback: OpenAPI -> Level 3 LSP -> Level 2 Tree-sitter -> Level 1 Text."""
        norm_path = str(Path(file_path).resolve())

        # 1. OpenAPI Cross-Language Contract Navigation
        openapi_links = self.openapi_bridge.find_cross_language_links(norm_path, line, col, current_line_text)
        if openapi_links:
            return openapi_links

        # 2. Level 3: LSP Semantic Server
        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._get_or_start_lsp(spec)
            if client:
                lsp_defs = client.goto_definition(norm_path, line, col)
                if lsp_defs:
                    return lsp_defs

        # 3. Level 2: Tree-sitter AST symbol resolution
        if symbol_name:
            ts_locs = self._resolve_treesitter_symbol(symbol_name, norm_path)
            if ts_locs:
                return ts_locs

        # 4. Level 1: Base Text Search Fallback
        if symbol_name:
            text_locs = self.text_analyzer.find_matches(
                symbol_name, max_results=20, is_definition_guess=True
            )
            if text_locs:
                return text_locs

        return []

    # ------------------------------------------------------------------
    # Query: Find References
    # ------------------------------------------------------------------
    def find_references(
        self,
        file_path: str,
        line: int,
        col: int,
        current_line_text: str = "",
        symbol_name: str = "",
    ) -> List[LspLocation]:
        """Find references across LSP semantics, OpenAPI contracts, and text occurrences."""
        norm_path = str(Path(file_path).resolve())
        results: List[LspLocation] = []

        # 1. OpenAPI Cross-Language References
        openapi_links = self.openapi_bridge.find_cross_language_links(norm_path, line, col, current_line_text)
        results.extend(openapi_links)

        # 2. Level 3: LSP Semantic References
        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._get_or_start_lsp(spec)
            if client:
                lsp_refs = client.find_references(norm_path, line, col)
                results.extend(lsp_refs)

        # 3. Level 1 / Level 2 Text Occurrences (Marked distinctly)
        if symbol_name and len(results) < 50:
            text_matches = self.text_analyzer.find_matches(symbol_name, max_results=50)
            # Avoid duplicates of exact same file and line
            existing_coords = {(loc.file_path, loc.line) for loc in results}
            for tm in text_matches:
                if (tm.file_path, tm.line) not in existing_coords:
                    results.append(tm)

        return results

    # ------------------------------------------------------------------
    # Query: Call Hierarchy
    # ------------------------------------------------------------------
    def get_call_hierarchy(self, file_path: str, line: int, col: int) -> Tuple[List[LspCallItem], List[LspCallItem]]:
        """Return (incoming_calls, outgoing_calls)."""
        norm_path = str(Path(file_path).resolve())
        spec = self.registry.get_by_path(norm_path)
        if spec:
            client = self._get_or_start_lsp(spec)
            if client:
                incoming, outgoing = client.call_hierarchy(norm_path, line, col)
                if incoming or outgoing:
                    return incoming, outgoing
        return [], []

    # ------------------------------------------------------------------
    # Query: Language Status & Tool Assistance
    # ------------------------------------------------------------------
    def get_language_status(self, file_path: str) -> Dict[str, Any]:
        """Return diagnostic status of analysis levels available for file."""
        norm_path = str(Path(file_path).resolve())
        spec = self.registry.get_by_path(norm_path)

        if not spec:
            return {
                "lang_id": "plaintext",
                "display_name": "Текст",
                "level": AnalysisLevel.TEXT,
                "badge": "Текст",
                "treesitter": False,
                "lsp_active": False,
                "server_name": None,
                "install_hint": "Для этого файла доступен базовый поиск по тексту.",
            }

        client = self._lsp_clients.get(spec.id)
        lsp_active = client is not None and client.is_alive and client.is_initialized

        configured_path = None
        try:
            from utils.settings_manager import get_settings_manager
            sm = get_settings_manager()
            configured_path = sm.get_setting(f"lsp_{spec.id}_path") or sm.get_setting(f"toolchain_{spec.toolchain_key}_path")
        except Exception:
            pass

        server_exe, _ = self.registry.resolve_lsp_server(spec, configured_path=configured_path)
        server_found = bool(server_exe)

        level = AnalysisLevel.SEMANTIC if lsp_active else AnalysisLevel.SYNTAX

        badge = f"{spec.display_name} (LSP)" if lsp_active else f"{spec.display_name} (Синтаксис)"

        return {
            "lang_id": spec.id,
            "display_name": spec.display_name,
            "level": level,
            "badge": badge,
            "treesitter": True,
            "lsp_active": lsp_active,
            "server_found": server_found,
            "server_name": Path(server_exe).name if server_exe else None,
            "install_hint": spec.install_hint if not server_found else "",
        }

    # ------------------------------------------------------------------
    # Helper: Tree-sitter symbol resolution
    # ------------------------------------------------------------------
    def _resolve_treesitter_symbol(self, symbol_name: str, current_file: str) -> List[LspLocation]:
        locations: List[LspLocation] = []

        # First check current file
        syms = self.get_file_structure(current_file)
        for s in syms:
            if s.name == symbol_name and s.kind in ("class", "function", "method", "struct", "interface", "enum", "type"):
                locations.append(LspLocation(
                    file_path=current_file,
                    line=s.line,
                    col=s.col,
                    end_line=s.end_line,
                    end_col=s.end_col,
                    preview=s.signature or s.name,
                    kind="syntax",
                    badge="[Синтаксическое определение (Tree-sitter)]",
                ))

        if locations:
            return locations

        # Check other open files in memory
        for fpath, (_, text) in self._file_buffers.items():
            if fpath == current_file:
                continue
            syms = self.get_file_structure(fpath, text=text)
            for s in syms:
                if s.name == symbol_name and s.kind in ("class", "function", "method", "struct", "interface", "enum", "type"):
                    locations.append(LspLocation(
                        file_path=fpath,
                        line=s.line,
                        col=s.col,
                        end_line=s.end_line,
                        end_col=s.end_col,
                        preview=s.signature or s.name,
                        kind="syntax",
                        badge="[Синтаксическое определение (Tree-sitter)]",
                    ))
                    if len(locations) >= 10:
                        return locations

        return locations


_GLOBAL_SERVICE: Optional[UnifiedCodeAnalysisService] = None


def get_code_analysis_service() -> UnifiedCodeAnalysisService:
    global _GLOBAL_SERVICE
    if _GLOBAL_SERVICE is None:
        _GLOBAL_SERVICE = UnifiedCodeAnalysisService()
    return _GLOBAL_SERVICE
