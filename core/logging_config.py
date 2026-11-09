"""Centralized logging configuration for PyScribe.

The application uses the standard library logging package so diagnostics are
available both during development and in installed builds without relying on
``print`` statements.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

_CONFIGURED = False


def configure_logging(base_path: Union[str, Path], level: int = logging.INFO) -> logging.Logger:
    """Configure file and stderr logging once and return the application logger."""
    global _CONFIGURED
    logger = logging.getLogger("pyscribe")
    if _CONFIGURED:
        return logger
    root = Path(base_path)
    log_dir = root / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "pyscribe.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(file_handler)
    except OSError:
        pass
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    logger.setLevel(level)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger from the PyScribe logging namespace."""
    return logging.getLogger("pyscribe" + (f".{name}" if name else ""))
