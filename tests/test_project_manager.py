"""Tests for ProjectManager deletion and toolchain detection."""
import os
import sys
import tempfile
from pathlib import Path

# Ensure root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from widgets.ProjectManager import project_manager
from utils.toolchain_detector import detect_all_toolchains, build_run_command_for_file


def test_project_delete_case_insensitive():
    """Verify projects can be deleted regardless of path casing on Windows."""
    test_dir = os.path.join(tempfile.gettempdir(), "py_scribe_del_test_case")
    os.makedirs(test_dir, exist_ok=True)
    
    cfg = project_manager.create_project(test_dir, name="CaseDelTest")
    assert cfg is not None
    
    # Try deleting with upper case
    res = project_manager.delete_project(test_dir.upper())
    assert res is True
    
    # Verify no longer present
    recent_names = [p.name for p in project_manager.get_recent_projects()]
    assert "CaseDelTest" not in recent_names


def test_toolchain_detector():
    """Verify toolchain detector finds Python and builds valid execution commands."""
    toolchains = detect_all_toolchains()
    assert "python" in toolchains
    assert toolchains["python"]["found"] is True
    
    cmd, err = build_run_command_for_file("script.py")
    assert cmd is not None
    assert "script.py" in cmd
    assert err is None


if __name__ == "__main__":
    test_project_delete_case_insensitive()
    print("test_project_delete_case_insensitive: PASS")
    test_toolchain_detector()
    print("test_toolchain_detector: PASS")
    print("ALL TESTS PASSED!")
