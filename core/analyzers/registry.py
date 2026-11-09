"""Built-in Project Intelligence analyzer registry."""
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass(frozen=True)
class AnalyzerSpec:
    key: str
    name: str
    category: str
    description: str
    optional_backend: str = ""

ANALYZERS: Tuple[AnalyzerSpec, ...] = (
    AnalyzerSpec("structure", "Структура кода", "Код", "Файлы, классы, функции, методы и символы."),
    AnalyzerSpec("dependencies", "Зависимости", "Код", "Импорты, связи и циклические зависимости.", "networkx"),
    AnalyzerSpec("metrics", "Метрики", "Качество", "SLOC, сложность и показатели поддерживаемости.", "radon"),
    AnalyzerSpec("health", "Качество и техдолг", "Качество", "Code smells, TODO/FIXME/HACK и итоговый Health Score."),
    AnalyzerSpec("security", "Безопасность", "Безопасность", "Статические проверки опасных конструкций и Bandit для Python.", "bandit"),
    AnalyzerSpec("binaries", "Бинарные файлы", "Артефакты", "PE, ELF, Mach-O, DEX, импорты, секции и метаданные.", "lief / capstone"),
)

def analyzer_map() -> Dict[str, AnalyzerSpec]:
    """Return analyzer specifications keyed by stable configuration id."""
    return {item.key: item for item in ANALYZERS}
