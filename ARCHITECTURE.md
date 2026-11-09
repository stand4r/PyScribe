# PyScribe 1.0.2 — Architecture & Project Structure

## 1. Layers Overview

- **`main.py`**: Lightweight, declarative bootstrap entry point (~50 lines). Retains backwards-compatible re-exports for external scripts and frozen executables.
- **`app/`**: Application shell, lifecycle orchestration, and main window composition:
  - `application.py`: `ApplicationManager` lifecycle, per-user persistent config resolution, and `main()` application bootstrap.
  - `main_window.py`: `ModernMainWindow` UI shell, editor group management, and action routing.
  - `controller.py`: `WorkbenchController` centralized coordinator for execution, terminal announcements, and testing workflows.
  - `top_bar.py`: `WorkbenchTopBar` (VS Code-style header, title, instant popup menus, window controls) and `ExplorerHeader`.
  - `ui_manager.py`: `UIManager` responsible for assembling activity bars, splitters, side panels, and status bar.
  - `file_manager.py`: `FileManager` responsible for safe text/BOM decoding, binary hex viewer routing, office document preview, and file sessions.
  - `project_handler.py`: `ProjectHandler` project opening, analyzer profile selection, session restoration, and workspace binding.
  - `code_runner.py`: `CodeRunner` script execution and launch arguments dispatch.
  - `styling.py`: Design token interpolation, application-wide Fusion palette setup, QSS loading, and Windows AppUserModelID registration.
- **`core/`**: Domain models, syntax trees, analyzers, workspace indexing, and analysis engine:
  - `project_intelligence.py`: Core analysis engine and data models (`ProjectAnalysis`, `FileInfo`, `Issue`, `Symbol`).
  - `workspace_index.py`: Codebase indexing and fast completion lookup. Building the index for a whole project is expensive, so `set_root(root, defer=True)` only scans the file list and `process_batch(n)` parses it in slices; the main window drives those slices from a `QTimer`, which keeps project opening responsive on very large trees.
  - `language_services.py`: Language-specific AST analysis and inspection.
  - `analyzers/`: Modular analyzer plug-ins (structure, dependencies, metrics, health, security, binaries).
  - Terminal (`widgets/TerminalWidget.py`): one real shell per tab (PowerShell by default, cmd or Git Bash on request, or a bare REPL such as python). IDE-issued commands are typed into the shell so builtins and compound commands work; running a file keeps the separate-process path with a streamed exit code. A replaced shell is detached from its `finished` handler — otherwise the kill scheduled a restart that killed the new shell, producing an endless respawn loop.
  - `adversary.py`: Adversarial tester («Адвокат дьявола»). Infers parameter kinds from annotations *or* from body usage (`items[0]` → sequence, `x / 2` → number), generates boundary inputs, runs each case in a **subprocess with a timeout** (so crashes and hangs cannot kill the IDE), minimizes a failing input by delta-debugging, and exports findings as Markdown or pytest. No Qt imports — testable headlessly.
  - Panel typography: the analysis dashboard deliberately uses the *editor* font (`apply_editor_font`) because it reports code paths and symbols; the editor's CodeLens strip has its own background and hairline borders so it no longer merges with the code area.
  - Chat rendering (`widgets/ChatMessage.py`): answers are composed as text blocks plus code blocks. Inline code is drawn as a **rounded chip** — Qt rich text cannot round an inline background, so the HTML uses a sentinel colour that is converted into the custom char-format property `INLINE_PROP` and painted with `drawRoundedRect` behind the glyphs. Fenced blocks are rendered by `CodeSnippet`, which reuses `ModernSyntaxHighlighter` from `widgets/QCodeEditor.py`, so chat code is highlighted by the same engine as the editor.
  - Chat chrome: the tutor mode is a **chat command** (`/mode`, `/strictness`), not a compose-bar button; only the context and model pickers remain in the composer, so the input stays uncluttered. CodeLens breadcrumbs are styled through the dynamic property selectors `QToolButton[class="lensCrumbBtn"]` — the previous `.lensCrumbBtn` form matched a C++ class name, so the buttons kept the default background while the `›` dividers were transparent.
  - `agent_tools.py`: Project tools for the AI agent (`read_file`, `list_directory`, `search_in_project`, `write_file`, `run_terminal_command`, `open_application`). Every path is resolved against the project root, mutating calls ask the user through a confirmation callback, output is truncated, commands time out, and permissions can be disabled in Settings. No Qt imports here.
  - `project_tasks.py`: Project task board — `Task`/`TaskStore` with JSON persistence in `.pyscribe/tasks.json`, statuses (todo/doing/done), priorities, sorting and a report-friendly `stats()`. No Qt imports, so it is unit-tested directly.
  - `ignore_rules.py`: One place that decides **what a project scan may touch**. `walk_files()` uses `os.walk(topdown=True)` and prunes ignored directories *during* traversal — `Path.rglob` descends first and filters later, which is what made large projects slow (and memory-heavy) to open. Also enforces `MAX_FILES_DEFAULT` (4000) and `MAX_SOURCE_BYTES` (512 KB), honours `.gitignore` and `.pyscribeignore`, and returns a `ScanResult` with what was skipped. Every full-tree walk (analysis, completion index, quick open, search, run targets, AI context) goes through it.
  - Analysis pacing: the engine reads files with a small pause between them (`io_pause_sec`) and stops at a hard time budget (`time_budget_sec`). Without the pause, reading hundreds of files from a cloud-synced folder saturates disk I/O and the window stutters; a single pathological file also cannot hang the scan.
  - `logging_config.py` & `single_instance.py`: Infrastructure primitives.
- **`services/`**: Application services bridging UI and domain models:
  - `code_intelligence_service.py`: Health grading, recommendation generation, and code metrics transformation.
  - `ai_providers.py`: Declarative provider registry — the single source of truth for the settings page, the model pickers and the HTTP client. Providers: DeepSeek, OpenAI/ChatGPT, **Claude (Anthropic)**, **Google Gemini**, **opencode zen**, OpenRouter, Groq, Ollama, LM Studio, custom. Each declares its protocol, base URL, models (with `free` flags), key page and hint.
  - `ai_service.py`: Provider-agnostic chat client over two protocols using stdlib `urllib` only — OpenAI-compatible `/chat/completions` (SSE) and the native **Anthropic `/messages`** API (`x-api-key` + `anthropic-version`, `content_block_delta` streaming). Provides `stream`/`complete`, `converse()` (streaming plus a bounded MCP tool loop), `test_connection()`, `list_models()`, and actionable errors (wrong key shape, 401, 402, 429, offline).
  - `ai_commands.py`: Slash-command table and `parse_input()` — splits a message into a `/command`, `@mentions` and plain text.
  - **Agent modes** (`ai_mode` setting): `solve` (default) answers fully; `teach` is a Socratic tutor — `TEACHING_PROMPT` forbids ready-made code, allows one question per reply and a graded hint ladder. Strictness (`ai_teach_strictness`: `soft` 5 lines / `normal` 3 / `strict` 0) is appended to the prompt and also enforced in code: `enforce_teaching_rules()` retries once with `TEACHING_RETRY_NUDGE`, then hides any block above the limit and appends a guiding question. Switchable from the composer chip, `/mode`, `/strictness`, and Settings.  - `mcp_client.py`: Model Context Protocol client supporting **stdio** (newline JSON-RPC over a child process) and **streamable HTTP**; `initialize` → `tools/list` → `tools/call`. Tools are namespaced `server__tool` and offered to the model as function definitions.
- **`widgets/`**: Specialized Qt visual components and dialogs:
  - `QCodeEditor.py`: Modern code editor with syntax highlighting, line numbers, and completions.
  - `ConsoleWidget.py`: Integrated terminal, problems list, and file diagnostic viewer (supports copying and file export).
  - `ProjectIntelligenceDashboard.py`: Project intelligence dashboard, recommendations, structure trees, and graph editor (supports copying and file export).
  - `Explorer.py`, `GitPanel.py`, `SearchPanel.py`, `RunDebugPanel.py`, `TabWidget.py`, `ActivityBar.py`.
  - `animations.py`: Shared animation toolkit (fade, slide, pulse, flash, staggered reveals, animated splitter heights). Every helper is defensive against deleted Qt objects and always lands on the requested final state.
  - `AIAgentPanel.py`: AI agent sidebar (`ИИ-агент`) rendered as a **Telegram-style chat**: messages are real widget bubbles in a `QVBoxLayout` (not a QTextDocument — rich-text bubbles cannot be measured reliably there). Bubbles are painted by `_BubbleFrame`: vertical gradient, asymmetric corner radius, and a curved tail on the author's own bottom corner; consecutive messages from one author are grouped with tighter spacing. The user's messages are blue and right-aligned, answers grey and left-aligned. **No time stamps.** Two inline pickers select the **context scope** and the **model**. Streaming shows a single temporary "Думает…" bubble deleted the moment the answer arrives, so **no reasoning text survives**; the finished answer is rendered once as markdown. A message sent while the model is answering is **queued** (hint chip in the composer) and sent automatically when the current answer finishes. `/` opens a command menu, `@` completes project files. Requests run on `AIWorker` (QThread); `Esc` stops a streaming answer.
  - Context scope is a **radio group** (exactly one active: `none` / `file` / `project`). Opening a project selects `project`; closing it falls back to `none`. An explicitly chosen `file` scope is **never** overridden by that sync. Providers without a configured API key are hidden from the model menu.
- **`design/`**: Central design system tokens, `theme.qss` styling, SVG icons, and theme definitions (`themes.py`).
  - Typography: `theme.qss` declares families as the tokens `@ui_font@` / `@mono_font@`. `app/styling.py` resolves them once (`resolve_ui_font` → user setting `ui_font`, else the first installed candidate: Bahnschrift → Segoe UI Variable Text → Inter → Segoe UI) and substitutes them into the sheet, so no widget needs a hard-coded family.
  - `design/icons.py`: Codicon iconography. PyScribe ships VS Code's official `codicon.ttf` (`design/fonts/`), so the activity bar, explorer toolbar, terminal and window controls use the exact glyphs VS Code uses. `codicon_icon(name, size, color)` builds a retina-aware QIcon; `src/icons/*.svg` (generated by `tools/generate_icons.py`) provides the Seti-style file-type icons.
- **`ui/`**: Stable public UI facades (e.g. `titlebar.py`).
- **`utils/`**: Helper utilities (settings manager, compilation, process invocation).
- **`tools/`**: Developer scripts (`generate_icons.py` regenerates the explorer file-type icons).
- **`tests/`**: Unit and regression test suites (`test_editor_and_terminal.py` covers the editor/terminal regressions described below).

## 2. Dependency Direction & Principles

1. **Separation of Concerns**: Presentation (`widgets/`, `app/main_window.py`) depends on domain services (`core/`, `services/`), never the reverse.
2. **Single Responsibility**: `main.py` is an entry point, not a god-object. Subsystems are isolated into single-purpose modules under `app/`.
3. **Encoding & Binary Safety**: Text decoding handles UTF-8, UTF-8-SIG, UTF-16, CP1251, and falls back to hex view for binary files.
4. **Export & Diagnostics**: Problem lists and code recommendations support instant clipboard copying and multi-format export (`.md`, `.txt`, `.json`).

## 3. Visual System (VS Code-aligned)

All chrome metrics are uniform and defined in one place (`design/theme.qss`).
Do not hardcode sizes on individual widgets — that is what previously produced
mismatched text/icon sizes ("плывущий" интерфейс).

| Element | Height / size | Notes |
| :--- | :--- | :--- |
| Menu strip (title bar) | 40 px | menus 24 px hits, 13 px text |
| Activity bar | 48 px wide | 48×48 hits, 24 px codicons, 2 px active stripe |
| Sidebar title | 35 px | 11 px uppercase, letter-spaced |
| Explorer row | 22 px | 8 px indent step, 16 px file icons |
| Explorer toolbar button | 24×24 | 16 px codicons, borderless |
| Editor tab | 35 px | flat, active = accent top border |
| Panel tabs | 35 px | flat, active = accent underline |
| Editor status strip | 24 px | 12 px text |
| Inputs / buttons | 26 px | flat `#313131`, focus ring `#007FD4` |

Rules:
1. Only three font sizes exist in the chrome: 11 px (section titles, badges),
   12 px (secondary/status text), 13 px (body, lists, menus, tabs).
2. Radii are 2–4 px; there are no pills, glows or gradient buttons.
3. The accent colour (`#0078D4`) marks the active item and focus ring only.
4. Never set a widget-level stylesheet for chrome: put the rule in `theme.qss`
   (per-widget QSS is reserved for the terminal screen, where the user's font
   size must win).
5. Icons come from `design/icons.py` (codicons) or `src/icons/*.svg`; no emoji
   and no bespoke neon line art.
6. User-configurable values are appended after the design system by
   `app.styling.user_appearance_qss()`. That block must **never** set
   `background` on a generic `QWidget`: it is appended last, so it would win
   over `QLabel`/`QToolButton` `background: transparent` and every label would
   paint the window colour on top of cards and inputs (text rectangles that do
   not match their widget — the Git panel bug). Only top-level windows
   (`QMainWindow`, `QDialog`) and named chrome surfaces get a background there.

## 4. Editor & Terminal Contracts

### Code editor (`widgets/QCodeEditor.py`)

- Line operations (comment toggle, duplicate, delete, move) rewrite the document
  through a single `_replace_document_lines()` call, so each action is exactly
  one undo step and multi-line selections never lose text.
- Comment toggling follows VS Code semantics: all touched lines are commented,
  or all are uncommented, and the common indent is preserved.
- The editor never claims standard editing keys (`Ctrl+C/V/X/A/Z/Y/W/D`); those
  stay with `QPlainTextEdit`. Workbench actions arrive through `QShortcut` in
  `ModernMainWindow`, and every key sequence there must be unique.
- Deferred callbacks (`QTimer.singleShot`) must not capture widgets that can be
  destroyed; use a bound method that tolerates `RuntimeError`.

### Integrated terminal (`widgets/TerminalWidget.py`)

- **Two channels.** Typed commands go to the interactive shell. IDE-issued runs
  (`Run file`, `Run project`, tests, C# build) go through `start_run_process()`:
  a dedicated child `QProcess` whose stdout/stderr stream into the buffer line by
  line while the program runs, ending with an exit-code badge. The shell never
  echoes these commands, so output can never be mistaken for shell noise.
- Interactive programs work: Enter feeds the typed line to the running process's
  stdin; Ctrl+C kills it.
- Renders a real shell (PowerShell by default on Windows, `bash`/`zsh` on POSIX)
  inside the text buffer, with a PyScribe-drawn prompt.
- All I/O is UTF-8. On Windows the shell is initialised with
  `[Console]::OutputEncoding = UTF8`, and paths handed to PowerShell's `cd` are
  base64/UTF-16 encoded so non-ASCII directories survive the OEM stdin decoder.
- Shell noise (the `PS>` continuation prompt, our own echoed prompt, the init
  line and internal `cd` sync lines) is filtered **by count, never by content**,
  so user output can never be swallowed. The prompt is drawn only once the shell
  is actually running, and the init echo is discarded until its newline arrives.
- Tab completion shows an inline completion popup (files, directories, commands)
  with keyboard navigation instead of dumping matches into the buffer.
- Output is colourised per line (errors, warnings, success, paths) and ANSI SGR
  sequences are translated.

### GUI-thread budget (why animations never freeze)

Qt advances **every** animation from the GUI thread's event loop, so a long
synchronous call is not a "slow action" — it is a visible freeze of the whole
window. Anything that can take more than a few milliseconds is therefore
deferred, batched, cached or moved to a worker:

- **Project analysis** runs on `AnalysisWorker` (`QThread`) inside
  `ProjectIntelligenceDashboard`. `ModernMainWindow._ensure_engine_analysis()`
  only *starts* it; actions that need the result (architecture graph,
  defence passport) register with `_defer_until_analysis()` and are executed
  from `on_project_analysis_ready()` — or dropped with a status message from
  `on_project_analysis_failed()`, so a failure can neither hang the UI nor
  restart the analysis in a loop.
- **Completion indexing** reserves file batches with
  `WorkspaceIndex.take_batch_paths()`, parses them through
  `services/background.run_async()` and merges the result with
  `apply_parsed()`. `process_batch(limit, budget_ms=...)` keeps the synchronous
  fallback bounded in time.
- **Session restore** opens one tab per event-loop turn
  (`ProjectHandler._restore_next_session_file`), and the completion-index walk
  runs off-thread (`_start_index`).
- **Diagnostics for the active file** are cached by
  `(content fingerprint, analyzers, project root)` in `ConsoleWidget`, so
  switching tabs does not re-parse the file.
- **Git** status is queried when the panel is first shown, not while a project
  is opening — and every read (`refresh()` → `_collect_state()`) as well as
  pull/push/commit/stage runs on the thread pool (`_run_background`). Each
  ``git`` call spawns a process (~60–90 ms on Windows), so four of them on the
  GUI thread froze the window for half a second on every View refresh.
- **Typing** never re-indexes synchronously: `on_text_changed()` starts a 500 ms
  debounce (`_on_typing_settled`).

Animations themselves live in `widgets/animations.py`; every helper ends in the
requested final state, so an interrupted animation can never leave a widget
transparent or half-open.

### Child processes (no console windows)

PyScribe is a windowed process (`pythonw`), so Windows gives every console
program started from it **its own console window** — the black `cmd` window
that used to flash on each git call, compiler run or MCP start. Consequences:

- Every child process goes through `core/subprocess_utils`
  (`run_hidden()` / `popen_hidden()`, which add `CREATE_NO_WINDOW` and a hidden
  `STARTUPINFO`). `tests/test_subprocess_window.py` fails if a raw
  `subprocess.run/Popen` call appears anywhere in `app/`, `core/`, `services/`,
  `utils/` or `widgets/`.
- The integrated terminal is the **user's interactive shell**. Background work
  (git, compilers, analysis helpers, MCP servers) is not written there: it
  would mix machine output with user commands, steal the prompt and require
  parsing text to learn exit codes. Background jobs report through the panel
  status line / Output tab instead.
- `QProcess` used by the terminal sets the same flag through
  `createProcessArgumentsModifier`, so the shell itself never opens a visible
  console either.

### UI scale (accessibility)

`app/ui_scale.py` implements the global workbench scale (`Настройки → Интерфейс →
Масштаб интерфейса`, 75–200%, `Ctrl+Alt+=` / `Ctrl+Alt+−` / `Ctrl+Alt+0`).
It scales the application font, rewrites every `Npx` metric in the stylesheet,
and asks widgets implementing `on_ui_scale_changed(percent)` to resize their
fixed-size parts (activity bar, explorer toolbar, title bar, panel strip). Fixed
pixel sidebar/panel sizes are scaled in `ModernMainWindow.apply_accessibility_scale()`.

### AI agent (`services/agent_harness.py`)

`Ctrl+Shift+I` (or the sparkle icon in the activity bar) opens the agent.
It talks to any OpenAI-compatible `/chat/completions` endpoint configured in
`Настройки → ИИ-агент`; Claude uses the native `/messages` protocol. The panel
never blocks: requests run on `AIWorker` and stream token by token.

The tool loop is owned by **`AgentHarness`**, not by the panel:

- The loop keeps calling tools until the model writes its final answer. There
  is **no low round limit** (the old `MAX_TOOL_ROUNDS = 6` is why the agent read
  a few files and "stopped mid-way"); only a safety fuse of 200 rounds exists.
- Tool results are passed back **in full**. The old code cut every result at
  8000 characters, so the model never saw the rest of a file and re-read it
  until the rounds ran out. `read_file` also supports `offset`/`limit`.
- Identical `(tool, arguments)` calls are detected after 3 executions: the
  result is reused and the model is told to continue instead of looping.
- Transient provider errors (429/5xx/network) are retried with backoff;
  non-retryable errors (401/402/404) surface immediately.
- Usage is summed over all rounds and shown in the "Готово" line.

**No token limits by default.** The request does not send `max_tokens` at all
(the provider's own maximum applies); an explicit user budget is only sent when
it is larger than the old 8192 default. Context is not character-truncated.
Anthropic still requires `max_tokens`, so a generous 32 000 is used there.
A truncated answer is auto-continued while the provider reports `length`.

**Reasoning depth.** `ai_reasoning_effort` = `auto | none | low | medium | high`
is selectable in the chat composer («Мысли: …»), in Настройки → ИИ-агент and
via `/reasoning`. OpenAI-compatible endpoints receive `reasoning_effort`;
Claude receives `thinking` with a budget (and `temperature = 1`). If a server
rejects the parameter with 400, the request layer retries once without it and
remembers that for the session.

**Context and cache (`services/ai_context.py`).** The project map is a compact
per-directory summary; @-mentioned files are sent whole from an mtime-keyed
stat-cache, so unchanged files are not re-read. The stable prefix (system prompt
+ tool catalogue) is marked `cache_control: ephemeral` for Anthropic-style
servers, so prompt caching works across rounds. The conversation is persisted to
`<project>/.pyscribe/ai_chat.json` and restored when the project is reopened;
`/clear` removes it. A "Готово" line reports tokens, tool count and cache hits.

**Chat output policy.** The agent works through **code**, not chat text: the
system prompt tells the model to apply changes with `write_file` and answer with
a short 3–6 line summary plus a verification command. The transcript contains
only the conversation: tool calls are a **single live activity line**
(`› read_file · path`) that is updated while the request runs and removed when
the answer lands. Nothing about the tool loop stays in the history — no step
lines, no JSON, no usage text.

Intermediate narration is **not part of the answer**. Models stream "Читаю файл
и проверяю…" before a tool call; the old loop concatenated every round, which
pushed that narration into the final bubble (and looked like reasoning that never
went away). `AgentHarness` now keeps only the last round's text as the answer.

Chat typography follows the workbench settings: `ChatMessage` derives the body
size from `ui_font_size` × `ui_scale_percent` (+2 px, never below 16 px), uses a
1.65 line height and 12 px paragraph spacing. List items are two-column tables
with a short marker cell (hanging indent), so wrapped text aligns under the item
text instead of under its number; a fully bold line is rendered as a subheading.
Code blocks never go below 11 pt even when the editor font is configured at
9 pt.

A single muted metrics line under the composer mirrors the harness status bar:
answers, tool steps, tokens per second, completion tokens and the local file
cache hit rate. It is updated on each finished answer and cleared by `/clear`;
the transcript itself carries no usage lines any more, so the chat stays focused
on the explanation.

Markdown tables render with a quiet header background, equal column widths,
top-aligned cells and visible row separators. Inline code **inside table cells**
is plain monospace: the rounded chip used in prose turned a comparison table
into a wall of gray blocks. Restored-session notices are centered muted lines,
not tool-style chips.

**Access modes.** `Полный доступ` (`ai_access_mode = "full"`) performs file
writes and terminal commands **without confirmation dialogs** — that is the
default working mode. `Только чтение` and `Только запись` ask before mutating
actions (`LocalToolbox._ask`), and the settings switches
`ai_allow_file_edits` / `ai_allow_commands` can remove the tools entirely.
Without this, the agent asked on every edit and never finished a task.

Pressing "Применить" inserts the first fenced code block on its own lines and
selects it.
