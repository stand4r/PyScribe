import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.project_intelligence import ProjectIntelligenceEngine
from core.analyzers.registry import analyzer_map



def test_all_analyzers_are_registered():
    specs = analyzer_map()
    assert {"structure", "dependencies", "metrics", "health", "security", "binaries"} <= set(specs)


def test_empty_analyzer_selection_is_a_true_noop(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('should not be scanned')\n", encoding="utf-8")
    engine = ProjectIntelligenceEngine(str(tmp_path), enabled_analyzers=[])
    result = engine.analyze()
    assert result.files == {}
    assert result.issues == []


def test_python_structure_analysis(tmp_path: Path):
    source = tmp_path / "main.py"
    source.write_text("class A:\n    def run(self):\n        return 1\n", encoding="utf-8")
    engine = ProjectIntelligenceEngine(str(tmp_path), enabled_analyzers={"structure"})
    result = engine.analyze()
    assert str(source) in result.files
    assert any(symbol.name == "A" for symbol in result.symbols)
    assert any(symbol.name == "run" for symbol in result.symbols)


if __name__ == "__main__":
    test_all_analyzers_are_registered()
    print("test_all_analyzers_are_registered: PASS")
    with tempfile.TemporaryDirectory() as td:
        test_empty_analyzer_selection_is_a_true_noop(Path(td))
        print("test_empty_analyzer_selection_is_a_true_noop: PASS")
    with tempfile.TemporaryDirectory() as td:
        test_python_structure_analysis(Path(td))
        print("test_python_structure_analysis: PASS")
    print("ALL PROJECT INTELLIGENCE TESTS PASSED!")

