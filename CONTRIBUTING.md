# Contributing to PyScribe

## Quality gate

Before opening a pull request:

```text
python -m compileall -q main.py core services utils widgets extensions
pytest
ruff check .
black --check .
```

The application is divided into `core`, `services`, `widgets`, `utils`, `extensions` and `design`.
New code should keep UI code in `widgets`, application contracts in `core`, reusable process/state
logic in `services`, and visual tokens in `design`.

Do not use `print()` for diagnostics. Use `core.logging_config.get_logger()`.
Do not execute project source during static analysis. Third-party analyzer failures must degrade to
an explicit backend status rather than crashing the workbench.
