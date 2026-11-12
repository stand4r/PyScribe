"""Unified Multi-Language Code Analysis Subsystem for PyScribe."""
from core.code_analysis.registry import (
    AnalysisLevel,
    LanguageRegistry,
    LanguageSpec,
    get_language_registry,
)
from core.code_analysis.syntax_treesitter import (
    AnalyzedSymbol,
    SyntaxParseResult,
    TreeSitterEngine,
    get_treesitter_engine,
)
from core.code_analysis.lsp_client import (
    LspCallItem,
    LspClient,
    LspDiagnostic,
    LspLocation,
    path_to_uri,
    uri_to_path,
)
from core.code_analysis.text_analyzer import TextCodeAnalyzer
from core.code_analysis.openapi_bridge import (
    ClientApiCall,
    OpenApiBridge,
    OpenApiOperation,
    ServerRouteHandler,
)
from core.code_analysis.service import (
    UnifiedCodeAnalysisService,
    get_code_analysis_service,
)

__all__ = [
    "AnalysisLevel",
    "LanguageRegistry",
    "LanguageSpec",
    "get_language_registry",
    "AnalyzedSymbol",
    "SyntaxParseResult",
    "TreeSitterEngine",
    "get_treesitter_engine",
    "LspCallItem",
    "LspClient",
    "LspDiagnostic",
    "LspLocation",
    "path_to_uri",
    "uri_to_path",
    "TextCodeAnalyzer",
    "ClientApiCall",
    "OpenApiBridge",
    "OpenApiOperation",
    "ServerRouteHandler",
    "UnifiedCodeAnalysisService",
    "get_code_analysis_service",
]
