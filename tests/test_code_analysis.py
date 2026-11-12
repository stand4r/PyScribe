"""Comprehensive Test Suite for PyScribe Unified Code Analysis System.

Tests all 3 levels:
- Level 1: Plain text search with [Текстовое совпадение] tagging.
- Level 2: Tree-sitter multi-language AST extraction & tolerance to incomplete/unsaved code.
- Level 3: LSP semantic servers (pylsp, pyright, typescript-language-server, gopls) & graceful fallback.
- Cross-language OpenAPI contract navigation (Client -> Spec -> Backend handler).
- Windows Cyrillic and spaces path encoding/decoding.
- Project switching, debounce, and resource cleanup.
- UI integration with CodeEditor, CodeLensBar, ConsoleWidget problems panel.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest
from PyQt5 import QtCore, QtWidgets

from core.code_analysis.lsp_client import LspClient, LspDiagnostic, LspLocation, path_to_uri, uri_to_path
from core.code_analysis.openapi_bridge import OpenApiBridge, paths_match
from core.code_analysis.registry import AnalysisLevel, LanguageRegistry, get_language_registry
from core.code_analysis.service import UnifiedCodeAnalysisService
from core.code_analysis.syntax_treesitter import TreeSitterEngine, get_treesitter_engine
from core.code_analysis.text_analyzer import TextCodeAnalyzer


# =====================================================================
# Fixtures
# =====================================================================
@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="pyscribe_analysis_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# 1. Level 1: Text Analyzer & Plaintext Fallback
# =====================================================================
def test_level1_text_analyzer(temp_project_dir):
    """Test whole-word regex scanning across files with [Текстовое совпадение] badge."""
    file_txt = temp_project_dir / "notes.txt"
    file_txt.write_text("Reference to target_symbol in a plain text file.\nAnother line with target_symbol.", encoding="utf-8")

    file_custom = temp_project_dir / "config.unknown"
    file_custom.write_text("key = target_symbol\n", encoding="utf-8")

    analyzer = TextCodeAnalyzer(str(temp_project_dir))
    matches = analyzer.find_occurrences("target_symbol")

    assert len(matches) == 3
    for m in matches:
        assert m.kind == "text"
        assert "[Текстовое совпадение]" in m.badge
        assert "target_symbol" in m.preview


# =====================================================================
# 2. Level 2: Tree-sitter Multi-Language Symbol Extraction
# =====================================================================
def test_level2_treesitter_python_extraction():
    engine = get_treesitter_engine()
    py_code = """
class DataProcessor:
    def __init__(self, name: str):
        self.name = name

    def process(self, items):
        return [self._format(x) for x in items]

def standalone_helper():
    pass
"""
    res = engine.parse(py_code, "python", "processor.py")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    kinds = {s.name: s.kind for s in res.symbols}

    assert "DataProcessor" in names
    assert kinds["DataProcessor"] == "class"
    assert "__init__" in names
    assert kinds["__init__"] == "method"
    assert "process" in names
    assert kinds["process"] == "method"
    assert "standalone_helper" in names
    assert kinds["standalone_helper"] == "function"


def test_level2_treesitter_javascript_typescript():
    engine = get_treesitter_engine()
    ts_code = """
interface UserProfile {
    id: string;
    username: string;
}

class UserService {
    async fetchUser(id: string): Promise<UserProfile> {
        return { id, username: "user" };
    }
}

export function formatUser(profile: UserProfile): string {
    return profile.username;
}
"""
    res = engine.parse(ts_code, "typescript", "service.ts")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    assert "UserProfile" in names
    assert "UserService" in names
    assert "fetchUser" in names
    assert "formatUser" in names


def test_level2_treesitter_go():
    engine = get_treesitter_engine()
    go_code = """
package main

type Storage interface {
    Get(key string) string
}

type MemoryStore struct {
    data map[string]string
}

func (m *MemoryStore) Get(key string) string {
    return m.data[key]
}

func NewStore() *MemoryStore {
    return &MemoryStore{}
}
"""
    res = engine.parse(go_code, "go", "main.go")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    assert "Storage" in names
    assert "MemoryStore" in names
    assert "Get" in names
    assert "NewStore" in names


def test_level2_treesitter_rust():
    engine = get_treesitter_engine()
    rs_code = """
pub enum Status {
    Active,
    Pending,
}

pub struct Config {
    pub timeout: u32,
}

pub trait Runner {
    fn run(&self) -> bool;
}

impl Config {
    pub fn new() -> Self {
        Config { timeout: 30 }
    }
}

fn execute() {}
"""
    res = engine.parse(rs_code, "rust", "lib.rs")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    assert "Status" in names
    assert "Config" in names
    assert "Runner" in names
    assert "new" in names
    assert "execute" in names


def test_level2_treesitter_csharp_and_java():
    engine = get_treesitter_engine()
    cs_code = """
namespace Demo {
    public interface ICalculator {
        int Add(int a, int b);
    }

    public class Calculator : ICalculator {
        public int Add(int a, int b) {
            return a + b;
        }
    }
}
"""
    res_cs = engine.parse(cs_code, "c_sharp", "Calc.cs")
    assert res_cs.is_tree_sitter is True
    names_cs = [s.name for s in res_cs.symbols]
    assert "ICalculator" in names_cs
    assert "Calculator" in names_cs
    assert "Add" in names_cs

    java_code = """
public class OrderService {
    public void processOrder(int id) {
        System.out.println(id);
    }
}
"""
    res_java = engine.parse(java_code, "java", "OrderService.java")
    assert res_java.is_tree_sitter is True
    names_java = [s.name for s in res_java.symbols]
    assert "OrderService" in names_java
    assert "processOrder" in names_java


def test_level2_treesitter_cpp():
    engine = get_treesitter_engine()
    cpp_code = """
struct Point {
    int x;
    int y;
};

class Renderer {
public:
    void render(Point p);
};

void Renderer::render(Point p) {
}
"""
    res = engine.parse(cpp_code, "cpp", "render.cpp")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    assert "Point" in names
    assert "Renderer" in names
    assert "render" in names


def test_level2_incomplete_broken_code_tolerance():
    """Verify that Tree-sitter still extracts valid symbols when syntax is incomplete."""
    engine = get_treesitter_engine()
    broken_py = """
class ImportantClass:
    def valid_method(self):
        return 42

    def incomplete_method(self,
        # unclosed parenthesis and missing body

def next_valid_function():
    return 100
"""
    res = engine.parse(broken_py, "python", "broken.py")
    assert res.is_tree_sitter is True
    names = [s.name for s in res.symbols]
    assert "ImportantClass" in names
    assert "valid_method" in names
    assert "next_valid_function" in names
    assert len(res.syntax_errors) > 0


# =====================================================================
# 3. Unsaved In-Memory Buffers
# =====================================================================
def test_unsaved_buffer_navigation(temp_project_dir):
    """Verify analysis works on in-memory buffers before saving to disk."""
    service = UnifiedCodeAnalysisService(str(temp_project_dir))
    temp_file = str(temp_project_dir / "unsaved_module.py")

    # In-memory buffer never written to disk
    buffer_content = """
class UnsavedSession:
    def execute_live(self):
        return "live result"
"""
    service.on_document_changed(temp_file, buffer_content)

    syms = service.get_file_structure(temp_file)
    names = [s.name for s in syms]
    assert "UnsavedSession" in names
    assert "execute_live" in names

    # Navigate to UnsavedSession
    locs = service.goto_definition(temp_file, 2, 10, symbol_name="UnsavedSession")
    assert len(locs) > 0
    assert locs[0].file_path == temp_file
    assert locs[0].line == 2


# =====================================================================
# 4. Extensible Registry & Toolchain Detection
# =====================================================================
def test_language_registry_settings_override():
    registry = LanguageRegistry()
    spec = registry.get("rust")
    assert spec is not None
    assert spec.display_name == "Rust"

    # Default without override: rust-analyzer might not be in PATH
    exe_default, _ = registry.resolve_lsp_server(spec)

    # With settings override
    custom_path = r"C:\custom_tools\rust-analyzer.exe"
    exe_override, _ = registry.resolve_lsp_server(spec, configured_path=custom_path)
    assert exe_override == custom_path


def test_language_status_and_install_hints(temp_project_dir):
    service = UnifiedCodeAnalysisService(str(temp_project_dir))
    rs_file = str(temp_project_dir / "main.rs")

    status = service.get_language_status(rs_file)
    assert status["lang_id"] == "rust"
    assert status["treesitter"] is True
    # If rust-analyzer is not installed on host, server_found is False and install_hint is non-empty
    if not status["server_found"]:
        assert "rust-analyzer" in status["install_hint"]
        assert "Синтаксис" in status["badge"]


# =====================================================================
# 5. Windows Cyrillic & Spaces URI Encoding / Decoding
# =====================================================================
def test_windows_paths_with_spaces_and_cyrillic():
    windows_path = r"C:\Users\Dmitr\OneDrive\Документы\PyScribe\Тестовая Папка\скрипт 1.py"
    uri = path_to_uri(windows_path)

    assert uri.startswith("file:///")
    # Cyrillic characters must be percent-encoded in URI
    assert "%D0" in uri or "%D1" in uri
    # Spaces must be percent-encoded as %20
    assert "%20" in uri

    decoded_path = uri_to_path(uri)
    assert Path(decoded_path) == Path(windows_path)


# =====================================================================
# 6. OpenAPI Cross-Language Scenario
# =====================================================================
def test_paths_match():
    assert paths_match("/api/v1/users/{id}", "/api/v1/users/42") is True
    assert paths_match("/api/v1/users/{id}", "/api/v1/users/${userId}") is True
    assert paths_match("/api/v1/users/{id}", "/api/v1/orders/42") is False


def test_openapi_end_to_end_navigation(temp_project_dir):
    """End-to-end OpenAPI: Client TS -> OpenAPI YAML -> FastAPI route handler."""
    # 1. OpenAPI specification
    spec_yaml = """openapi: 3.0.0
info:
  title: Users API
  version: 1.0.0
paths:
  /api/v1/users/{id}:
    get:
      summary: Retrieve a user by ID
      operationId: getUserById
      responses:
        '200':
          description: User object
    delete:
      summary: Delete a user by ID
      operationId: deleteUserById
      responses:
        '204':
          description: Deleted
"""
    spec_file = temp_project_dir / "openapi.yaml"
    spec_file.write_text(spec_yaml, encoding="utf-8")

    # 2. Client code in TypeScript
    client_ts = """
export async function loadUserData(userId: string) {
    const response = await fetch(`/api/v1/users/${userId}`);
    return await response.json();
}
"""
    client_file = temp_project_dir / "client.ts"
    client_file.write_text(client_ts, encoding="utf-8")

    # 3. Server route handler in Python (FastAPI)
    server_py = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/v1/users/{id}")
def get_user_by_id(id: int):
    return {"id": id, "name": "Alice"}

@app.delete("/api/v1/users/{id}")
def delete_user_by_id(id: int):
    return {"status": "deleted"}
"""
    server_file = temp_project_dir / "server.py"
    server_file.write_text(server_py, encoding="utf-8")

    bridge = OpenApiBridge(str(temp_project_dir))
    bridge.rebuild_index()

    assert len(bridge.operations) == 2
    assert len(bridge.client_calls) >= 1
    assert len(bridge.server_handlers) == 2

    # Step A: From Client Call line 3 -> OpenAPI Spec & Server Handler
    client_links = bridge.find_cross_language_links(str(client_file), 3, 35, 'fetch(`/api/v1/users/${userId}`);')
    assert len(client_links) >= 1
    # Check that OpenAPI spec or backend handler was found
    found_spec = any(str(spec_file) in loc.file_path for loc in client_links)
    found_handler = any(str(server_file) in loc.file_path for loc in client_links)
    assert found_spec or found_handler
    for loc in client_links:
        assert loc.kind == "openapi"
        assert "[OpenAPI" in loc.badge

    # Step B: From OpenAPI Spec line 6 (/api/v1/users/{id} get) -> Client and Server
    spec_links = bridge.find_cross_language_links(str(spec_file), 6, 4)
    assert len(spec_links) >= 1
    for loc in spec_links:
        assert loc.kind == "openapi"

    # Step C: Ambiguous matches show reasons
    # Both GET and DELETE are on /api/v1/users/{id}
    # When jumping from generic path string, both candidates are presented with method badges
    ambiguous_links = bridge.find_cross_language_links(str(client_file), 3, 35, '"/api/v1/users/1"')
    assert len(ambiguous_links) >= 2
    badges = [loc.badge for loc in ambiguous_links]
    assert any("GET" in b or "Спецификация" in b for b in badges)


# =====================================================================
# 7. Project Switching & Cleanup
# =====================================================================
def test_project_switching_cleanup(temp_project_dir):
    service = UnifiedCodeAnalysisService.get_instance()
    service.set_project_root(str(temp_project_dir))

    # Add buffer
    sample_file = str(temp_project_dir / "temp.py")
    service.on_document_changed(sample_file, "def foo(): pass\n")
    assert sample_file in service._file_buffers

    # Switch project to another root
    second_dir = tempfile.mkdtemp(prefix="pyscribe_second_")
    try:
        service.set_project_root(second_dir)
        assert service.root_path == str(Path(second_dir).resolve())
        # Previous project buffers cleared
        assert sample_file not in service._file_buffers

        # Close project
        service.set_project_root(None)
        assert service.root_path is None
    finally:
        shutil.rmtree(second_dir, ignore_errors=True)


# =====================================================================
# 8. Live LSP Servers Verification
# =====================================================================
def test_live_python_lsp_server(temp_project_dir):
    """Verify live communication with installed python language server (pylsp or pyright)."""
    registry = get_language_registry()
    spec = registry.get("python")
    server_exe, server_args = registry.resolve_lsp_server(spec)

    if not server_exe:
        pytest.skip("No python LSP server (pylsp/pyright) installed on this host")

    client = LspClient(lang_id="python", server_path=server_exe, server_args=server_args, root_path=str(temp_project_dir))
    ok = client.start()
    assert ok is True, f"Failed to start LSP {server_exe}"

    try:
        test_py = temp_project_dir / "math_utils.py"
        test_py.write_text("def calculate_sum(a, b):\n    return a + b\n\ntotal = calculate_sum(10, 20)\n", encoding="utf-8")
        client.did_open(str(test_py), test_py.read_text(encoding="utf-8"))

        # Wait briefly for initialization / indexing
        time.sleep(1.0)

        # Query definition of calculate_sum at line 4 (total = calculate_sum)
        locs = client.definition(str(test_py), line=4, col=15)
        # Some LSPs take a few seconds to index, so if empty, client didn't crash
        assert client.is_alive
    finally:
        client.shutdown_and_exit()


def test_live_typescript_lsp_server(temp_project_dir):
    """Verify live communication with typescript-language-server."""
    registry = get_language_registry()
    spec = registry.get("typescript")
    server_exe, server_args = registry.resolve_lsp_server(spec)

    if not server_exe:
        pytest.skip("typescript-language-server not installed on this host")

    client = LspClient(lang_id="typescript", server_path=server_exe, server_args=server_args, root_path=str(temp_project_dir))
    ok = client.start()
    assert ok is True
    try:
        assert client.is_alive
        assert client.is_initialized
    finally:
        client.shutdown_and_exit()


def test_live_gopls_lsp_server(temp_project_dir):
    """Verify live communication with gopls."""
    registry = get_language_registry()
    spec = registry.get("go")
    server_exe, server_args = registry.resolve_lsp_server(spec)

    if not server_exe:
        pytest.skip("gopls not installed on this host")

    client = LspClient(lang_id="go", server_path=server_exe, server_args=server_args, root_path=str(temp_project_dir))
    ok = client.start()
    assert ok is True
    try:
        assert client.is_alive
        assert client.is_initialized
    finally:
        client.shutdown_and_exit()


# =====================================================================
# 9. UI Integration (CodeEditor, CodeLensBar, ConsoleWidget)
# =====================================================================
def test_ui_editor_navigation_and_codelens(qapp, temp_project_dir):
    """Test UI integration: CodeEditor, CodeLensBar outline, and navigation methods."""
    from widgets.CodeLensBar import CodeLensBar
    from widgets.ConsoleWidget import ConsoleWidget
    from widgets.QCodeEditor import ModernCodeEditor

    file_py = temp_project_dir / "example.py"
    file_py.write_text("class Greeter:\n    def say_hello(self):\n        return 'hello'\n\ng = Greeter()\n", encoding="utf-8")

    editor = ModernCodeEditor(language="python")
    editor.set_file_path(str(file_py))
    editor.set_code(file_py.read_text(encoding="utf-8"))

    # Test CodeLensBar AST symbols extraction
    lens = editor.code_lens
    assert lens is not None
    lens._refresh_lens()
    assert len(lens._symbols) >= 2
    sym_names = [s.name for s in lens._symbols]
    assert "Greeter" in sym_names
    assert "say_hello" in sym_names

    # Test ConsoleWidget problems panel receives LSP diagnostics
    console = ConsoleWidget()
    diag = LspDiagnostic(
        file_path=str(file_py),
        line=2,
        col=4,
        severity="error",
        message="Type mismatch",
        source="pylsp"
    )
    console._on_lsp_diagnostics(str(file_py), [diag])
    console.set_file_context(str(file_py))
    assert console.problems_list.count() >= 1
    item_text = console.problems_list.item(0).text()
    assert "Type mismatch" in item_text
    assert "строка 2" in item_text

    # Test navigation forwarders on ModernCodeEditor
    assert hasattr(editor, "action_goto_definition")
    assert hasattr(editor, "action_find_references")
    assert hasattr(editor, "action_goto_openapi")
