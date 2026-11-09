# PyScribe Project Intelligence

## Назначение

`Project Intelligence` — центральная подсистема структурного анализа Python-проектов PyScribe. Она превращает проект из набора файлов в машинно-обрабатываемую модель: файлы, модули, классы, функции, зависимости, метрики сложности и диагностические проблемы.

## Архитектура

```text
ProjectIntelligenceWidget
        │
        │ background QThread
        ▼
ProjectIntelligenceEngine
        │
        ├── Python AST parser
        ├── Symbol extraction
        ├── Local dependency resolver
        ├── Complexity metrics
        └── Explainable diagnostics
        │
        ▼
ProjectAnalysis
        ├── files
        ├── symbols
        ├── dependencies
        ├── reverse_dependencies
        └── issues
```

## Возможности

### 1. Project Overview

Показывает:

- количество Python-файлов;
- количество строк;
- количество символов;
- функции и классы;
- локальные зависимости;
- ошибки и предупреждения;
- среднюю цикломатическую сложность проекта.

### 2. Symbols

AST используется для построения списка:

- классов;
- функций;
- методов;
- импортов;
- их файлов и строк.

Двойной клик открывает соответствующий файл и переводит курсор к строке.

### 3. Dependency Graph

Для локальных Python-модулей строится ориентированный граф зависимостей.

`A -> B` означает, что модуль `A` импортирует `B`.

Граф строится без внешнего графового движка, чтобы PyScribe оставался самодостаточным.

### 4. Code Quality

Диагностика основана на AST и является объяснимой. Сейчас реализованы правила:

- `PY001` — `eval()`;
- `PY002` — `exec()`;
- `PY003` — динамический `compile()`;
- `PY004` — `os.system()` / `os.popen()`;
- `PY010` — bare `except`;
- `PY020` — слишком длинная функция;
- `PY021` — слишком много параметров;
- `PY030` — возможный hard-coded secret;
- `PY100` — синтаксическая ошибка.

### 5. Impact Analysis

После выбора файла PyScribe ищет обратные зависимости и показывает модули, которые прямо или косвенно зависят от изменённого файла.

Алгоритм использует reverse dependency graph и BFS, поэтому учитывает цепочки:

```text
A -> B -> C -> D
```

Если изменён `D`, анализ покажет `C`, `B` и `A` как потенциально затронутые модули.

## Интеграция с IDE

Новая кнопка `Project Intelligence` добавлена в Activity Bar.

Также доступны команды Command Palette:

- `Project: Intelligence`
- `Project: Analyze Current File Impact`

При открытии проекта подсистема автоматически начинает индексацию. Индексация выполняется в отдельном `QThread`, поэтому UI не блокируется на больших проектах.

При сохранении открытого файла, если панель Intelligence видима, анализ запускается повторно.

## Ограничения текущей версии

- основной структурный анализ рассчитан на Python;
- разрешаются локальные импорты проекта, а не полный импортный граф всех установленных пакетов;
- граф является модульным, а не построчным графом вызовов;
- диагностика является набором детерминированных правил и не заменяет полноценный linter/type checker.

Эти ограничения полезны для дипломной работы: на их основе можно формально расширять исследуемую подсистему и проводить экспериментальное сравнение.

## Расширенный структурный граф

Граф Project Intelligence поддерживает четыре представления:

- **Modules** — модули проекта и локальные связи импорта; модуль можно раскрыть и увидеть его верхнеуровневые классы и функции.
- **Classes** — классы и методы выбранного Python-файла.
- **Functions** — функции/методы выбранного файла; связи вызовов между функциями разрешаются по имени внутри выбранного файла.
- **Variables** — переменные, создаваемые внутри выбранной функции.

Граф интерактивный: узлы можно раскрывать и сворачивать, масштабировать колесом с Ctrl, перемещать панорамированием, а двойной клик открывает исходный файл. Управление `Expand All` / `Collapse All` позволяет быстро менять уровень детализации.

## Project Intelligence v3 — Polyglot + Binary Analysis

The intelligence subsystem now uses a layered analyzer architecture:

```text
ProjectIntelligenceEngine
├── Python AST analyzer
├── Tree-sitter polyglot analyzer (optional)
│   ├── JavaScript / TypeScript / TSX
│   ├── C / C++
│   ├── Java
│   ├── Go
│   ├── Rust
│   ├── C# / PHP / Ruby / Swift / Kotlin / Scala / Dart / Lua / Bash / SQL / R
│   └── additional Tree-sitter grammars can be enabled without changing the engine
├── Python metrics: Radon (optional)
├── Python security: Bandit (optional)
└── Binary analyzer
    ├── LIEF: PE / ELF / Mach-O and related executable metadata
    ├── Capstone: read-only multi-architecture disassembly sample
    └── raw fallback: magic, SHA-256, entropy and embedded-string inspection
```

### New source-level information
- language and parser backend per file;
- classes, interfaces, structs, enums, functions, methods and constructors;
- import/dependency edges;
- call edges where the parser exposes a callable name;
- inheritance/reference edges for supported AST constructs;
- parser recovery diagnostics;
- conservative security diagnostics;
- Python maintainability, SLOC, LLOC, comments and Radon metrics when installed;
- Bandit findings when installed.

### New binary-level information
- format and architecture;
- bitness and entry point;
- SHA-256 and file size;
- sections, offsets, sizes, virtual sizes and entropy where the binary parser exposes them;
- imported/exported symbols;
- symbol table entries when available;
- entropy and suspicious embedded strings in the fallback mode;
- a bounded Capstone disassembly sample when the architecture can be mapped.

**Safety model:** inspected source and binaries are never executed by the intelligence engine. Third-party analyzers are used only as parsers/static analyzers. External analyzers are isolated from the primary indexer so a missing or broken optional package does not abort the project scan.

### Graph views
The Graph page now supports:
- Modules
- Classes
- Functions
- Variables
- Binaries
- Imports
- Exports

The module graph keeps module roots and their top-level declarations, so the existing expand/collapse interaction can reveal more structure progressively.
