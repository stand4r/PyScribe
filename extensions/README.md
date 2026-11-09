# PyScribe Extensions

PyScribe now has a small extension API separated from the UI implementation.

## Project extension

Create:

```text
my-project/
└── .pyscribe/
    └── extensions/
        └── my_extension/
            ├── pyscribe-extension.json
            └── extension.py
```

Manifest:

```json
{
  "id": "example.hello",
  "name": "Hello Extension",
  "version": "1.0.0",
  "entry": "extension.py",
  "class": "HelloExtension"
}
```

Entry point:

```python
from extensions.api import Extension

class HelloExtension(Extension):
    def activate(self, context):
        context.register_command("example.hello", lambda: print("Hello"))
```

Extensions can register commands and completion providers without importing
PyScribe's editor internals. The manager loads project extensions from
`.pyscribe/extensions` and installed extensions from `extensions/installed`.
