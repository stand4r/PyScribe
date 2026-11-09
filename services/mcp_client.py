"""Minimal Model Context Protocol (MCP) client for the PyScribe AI agent.

Supports both transports that the ecosystem actually uses:

* **stdio** — a local command line (``npx -y @modelcontextprotocol/server-filesystem .``),
  spoken to with newline-delimited JSON-RPC 2.0 over stdin/stdout.
* **http** — the "streamable HTTP" transport, where each JSON-RPC message is a
  single POST to the server URL and the reply is either ``application/json`` or
  an SSE stream.

Only the standard library is used. The client implements the subset an IDE
assistant needs: ``initialize`` → ``tools/list`` → ``tools/call``.

MCP servers are configured in *Настройки → ИИ-агент → MCP-серверы* as JSON:

```json
[
  {"name": "files", "transport": "stdio", "command": "npx",
   "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
  {"name": "docs", "transport": "http", "url": "http://localhost:3001/mcp"}
]
```
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.subprocess_utils import popen_hidden

__all__ = [
    "MCPError",
    "MCPServerConfig",
    "MCPClient",
    "MCPTool",
    "parse_servers",
    "run_tool",
]

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "PyScribe", "version": "1.0"}


class MCPError(RuntimeError):
    """Raised when an MCP server cannot be reached or returns an error."""


@dataclass
class MCPTool:
    """A tool advertised by an MCP server."""

    server: str
    name: str
    description: str = ""
    schema: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        # Namespaced so two servers can expose the same tool name.
        return f"{self.server}__{self.name}"

    def as_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.full_name,
                "description": (self.description or self.name)[:1024],
                "parameters": self.schema or {"type": "object", "properties": {}},
            },
        }


@dataclass
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @property
    def label(self) -> str:
        return self.name or (self.command or self.url or "mcp")


def parse_servers(text: str) -> List[MCPServerConfig]:
    """Parse the JSON configuration typed in Settings into server configs."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MCPError(f"Некорректный JSON конфигурации MCP: {exc}") from None
    if isinstance(data, dict):
        data = data.get("mcpServers") or data.get("servers") or []
    # The standard MCP config form is a *map*: {"mcpServers": {"files": {...}}}.
    # Convert it to the list form, using the map key as the server name.
    if isinstance(data, dict):
        named = []
        for name, item in data.items():
            if isinstance(item, dict):
                entry = dict(item)
                entry.setdefault("name", name)
                named.append(entry)
        data = named
    if not isinstance(data, list):
        raise MCPError("Ожидался список MCP-серверов в формате JSON.")
    servers = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "").strip()
        url = str(item.get("url") or "").strip()
        transport = str(item.get("transport") or ("http" if url and not command else "stdio"))
        servers.append(MCPServerConfig(
            name=str(item.get("name") or item.get("id") or f"mcp{index + 1}"),
            transport=transport,
            command=command,
            args=[str(a) for a in (item.get("args") or [])],
            url=url,
            env={str(k): str(v) for k, v in (item.get("env") or {}).items()},
            enabled=item.get("enabled", True) is not False,
        ))
    return servers


class MCPClient:
    """A single MCP server connection (stdio process or HTTP endpoint)."""

    def __init__(self, config: MCPServerConfig, timeout: float = 25.0):
        self.config = config
        self.timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: Dict[int, Any] = {}
        self._reader: Optional[threading.Thread] = None
        self._buffer: List[str] = []
        self._stderr: List[str] = []
        self.tools: List[MCPTool] = []
        self.server_info: Dict[str, Any] = {}
        self.initialized = False

    # ------------------------------------------------------------------
    # Transport: stdio
    # ------------------------------------------------------------------
    def _start_stdio(self):
        if self._proc is not None:
            return
        if not self.config.command:
            raise MCPError(f"MCP «{self.config.label}»: не задана команда запуска.")
        env = dict(os.environ)
        env.update(self.config.env or {})
        try:
            self._proc = popen_hidden(
                [self.config.command] + list(self.config.args or []),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError:
            raise MCPError(
                f"MCP «{self.config.label}»: команда «{self.config.command}» не найдена. "
                "Установите её (например, Node.js для npx) и проверьте путь."
            ) from None
        except OSError as exc:
            raise MCPError(f"MCP «{self.config.label}»: не удалось запустить — {exc}") from None
        self._reader = threading.Thread(target=self._pump_stdout, daemon=True)
        self._reader.start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self):
        for line in self._proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._dispatch(message)

    def _pump_stderr(self):
        for line in self._proc.stderr:  # type: ignore[union-attr]
            text = line.strip()
            if text:
                self._stderr.append(text)
                del self._stderr[:-40]

    def _dispatch(self, message: Dict[str, Any]):
        if "id" in message and ("result" in message or "error" in message):
            self._pending[message["id"]] = message
        # Server-initiated requests (sampling/roots) are answered minimally so
        # servers that probe the client do not hang.
        elif "method" in message and "id" in message:
            self._reply(message["id"], {})

    def _reply(self, message_id, result):
        try:
            self._write({"jsonrpc": "2.0", "id": message_id, "result": result})
        except Exception:
            pass

    def _write(self, payload: Dict[str, Any]):
        if self._proc is None or self._proc.stdin is None:
            raise MCPError("MCP-процесс не запущен.")
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    # ------------------------------------------------------------------
    # Transport: HTTP (streamable)
    # ------------------------------------------------------------------
    def _post_http(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import urllib.error
        import urllib.request

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.config.url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise MCPError(f"MCP «{self.config.label}»: HTTP {exc.code}") from None
        except Exception as exc:  # noqa: BLE001
            raise MCPError(f"MCP «{self.config.label}»: нет соединения — {exc}") from None
        if "text/event-stream" in ctype:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        message = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if isinstance(message, dict) and message.get("id") == payload.get("id"):
                        return message
            return {}
        try:
            return json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            raise MCPError(f"MCP «{self.config.label}»: ответ не является JSON.") from None

    # ------------------------------------------------------------------
    # JSON-RPC core
    # ------------------------------------------------------------------
    def request(self, method: str, params: Optional[Dict[str, Any]] = None,
                timeout: Optional[float] = None) -> Dict[str, Any]:
        limit = timeout or self.timeout
        with self._lock:
            message_id = self._next_id
            self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": message_id, "method": method,
                   "params": params or {}}

        if self.config.transport == "http":
            reply = self._post_http(payload)
        else:
            self._start_stdio()
            self._write(payload)
            deadline = time.time() + limit
            while time.time() < deadline:
                reply = self._pending.pop(message_id, None)
                if reply is not None:
                    break
                if self._proc is not None and self._proc.poll() is not None:
                    detail = " | ".join(self._stderr[-3:])
                    raise MCPError(
                        f"MCP «{self.config.label}» завершился: {detail or 'без описания'}"
                    )
                time.sleep(0.01)
            else:
                raise MCPError(
                    f"MCP «{self.config.label}» не ответил за {limit:.0f} с."
                )
        if "error" in reply:
            error = reply["error"] or {}
            raise MCPError(f"MCP «{self.config.label}»: {error.get('message', error)}")
        return reply.get("result") or {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> List[MCPTool]:
        """Handshake with the server and return its tools."""
        source = self.config.command if self.config.transport == "stdio" else self.config.url
        self.stderr_hint = ""
        result = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"roots": {"listChanged": False}, "tools": {}},
            "clientInfo": CLIENT_INFO,
        })
        self.server_info = result.get("serverInfo") or {}
        self.initialized = True
        # The spec requires a notification after initialize (no id, no reply).
        if self.config.transport != "http":
            try:
                self._write({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            except Exception:
                pass
        self.tools = self.list_tools()
        del source
        return self.tools

    def list_tools(self) -> List[MCPTool]:
        result = self.request("tools/list", {})
        tools = []
        for item in result.get("tools") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            tools.append(MCPTool(
                server=self.config.name,
                name=str(item["name"]),
                description=str(item.get("description") or ""),
                schema=item.get("inputSchema") or {},
            ))
        return tools

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        chunks: List[str] = []
        for item in result.get("content") or []:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text") or ""))
                elif item.get("type") == "resource":
                    resource = item.get("resource") or {}
                    chunks.append(str(resource.get("text") or resource.get("uri") or ""))
                else:
                    chunks.append(json.dumps(item, ensure_ascii=False)[:2000])
            else:
                chunks.append(str(item))
        if result.get("isError"):
            return "Ошибка инструмента: " + ("\n".join(chunks) or "без описания")
        return "\n".join(c for c in chunks if c).strip() or "Готово."

    def close(self):
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ----------------------------------------------------------------------
# Helpers used by the agent loop
# ----------------------------------------------------------------------
def run_tool(servers: Dict[str, MCPClient], tool_name: str,
             arguments: Dict[str, Any]) -> str:
    """Execute ``server__tool`` through the matching live client."""
    if "__" not in tool_name:
        return f"Неизвестный инструмент: {tool_name}"
    server_key, name = tool_name.split("__", 1)
    client = servers.get(server_key)
    if client is None:
        return f"Сервер MCP «{server_key}» не подключён."
    return client.call_tool(name, arguments)
