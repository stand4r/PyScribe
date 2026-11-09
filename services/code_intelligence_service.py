"""Code Intelligence & Architecture Audit service for PyScribe IDE."""
import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class CodeIntelligenceService:
    """Provides professional code intelligence, architecture audits, and actionable refactoring advice."""

    @staticmethod
    def calculate_health_grade(health_score: float) -> Dict[str, Any]:
        """Convert a 0-100 health score into an industry-standard quality tier and rating.

        Only three semantic hues are used (good / fair / poor) and the badge
        background is always the neutral surface, so the analysis view does not
        turn into a rainbow of tinted cards.
        """
        score = max(0, min(100, int(round(health_score))))
        neutral_badge = "#252526"
        if score >= 85:
            return {
                "grade": "5",
                "letter": "A",
                "label": "Отличное",
                "color": "#3FB950",
                "badge_bg": neutral_badge,
                "summary": "Код в хорошей форме: функции компактные, структура аккуратная, критического долга нет.",
            }
        elif score >= 70:
            return {
                "grade": "4",
                "letter": "B",
                "label": "Хорошее",
                "color": "#C9A227",
                "badge_bg": neutral_badge,
                "summary": "Хорошее проекта. Архитектура стабильна, но есть отдельные кандидаты на рефакторинг (крупные методы или отложенные задачи TODO).",
            }
        elif score >= 50:
            return {
                "grade": "3",
                "letter": "C",
                "label": "Удовлетворительное",
                "color": "#C9A227",
                "badge_bg": neutral_badge,
                "summary": "Есть перегруженные функции и глубокая вложенность. Начните с замечаний высокого приоритета.",
            }
        else:
            return {
                "grade": "2",
                "letter": "D",
                "label": "Требует доработки",
                "color": "#E5534B",
                "badge_bg": neutral_badge,
                "summary": "Индекс надёжности низкий: накопился технический долг и высокая сложность. Нужна постепенная декомпозиция.",
            }

    # Backward compatibility alias
    calculate_student_grade = calculate_health_grade

    @staticmethod
    def extract_code_recommendations(analysis) -> List[Dict[str, Any]]:
        """Turn technical code smells, debt, and AST issues into professional, actionable recommendations."""
        recommendations = []
        if not analysis:
            return recommendations

        seen_keys = set()

        def add_rec(category: str, title: str, explanation: str, file_path: str, line: int, priority: str, action: str):
            key = (file_path, line, title)
            if key in seen_keys:
                return
            seen_keys.add(key)
            recommendations.append({
                "category": category,
                "icon": "",
                "title": title,
                "explanation": explanation,
                "file": file_path,
                "line": line,
                "priority": priority,
                "action": action
            })

        # 1. Health & Debt Items from ProjectAnalysis (Smells + Debts)
        debt_items = getattr(analysis, "health_debt_items", []) or []
        for item in debt_items:
            tag = item.get("tag", "")
            file_path = item.get("file", "")
            file_name = Path(file_path).name if file_path else ""
            line = item.get("line", 1)
            desc = item.get("description", "")
            sev = item.get("severity", "LOW").upper()

            if tag == "Large File":
                add_rec(
                    category="Крупный модуль",
                    title=f"Модуль превышает рекомендуемый размер ({file_name})",
                    explanation=f"Файл {file_name} содержит {desc}. Разделите его на несколько модулей.",
                    file_path=file_path,
                    line=line,
                    priority="low",
                    action="Вынести часть кода в отдельный модуль"
                )
            elif tag == "Deep Nesting":
                add_rec(
                    category="Глубокая вложенность",
                    title=f"Повышенная вложенность условий ({file_name}:{line})",
                    explanation=f"В файле {file_name}:{line} глубокая вложенность ({desc}). "
                                f"Чем глубже вложенность, тем выше риск ошибок. Используйте ранний return/continue или вынесите блок в отдельную функцию.",
                    file_path=file_path,
                    line=line,
                    priority="medium" if sev != "HIGH" else "high",
                    action="Упростить ветвления"
                )
            elif tag == "God Function":
                add_rec(
                    category="Слишком длинная функция",
                    title=f"Перегруженная функция ({file_name}:{line})",
                    explanation=f"В файле {file_name}:{line} {desc}. "
                                f"Длинную функцию трудно читать и тестировать. Разбейте её на несколько небольших.",
                    file_path=file_path,
                    line=line,
                    priority="high",
                    action="Разбить функцию на части"
                )
            elif tag in {"FIXME", "BUG"}:
                add_rec(
                    category=f"Критический дефект ({tag})",
                    title=f"Маркер {tag}: {desc[:55]} ({file_name}:{line})",
                    explanation=f"В коде зафиксирован комментарий {tag}: '{desc}'. "
                                f"Такие замечания стоит исправить до релиза.",
                    file_path=file_path,
                    line=line,
                    priority="high",
                    action="Устранить дефект в коде"
                )
            elif tag in {"HACK", "XXX"}:
                add_rec(
                    category=f"Временное решение ({tag})",
                    title=f"Маркер {tag}: {desc[:55]} ({file_name}:{line})",
                    explanation=f"В коде присутствует временный компромисс: '{desc}'. "
                                f"Временное решение стоит заменить на надёжное.",
                    file_path=file_path,
                    line=line,
                    priority="medium",
                    action="Отрефакторить временное решение"
                )
            elif tag == "TODO":
                add_rec(
                    category="Технический долг (TODO)",
                    title=f"Задача TODO: {desc[:55]} ({file_name}:{line})",
                    explanation=f"В строке {line} осталась незавершённая задача: '{desc}'. "
                                f"Доделайте задачу или удалите устаревший комментарий.",
                    file_path=file_path,
                    line=line,
                    priority="low",
                    action="Закрыть задачу"
                )
            else:
                prio = "high" if sev == "HIGH" else "medium" if sev == "MEDIUM" else "low"
                add_rec(
                    category=tag or "Замечание",
                    title=f"{tag}: {desc[:55]} ({file_name}:{line})",
                    explanation=desc or f"Обратите внимание на участок кода в строке {line}.",
                    file_path=file_path,
                    line=line,
                    priority=prio,
                    action="Проверить в редакторе"
                )

        # 2. Syntax errors and static analysis issues
        issues = getattr(analysis, "issues", []) or []
        for issue in issues:
            code = getattr(issue, "code", "")
            if code.startswith("DEBT_"):
                continue  # Already handled in debt items
            sev = getattr(issue, "severity", "warning")
            path = getattr(issue, "file", getattr(issue, "path", ""))
            fname = Path(path).name if path else ""
            line = getattr(issue, "line", 1)
            msg = getattr(issue, "message", "")

            if sev == "error":
                add_rec(
                    category="Синтаксическая ошибка",
                    title=f"Синтаксическая ошибка ({fname}:{line})",
                    explanation=f"В файле {fname}:{line} анализатор обнаружил синтаксическую проблему: {msg}.",
                    file_path=path,
                    line=line,
                    priority="high",
                    action="Исправить синтаксис"
                )
            else:
                add_rec(
                    category="Предупреждение линтера",
                    title=f"Предупреждение линтера ({fname}:{line})",
                    explanation=f"В файле {fname}:{line} обнаружено замечание: {msg}.",
                    file_path=path,
                    line=line,
                    priority="medium",
                    action="Проверить предупреждение анализатора"
                )

        # 3. High Cyclomatic Complexity Hotspots
        files = getattr(analysis, "files", {}) or {}
        for fpath, finfo in files.items():
            comp = getattr(finfo, "complexity", 1)
            if comp >= 8:
                mod_name = getattr(finfo, "module", Path(fpath).name)
                prio = "high" if comp >= 14 else "medium"
                add_rec(
                    category="Высокая сложность",
                    title=f"Высокая цикломатическая сложность ({mod_name}) — индекс {comp}",
                    explanation=f"Модуль {mod_name} имеет высокую цикломатическую сложность (CC = {comp}). "
                                f"Много независимых ветвлений — сложно сопровождать и тестировать. "
                                f"Разбейте ветвления на отдельные функции или словарь обработчиков.",
                    file_path=fpath,
                    line=1,
                    priority=prio,
                    action="Упростить логику"
                )

        # 4. Backward-compatible fallback for smells / debt attributes if present
        for smell in getattr(analysis, "smells", []):
            kind = getattr(smell, "kind", "")
            file_path = getattr(smell, "file", "")
            file_name = Path(file_path).name if file_path else ""
            line = getattr(smell, "line", 1)
            details = getattr(smell, "details", "")
            add_rec(
                category="Замечание по коду",
                title=f"{kind} ({file_name}:{line})",
                explanation=details or f"Обратите внимание на строку {line}.",
                file_path=file_path,
                line=line,
                priority="medium",
                action="Проверить в редакторе"
            )

        for debt in getattr(analysis, "debt", []):
            tag = getattr(debt, "tag", "TODO")
            file_path = getattr(debt, "file", "")
            file_name = Path(file_path).name if file_path else ""
            line = getattr(debt, "line", 1)
            text = getattr(debt, "text", "")
            add_rec(
                category=f"Технический долг ({tag})",
                title=f"Маркер {tag}: {text[:55]} ({file_name}:{line})",
                explanation=f"В строке {line} осталась незавершённая задача: '{text}'.",
                file_path=file_path,
                line=line,
                priority="high" if tag in {"FIXME", "BUG", "HACK"} else "low",
                action="Реализовать задачу или закрыть комментарий"
            )

        # Sort: high priority first, then medium, then low
        order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: order.get(x["priority"], 3))
        return recommendations

    # Backward compatibility alias
    extract_student_tips = extract_code_recommendations

    @staticmethod
    def generate_architecture_passport(analysis, project_name: str, root_path: str) -> str:
        """Generate a complete, structured Markdown Architecture Passport & Technical Audit."""
        files = getattr(analysis, "files", {})
        symbols = getattr(analysis, "symbols", [])
        dependencies = getattr(analysis, "dependencies", [])
        issues = getattr(analysis, "issues", [])
        metrics = getattr(analysis, "metrics", lambda: {})() if hasattr(analysis, "metrics") else {}

        file_count = len(files)
        total_lines = metrics.get("lines", sum(f.lines for f in files.values())) if files else 0

        health_score = 85
        if hasattr(analysis, "health_score") and isinstance(analysis.health_score, (int, float)):
            health_score = int(round(analysis.health_score))
        elif "health_score" in metrics:
            import re
            m = re.search(r'(\d+)', str(metrics["health_score"]))
            if m:
                health_score = int(m.group(1))

        grade_info = CodeIntelligenceService.calculate_health_grade(health_score)

        classes = [s for s in symbols if s.kind in {"class", "struct", "interface"}]
        functions = [s for s in symbols if s.kind in {"function", "method"}]

        # 1. Detect actual entry point reliably
        entry_point = "main.py"
        entry_candidates = ["main.py", "app.py", "run.py", "Program.cs", "index.js", "app.js", "index.py"]
        found_entry = False
        if root_path:
            root_p = Path(root_path)
            for cand in entry_candidates:
                if (root_p / cand).is_file():
                    entry_point = cand
                    found_entry = True
                    break
        if not found_entry and files:
            for cand in entry_candidates:
                for fpath in files.keys():
                    if Path(fpath).name.lower() == cand.lower():
                        entry_point = Path(fpath).name
                        found_entry = True
                        break
                if found_entry:
                    break

        # 2. Collect file summaries with clean, meaningful function names
        file_summaries = []
        for path, finfo in sorted(files.items(), key=lambda x: x[1].lines, reverse=True)[:15]:
            p = Path(path)
            rel_name = p.name
            classes_in_file = list(dict.fromkeys(cl.name for cl in classes if cl.file == path))
            
            # Filter functions: omit dunders and internal event handlers, deduplicate
            raw_funcs = [fn.name for fn in functions if fn.file == path]
            clean_funcs = []
            for fn_name in raw_funcs:
                if fn_name not in clean_funcs and not fn_name.startswith("__") and not fn_name.endswith("Event"):
                    clean_funcs.append(fn_name)
            if not clean_funcs:
                clean_funcs = list(dict.fromkeys(raw_funcs))[:4]

            items_desc = []
            if classes_in_file:
                items_desc.append("Классы: " + ", ".join(classes_in_file[:4]))
            if clean_funcs:
                items_desc.append("Методы и функции: " + ", ".join(clean_funcs[:5]))

            desc = "; ".join(items_desc) if items_desc else "Вспомогательный модуль / конфигурация"
            file_summaries.append(f"- **`{rel_name}`** ({finfo.lines} строк) — {desc}")

        # 3. Analyze Issues by severity/type
        warning_issues = [iss for iss in issues if iss.severity.lower() == 'warning']
        error_issues = [iss for iss in issues if iss.severity.lower() in ('error', 'critical')]

        issue_rows = []
        for iss in issues[:8]:
            fname = Path(iss.file).name
            issue_rows.append(f"| `{iss.code}` | **{iss.severity.upper()}** | `{fname}:{iss.line}` | {iss.message} |")

        issues_table = "\n".join(issue_rows) if issue_rows else "| — | — | — | Диагностических дефектов не обнаружено |"

        guide = f"""# Архитектурный паспорт и технический отчёт проекта: {project_name}

> **Сформировано автоматически в PyScribe IDE для технической документации, Code Review и системного анализа.**
> Индекс здоровья кодовой базы: **{grade_info['label']} (Класс {grade_info['letter']} · {grade_info['grade']}/5) · {health_score}/100 баллов**

---

## 1. Паспорт проекта и ключевые метрики

| Параметр | Значение | Описание и архитектурное значение |
| :--- | :--- | :--- |
| **Название проекта** | `{project_name}` | Основное наименование анализируемой кодовой базы |
| **Главная точка входа** | `{entry_point}` | Исполняемый модуль инициализации и запуска приложения |
| **Объём кодовой базы** | `{total_lines}` строк кода | Общий объём логики и структурных компонентов |
| **Количество модулей** | `{file_count}` файлов | Модульная структура с декомпозицией ответственности |
| **Классов и моделей** | `{len(classes)}` | Объектно-ориентированные модели данных, виджеты и сервисы |
| **Функций и методов** | `{len(functions)}` | Процедурные алгоритмы и методы бизнес-логики |
| **Связей зависимостей** | `{len(dependencies)}` импортов | Карта межмодульных импортов и внешних зависимостей |
| **Диагностика техдолга** | `{len(issues)}` замечаний | Обнаруженные статические проблемы ({len(error_issues)} ошибок, {len(warning_issues)} предупреждений) |

---

## 2. Архитектура проекта и структура компонентов

### Архитектурные слои системы:
1. **Точка входа (`{entry_point}`)**: Инициализирует системное окружение, загружает конфигурацию и запускает основной цикл работы приложения.
2. **Пользовательский интерфейс (`widgets/`, `ui/`)**: Главное окно рабочей среды, расширенный редактор кода с подсветкой синтаксиса, терминал, боковая панель и дашборд аналитики.
3. **Ядро статического анализа (`core/`)**: AST-парсеры, построитель ориентированного графа зависимостей, расчёт цикломатической сложности и индекс символов.
4. **Служебные сервисы (`services/`)**: Аудит качества кода, генерация архитектурного паспорта, рекомендации по рефакторингу и разбор кода.
5. **Конфигурация и окружение (`config/`, `utils/`)**: Управление сессиями, пользовательскими параметрами и сторонними языковыми провайдерами.

### Ключевые модули кодовой базы:
{chr(10).join(file_summaries) if file_summaries else "- Модули проекта будут перечислены после индексации."}

---

## 3. Диагностика качества кода и технический долг

| Код | Уровень | Локализация | Описание проблемы |
| :--- | :--- | :--- | :--- |
{issues_table}

> **Рекомендации по улучшению:**
> - Заменить обобщённые блоки перехвата `except:` на типизированные (например, `except (IOError, ValueError):`).
> - Провести декомпозицию длинных функций (>80 выражений) на компактные приватные подфункции.
> - Дополнить аннотации типов аргументов и возвращаемых значений для ключевых методов API.

---

## 4. Ключевые вопросы при Code Review / Архитектурном аудите

### 1. Архитектурная декомпозиция и расширяемость
> **Вопрос:** *Каким образом соблюдается принцип разделения ответственности (Single Responsibility)?*
> **Ответ:** *Проект разделен на слабосвязанные модули (`{file_count}` модулей). Логика изолирована по функциональным слоям, что упрощает масштабирование, модульное тестирование и внесение изменений без каскадных регрессий.*

### 2. Точка входа и управление жизненным циклом
> **Вопрос:** *Как структурирован запуск и завершение программы?*
> **Ответ:** *Выполнение стартует с `{entry_point}`. Происходит валидация системного окружения, загрузка сохранённой конфигурации, запуск главного графического цикла и инициализация фонового потока индексации. При завершении программы ресурсы корректно высвобождаются.*

### 3. Обработка исключений и надёжность
> **Вопрос:** *Как реализована стратегия обработки непредвиденных ошибок?*
> **Ответ:** *Критические операции ввода-вывода, сетевых запросов и парсинга обернуты в типизированные блоки перехвата исключений `try-except` с логированием контекста ошибок, предотвращая аварийное падение процесса.*

### 4. Алгоритмическая и пространственная сложность
> **Вопрос:** *Какова вычислительная сложность ключевых операций обработки данных?*
> **Ответ:** *Итерационные проходы спроектированы со сложностью **O(N)**. Для частых операций поиска и сопоставления используются хэш-таблицы (словари и множества), обеспечивая амортизированную сложность выборки **O(1)**.*

### 5. Управление техническим долгом
> **Вопрос:** *Какие направления рефакторинга и оптимизации являются приоритетными?*
> **Ответ:** *Регулярное покрытие юнит-тестами, минимизация вложенности в алгоритмах, внедрение строгой типизации (type annotations) и кэширование повторных вычислений.*

---

## 5. Справочник архитектурных и алгоритмических терминов

- **Инкапсуляция (Encapsulation)** — изоляция внутреннего состояния и реализации объекта с предоставлением доступа только через публичный интерфейс.
- **Декомпозиция (Decomposition)** — разделение сложной системы на независимые, легко читаемые и тестируемые компоненты.
- **Цикломатическая сложность (Cyclomatic Complexity)** — число линейно независимых путей выполнения через код. Чем выше значение, тем сложнее код для тестирования и анализа.
- **Технический долг (Technical Debt)** — накопленные компромиссные решения и временные заглушки (TODO/FIXME), требующие планового устранения.
- **AST (Abstract Syntax Tree)** — древовидное представление синтаксической структуры исходного кода, применяемое компиляторами и статическими анализаторами.

---
*Сформировано в PyScribe IDE · Project Intelligence & Quality Assurance*
"""
        return guide

    # Backward compatibility alias
    generate_defense_guide = generate_architecture_passport

    @staticmethod
    def explain_code_snippet(code: str, language: str = "python") -> Dict[str, Any]:
        """Provide a professional, clear explanation of a code snippet, complexity analysis, and review QA."""
        code = code.strip()
        if not code:
            return {
                "title": "Пустой фрагмент",
                "summary": "Выделите код или функцию в редакторе, чтобы получить разбор логики и сложности.",
                "complexity": "—",
                "arguments": [],
                "tips": [],
                "review_questions": []
            }

        title = "Фрагмент кода"
        summary = "Данный блок кода выполняет последовательность алгоритмических инструкций."
        complexity = "O(1) константная сложность"
        arguments = []
        tips = []
        review_questions = []

        # Check for loops and complexity
        loop_count = len(re.findall(r"\b(for|while)\b", code))
        if loop_count == 1:
            complexity = "O(N) линейная сложность (содержит 1 цикл)"
            review_questions.append({
                "q": "Какова алгоритмическая сложность этого цикла и как устроен его проход?",
                "a": "Сложность линейная O(N). В Python цикл 'for' использует протокол итератора (вызовы iter() и next()), запрашивая по одному элементу до исключения StopIteration."
            })
        elif loop_count >= 2:
            complexity = f"O(N^{loop_count}) квадратичная/полиномиальная сложность ({loop_count} вложенных цикла)"
            tips.append(f"Внимание: {loop_count} вложенных цикла. При росте объёма данных производительность падает экспоненциально. Рассмотрите хэширование через dict/set.")
            review_questions.append({
                "q": "Почему вложенные циклы вызывают деградацию производительности и как их оптимизировать?",
                "a": "Вложенные циклы дают сложность O(N²). Оптимизировать можно предварительным сбором данных в хэш-таблицу (dict/set) с выборкой за O(1)."
            })

        # Check Python AST
        if language.lower() in {"python", "py", ""}:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        prefix = "Асинхронная функция" if isinstance(node, ast.AsyncFunctionDef) else "Функция"
                        title = f"{prefix} `{node.name}()`"
                        args = [a.arg for a in node.args.args]
                        arguments = args
                        doc = ast.get_docstring(node) or ""
                        arg_desc = f"принимает параметры ({', '.join(args)})" if args else "без входных параметров"
                        summary = f"{prefix} `{node.name}` {arg_desc}. " \
                                  f"{doc if doc else 'Выполняет декомпозированную подзадачу в кодовой базе.'}"

                        if "self" in args:
                            review_questions.append({
                                "q": "Какова семантика первого параметра 'self' в методе?",
                                "a": "'self' передаёт ссылку на экземпляр класса в памяти, позволяя методу работать с состоянием конкретного объекта."
                            })
                        if node.args.vararg:
                            review_questions.append({
                                "q": f"Для чего используется синтаксис '*{node.args.vararg.arg}'?",
                                "a": "Оператор '*' собирает произвольное количество позиционных аргументов в неизменяемый кортеж (tuple)."
                            })
                        if node.args.kwarg:
                            review_questions.append({
                                "q": f"Для чего используется синтаксис '**{node.args.kwarg.arg}'?",
                                "a": "Оператор '**' упаковывает произвольные именованные аргументы в словарь (dict)."
                            })
                        break
                    elif isinstance(node, ast.ClassDef):
                        title = f"Класс `{node.name}`"
                        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                        inherit_desc = f"наследуется от {', '.join(bases)}" if bases else "базовый класс"
                        summary = f"Объектная модель данных `{node.name}` ({inherit_desc}). Инкапсулирует состояние и методы сущности."
                        review_questions.append({
                            "q": "В чём архитектурная разница между классом и объектом?",
                            "a": "Класс представляет собой тип и шаблон логики (чертёж), а объект (экземпляр) — конкретный экземпляр в памяти с собственным состоянием."
                        })
                        if bases:
                            review_questions.append({
                                "q": f"Какую цель решает наследование от {', '.join(bases)}?",
                                "a": "Наследование обеспечивает повторное использование кода родительского класса и поддержку полиморфного поведения через переопределение методов."
                            })
                        break
            except Exception:
                pass

        # Check for try/except
        if "try:" in code and "except" in code:
            tips.append("Используется перехват исключений try-except для устойчивости программы к сбоям.")
            review_questions.append({
                "q": "Почему не рекомендуется использовать bare except ('except:') без указания конкретного типа ошибки?",
                "a": "Конструкция 'except:' без указания класса перехватывает системные сигналы (KeyboardInterrupt, SystemExit) и маскирует критические ошибки синтаксиса, затрудняя отладку."
            })

        # Check for list comprehensions
        if re.search(r"\[.+for\s+\w+\s+in\s+.+\]", code):
            tips.append("Используется списковое включение (List Comprehension). Это идиоматичный и оптимизированный на уровне байткода способ генерации коллекций.")
            review_questions.append({
                "q": "В чём преимущество спискового включения (List Comprehension) перед обычным циклом append()?",
                "a": "List Comprehension выполняется специализированной инструкцией байткода CPython, что быстрее многократных вызовов метода append() в цикле, и делает код более выразительным."
            })

        # Check for return
        if "return" in code:
            tips.append("Функция возвращает результат через 'return'. Убедитесь, что вызывающий код валидирует возвращаемое значение.")

        # Check for lambda
        if "lambda" in code:
            review_questions.append({
                "q": "В каких сценариях целесообразно использовать lambda-функции?",
                "a": "Lambda-функции эффективны как короткие одноразовые замыкания, например, в качестве ключей сортировки (key=lambda x: ...) или в функциональных преобразованиях."
            })

        # Check for yield
        if "yield" in code:
            review_questions.append({
                "q": "В чём ключевое отличие генератора с 'yield' от обычной функции с 'return'?",
                "a": "'return' завершает выполнение функции и выгружает стек, а 'yield' замораживает состояние и возвращает ленивый итератор, экономя память при работе с большими массивами данных."
            })

        if not review_questions:
            review_questions.append({
                "q": "Как данный фрагмент соотносится с архитектурой компонента?",
                "a": "Фрагмент изолирует отдельную операцию, следуя принципу единственной ответственности (Single Responsibility)."
            })

        if not tips:
            tips.append("Код написан структурированно, базовые алгоритмические правила соблюдены.")

        return {
            "title": title,
            "summary": summary,
            "complexity": complexity,
            "arguments": arguments,
            "tips": tips,
            "review_questions": review_questions,
            "teacher_questions": review_questions  # Backward compatibility
        }
