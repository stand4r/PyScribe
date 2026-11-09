"""PyScribe extensions/api.py: application module and reusable component."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any


@dataclass
class CompletionItem:
    label: str
    kind: str = "symbol"
    detail: str = ""
    sort_text: str = ""


@dataclass
class ExtensionContext:
    root_path: Optional[Path]
    settings: Dict[str, Any] = field(default_factory=dict)
    commands: Dict[str, Callable] = field(default_factory=dict)
    completion_providers: List[Any] = field(default_factory=list)
    disposables: List[Callable] = field(default_factory=list)

    def register_command(self, command_id: str, handler: Callable) -> None:
        self.commands[command_id] = handler

    def register_completion_provider(self, provider: Any) -> None:
        self.completion_providers.append(provider)

    def on_dispose(self, callback: Callable) -> None:
        self.disposables.append(callback)


class Extension:
    """Base class for PyScribe extensions.

    Extensions implement activate(context) and may contribute commands,
    completion providers, language providers, or UI integrations through the
    context. The API is intentionally small so it can evolve without tying
    plugins to internal widgets.
    """

    id = "extension"
    name = "PyScribe Extension"
    version = "0.1.0"

    def activate(self, context: ExtensionContext) -> None:
        pass

    def deactivate(self) -> None:
        pass
