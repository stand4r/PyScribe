"""Security helpers shared by PyScribe UI/services."""
from pathlib import Path

def resolve_inside(root, candidate, allow_missing=False):
    root = Path(root).resolve()
    candidate = Path(candidate).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PermissionError("Path escapes the workspace root")
    if not allow_missing and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate

def safe_extension_entry(extension_dir, entry):
    return resolve_inside(extension_dir, Path(extension_dir) / entry, allow_missing=False)
