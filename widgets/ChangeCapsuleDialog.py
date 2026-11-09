"""PyScribe Change Capsule: a deterministic change-impact passport for a project."""
from pathlib import Path
import subprocess
from PyQt5 import QtWidgets

from core.subprocess_utils import run_hidden


class ChangeCapsuleDialog(QtWidgets.QDialog):
    """Generate a human-readable risk/impact capsule from Git and project analysis."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.window_ref = main_window
        self.setWindowTitle("Change Capsule")
        self.resize(760, 620)
        self._build()
        self._generate()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        title = QtWidgets.QLabel("Change Capsule")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        subtitle = QtWidgets.QLabel("Паспорт текущих изменений: что изменилось, что затронуто и что стоит проверить перед commit.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("dialogSubtitle")
        root.addWidget(subtitle)
        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("capsuleSummary")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        root.addWidget(self.output, 1)
        buttons = QtWidgets.QHBoxLayout()
        refresh = QtWidgets.QPushButton("Пересчитать")
        refresh.clicked.connect(self._generate)
        close = QtWidgets.QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        buttons.addStretch(); buttons.addWidget(refresh); buttons.addWidget(close)
        root.addLayout(buttons)

    def _git(self, root, args):
        try:
            p = run_hidden(["git", *args], cwd=str(root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", timeout=8)
            return p.returncode == 0, p.stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def _generate(self):
        project = getattr(self.window_ref, "current_project", None)
        if not project:
            self.summary.setText("Откройте проект, чтобы построить Change Capsule.")
            self.output.setPlainText("")
            return
        root = Path(project.root_path)
        ok, status = self._git(root, ["status", "--porcelain"])
        if not ok:
            self.summary.setText("Git недоступен для проекта. Capsule требует Git-рабочее дерево.")
            self.output.setPlainText(status)
            return
        files = []
        for line in status.splitlines():
            if len(line) >= 3:
                files.append(line[3:].strip().strip('"'))
        analysis = getattr(getattr(self.window_ref, "intelligence_panel", None), "analysis", None)
        impacted = set()
        if analysis:
            changed_abs = {str((root / f).resolve()) for f in files if (root / f).exists()}
            for info in getattr(analysis, "files", {}).values():
                if getattr(info, "path", None) in changed_abs:
                    impacted.update(analysis.reverse_dependencies.get(info.path, set()))
        risk = "Низкий"
        if len(files) >= 8: risk = "Высокий"
        elif len(files) >= 3 or impacted: risk = "Средний"
        checks = ["Открыть Problems и проверить текущий файл", "Запустить затронутые тесты"]
        if impacted: checks.append("Проверить обратные зависимости в Project Intelligence")
        if any(f.lower().endswith((".json", ".yaml", ".yml", ".env")) for f in files): checks.append("Проверить конфигурацию и окружение")
        if any("security" in str(getattr(i, "category", "")).lower() for i in getattr(analysis, "issues", []) if analysis): checks.append("Повторить анализ безопасности")
        lines = [f"Проект: {project.name}", f"Риск: {risk}", f"Изменено файлов: {len(files)}", "", "ИЗМЕНЕНИЯ"]
        lines += [f"  • {f}" for f in files] or ["  • рабочее дерево чистое"]
        lines += ["", "ВОЗМОЖНО ЗАТРОНУТЫЕ ФАЙЛЫ"]
        lines += [f"  • {f}" for f in sorted(impacted)] or ["  • явные зависимости не найдены"]
        lines += ["", "ПРОВЕРКИ ПЕРЕД COMMIT"]
        lines += [f"  • {c}" for c in checks]
        self.summary.setText(f"{risk} риск · {len(files)} изменённых файлов · {len(impacted)} потенциально затронутых файлов")
        self.output.setPlainText("\n".join(lines))
