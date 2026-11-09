"""PyScribe extensions/manager.py: application module and reusable component."""
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .api import Extension, ExtensionContext
from core.security import safe_extension_entry


class ExtensionManager:
    """Discovers and activates PyScribe extensions.

    Supported locations:
      * <project>/.pyscribe/extensions/<extension>/pyscribe-extension.json
      * <app>/extensions/installed/<extension>/pyscribe-extension.json

    Manifest example:
      {"id":"my.ext", "name":"My Extension", "version":"1.0.0",
       "entry":"extension.py", "class":"MyExtension"}
    """

    def __init__(self, app_root: Path, settings=None):
        self.app_root = Path(app_root)
        self.settings = settings or {}
        self.context = ExtensionContext(root_path=None, settings=self.settings)
        self.extensions: Dict[str, Extension] = {}
        self.manifests: Dict[str, dict] = {}
        self.errors: Dict[str, str] = {}
        self._modules = {}

    def set_project_root(self, root: Optional[str]) -> None:
        self.deactivate_project_extensions()
        self.errors.clear()
        self.context.root_path = Path(root).resolve() if root else None
        self.load_project_extensions()

    def _manifest_dirs(self) -> List[Path]:
        dirs = [self.app_root / "extensions" / "installed"]
        if self.context.root_path:
            dirs.insert(0, self.context.root_path / ".pyscribe" / "extensions")
        return dirs

    def discover(self) -> List[Tuple[Path, dict]]:
        found = []
        for base in self._manifest_dirs():
            if not base.exists():
                continue
            candidates = [base / "pyscribe-extension.json"]
            candidates.extend(base.glob("*/pyscribe-extension.json"))
            for manifest_path in candidates:
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if data.get("id") and data.get("entry"):
                        found.append((manifest_path.parent, data))
                except Exception as exc:
                    self.errors[str(manifest_path)] = str(exc)
        return found

    def load_project_extensions(self) -> None:
        for directory, manifest in self.discover():
            self._activate(directory, manifest)

    def _activate(self, directory: Path, manifest: dict) -> None:
        ext_id = manifest["id"]
        if not isinstance(ext_id, str) or not ext_id or len(ext_id) > 80:
            raise ValueError("Invalid extension id")
        if ext_id in self.extensions:
            return
        try:
            entry = safe_extension_entry(directory, manifest["entry"])
            if not entry.is_file():
                raise FileNotFoundError(f"Extension entry not found: {entry}")
            module_name = "pyscribe_ext_" + ext_id.replace(".", "_").replace("-", "_")
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load entry point: {entry}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            cls_name = manifest.get("class", "Extension")
            cls = getattr(module, cls_name)
            instance = cls()
            instance.activate(self.context)
            self.extensions[ext_id] = instance
            self.manifests[ext_id] = manifest
            self._modules[ext_id] = module
        except Exception as exc:
            self.errors[ext_id] = f"{type(exc).__name__}: {exc}"

    def deactivate_project_extensions(self) -> None:
        for ext_id, extension in list(self.extensions.items()):
            try:
                extension.deactivate()
            except Exception:
                pass
            self.extensions.pop(ext_id, None)
            self.manifests.pop(ext_id, None)
            self._modules.pop(ext_id, None)
        self.context.commands.clear()
        self.context.completion_providers.clear()

    def get_completion_providers(self):
        return list(self.context.completion_providers)

    def list_extensions(self) -> List[dict]:
        result = []
        for ext_id, manifest in self.manifests.items():
            result.append({"id": ext_id, **manifest})
        return result
