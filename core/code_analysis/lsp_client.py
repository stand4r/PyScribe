"""Level 3: Language Server Protocol (LSP) Client for PyScribe.

Implements JSON-RPC over stdio communication with language servers:
- Asynchronous non-blocking message reading in background thread.
- Lifecycle: initialize, initialized, didOpen, didChange, didSave, didClose, shutdown, exit.
- Features: definition (F12), references (Shift+F12), documentSymbol, diagnostics, call hierarchy.
- Robust Windows URI parsing supporting spaces, Cyrillic, and drive letters.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def path_to_uri(path: Union[str, Path]) -> str:
    """Convert a file system path to a valid file:// URI."""
    try:
        p = Path(path).resolve()
        return p.as_uri()
    except Exception:
        clean = str(path).replace("\\", "/")
        if not clean.startswith("/"):
            clean = "/" + clean
        return "file://" + urllib.parse.quote(clean)


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a local absolute file system path."""
    parsed = urllib.parse.urlparse(uri)
    raw_path = urllib.parse.unquote(parsed.path)
    # On Windows, urlparse('/C:/path') yields '/C:/path'
    if sys.platform == "win32" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return str(Path(raw_path).resolve())


@dataclass
class LspLocation:
    """Represents a source code location returned by LSP or fallback."""
    file_path: str
    line: int          # 1-based
    col: int = 0       # 0-based
    end_line: int = 0
    end_col: int = 0
    preview: str = ""
    kind: str = "semantic"  # semantic, openapi, syntax, text
    badge: str = "[Семантический переход]"


@dataclass
class LspDiagnostic:
    """Represents a diagnostic issue from a language server."""
    file_path: str
    line: int          # 1-based
    col: int = 0       # 0-based
    end_line: int = 0
    end_col: int = 0
    severity: str = "info"  # error, warning, info, hint
    message: str = ""
    source: str = ""
    code: Optional[str] = None


@dataclass
class LspCallItem:
    """Represents a call in the call hierarchy."""
    name: str
    kind: str
    file_path: str
    line: int
    col: int
    direction: str = "incoming"  # incoming or outgoing
    caller_or_callee_name: str = ""


class LspClient:
    """Manages an individual language server subprocess over stdio."""

    def __init__(
        self,
        lang_id: str,
        server_path: str,
        server_args: List[str],
        root_path: str,
        on_diagnostics: Optional[Callable[[str, List[LspDiagnostic]], None]] = None,
        on_exit: Optional[Callable[[str, int], None]] = None,
    ):
        self.lang_id = lang_id
        self.server_path = server_path
        self.server_args = list(server_args)
        self.root_path = str(Path(root_path).resolve()) if root_path else ""
        self.on_diagnostics = on_diagnostics
        self.on_exit = on_exit

        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._next_id = 1
        self._id_lock = threading.Lock()
        self._pending_requests: Dict[int, Tuple[threading.Event, Dict[str, Any]]] = {}
        self._server_capabilities: Dict[str, Any] = {}
        self._is_initialized = False
        self._is_shutting_down = False
        self._open_documents: Dict[str, int] = {}  # uri -> version

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def capabilities(self) -> Dict[str, Any]:
        return dict(self._server_capabilities)

    def start(self, timeout: float = 10.0) -> bool:
        """Spawn the language server process and perform initialization."""
        try:
            cmd = [self.server_path, *self.server_args]
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            cwd = self.root_path if self.root_path and os.path.isdir(self.root_path) else None

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                creationflags=creationflags,
                bufsize=0,
            )

            self._reader_thread = threading.Thread(
                target=self._read_loop,
                name=f"lsp-{self.lang_id}-reader",
                daemon=True,
            )
            self._reader_thread.start()

            # Perform initialize request
            root_uri = path_to_uri(self.root_path) if self.root_path else None
            init_params = {
                "processId": os.getpid(),
                "rootUri": root_uri,
                "rootPath": self.root_path or None,
                "capabilities": {
                    "textDocument": {
                        "synchronization": {
                            "dynamicRegistration": False,
                            "willSave": False,
                            "didSave": True,
                        },
                        "definition": {"dynamicRegistration": False},
                        "references": {"dynamicRegistration": False},
                        "publishDiagnostics": {"relatedInformation": True},
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "callHierarchy": {"dynamicRegistration": False},
                    },
                    "workspace": {
                        "workspaceFolders": True,
                    },
                },
                "workspaceFolders": [{"name": Path(self.root_path).name, "uri": root_uri}] if root_uri else None,
            }

            resp = self._send_request("initialize", init_params, timeout=timeout)
            if resp and "result" in resp:
                self._server_capabilities = resp["result"].get("capabilities", {})
                self._send_notification("initialized", {})
                self._is_initialized = True
                logger.info("LSP server initialized for %s (%s)", self.lang_id, self.server_path)
                return True
            else:
                logger.warning("LSP initialize failed for %s: %s", self.lang_id, resp)
                return False

        except Exception as exc:
            logger.warning("Failed to start LSP server for %s (%s): %s", self.lang_id, self.server_path, exc)
            return False

    def did_open(self, file_path: str, language_id_or_text: str, text: Optional[str] = None, version: int = 1) -> None:
        """Notify server that a document was opened."""
        if not self.is_alive or not self._is_initialized:
            return
        if text is None:
            text = language_id_or_text
            language_id = self.lang_id
        else:
            language_id = language_id_or_text

        uri = path_to_uri(file_path)
        self._open_documents[uri] = version
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text,
            }
        }
        self._send_notification("textDocument/didOpen", params)

    def did_change(self, file_path: str, text: str, version: Optional[int] = None) -> None:
        """Notify server that document content changed."""
        if not self.is_alive or not self._is_initialized:
            return
        uri = path_to_uri(file_path)
        ver = version or (self._open_documents.get(uri, 0) + 1)
        self._open_documents[uri] = ver
        params = {
            "textDocument": {
                "uri": uri,
                "version": ver,
            },
            "contentChanges": [
                {"text": text}
            ],
        }
        self._send_notification("textDocument/didChange", params)

    def did_save(self, file_path: str, text: Optional[str] = None) -> None:
        if not self.is_alive or not self._is_initialized:
            return
        uri = path_to_uri(file_path)
        params: Dict[str, Any] = {"textDocument": {"uri": uri}}
        if text is not None:
            params["text"] = text
        self._send_notification("textDocument/didSave", params)

    def did_close(self, file_path: str) -> None:
        if not self.is_alive or not self._is_initialized:
            return
        uri = path_to_uri(file_path)
        self._open_documents.pop(uri, None)
        self._send_notification("textDocument/didClose", {"textDocument": {"uri": uri}})

    def goto_definition(self, file_path: str, line: int, col: int, timeout: float = 4.0) -> List[LspLocation]:
        """Request textDocument/definition and return normalized locations."""
        if not self.is_alive or not self._is_initialized:
            return []
        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": max(0, line - 1), "character": max(0, col)},
        }
        resp = self._send_request("textDocument/definition", params, timeout=timeout)
        if not resp or "result" not in resp or resp["result"] is None:
            return []
        return self._normalize_locations(resp["result"], default_badge="[LSP Определение]")

    definition = goto_definition

    def find_references(self, file_path: str, line: int, col: int, timeout: float = 4.0) -> List[LspLocation]:
        """Request textDocument/references and return normalized locations."""
        if not self.is_alive or not self._is_initialized:
            return []
        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": max(0, line - 1), "character": max(0, col)},
            "context": {"includeDeclaration": True},
        }
        resp = self._send_request("textDocument/references", params, timeout=timeout)
        if not resp or "result" not in resp or resp["result"] is None:
            return []
        return self._normalize_locations(resp["result"], default_badge="[LSP Ссылка]")

    references = find_references

    def document_symbols(self, file_path: str, timeout: float = 4.0) -> List[Dict[str, Any]]:
        """Request textDocument/documentSymbol."""
        if not self.is_alive or not self._is_initialized:
            return []
        uri = path_to_uri(file_path)
        params = {"textDocument": {"uri": uri}}
        resp = self._send_request("textDocument/documentSymbol", params, timeout=timeout)
        if not resp or "result" not in resp or not resp["result"]:
            return []
        return resp["result"]

    def call_hierarchy(self, file_path: str, line: int, col: int, timeout: float = 4.0) -> Tuple[List[LspCallItem], List[LspCallItem]]:
        """Request incoming and outgoing call hierarchy when supported."""
        incoming: List[LspCallItem] = []
        outgoing: List[LspCallItem] = []
        if not self.is_alive or not self._is_initialized:
            return incoming, outgoing

        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": max(0, line - 1), "character": max(0, col)},
        }
        resp = self._send_request("textDocument/prepareCallHierarchy", params, timeout=timeout)
        if not resp or "result" not in resp or not resp["result"]:
            return incoming, outgoing

        items = resp["result"]
        first_item = items[0] if isinstance(items, list) and items else items
        if not isinstance(first_item, dict):
            return incoming, outgoing

        # 1. Incoming calls
        inc_resp = self._send_request("callHierarchy/incomingCalls", {"item": first_item}, timeout=timeout)
        if inc_resp and "result" in inc_resp and isinstance(inc_resp["result"], list):
            for inc in inc_resp["result"]:
                from_item = inc.get("from", {})
                ranges = inc.get("fromRanges", [])
                r = ranges[0] if ranges else from_item.get("range", {}).get("start", {})
                line_no = (r.get("start", {}).get("line") if "start" in r else r.get("line", 0)) + 1
                col_no = (r.get("start", {}).get("character") if "start" in r else r.get("character", 0))
                incoming.append(LspCallItem(
                    name=from_item.get("name", ""),
                    kind=self._symbol_kind_to_str(from_item.get("kind", 12)),
                    file_path=uri_to_path(from_item.get("uri", "")),
                    line=line_no,
                    col=col_no,
                    direction="incoming",
                    caller_or_callee_name=first_item.get("name", ""),
                ))

        # 2. Outgoing calls
        out_resp = self._send_request("callHierarchy/outgoingCalls", {"item": first_item}, timeout=timeout)
        if out_resp and "result" in out_resp and isinstance(out_resp["result"], list):
            for out in out_resp["result"]:
                to_item = out.get("to", {})
                ranges = out.get("fromRanges", [])
                r = ranges[0] if ranges else to_item.get("range", {}).get("start", {})
                line_no = (r.get("start", {}).get("line") if "start" in r else r.get("line", 0)) + 1
                col_no = (r.get("start", {}).get("character") if "start" in r else r.get("character", 0))
                outgoing.append(LspCallItem(
                    name=to_item.get("name", ""),
                    kind=self._symbol_kind_to_str(to_item.get("kind", 12)),
                    file_path=uri_to_path(to_item.get("uri", "")),
                    line=line_no,
                    col=col_no,
                    direction="outgoing",
                    caller_or_callee_name=first_item.get("name", ""),
                ))

        return incoming, outgoing

    def shutdown_and_exit(self, timeout: float = 2.0) -> None:
        """Gracefully shutdown and terminate server process."""
        self._is_shutting_down = True
        if self.is_alive and self._is_initialized:
            try:
                self._send_request("shutdown", {}, timeout=timeout)
                self._send_notification("exit", {})
            except Exception:
                pass

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    # ------------------------------------------------------------------
    # JSON-RPC Protocol Internals
    # ------------------------------------------------------------------
    def _send_request(self, method: str, params: Any, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        if not self.is_alive:
            return None

        with self._id_lock:
            req_id = self._next_id
            self._next_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        event = threading.Event()
        resp_holder: Dict[str, Any] = {}
        self._pending_requests[req_id] = (event, resp_holder)

        self._write_message(payload)

        # Wait for reply
        signaled = event.wait(timeout=timeout)
        self._pending_requests.pop(req_id, None)

        if not signaled:
            logger.debug("LSP request %s (id %s) timed out", method, req_id)
            return None
        return resp_holder.get("data")

    def _send_notification(self, method: str, params: Any) -> None:
        if not self.is_alive:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._write_message(payload)

    def _write_message(self, message: Dict[str, Any]) -> None:
        try:
            body = json.dumps(message, ensure_ascii=False).encode("utf-8")
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            if self._process and self._process.stdin:
                self._process.stdin.write(header + body)
                self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            logger.debug("LSP write failed for %s: %s", self.lang_id, exc)

    def _read_loop(self) -> None:
        """Background thread loop parsing Content-Length framed JSON-RPC messages."""
        stdout = self._process.stdout if self._process else None
        if not stdout:
            return

        buffer = bytearray()
        while self.is_alive and not self._is_shutting_down:
            try:
                line = stdout.readline()
                if not line:
                    break

                if line.startswith(b"Content-Length:"):
                    length = int(line.split(b":")[1].strip())
                    # Read until empty line \r\n
                    while True:
                        sep = stdout.readline()
                        if sep in (b"\r\n", b"\n", b""):
                            break

                    body = stdout.read(length)
                    if not body:
                        break

                    try:
                        msg = json.loads(body.decode("utf-8", errors="replace"))
                        self._handle_incoming_message(msg)
                    except Exception as exc:
                        logger.debug("LSP JSON decode error: %s", exc)

            except Exception as exc:
                if not self._is_shutting_down:
                    logger.debug("LSP read error: %s", exc)
                break

        exit_code = self._process.poll() if self._process else 0
        if self.on_exit and not self._is_shutting_down:
            self.on_exit(self.lang_id, exit_code or 0)

    def _handle_incoming_message(self, msg: Dict[str, Any]) -> None:
        # 1. Response to our request
        if "id" in msg and msg["id"] in self._pending_requests:
            event, holder = self._pending_requests[msg["id"]]
            holder["data"] = msg
            event.set()
            return

        # 2. Server notifications
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "textDocument/publishDiagnostics":
            self._handle_diagnostics(params)

    def _handle_diagnostics(self, params: Dict[str, Any]) -> None:
        uri = params.get("uri", "")
        file_path = uri_to_path(uri)
        raw_diagnostics = params.get("diagnostics", [])
        diagnostics: List[LspDiagnostic] = []

        sev_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        for d in raw_diagnostics:
            rng = d.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            start_l = start.get("line", 0) + 1
            start_c = start.get("character", 0)
            end_l = end.get("line", start_l - 1) + 1
            end_c = end.get("character", start_c)
            sev = sev_map.get(d.get("severity", 1), "error")
            msg = d.get("message", "").strip()
            source = d.get("source", self.lang_id)
            code = str(d.get("code")) if d.get("code") is not None else None

            diagnostics.append(LspDiagnostic(
                file_path=file_path,
                line=start_l,
                col=start_c,
                end_line=end_l,
                end_col=end_c,
                severity=sev,
                message=msg,
                source=source,
                code=code,
            ))

        if self.on_diagnostics:
            self.on_diagnostics(file_path, diagnostics)

    def _normalize_locations(self, result: Any, default_badge: str = "[LSP]") -> List[LspLocation]:
        """Convert LSP Location, LocationLink, or list into LspLocation objects."""
        items = result if isinstance(result, list) else [result]
        locations: List[LspLocation] = []

        for it in items:
            if not isinstance(it, dict):
                continue

            uri = it.get("uri") or it.get("targetUri")
            if not uri:
                continue

            rng = it.get("range") or it.get("targetSelectionRange") or it.get("targetRange") or {}
            start = rng.get("start", {})
            end = rng.get("end", {})
            start_l = start.get("line", 0) + 1
            start_c = start.get("character", 0)
            end_l = end.get("line", start_l - 1) + 1
            end_c = end.get("character", start_c)

            path = uri_to_path(uri)
            preview = self._extract_preview(path, start_l)

            locations.append(LspLocation(
                file_path=path,
                line=start_l,
                col=start_c,
                end_line=end_l,
                end_col=end_c,
                preview=preview,
                kind="semantic",
                badge=default_badge,
            ))

        return locations

    def _extract_preview(self, file_path: str, line: int) -> str:
        try:
            p = Path(file_path)
            if p.is_file():
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                if 0 <= line - 1 < len(lines):
                    return lines[line - 1].strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _symbol_kind_to_str(kind: int) -> str:
        mapping = {
            1: "file", 2: "module", 3: "namespace", 4: "package", 5: "class",
            6: "method", 7: "property", 8: "field", 9: "constructor", 10: "enum",
            11: "interface", 12: "function", 13: "variable", 14: "constant",
            23: "struct", 26: "type",
        }
        return mapping.get(kind, "symbol")
