"""Tests for the AI agent service and the global UI scale (accessibility)."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ----------------------------------------------------------------------
# Mock OpenAI-compatible server
# ----------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.endswith("/models"):
            body = json.dumps({"data": [{"id": "mock-a"}, {"id": "mock-b"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).requests.append({
            "path": self.path,
            "payload": payload,
            "auth": self.headers.get("Authorization"),
        })
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for piece in ("Привет", ", мир"):
                chunk = {"choices": [{"delta": {"content": piece}}]}
                self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        body = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def _config(port, **overrides):
    cfg = {
        "ai_enabled": True,
        # "custom" = generic OpenAI-compatible server: no provider-specific key
        # shape checks, which is exactly what the mock server is.
        "ai_provider": "custom",
        "ai_base_url": f"http://127.0.0.1:{port}/v1",
        "ai_model": "mock-a",
        "ai_api_key": "secret-key",
        "ai_temperature": 3,
        "ai_max_tokens": 256,
    }
    cfg.update(overrides)
    return cfg


# ----------------------------------------------------------------------
# AI service
# ----------------------------------------------------------------------
def test_ai_complete_and_stream():
    from services.ai_service import AIService
    server, port = _start_server()
    try:
        service = AIService(config=_config(port))
        assert service.configuration_problem() is None
        assert service.complete("hi") == "OK"
        text = "".join(service.stream("hi"))
        assert text == "Привет, мир"
        last = _Handler.requests[-1]
        assert last["path"] == "/v1/chat/completions"
        assert last["auth"] == "Bearer secret-key"
        assert last["payload"]["model"] == "mock-a"
        # temperature is stored as 0..20 ints and exposed as 0..2 floats
        assert abs(last["payload"]["temperature"] - 0.3) < 1e-6
    finally:
        server.shutdown()


def test_ai_configuration_validation():
    from services.ai_service import AIService
    disabled = AIService(config={"ai_enabled": False}).configuration_problem()
    assert disabled and ("отключ" in disabled)
    no_url = AIService(config={"ai_model": "m", "ai_api_key": "k", "ai_base_url": ""}).configuration_problem()
    assert no_url and ("URL" in no_url)
    # A missing key falls back to the default provider URL.
    assert AIService(config={"ai_model": "m", "ai_api_key": "k"}).base_url.startswith("https://")
    no_key = AIService(config={"ai_base_url": "https://api.example.com/v1",
                               "ai_model": "m"}).configuration_problem()
    assert no_key and ("ключ" in no_key)
    # local providers do not need a key
    local = AIService(config={"ai_base_url": "http://localhost:1234/v1", "ai_model": "m"})
    assert local.configuration_problem() is None
    assert local.requires_api_key() is False


def test_ai_error_message_is_friendly():
    from services.ai_service import AIService, AIError
    service = AIService(config=_config(9))  # nothing listens on port 9
    try:
        service.complete("hi")
    except AIError as exc:
        assert "соединени" in str(exc).lower() or "подключ" in str(exc).lower()
    else:
        raise AssertionError("expected AIError")


def test_ai_context_and_extraction():
    from services.ai_service import AIService, extract_code_blocks
    ctx = AIService.build_context_block("C:/p/a.py", "print(1)", "python", "print(1)", ["E1: x"])
    assert "<context>" in ctx and "a.py" in ctx and "E1: x" in ctx
    assert extract_code_blocks("text\n```python\nprint(1)\n```\n") == ["print(1)"]


def test_ai_panel_streams_against_mock():
    import time
    from services.ai_service import extract_code_blocks
    from utils.settings_manager import init_settings_manager, get_settings_manager
    server, port = _start_server()
    try:
        try:
            init_settings_manager(ROOT)
        except Exception:
            pass
        get_settings_manager().settings.update(_config(port))
        from widgets.AIAgentPanel import AIAgentPanel
        panel = AIAgentPanel(None)
        panel.show()
        panel.input.setPlainText("привет")
        panel.send_message()
        deadline = time.time() + 15
        while time.time() < deadline:
            _APP.processEvents()
            if panel._worker is None and panel._history:
                break
            time.sleep(0.02)
        _APP.processEvents()
        assert panel._history, "the answer must be appended to the conversation"
        assert "Привет" in panel.transcript_text()
        assert extract_code_blocks("```py\nx=1\n```") == ["x=1"]
    finally:
        server.shutdown()


def test_ai_panel_renders_user_bubble_widget():
    """User messages are real rounded widgets embedded in the transcript."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    panel.resize(380, 600)
    panel.show()
    _APP.processEvents()
    panel._append_user("Проверь функцию greet")
    for _ in range(10):
        _APP.processEvents()
    widgets = panel.findChildren(panel_module._UserBubble)
    assert widgets, "a user bubble widget must be embedded"
    assert "greet" in widgets[-1].label.text()
    assert widgets[-1].side == "out"
    # The bubble is really part of the message list, not a detached widget.
    assert widgets[-1].parent() is not None
    assert panel.messages.indexOf(widgets[-1]) >= 0


def test_ai_markdown_is_split_into_text_and_code():
    """Code fences become editor-backed widgets, prose stays rich text."""
    from widgets.ChatMessage import split_markdown_blocks
    blocks = split_markdown_blocks("text\n```python\nprint(1)\n```\nafter")
    kinds = [kind for kind, _ in blocks]
    assert kinds == ["text", "code", "text"], kinds
    language, code = blocks[1][1]
    assert language == "python"
    assert "print(1)" in code
    # Prose carries no <pre> and no leftover fences.
    prose = "".join(payload for kind, payload in blocks if kind == "text")
    assert "<pre" not in prose
    assert "```" not in prose
    assert "after" in prose


def test_ai_key_shape_diagnostics():
    """Wrong *shapes* of key are explained instead of a bare provider 401."""
    from services.ai_service import AIService, AIError

    base = {"ai_enabled": True, "ai_provider": "deepseek",
            "ai_base_url": "https://api.deepseek.com/v1",
            "ai_model": "deepseek-chat"}

    # The real support case: a UUID (a key *id*, not a key) was pasted.
    uuid_key = "3e0ff2db-f9cb-4888-ba7d-be13b833ffb0"
    svc = AIService(config={**base, "ai_api_key": uuid_key})
    assert svc.api_key == uuid_key
    assert "UUID" in svc.key_looks_like()
    problem = svc.configuration_problem()
    assert problem and "UUID" in problem and "sk-" in problem

    # A valid-looking key passes validation.
    assert AIService(config={**base, "ai_api_key": "sk-" + "a" * 32}).configuration_problem() is None

    # A "Bearer " prefix is stripped automatically instead of causing a 401.
    bearer = AIService(config={**base, "ai_api_key": "Bearer sk-" + "b" * 32})
    assert bearer.api_key == "sk-" + "b" * 32
    assert bearer.configuration_problem() is None

    # Pasted parameter names and URLs are rejected with advice.
    assert "api_key=" in AIService(config={**base, "ai_api_key": "api_key=sk-abc"}).key_format_problem()
    assert "URL" in AIService(config={**base, "ai_api_key": "https://x.y/keys"}).key_format_problem()

    # The 401 text names the problem and echoes the provider's masked tail.
    message = svc._describe_401("Authentication Fails, Your api key: ****ffb0 is invalid")
    assert "401" in message and "sk-" in message and "ffb0" in message


def test_ai_http_401_is_actionable():
    from services.ai_service import AIService, AIError
    svc = AIService(config={"ai_enabled": True, "ai_base_url": "https://api.deepseek.com/v1",
                            "ai_model": "deepseek-chat",
                            "ai_api_key": "3e0ff2db-f9cb-4888-ba7d-be13b833ffb0"})
    err = svc._friendly_http_error(
        401, '{"error":{"message":"Authentication Fails, Your api key: ****ffb0 is invalid"}}')
    assert isinstance(err, AIError)
    text = str(err)
    assert "UUID" in text and "platform.deepseek.com" in text


# ----------------------------------------------------------------------
# UI scale
# ----------------------------------------------------------------------
def test_provider_registry_covers_requested_services():
    """DeepSeek, OpenAI/ChatGPT, Claude, Gemini, opencode must all exist."""
    from services.ai_providers import PROVIDERS, get_provider
    for key in ("deepseek", "openai", "anthropic", "gemini", "opencode"):
        assert key in PROVIDERS, f"missing provider {key}"
        spec = get_provider(key)
        assert spec.base_url, f"{key} needs a base url"
        assert spec.models, f"{key} needs models"
        assert spec.key_url, f"{key} needs a key page"
    # Claude speaks its own protocol, everything else is OpenAI-compatible.
    assert get_provider("anthropic").kind == "anthropic"
    assert get_provider("gemini").kind == "openai"


def test_free_models_are_offered():
    from services.ai_providers import PROVIDERS
    free = [m for spec in PROVIDERS.values() for m in spec.models if m.free]
    assert len(free) >= 8, "several free models must be advertised"
    assert any(":free" in m.id for m in free)      # OpenRouter
    assert any(m.id.startswith("gemini") for m in free)


def test_anthropic_protocol_uses_native_headers_and_payload():
    from services.ai_service import AIService
    svc = AIService(config={"ai_enabled": True, "ai_provider": "anthropic",
                            "ai_base_url": "https://api.anthropic.com/v1",
                            "ai_model": "claude-sonnet-4-5", "ai_api_key": "sk-ant-test"})
    headers = svc._headers()
    assert headers.get("x-api-key") == "sk-ant-test"
    assert "Authorization" not in headers
    assert headers.get("anthropic-version")
    payload = svc._payload([{"role": "system", "content": "sys"},
                            {"role": "user", "content": "hi"}], stream=True)
    # The system prompt is a cacheable block (prompt caching) for Anthropic.
    system = payload["system"]
    assert isinstance(system, list) and system[0]["text"] == "sys"
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert all(m["role"] != "system" for m in payload["messages"])
    assert svc._endpoint("/messages") == "https://api.anthropic.com/v1/messages"


def test_gemini_key_shape_hint():
    from services.ai_service import AIService
    svc = AIService(config={"ai_enabled": True, "ai_provider": "gemini",
                            "ai_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                            "ai_model": "gemini-2.5-flash", "ai_api_key": "sk-not-google"})
    problem = svc.key_format_problem()
    assert problem and "AIza" in problem


def test_chat_commands_and_mentions_parse():
    from services.ai_commands import COMMANDS, parse_input
    assert len(COMMANDS) >= 10
    parsed = parse_input("/model claude-sonnet-4-5")
    assert parsed.is_command and parsed.command.name == "model"
    assert parsed.command_arg == "claude-sonnet-4-5"
    parsed = parse_input("@src/app.py объясни код")
    assert parsed.mentions == ["src/app.py"]
    assert parsed.text == "объясни код"
    parsed = parse_input("обычный вопрос")
    assert not parsed.is_command and not parsed.mentions


def test_default_context_scope_is_none():
    """An independent request is the default (no project attached)."""
    from utils.settings_manager import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS.get("ai_context_scope") == "none"


def test_mcp_server_config_parsing():
    import json as _json
    from services.mcp_client import parse_servers, MCPError
    cfg = _json.dumps([
        {"name": "files", "transport": "stdio", "command": "npx", "args": ["-y", "srv"]},
        {"name": "docs", "url": "http://localhost:3001/mcp"},
    ])
    servers = parse_servers(cfg)
    assert [s.name for s in servers] == ["files", "docs"]
    assert servers[0].transport == "stdio" and servers[0].command == "npx"
    assert servers[1].transport == "http"
    assert parse_servers("") == []
    try:
        parse_servers("{not json")
    except MCPError:
        pass
    else:
        raise AssertionError("invalid JSON must raise MCPError")


def test_mcp_tool_is_namespaced_for_the_model():
    from services.mcp_client import MCPTool
    tool = MCPTool(server="files", name="read_file", description="read",
                   schema={"type": "object", "properties": {}})
    assert tool.full_name == "files__read_file"
    spec = tool.as_openai_tool()
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "files__read_file"


def test_ai_welcome_is_removed_when_chat_starts():
    """Regression: the greeting hints stayed behind the first message."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    panel.resize(380, 600)
    panel.show()
    _APP.processEvents()
    assert panel._welcome_visible
    assert "Чем помочь" in panel.transcript_text()
    panel._clear_welcome()
    _APP.processEvents()
    assert not panel._welcome_visible
    assert "Чем помочь" not in panel.transcript_text()
    assert "Enter — отправить" not in panel.transcript_text()
    # Clearing twice must be a no-op (and must not hang).
    panel._clear_welcome()


def test_ai_panel_has_model_and_scope_pickers():
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    _APP.processEvents()
    assert panel.model_btn.text()
    assert panel.scope_btn.text() in panel_module.SCOPE_LABELS.values()
    scope_items = [a.text() for a in panel._scope_menu.actions()]
    assert len(scope_items) == 3
    assert any(a.text() for a in panel._model_menu.actions())


def test_deepseek_models_are_current():
    """DeepSeek's current API models are deepseek-flash (V4.1-Flash-1017) and v4-pro."""
    from services.ai_providers import get_provider, models_for
    spec = get_provider("deepseek")
    ids = [m.id for m in spec.models]
    assert "deepseek-flash" in ids
    assert "deepseek-v4-pro" in ids
    flash = next(m for m in spec.models if m.id == "deepseek-flash")
    assert flash.version == "DeepSeek-V4.1-Flash-1017"
    # Retired names must not be offered as first-class choices.
    assert "deepseek-reasoner" not in ids
    assert spec.default_model == "deepseek-flash"
    # The Anthropic-format endpoint is declared for Claude-compatible clients.
    assert spec.anthropic_base_url.endswith("/anthropic")


def test_no_stale_models_advertised():
    """Guard against re-introducing models that providers no longer serve."""
    from services.ai_providers import PROVIDERS
    retired = {
        "deepseek-chat", "deepseek-reasoner", "gpt-4o", "o3-mini",
        "claude-opus-4-1-20250805", "gemini-2.0-flash", "gemini-2.0-flash-lite",
        "mixtral-8x7b-32768",
    }
    offered = {m.id for spec in PROVIDERS.values() for m in spec.models}
    assert not (offered & retired), f"stale models still offered: {offered & retired}"


def test_endpoint_building_matches_each_provider_style():
    from services.ai_service import AIService

    def url(base, provider, path):
        svc = AIService(config={"ai_provider": provider, "ai_base_url": base,
                                "ai_model": "m", "ai_api_key": "k"})
        return svc._endpoint(path)

    # Bare host and explicit /v1 must both work (DeepSeek docs list both).
    assert url("https://api.deepseek.com", "deepseek", "/chat/completions") == \
        "https://api.deepseek.com/v1/chat/completions"
    assert url("https://api.deepseek.com/v1", "deepseek", "/chat/completions") == \
        "https://api.deepseek.com/v1/chat/completions"
    # Gemini's compatibility endpoint keeps its own path.
    assert url("https://generativelanguage.googleapis.com/v1beta/openai", "gemini",
               "/chat/completions").endswith("/v1beta/openai/chat/completions")
    # Anthropic must never grow a /v1 prefix.
    assert url("https://api.anthropic.com/v1", "anthropic", "/messages") == \
        "https://api.anthropic.com/v1/messages"
    assert url("https://api.deepseek.com/anthropic", "anthropic", "/messages") == \
        "https://api.deepseek.com/anthropic/messages"


def test_chat_messages_are_telegram_bubbles():
    """User bubbles align right ("out"), answers align left ("in"), with a stamp."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    panel.resize(420, 600)
    panel.show()
    _APP.processEvents()
    panel._clear_welcome()
    user = panel._append_user("Улучши greet")
    bot = panel._append_assistant("Готово.", mark_thinking=False)
    _APP.processEvents()
    assert user.side == "out" and bot.side == "in"
    # No time stamp: the bubbles stay clean (the design has no message clock).
    assert not hasattr(user, "time_label")
    # Author grouping: the second message from the same author is tighter.
    second = panel._append_assistant("Ещё.", mark_thinking=False)
    assert second._grouped is True
    assert user._grouped is False


def test_reasoning_bubble_is_removed_on_finish():
    """The live "thinking" placeholder must not survive the final answer."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    panel.resize(420, 600)
    panel.show()
    _APP.processEvents()
    panel._clear_welcome()
    panel._append_user("вопрос")
    panel._on_chunk("Думаю про имя. ")
    _APP.processEvents()
    assert panel._thinking_bubble is not None
    assert "Думает" in panel.transcript_text()
    panel._on_finished("вопрос", "Финальный ответ.")
    _APP.processEvents()
    text = panel.transcript_text()
    assert "Думает" not in text, "thinking placeholder must be removed"
    assert "Финальный ответ." in text


def test_context_menu_is_exclusive():
    """Exactly one context scope can be active at a time."""
    from widgets import AIAgentPanel as panel_module
    from utils.settings_manager import init_settings_manager, get_settings_manager
    try:
        init_settings_manager(ROOT)
    except Exception:
        pass
    get_settings_manager().settings["ai_context_scope"] = "none"
    panel = panel_module.AIAgentPanel(None)
    panel._refresh_menus()
    panel._set_scope("file")
    checked = [a.text() for a in panel._scope_menu.actions() if a.isChecked()]
    assert len(checked) == 1, f"expected one checked scope, got {checked}"
    panel._set_scope("project")
    checked = [a.text() for a in panel._scope_menu.actions() if a.isChecked()]
    assert len(checked) == 1


def test_models_hidden_without_api_key():
    """Providers without a key must not appear in the model menu."""
    from widgets import AIAgentPanel as panel_module
    from utils.settings_manager import init_settings_manager, get_settings_manager
    try:
        init_settings_manager(ROOT)
    except Exception:
        pass
    settings = get_settings_manager().settings
    settings.update({"ai_provider": "deepseek", "ai_api_key": "sk-test",
                     "ai_model": "deepseek-flash"})
    panel = panel_module.AIAgentPanel(None)
    panel._refresh_menus()
    labels = " | ".join(a.text() for a in panel._model_menu.actions() if a.text())
    assert "Claude" not in labels, "Claude has no key and must be hidden"
    assert "Google Gemini" not in labels
    assert "OpenAI" not in labels
    assert "DeepSeek Flash" in labels


def test_messages_queue_while_busy():
    """Sending during an answer must queue, not drop, the message."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    panel.resize(420, 600)
    panel.show()
    _APP.processEvents()
    # A live worker means "busy": _send must enqueue instead of starting a new one.
    panel._worker = object()
    try:
        panel._send("второе сообщение", "", None)
        panel._send("третье сообщение", "", None)
        assert panel.pending_count() == 2
        assert panel.queue_chip.isVisible()
        assert "2" in panel.queue_chip.text()
    finally:
        panel._worker = None
    # Draining pops one message and starts it.
    panel._drain_queue()
    _APP.processEvents()
    assert panel.pending_count() == 1


def test_file_scope_is_not_overridden_by_project_sync():
    """Choosing "текущий файл" must survive a project open/close sync."""
    from widgets import AIAgentPanel as panel_module
    from utils.settings_manager import init_settings_manager, get_settings_manager
    try:
        init_settings_manager(ROOT)
    except Exception:
        pass
    panel = panel_module.AIAgentPanel(None)
    panel._set_scope("file")
    assert panel._scope() == "file"
    # No project open: syncing must keep "file", not fall back to none.
    panel.main_window = None
    panel.sync_scope_with_project()
    assert panel._scope() == "file"


def test_projects_file_uses_absolute_writable_path():
    """Regression: projects.json was a relative path → PermissionError on save."""
    from widgets.ProjectManager import ProjectManager
    manager = ProjectManager()
    path = Path(manager.projects_file)
    assert path.is_absolute(), f"projects file must be absolute, got {path}"
    # It must live in the user's profile, never in the working directory.
    assert str(path) != "projects.json"
    assert os.path.abspath(path) != os.path.abspath("projects.json")
    # Saving must succeed and be readable back.
    assert manager.save_projects() is True
    assert path.exists()
    import json as _json
    _json.loads(path.read_text(encoding="utf-8"))


def test_projects_file_survives_unwritable_cwd():
    """Saving must not depend on the process working directory."""
    import tempfile
    from widgets.ProjectManager import ProjectManager
    manager = ProjectManager()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "projects.json"
        manager.projects_file = target
        manager.projects = {}
        assert manager.save_projects() is True
        assert target.exists()


def test_output_budget_is_not_limited_by_default():
    """There is no local token cap any more: the provider's limit applies."""
    from services.ai_service import AIService

    base = {"ai_enabled": True, "ai_provider": "deepseek",
            "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-flash", "ai_api_key": "sk-test"}

    # No configured budget -> the field is not sent at all.
    assert AIService(config=base).max_tokens is None
    # The legacy saved budget must not keep limiting answers either.
    assert AIService(config={**base, "ai_max_tokens": 1600}).max_tokens is None
    assert AIService(config={**base, "ai_max_tokens": 8192}).max_tokens is None
    # A deliberate larger value is respected verbatim.
    assert AIService(config={**base, "ai_max_tokens": 32000}).max_tokens == 32000


def test_truncated_answer_is_auto_continued():
    """finish_reason=length must resume generation instead of showing half a sentence."""
    import json as _json
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = _json.loads(self.rfile.read(n) or b"{}")
            continued = any("Продолжи ответ" in str(m.get("content", ""))
                            for m in body.get("messages", []))
            calls.append(continued)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if not continued:
                pieces = ["Первая половина, "]
                finish = "length"
            else:
                pieces = ["вторая половина."]
                finish = "stop"
            for piece in pieces:
                chunk = {"choices": [{"delta": {"content": piece}}]}
                self.wfile.write(("data: " + _json.dumps(chunk, ensure_ascii=False)
                                  + "\n\n").encode())
                self.wfile.flush()
            final = {"choices": [{"delta": {}, "finish_reason": finish}]}
            self.wfile.write(("data: " + _json.dumps(final) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    from services.ai_service import AIService
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        svc = AIService(config={"ai_enabled": True, "ai_provider": "custom",
                                "ai_base_url": f"http://127.0.0.1:{port}/v1",
                                "ai_model": "m", "ai_api_key": "k"})
        answer = svc.converse("вопрос")
    finally:
        server.shutdown()
    assert answer == "Первая половина, вторая половина."
    assert calls == [False, True], "a second continuation request must be made"
    assert svc.last_finish_reason == "stop"
    assert svc.truncated is False


def test_slash_only_input_does_not_crash():
    """Regression: typing just "/" raised IndexError inside a Qt slot."""
    from services.ai_commands import find_command, parse_input
    assert find_command("/") is None
    assert find_command("") is None
    assert find_command("/   ") is None
    parsed = parse_input("/")
    assert parsed.command is None
    assert find_command("/help").name == "help"


def test_mcp_config_accepts_map_form():
    """The standard {"mcpServers": {...}} map must parse, not raise."""
    import json as _json
    from services.mcp_client import parse_servers
    payload = _json.dumps({"mcpServers": {
        "files": {"command": "npx", "args": ["-y", "srv"]},
        "docs": {"url": "http://localhost:3001/mcp"},
    }})
    servers = parse_servers(payload)
    assert sorted(s.name for s in servers) == ["docs", "files"]
    by_name = {s.name: s for s in servers}
    assert by_name["files"].transport == "stdio"
    assert by_name["docs"].transport == "http"


def test_clear_conversation_resets_queue_and_state():
    """A new dialog must not inherit the previous queue or request state."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    _APP.processEvents()
    panel._enqueue("старое сообщение", "", None)
    assert panel.pending_count() == 1
    panel._last_request = ("старое", "", None)
    panel.clear_conversation()
    _APP.processEvents()
    assert panel.pending_count() == 0
    assert panel._last_request is None
    assert not panel._history


def test_tool_call_signal_exists():
    """MCP tool calls used to raise AttributeError: no such signal."""
    from widgets import AIAgentPanel as panel_module
    panel = panel_module.AIAgentPanel(None)
    assert hasattr(panel_module.AIAgentPanel, "_tool_called")
    panel._tool_called.emit("files__list", "{}")
    _APP.processEvents()


def test_teaching_prompt_is_added_only_in_teach_mode():
    """The tutor rules must appear in the system prompt only in teach mode."""
    from services.ai_service import AIService
    base = {"ai_provider": "deepseek", "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-flash", "ai_api_key": "sk-test"}
    solve = AIService(config=dict(base, ai_mode="solve"))
    teach = AIService(config=dict(base, ai_mode="teach"))
    assert solve.mode == "solve"
    assert teach.mode == "teach"
    assert "НАСТАВНИК" not in solve.build_system_prompt()
    assert "НАСТАВНИК" in teach.build_system_prompt()
    # The "give ready code" instruction must not fight the tutor rules.
    assert "готовый к запуску код" not in teach.build_system_prompt()


def test_teaching_filter_strips_long_code_blocks():
    """A long ready-made block is hidden in teach mode and kept in solve mode."""
    from services.ai_service import (
        AIService, enforce_teaching_rules, has_forbidden_solution,
        TEACHING_HIDDEN_NOTE, TEACHING_FOLLOWUP_QUESTION)
    fence = "```"
    long_block = ("Вот решение:\n" + fence + "python\n"
                  + "\n".join(f"x = {i}" for i in range(5))
                  + "\n" + fence + "\nГотово.")
    short_hint = ("Подсказка: " + fence + "python\nreturn x\n" + fence
                  + "\nЧто вернёт при пустом списке?")
    base = {"ai_provider": "deepseek", "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-flash", "ai_api_key": "sk-test"}

    assert has_forbidden_solution(long_block) is True
    assert has_forbidden_solution(short_hint) is False

    teach = AIService(config=dict(base, ai_mode="teach"))
    filtered = enforce_teaching_rules(long_block, teach)
    assert TEACHING_HIDDEN_NOTE in filtered
    assert TEACHING_FOLLOWUP_QUESTION in filtered
    assert "x = 0" not in filtered

    solve = AIService(config=dict(base, ai_mode="solve"))
    assert enforce_teaching_rules(long_block, solve) == long_block
    # A single-line hint is explicitly allowed by the rules.
    assert enforce_teaching_rules(short_hint, teach) == short_hint


def test_mode_command_switches_and_persists():
    """`/mode teach|solve` changes the stored setting; there is no mode button."""
    from widgets import AIAgentPanel as panel_module
    from utils.settings_manager import init_settings_manager, get_settings_manager
    try:
        init_settings_manager(ROOT)
    except Exception:
        pass
    sm = get_settings_manager()
    sm.settings["ai_mode"] = "solve"

    panel = panel_module.AIAgentPanel(None)
    _APP.processEvents()
    # The tutor mode is a command now: no dedicated button in the composer.
    assert getattr(panel, "mode_btn", None) is None
    assert panel.mode_badge.isHidden()

    assert panel.set_mode("teach") is True
    _APP.processEvents()
    assert sm.get_setting("ai_mode") == "teach"
    assert not panel.mode_badge.isHidden()

    assert panel.set_mode("solve") is True
    _APP.processEvents()
    assert sm.get_setting("ai_mode") == "solve"
    assert panel.mode_badge.isHidden()

    # Unknown values are rejected and do not change the mode.
    assert panel.set_mode("nonsense") is False
    assert sm.get_setting("ai_mode") == "solve"


def test_mode_defaults_to_solve():
    from services.ai_service import AIService
    svc = AIService(config={"ai_provider": "deepseek",
                            "ai_base_url": "https://api.deepseek.com",
                            "ai_model": "deepseek-flash", "ai_api_key": "sk-test"})
    assert svc.mode == "solve"
    assert AIService(config={"ai_mode": "bogus"}).mode == "solve"


def test_teaching_strictness_levels():
    """Each strictness level allows a different amount of code."""
    from services.ai_service import (
        AIService, TEACH_STRICTNESS_CODE_LINES, enforce_teaching_rules,
        has_forbidden_solution)
    fence = "```"

    def block(lines: int) -> str:
        body = "\n".join(f"x{i} = {i}" for i in range(lines))
        return f"Смотри:\n{fence}python\n{body}\n{fence}\nЧто скажешь?"

    base = {"ai_provider": "deepseek", "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-flash", "ai_api_key": "sk-test",
            "ai_mode": "teach"}

    soft = AIService(config=dict(base, ai_teach_strictness="soft"))
    normal = AIService(config=dict(base, ai_teach_strictness="normal"))
    strict = AIService(config=dict(base, ai_teach_strictness="strict"))

    assert (soft.teach_code_limit, normal.teach_code_limit,
            strict.teach_code_limit) == (5, 3, 0)
    assert TEACH_STRICTNESS_CODE_LINES["soft"] > TEACH_STRICTNESS_CODE_LINES["normal"]

    # A 4-line block is fine for soft, forbidden for normal and strict.
    assert has_forbidden_solution(block(4), soft.teach_code_limit) is False
    assert has_forbidden_solution(block(4), normal.teach_code_limit) is True
    assert has_forbidden_solution(block(4), strict.teach_code_limit) is True

    # Strict forbids even a single line of code.
    assert has_forbidden_solution(block(1), strict.teach_code_limit) is True
    assert has_forbidden_solution(block(1), normal.teach_code_limit) is False

    # Enforcement follows the level.
    assert enforce_teaching_rules(block(4), soft) == block(4)
    assert "скрыт" in enforce_teaching_rules(block(4), normal)
    assert "скрыт" in enforce_teaching_rules(block(1), strict)

    # The strictness text reaches the system prompt.
    assert "МЯГКИЙ" in soft.build_system_prompt()
    assert "СТРОГИЙ" in strict.build_system_prompt()


def test_teaching_strictness_defaults_and_validation():
    from services.ai_service import AIService
    base = {"ai_provider": "deepseek", "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-flash", "ai_api_key": "sk-test", "ai_mode": "teach"}
    assert AIService(config=base).teach_strictness == "normal"
    assert AIService(config=dict(base, ai_teach_strictness="bogus")).teach_strictness == "normal"
    assert AIService(config=dict(base, ai_teach_strictness="STRICT")).teach_strictness == "strict"


def test_strictness_command_and_panel_picker():
    from widgets import AIAgentPanel as panel_module
    from utils.settings_manager import init_settings_manager, get_settings_manager
    try:
        init_settings_manager(ROOT)
    except Exception:
        pass
    sm = get_settings_manager()
    sm.settings["ai_mode"] = "teach"
    sm.settings["ai_teach_strictness"] = "normal"

    panel = panel_module.AIAgentPanel(None)
    _APP.processEvents()
    assert set(panel._strictness_actions) == {"soft", "normal", "strict"}

    assert panel.set_strictness("strict") is True
    _APP.processEvents()
    assert sm.get_setting("ai_teach_strictness") == "strict"
    assert "строгий" in panel.mode_badge.text()

    assert panel.set_strictness("soft") is True
    assert "мягкий" in panel.mode_badge.text()

    assert panel.set_strictness("bogus") is False
    assert sm.get_setting("ai_teach_strictness") == "soft"


def test_ui_scale_stylesheet_math():
    from app.ui_scale import normalize_scale, scale_stylesheet
    assert normalize_scale(10) == 75
    assert normalize_scale(500) == 200
    assert normalize_scale("125") == 125
    assert normalize_scale("nonsense") == 100
    qss = "QWidget { font-size: 13px; border: 1px solid #FFFFFF; padding: 0 8px; }"
    scaled = scale_stylesheet(qss, 150)
    assert "font-size: 19.5px" in scaled
    assert "padding: 0 12px" in scaled
    assert "#FFFFFF" in scaled
    # A hairline may scale to 1.5px, but never below 1px.
    tiny = scale_stylesheet("QLabel { border: 1px solid #000000; }", 75)
    assert "border: 1px solid" in tiny
    assert "0.5px" not in scale_stylesheet("QLabel { border: 1px solid #000000; }", 50)


def test_ui_scale_applies_and_restores():
    from app import ui_scale
    from PyQt5 import QtGui
    app = _APP
    base_point = app.font().pointSizeF()
    applied = ui_scale.apply_ui_scale(app, 150, stylesheet_provider=lambda: "QLabel { min-height: 20px; }")
    assert applied == 150
    assert ui_scale.current_scale() == 150
    assert ui_scale.scale_px(20) == 30
    assert app.font().pointSizeF() > base_point
    ui_scale.apply_ui_scale(app, 100, stylesheet_provider=lambda: "QLabel { min-height: 20px; }")
    assert ui_scale.current_scale() == 100
    assert ui_scale.scale_px(20) == 20


def test_ui_scale_presets_cover_range():
    from app.ui_scale import available_scales
    presets = available_scales()
    assert presets[0] == 75 and presets[-1] == 200
    assert 100 in presets and presets == sorted(presets)


def test_panel_reasoning_chip_reflects_setting():
    """The chat header offers every reasoning level and shows the current one."""
    from utils.settings_manager import get_settings_manager
    sm = get_settings_manager()
    previous = sm.settings.get("ai_reasoning_effort")
    sm.settings["ai_reasoning_effort"] = "high"
    try:
        from widgets.AIAgentPanel import AIAgentPanel
        panel = AIAgentPanel(None)
        try:
            panel._refresh_reasoning_menu()
            assert panel._reasoning_effort() == "high"
            assert "Выс" in panel.reasoning_btn.text(), panel.reasoning_btn.text()
            labels = [action.text() for action in panel._reasoning_menu.actions()]
            assert len(labels) == 5, labels
        finally:
            panel.deleteLater()
    finally:
        sm.settings["ai_reasoning_effort"] = previous


def test_chat_session_is_persisted_and_cleared():
    """A conversation survives a restart per project; /clear removes it."""
    import tempfile
    from pathlib import Path as _Path
    from services.ai_service import AIMessage
    from widgets.AIAgentPanel import AIAgentPanel

    project = _Path(tempfile.mkdtemp(prefix="pyscribe_session_"))

    class _Project:
        root_path = str(project)

    class _Window:
        current_project = _Project()

    panel = AIAgentPanel(None)
    try:
        panel.main_window = _Window()
        panel._history = [AIMessage("user", "привет"), AIMessage("assistant", "ответ")]
        panel.save_chat_session()
        saved = project / ".pyscribe" / "ai_chat.json"
        assert saved.is_file(), "session file must be written"
        panel._history = []
        assert panel.load_chat_session() == 2
        assert [m.role for m in panel._history] == ["user", "assistant"]
        panel.clear_conversation()
        assert not saved.exists(), "/clear must delete the saved session"
    finally:
        panel.deleteLater()


def test_agent_stats_footer_updates_and_resets():
    """The composer footer mirrors the harness metrics line."""
    import time as _time
    from widgets.AIAgentPanel import AIAgentPanel

    panel = AIAgentPanel(None)
    try:
        panel._tool_counters = {"read_file": 2, "write_file": 1}
        panel._request_started = _time.monotonic() - 1.0
        panel._record_session_stats({"prompt_tokens": 100, "completion_tokens": 50})
        text = panel.stats_label.text()
        assert "50 tok" in text, text
        assert "3 шагов" in text, text
        assert not panel.stats_label.isHidden()
        panel._record_session_stats({"prompt_tokens": 10, "completion_tokens": 10})
        assert "60 tok" in panel.stats_label.text(), panel.stats_label.text()
        panel._reset_session_stats()
        assert panel.stats_label.isHidden()
    finally:
        panel.deleteLater()


def test_tool_activity_line_is_transient():
    """Tool calls appear while running and vanish when the answer lands."""
    from widgets.AIAgentPanel import AIAgentPanel

    panel = AIAgentPanel(None)
    try:
        panel._clear_welcome()
        panel._on_tool_started("run_terminal_command",
                               {"command": "python -m py_compile documentation_module.py"})
        text = panel.transcript_text()
        assert "run_terminal_command" in text
        # A second tool replaces the same single line instead of appending.
        panel._on_tool_started("write_file", {"path": "documentation_module.py"})
        text = panel.transcript_text()
        assert "run_terminal_command" not in text
        assert text.count("write_file") == 1
        panel._on_finished("исправь", "Готово: файл обновлён.")
        text = panel.transcript_text()
        assert "write_file" not in text, "tool trace must be removed after the answer"
        assert "Готово: файл обновлён." in text
    finally:
        panel.deleteLater()


if __name__ == "__main__":
    tests = [(n, o) for n, o in list(globals().items())
             if n.startswith("test_") and callable(o)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}", flush=True)
        except Exception as exc:
            failed += 1
            import traceback
            print(f"FAIL {name}: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed", flush=True)
    sys.exit(1 if failed else 0)
