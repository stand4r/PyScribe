"""PyScribe extensions/examples/completion_demo/extension.py: application module and reusable component."""
from extensions.api import Extension, CompletionItem


class DemoProvider:
    def complete(self, editor, prefix):
        values = ["pyscribe_project", "pyscribe_command", "pyscribe_extension"]
        return [CompletionItem(v, kind="keyword", detail="Demo extension") for v in values if v.startswith(prefix)]


class CompletionDemoExtension(Extension):
    id = "example.completion-demo"
    name = "Completion Demo"
    version = "1.0.0"

    def activate(self, context):
        context.register_completion_provider(DemoProvider())
