"""Level 1: Base text matching and symbol search for any file.

When no syntax or semantic analyzer is active, or as a project-wide textual
fallback, this engine searches by token boundaries.
Results are explicitly tagged with kind='text' and badge='[Текстовое совпадение]'.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Set

from core.code_analysis.lsp_client import LspLocation

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
    "node_modules", "dist", "build", ".idea", ".vscode", "target", "bin", "obj"
}
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".exe", ".dll", ".so",
    ".dylib", ".zip", ".tar", ".gz", ".7z", ".pyc", ".pyd", ".o", ".a", ".class"
}


class TextCodeAnalyzer:
    """Searches plain text files across the project workspace."""

    def __init__(self, root_path: Optional[str] = None):
        self.root_path = Path(root_path).resolve() if root_path else None

    def set_root(self, root_path: Optional[str]):
        self.root_path = Path(root_path).resolve() if root_path else None

    def find_occurrences(self, symbol_name: str, max_results: int = 100) -> List[LspLocation]:
        """Alias for find_matches."""
        return self.find_matches(symbol_name, max_results=max_results)

    def find_matches(
        self,
        symbol_name: str,
        max_results: int = 50,
        filter_path: Optional[str] = None,
        is_definition_guess: bool = False,
    ) -> List[LspLocation]:
        """Find occurrences of symbol_name with word boundaries."""
        if not symbol_name or not self.root_path or not self.root_path.exists():
            return []

        pattern = re.compile(r"\b" + re.escape(symbol_name) + r"\b")
        locations: List[LspLocation] = []

        # If a single file is targeted
        if filter_path:
            p = Path(filter_path)
            if p.is_file():
                self._search_file(p, pattern, symbol_name, locations, max_results, is_definition_guess)
                return locations

        # Search across workspace files
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for file in files:
                if len(locations) >= max_results:
                    return locations

                p = Path(root) / file
                if p.suffix.lower() in BINARY_EXTENSIONS:
                    continue

                try:
                    if p.stat().st_size > 1_000_000:  # Skip files > 1 MB
                        continue
                except OSError:
                    continue

                self._search_file(p, pattern, symbol_name, locations, max_results, is_definition_guess)

        return locations

    def _search_file(
        self,
        path: Path,
        pattern: re.Pattern,
        symbol_name: str,
        locations: List[LspLocation],
        max_results: int,
        is_definition_guess: bool = False,
    ):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        def_indicators = ("def ", "class ", "function ", "fn ", "func ", "const ", "let ", "var ", "struct ", "interface ")

        for line_idx, line in enumerate(content.splitlines()):
            if len(locations) >= max_results:
                break

            for m in pattern.finditer(line):
                col = m.start()
                stripped = line.strip()

                badge = "[Текстовое совпадение]"
                if is_definition_guess and any(stripped.startswith(ind) for ind in def_indicators):
                    badge = "[Текстовое определение]"

                locations.append(LspLocation(
                    file_path=str(path.resolve()),
                    line=line_idx + 1,
                    col=col,
                    end_line=line_idx + 1,
                    end_col=col + len(symbol_name),
                    preview=stripped,
                    kind="text",
                    badge=badge,
                ))
                if len(locations) >= max_results:
                    break
