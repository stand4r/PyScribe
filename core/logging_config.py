"""Centralized logging configuration for PyScribe.

The application uses the standard library logging package so diagnostics are
available both during development and in installed builds without relying on
``print`` statements.
"""
from __future__ import annotations

import faulthandler
import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

_CONFIGURED = False
_crash_file = None


def log_directory(base_path: Union[str, Path]) -> Path:
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("APPDATA") or Path.home()) / "PyScribe" / "logs"
    return Path(base_path) / "logs"


def configure_logging(base_path: Union[str, Path], level: int = logging.INFO) -> logging.Logger:
    """Configure file and stderr logging once and return the application logger."""
    global _CONFIGURED
    logger = logging.getLogger("pyscribe")
    if _CONFIGURED:
        return logger
    log_dir = log_directory(base_path)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(log_dir / "pyscribe.log",
                                          maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
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


def install_diagnostics(base_path: Path):
    """Keep tracebacks for exceptions escaping the UI or a Python thread."""
    global _crash_file
    logger = configure_logging(base_path)
    from core.app_version import current_version

    logger.info("Запуск PyScribe %s | Python %s | %s",
                current_version(), platform.python_version(), platform.platform())
    try:
        _crash_file = (log_directory(base_path) / "crash.log").open("ab")
        faulthandler.enable(file=_crash_file)
    except (OSError, RuntimeError):
        logger.exception("Не удалось настроить журнал аварийных завершений")
    previous_hook = sys.excepthook
    previous_thread_hook = threading.excepthook

    def on_exception(exc_type, value, traceback):
        if not issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            logger.error("Необработанное исключение", exc_info=(exc_type, value, traceback))
        previous_hook(exc_type, value, traceback)

    def on_thread_exception(args):
        if not issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
            logger.error("Необработанное исключение в потоке",
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        previous_thread_hook(args)

    sys.excepthook = on_exception
    threading.excepthook = on_thread_exception


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger from the PyScribe logging namespace."""
    return logging.getLogger("pyscribe" + (f".{name}" if name else ""))
