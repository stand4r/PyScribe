"""JSON-backed state storage; deliberately avoids unsafe pickle deserialization."""
import json
from pathlib import Path

class StateStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
    def read_list(self, name):
        try:
            data = json.loads((self.root / f"{name}.json").read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []
    def write_list(self, name, values):
        (self.root / f"{name}.json").write_text(json.dumps(list(values), ensure_ascii=False, indent=2), encoding="utf-8")
