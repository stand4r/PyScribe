import ast
import re
import subprocess
from os import remove

from PyQt5.QtCore import Qt, QRegExp, pyqtSlot, pyqtSignal, QStringListModel, QPoint
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QFont, QTextCursor, QKeySequence
from PyQt5.QtWidgets import QCompleter, QPlainTextEdit, QShortcut, QWidget, QHBoxLayout

keywords = {
    "py": [
        "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import",
        "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "abs", "all", "any", "bin", "bool", "bytearray", "bytes", "callable", "chr", "classmethod",
        "compile", "complex", "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter",
        "float", "format", "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex", "id",
        "input", "int", "isinstance", "issubclass", "iter", "len", "list", "locals", "map", "max",
        "memoryview", "min", "next", "object", "oct", "open", "ord", "pow", "print", "property",
        "range", "repr", "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
        "str", "sum", "super", "tuple", "type", "vars", "zip"
    ],
    "cpp": [
        "default", "do", "double", "else", "enum", "extern",
        "float", "for", "goto", "if", "int",
        "long", "register", "return", "short", "signed",
        "sizeof", "static", "struct", "switch", "typedef",
        "union", "unsigned", "void", "volatile", "while",
        "asm", "auto", "bool", "break", "case", "catch", "char", "class", "const",
        "const_cast", "continue", "default", "delete", "do", "double", "dynamic_cast",
        "else", "enum", "explicit", "export", "extern", "false", "float", "for",
        "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace",
        "new", "operator", "private", "protected", "public", "register", "reinterpret_cast",
        "return", "short", "signed", "sizeof", "static", "static_cast", "struct",
        "switch", "template", "this", "throw", "true", "try", "typedef", "typeid",
        "typename", "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t",
        "while"
    ],

    "c": [
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
        'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'int', 'long',
        'register', 'return', 'short', 'signed', 'sizeof', 'static', 'struct', 'switch',
        'typedef', 'union', 'unsigned', 'void', 'volatile', 'while'
    ],
    "java": ["abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
             "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float",
             "for", "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native",
             "new", "package", "private", "protected", "public", "return", "short", "static", "strictfp",
             "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile",
             "while"
             ],
    "js": ["await", "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete",
           "do", "else", "enum", "export", "extends", "false", "finally", "for", "function", "if", "implements",
           "import", "in", "instanceof", "interface", "let", "new", "null", "package", "private", "protected",
           "public", "return", "super", "switch", "static", "this", "throw", "try", "typeof", "var", "void",
           "volatile", "while", "with", "yield"
           ],
    "kt": ["abstract", "annotation", "as", "break", "by", "catch", "class", "companion", "const",
           "constructor", "continue", "crossinline", "data", "do", "dynamic", "else", "enum", "external",
           "false", "file", "final", "finally", "for", "fun", "get", "if", "import", "in", "infix", "init",
           "inline", "inner", "interface", "internal", "is", "it", "lateinit", "noinline", "null", "object",
           "open", "operator", "out", "override", "package", "private", "protected", "public", "reified",
           "return", "sealed", "set", "super", "tailrec", "this", "throw", "true", "try", "typealias",
           "typeof", "val", "var", "when", "while"
           ],
    "php": ["__halt_compiler", "__CLASS__", "__DIR__", "__EXIT__", "__FILE__", "__FUNCTION__", "__LINE__",
            "__METHOD__", "__NAMESPACE__", "__TRAIT__", "abstract", "and", "array", "as", "break", "callable",
            "case", "catch", "class", "clone", "const", "continue", "declare", "default", "die", "do", "echo",
            "else", "elseif", "empty", "enddeclare", "endfor", "endforeach", "endif", "endswitch", "endwhile",
            "eval", "exit", "extends", "final", "finally", "for", "foreach", "function", "global", "goto", "if",
            "implements", "include", "include_once", "instanceof", "insteadof", "interface", "isset", "list",
            "namespace", "new", "or", "print", "private", "protected", "public", "require", "require_once",
            "return", "static", "switch", "throw", "trait", "try", "unset", "use", "var", "while", "xor",
            "yield", "yield from"
            ],
    "cs": ["abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked",
           "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else",
           "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for",
           "foreach", "goto", "if", "implicit", "in", "int", "interface", "internal", "is", "lock",
           "long", "namespace", "new", "null", "object", "operator", "out", "override", "params",
           "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short",
           "sizeof", "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true",
           "try", "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort", "using", "virtual",
           "void", "volatile", "while"
           ],
    "rb": ["alias", "and", "begin", "break", "case", "class", "def", "defined?", "do",
           "else", "elsif", "end", "ensure", "false", "for", "if", "in", "module", "next",
           "nil", "not", "or", "redo", "rescue", "retry", "return", "self", "super", "then",
           "true", "undef", "unless", "until", "when", "while", "yield"
           ],
    "go": ["break", "case", "chan", "const", "continue", "default", "defer",
           "else", "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
           "map", "package", "range", "return", "select", "struct", "switch", "type", "var"
           ],
    "lua": ["and", "break", "do", "else",
            "elseif", "end", "false", "for", "function", "if", "in", "local", "nil",
            "not", "or", "repeat", "return", "then", "true", "until", "while"
            ],
    "rust": ["as", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if",
             "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub", "return", "self", "static",
             "struct", "super", "trait", "true", "type", "unsafe", "use", "where", "while"
             ]
}

operators = [
    '=',
    # Comparison
    '==', '!=', '<', '<=', '>', '>=', '<>',
    # Arithmetic
    '\+', '-', '\*', '/', '//', '\%', '\*\*',
    # In-place
    '\+=', '-=', '\*=', '/=', '\%=',
    # Bitwise
    '\^', '\|', '\&', '\~', '>>', '<<',
]

braces = [
    '\{', '\}', '\(', '\)', '\[', '\]',
]

patterns = {
    "py": {
        (r"\band\b", "#c77a5a"), (r"\bassert\b", "#c77a5a"), (r"\bbreak\b", "#c77a5a"),
        (r"\bcontinue\b", "#c77a5a"), (r"\bdef\b", "#c77a5a"), (r"\bdel\b", "#c77a5a"),
        (r"\belif\b", "#c77a5a"), (r"\belse\b", "#c77a5a"), (r"\bexcept\b", "#c77a5a"),
        (r"\bexec\b", "#c77a5a"), (r"\bfinally\b", "#c77a5a"), (r"\bfor\b", "#c77a5a"),
        (r"\bfrom\b", "#c77a5a"), (r"\bglobal\b", "#c77a5a"), (r"\bglobal\b", "#c77a5a"),
        (r"\bif\b", "#c77a5a"), (r"\bimport\b", "#c77a5a"), (r"\bin\b", "#c77a5a"),
        (r'\bis\b', "#c77a5a"), (r'\blambda\b', "#c77a5a"), (r'\bnot\b', "#c77a5a"), (r'\bor\b', "#c77a5a"),
        (r'\bpass\b', "#c77a5a"), (r'\braise\b', "#c77a5a"), (r'\bis\b', "#c77a5a"), (r'\bis\b', "#c77a5a"),
        (r'\bis\b', "#c77a5a"), (r'\bprint\b', "#c77a5a"), (r'\breturn\b', "#c77a5a"), (r'\btry\b', "#c77a5a"),
        (r'\bwhile\b', "#c77a5a"), (r'\byield\b', "#c77a5a"), (r'\bNone\b', "#c77a5a"), (r'\bTrue\b', "#c77a5a"),
        (r'\bFalse\b', "#c77a5a"), (r'\bauto\b', "#c77a5a"), (r'\bbreak\b', "#c77a5a"), (r'\bcase\b', "#c77a5a"),
        (r'\bchar\b', "#c77a5a"), (r'\bconst\b', "#c77a5a"),
        (r'#.*$', "#FFFF9C"), (rf'"([^"]+)"', "#FFFF9C"), (rf"''", "#FFFF9C"), (rf'""', "#FFFF9C"),
        (r'class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]', "#FFFF9C"),
        (r'[A-Za-z_][A-Za-z0-9_]*\s*\(', '#FFFF9C'), (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"),
        (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
    "c": {
        (r'\b(int|float|char|double|short|long)\s+\w+', "#ffff00"), (r'\bint\b', "#c77a5a"), (r'\bfloat\b', "#c77a5a"),
        (r'\bchar\b', "#c77a5a"), (r'\bdouble\b', "#c77a5a"), (r'\bshort\b', "#c77a5a"), (r'\blong\b', "#c77a5a"),
        (r'\b\d+\b', "#7777FF"), (r"\{", "#ffff00"), (r"\}", "#ffff00"), (rf"\(", "#ffff00"), (rf"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a"), (r"#include\s+<[^>]+>", "#c77a5a"),
        (r'"([^"\\]|\\.)*"', "#FFFF9C"), (r'\([^\)]*\)', "#7777FF")
    },
    "cpp": {
        (r'\b\d+\b', "#7777FF"), (r"\{", "#ffff00"), (r"\}", "#ffff00"), (rf"\(", "#ffff00"), (rf"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
    "rb": {
        (r'\balias\b', '#c77a5a'), (r'\band\b', '#c77a5a'), (r'\bbegin\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'),
        (r'\bcase\b', '#c77a5a'), (r'\bclass\b', '#c77a5a'), (r'\bdef\b', '#c77a5a'), (r'\bdefined?\b', '#c77a5a'),
        (r'\bdo\b', '#c77a5a'), (r'\belse\b', '#c77a5a'), (r'\belsif\b', '#c77a5a'), (r'\bend\b', '#c77a5a'),
        (r'\bensure\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'), (r'\bif\b', '#c77a5a'),
        (r'\bin\b', '#c77a5a'), (r'\bmodule\b', '#c77a5a'), (r'\bnext\b', '#c77a5a'), (r'\bnil\b', '#c77a5a'),
        (r'\bnot\b', '#c77a5a'), (r'\bor\b', '#c77a5a'), (r'\bredo\b', '#c77a5a'), (r'\brescue\b', '#c77a5a'),
        (r'\bretry\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'), (r'\bself\b', '#c77a5a'), (r'\bsuper\b', '#c77a5a'),
        (r'\bthen\b', '#c77a5a'), (r'\btrue\b', '#c77a5a'), (r'\bundef\b', '#c77a5a'), (r'\bunless\b', '#c77a5a'),
        (r'\buntil\b', '#c77a5a'), (r'\bwhen\b', '#c77a5a'), (r'\bwhile\b', '#c77a5a'), (r'\byield\b', '#c77a5a'),
        (r'\b[A-Z]\w*\b', "#7777FF"),
        (r'\bclass\s+\w+', "#FFFF9C"),
        (r'\bdef\s+\w+', "#FFFF9C"), (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
    "java": {
        (r'\babstract\b', '#c77a5a'), (r'\bassert\b', '#c77a5a'), (r'\bboolean\b', '#c77a5a'),
        (r'\bbreak\b', '#c77a5a'),
        (r'\bbyte\b', '#c77a5a'), (r'\bcase\b', '#c77a5a'), (r'\bcatch\b', '#c77a5a'), (r'\bchar\b', '#c77a5a'),
        (r'\bclass\b', '#c77a5a'),
        (r'\bconst\b', '#c77a5a'), (r'\bcontinue\b', '#c77a5a'), (r'\bdefault\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'),
        (r'\bdouble\b', '#c77a5a'),
        (r'\belse\b', '#c77a5a'), (r'\benum\b', '#c77a5a'), (r'\bextends\b', '#c77a5a'), (r'\bfinal\b', '#c77a5a'),
        (r'\bfinally\b', '#c77a5a'),
        (r'\bfloat\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'), (r'\bgoto\b', '#c77a5a'), (r'\bif\b', '#c77a5a'),
        (r'\bimplements\b', '#c77a5a'),
        (r'\bimport\b', '#c77a5a'), (r'\binstanceof\b', '#c77a5a'), (r'\bint\b', '#c77a5a'),
        (r'\binterface\b', '#c77a5a'), (r'\blong\b', '#c77a5a'),
        (r'\bnative\b', '#c77a5a'), (r'\bnew\b', '#c77a5a'), (r'\bpackage\b', '#c77a5a'), (r'\bprivate\b', '#c77a5a'),
        (r'\bprotected\b', '#c77a5a'),
        (r'\bpublic\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'), (r'\bshort\b', '#c77a5a'), (r'\bstatic\b', '#c77a5a'),
        (r'\bstrictfp\b', '#c77a5a'),
        (r'\bsuper\b', '#c77a5a'), (r'\bswitch\b', '#c77a5a'), (r'\bsynchronized\b', '#c77a5a'),
        (r'\bthis\b', '#c77a5a'), (r'\bthrow\b', '#c77a5a'),
        (r'\bthrows\b', '#c77a5a'), (r'\btransient\b', '#c77a5a'), (r'\btry\b', '#c77a5a'), (r'\bvoid\b', '#c77a5a'),
        (r'\bvolatile\b', '#c77a5a'),
        (r'\bwhile\b', '#c77a5a'), (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "js": {
        (r'\bawait\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'), (r'\bcase\b', '#c77a5a'), (r'\bcatch\b', '#c77a5a'),
        (r'\bclass\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'), (r'\bcontinue\b', '#c77a5a'),
        (r'\bdebugger\b', '#c77a5a'),
        (r'\bdefault\b', '#c77a5a'), (r'\bdelete\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'), (r'\belse\b', '#c77a5a'),
        (r'\benum\b', '#c77a5a'),
        (r'\bexport\b', '#c77a5a'), (r'\bextends\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'), (r'\bfinally\b', '#c77a5a'),
        (r'\bfor\b', '#c77a5a'),
        (r'\bfunction\b', '#c77a5a'), (r'\bif\b', '#c77a5a'), (r'\bimplements\b', '#c77a5a'),
        (r'\bimport\b', '#c77a5a'), (r'\bin\b', '#c77a5a'),
        (r'\binstanceof\b', '#c77a5a'), (r'\binterface\b', '#c77a5a'), (r'\blet\b', '#c77a5a'), (r'\bnew\b', '#c77a5a'),
        (r'\bnull\b', '#c77a5a'),
        (r'\bpackage\b', '#c77a5a'), (r'\bprivate\b', '#c77a5a'), (r'\bprotected\b', '#c77a5a'),
        (r'\bpublic\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'),
        (r'\bsuper\b', '#c77a5a'), (r'\bswitch\b', '#c77a5a'), (r'\bstatic\b', '#c77a5a'), (r'\bthis\b', '#c77a5a'),
        (r'\bthrow\b', '#c77a5a'),
        (r'\btry\b', '#c77a5a'), (r'\btypeof\b', '#c77a5a'), (r'\bvar\b', '#c77a5a'), (r'\bvoid\b', '#c77a5a'),
        (r'\bvolatile\b', '#c77a5a'),
        (r'\bwhile\b', '#c77a5a'), (r'\bwith\b', '#c77a5a'), (r'\byield\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "kt": {
        (r'\babstract\b', '#c77a5a'), (r'\bannotation\b', '#c77a5a'), (r'\bas\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'),
        (r'\bby\b', '#c77a5a'),
        (r'\bcatch\b', '#c77a5a'), (r'\bclass\b', '#c77a5a'), (r'\bcompanion\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'),
        (r'\bconstructor\b', '#c77a5a'),
        (r'\bcontinue\b', '#c77a5a'), (r'\bcrossinline\b', '#c77a5a'), (r'\bdata\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'),
        (r'\bdynamic\b', '#c77a5a'),
        (r'\belse\b', '#c77a5a'), (r'\benum\b', '#c77a5a'), (r'\bexternal\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'),
        (r'\bfile\b', '#c77a5a'),
        (r'\bfinal\b', '#c77a5a'), (r'\bfinally\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'), (r'\bfun\b', '#c77a5a'),
        (r'\bget\b', '#c77a5a'),
        (r'\bif\b', '#c77a5a'), (r'\bimport\b', '#c77a5a'), (r'\bin\b', '#c77a5a'), (r'\binfix\b', '#c77a5a'),
        (r'\binit\b', '#c77a5a'),
        (r'\binline\b', '#c77a5a'), (r'\binner\b', '#c77a5a'), (r'\binterface\b', '#c77a5a'),
        (r'\binternal\b', '#c77a5a'), (r'\bis\b', '#c77a5a'),
        (r'\bit\b', '#c77a5a'), (r'\blateinit\b', '#c77a5a'), (r'\bnoinline\b', '#c77a5a'), (r'\bnull\b', '#c77a5a'),
        (r'\bobject\b', '#c77a5a'),
        (r'\bopen\b', '#c77a5a'), (r'\boperator\b', '#c77a5a'), (r'\bout\b', '#c77a5a'), (r'\boverride\b', '#c77a5a'),
        (r'\bpackage\b', '#c77a5a'),
        (r'\bprivate\b', '#c77a5a'), (r'\bprotected\b', '#c77a5a'), (r'\bpublic\b', '#c77a5a'),
        (r'\breified\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'),
        (r'\bsealed\b', '#c77a5a'), (r'\bset\b', '#c77a5a'), (r'\bsuper\b', '#c77a5a'), (r'\btailrec\b', '#c77a5a'),
        (r'\bthis\b', '#c77a5a'),
        (r'\bthrow\b', '#c77a5a'), (r'\btrue\b', '#c77a5a'), (r'\btry\b', '#c77a5a'), (r'\btypealias\b', '#c77a5a'),
        (r'\btypeof\b', '#c77a5a'),
        (r'\bval\b', '#c77a5a'), (r'\bvar\b', '#c77a5a'), (r'\bwhen\b', '#c77a5a'), (r'\bwhile\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "php": {
        (r'\b__halt_compiler\b', '#c77a5a'), (r'\b__CLASS__\b', '#c77a5a'), (r'\b__DIR__\b', '#c77a5a'),
        (r'\b__EXIT__\b', '#c77a5a'),
        (r'\b__FILE__\b', '#c77a5a'), (r'\b__FUNCTION__\b', '#c77a5a'), (r'\b__LINE__\b', '#c77a5a'),
        (r'\b__METHOD__\b', '#c77a5a'),
        (r'\b__NAMESPACE__\b', '#c77a5a'), (r'\b__TRAIT__\b', '#c77a5a'), (r'\babstract\b', '#c77a5a'),
        (r'\band\b', '#c77a5a'), (r'\barray\b', '#c77a5a'),
        (r'\bas\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'), (r'\bcallable\b', '#c77a5a'), (r'\bcase\b', '#c77a5a'),
        (r'\bcatch\b', '#c77a5a'),
        (r'\bclass\b', '#c77a5a'), (r'\bclone\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'), (r'\bcontinue\b', '#c77a5a'),
        (r'\bdeclare\b', '#c77a5a'),
        (r'\bdefault\b', '#c77a5a'), (r'\bdie\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'), (r'\becho\b', '#c77a5a'),
        (r'\belse\b', '#c77a5a'),
        (r'\belseif\b', '#c77a5a'), (r'\bempty\b', '#c77a5a'), (r'\benddeclare\b', '#c77a5a'),
        (r'\bendfor\b', '#c77a5a'), (r'\bendforeach\b', '#c77a5a'),
        (r'\bendif\b', '#c77a5a'), (r'\bendswitch\b', '#c77a5a'), (r'\bendwhile\b', '#c77a5a'),
        (r'\beval\b', '#c77a5a'), (r'\bexit\b', '#c77a5a'),
        (r'\bextends\b', '#c77a5a'), (r'\bfinal\b', '#c77a5a'), (r'\bfinally\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'),
        (r'\bforeach\b', '#c77a5a'),
        (r'\bfunction\b', '#c77a5a'), (r'\bglobal\b', '#c77a5a'), (r'\bgoto\b', '#c77a5a'), (r'\bif\b', '#c77a5a'),
        (r'\bimplements\b', '#c77a5a'),
        (r'\binclude\b', '#c77a5a'), (r'\binclude_once\b', '#c77a5a'), (r'\binstanceof\b', '#c77a5a'),
        (r'\binsteadof\b', '#c77a5a'),
        (r'\binterface\b', '#c77a5a'), (r'\bisset\b', '#c77a5a'), (r'\blist\b', '#c77a5a'),
        (r'\bnamespace\b', '#c77a5a'), (r'\bnew\b', '#c77a5a'),
        (r'\bor\b', '#c77a5a'), (r'\bprint\b', '#c77a5a'), (r'\bprivate\b', '#c77a5a'), (r'\bprotected\b', '#c77a5a'),
        (r'\bpublic\b', '#c77a5a'),
        (r'\brequire\b', '#c77a5a'), (r'\brequire_once\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'),
        (r'\bstatic\b', '#c77a5a'), (r'\bswitch\b', '#c77a5a'),
        (r'\bthrow\b', '#c77a5a'), (r'\btrait\b', '#c77a5a'), (r'\btry\b', '#c77a5a'), (r'\bunset\b', '#c77a5a'),
        (r'\buse\b', '#c77a5a'),
        (r'\bvar\b', '#c77a5a'), (r'\bwhile\b', '#c77a5a'), (r'\bxor\b', '#c77a5a'), (r'\byield\b', '#c77a5a'),
        (r'\byield from\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "cs": {
        (r'\babstract\b', '#c77a5a'), (r'\bas\b', '#c77a5a'), (r'\bbase\b', '#c77a5a'), (r'\bbool\b', '#c77a5a'),
        (r'\bbreak\b', '#c77a5a'),
        (r'\bbyte\b', '#c77a5a'), (r'\bcase\b', '#c77a5a'), (r'\bcatch\b', '#c77a5a'), (r'\bchar\b', '#c77a5a'),
        (r'\bchecked\b', '#c77a5a'),
        (r'\bclass\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'), (r'\bcontinue\b', '#c77a5a'), (r'\bdecimal\b', '#c77a5a'),
        (r'\bdefault\b', '#c77a5a'),
        (r'\bdelegate\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'), (r'\bdouble\b', '#c77a5a'), (r'\belse\b', '#c77a5a'),
        (r'\benum\b', '#c77a5a'),
        (r'\bevent\b', '#c77a5a'), (r'\bexplicit\b', '#c77a5a'), (r'\bextern\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'),
        (r'\bfinally\b', '#c77a5a'),
        (r'\bfixed\b', '#c77a5a'), (r'\bfloat\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'), (r'\bforeach\b', '#c77a5a'),
        (r'\bgoto\b', '#c77a5a'),
        (r'\bif\b', '#c77a5a'), (r'\bimplicit\b', '#c77a5a'), (r'\bin\b', '#c77a5a'), (r'\bint\b', '#c77a5a'),
        (r'\binterface\b', '#c77a5a'),
        (r'\binternal\b', '#c77a5a'), (r'\bis\b', '#c77a5a'), (r'\block\b', '#c77a5a'), (r'\blong\b', '#c77a5a'),
        (r'\bnamespace\b', '#c77a5a'),
        (r'\bnew\b', '#c77a5a'), (r'\bnull\b', '#c77a5a'), (r'\bobject\b', '#c77a5a'), (r'\boperator\b', '#c77a5a'),
        (r'\bout\b', '#c77a5a'),
        (r'\boverride\b', '#c77a5a'), (r'\bparams\b', '#c77a5a'), (r'\bprivate\b', '#c77a5a'),
        (r'\bprotected\b', '#c77a5a'), (r'\bpublic\b', '#c77a5a'),
        (r'\breadonly\b', '#c77a5a'), (r'\bref\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'), (r'\bsbyte\b', '#c77a5a'),
        (r'\bsealed\b', '#c77a5a'),
        (r'\bshort\b', '#c77a5a'), (r'\bsizeof\b', '#c77a5a'), (r'\bstackalloc\b', '#c77a5a'),
        (r'\bstatic\b', '#c77a5a'), (r'\bstring\b', '#c77a5a'),
        (r'\bstruct\b', '#c77a5a'), (r'\bswitch\b', '#c77a5a'), (r'\bthis\b', '#c77a5a'), (r'\bthrow\b', '#c77a5a'),
        (r'\btrue\b', '#c77a5a'),
        (r'\btry\b', '#c77a5a'), (r'\btypeof\b', '#c77a5a'), (r'\buint\b', '#c77a5a'), (r'\bulong\b', '#c77a5a'),
        (r'\bunchecked\b', '#c77a5a'),
        (r'\bunsafe\b', '#c77a5a'), (r'\bushort\b', '#c77a5a'), (r'\busing\b', '#c77a5a'), (r'\bvirtual\b', '#c77a5a'),
        (r'\bvoid\b', '#c77a5a'),
        (r'\bvolatile\b', '#c77a5a'), (r'\bwhile\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "go": {
        (r'\bbreak\b', '#c77a5a'), (r'\bcase\b', '#c77a5a'), (r'\bchan\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'),
        (r'\bcontinue\b', '#c77a5a'),
        (r'\bdefault\b', '#c77a5a'), (r'\bdefer\b', '#c77a5a'), (r'\belse\b', '#c77a5a'),
        (r'\bfallthrough\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'),
        (r'\bfunc\b', '#c77a5a'), (r'\bgo\b', '#c77a5a'), (r'\bgoto\b', '#c77a5a'), (r'\bif\b', '#c77a5a'),
        (r'\bimport\b', '#c77a5a'),
        (r'\binterface\b', '#c77a5a'), (r'\bmap\b', '#c77a5a'), (r'\bpackage\b', '#c77a5a'), (r'\brange\b', '#c77a5a'),
        (r'\breturn\b', '#c77a5a'),
        (r'\bselect\b', '#c77a5a'), (r'\bstruct\b', '#c77a5a'), (r'\bswitch\b', '#c77a5a'), (r'\btype\b', '#c77a5a'),
        (r'\bvar\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "lua": {
        (r'\band\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'), (r'\bdo\b', '#c77a5a'), (r'\belse\b', '#c77a5a'),
        (r'\belseif\b', '#c77a5a'),
        (r'\bend\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'), (r'\bfor\b', '#c77a5a'), (r'\bfunction\b', '#c77a5a'),
        (r'\bif\b', '#c77a5a'),
        (r'\bin\b', '#c77a5a'), (r'\blocal\b', '#c77a5a'), (r'\bnil\b', '#c77a5a'), (r'\bnot\b', '#c77a5a'),
        (r'\bor\b', '#c77a5a'),
        (r'\brepeat\b', '#c77a5a'), (r'\breturn\b', '#c77a5a'), (r'\bthen\b', '#c77a5a'), (r'\btrue\b', '#c77a5a'),
        (r'\buntil\b', '#c77a5a'),
        (r'\bwhile\b', '#c77a5a'), (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },

    "rust": {
        (r'\bas\b', '#c77a5a'), (r'\bbreak\b', '#c77a5a'), (r'\bconst\b', '#c77a5a'), (r'\bcontinue\b', '#c77a5a'),
        (r'\bcrate\b', '#c77a5a'),
        (r'\belse\b', '#c77a5a'), (r'\benum\b', '#c77a5a'), (r'\bextern\b', '#c77a5a'), (r'\bfalse\b', '#c77a5a'),
        (r'\bfn\b', '#c77a5a'),
        (r'\bfor\b', '#c77a5a'), (r'\bif\b', '#c77a5a'), (r'\bimpl\b', '#c77a5a'), (r'\bin\b', '#c77a5a'),
        (r'\blet\b', '#c77a5a'), (r'\bloop\b', '#c77a5a'),
        (r'\bmatch\b', '#c77a5a'), (r'\bmod\b', '#c77a5a'), (r'\bmove\b', '#c77a5a'), (r'\bmut\b', '#c77a5a'),
        (r'\bpub\b', '#c77a5a'),
        (r'\breturn\b', '#c77a5a'), (r'\bself\b', '#c77a5a'), (r'\bstatic\b', '#c77a5a'), (r'\bstruct\b', '#c77a5a'),
        (r'\bsuper\b', '#c77a5a'),
        (r'\btrait\b', '#c77a5a'), (r'\btrue\b', '#c77a5a'), (r'\btype\b', '#c77a5a'), (r'\bunsafe\b', '#c77a5a'),
        (r'\buse\b', '#c77a5a'),
        (r'\bwhere\b', '#c77a5a'), (r'\bwhile\b', '#c77a5a'),
        (r'\{', "#ffff00"), (r"\}", "#ffff00"), (r"\(", "#ffff00"), (r"\)", "#ffff00"),
        (rf"\[", "#ffff00"), (rf"\]", "#ffff00"), (rf"=", "#c77a5a"),
        (rf"==", "#c77a5a"), (rf"!=", "#c77a5a"), (rf"<", "#c77a5a"),
        (rf"<=", "#c77a5a"), (rf">", "#c77a5a"), (rf">=", "#c77a5a"), (rf"\+", "#c77a5a"), (rf"-", "#c77a5a"),
        (rf"\*", "#c77a5a"), (rf"/", "#c77a5a"), (rf"//", "#c77a5a"), (rf"\%", "#c77a5a"), (rf"\*\*", "#c77a5a"),
        (rf"\+=", "#c77a5a"), (rf"-=", "#c77a5a"), (rf"\*=", "#c77a5a"), (rf"/=", "#c77a5a"), (rf"\%=", "#c77a5a"),
        (rf"\^", "#c77a5a"), (rf"\|", "#c77a5a"), (rf"\&", "#c77a5a"),
        (rf"\~", "#c77a5a"), (rf">>", "#c77a5a"), (rf"<<", "#c77a5a")
    },
}


def convert_to_hex(content):
    hex_string = ""
    ascii_string = ""

    for i, byte in enumerate(content):
        if i % 16 == 0:
            if i > 0:
                hex_string += f"   {ascii_string}\n"
            hex_string += "{:08X}   ".format(i)
            ascii_string = ""
        ascii_string += chr(byte) if 32 <= byte <= 126 else "."
        hex_string += f"{byte:02X} "
    return hex_string.strip()


class CodeTextEdit(QPlainTextEdit):
    def __init__(self, parent=None, language="", d=[], settings={}):
        super(CodeTextEdit, self).__init__(parent)
        self.filename = ""
        self.fullfilepath = ""
        self.language = language
        self.settings = settings
        self.welcome = False
        self.main_color = self.settings["settings"]['main_color']  # 013B81
        self.text_color = self.settings["settings"]["text_color"]  # ABB2BF
        self.first_color = self.settings["settings"]['first_color']  # 16171D
        self.second_color = self.settings["settings"]['second_color']  # 131313
        self.tab_color = self.settings["settings"]['tab_color']  # 1F2228
        self.languages = self.settings["languages"]
        self.mode = settings["languages_type"][self.language]
        self.font_size = int(self.settings["settings"]["fontsize"])
        self.dict = d
        self.flag = 0
        self.prev_key = ""
        self.executable = False
        self.tabWidth = 4
        self.setFont(QFont("Courier New", self.font_size))
        self.setStyleSheet(
            f"background-color: {self.second_color};\n"
            "color: #ffffff;\n"
            "padding: 20px;\n"
            "padding-top: 10px;\n"
            "letter-spacing:1px;\n"
            "width: 0px;\n"
            "border: none"
        )
        if self.mode == 0:
            self.setReadOnly(True)
            self.setFont(QFont("Courier New", self.font_size))
        else:
            self.analyzer = CodeAnalyzer(self.language)
            self.blockCountChanged.connect(self.analyzeCode)
            self.completer = MyCompleter(self.dict, self.second_color, self.font_size)
            self.completer.setWidget(self)
            self.completer.insertText.connect(self.insertCompletion)
            self.highlighter = WordHighlighter(self.document(), self.language)
            self.highlighter.rehighlight()

    def analyzeAndHighlightErrors(self):
        code = self.toPlainText()

        # Create temporary file for code
        with open("temp_file.py", "w") as temp_file:
            temp_file.write(code)

        # Run flake8 on temporary file
        try:
            result = subprocess.check_output(["python", "-m", "flake8", "temp_file.py"])
            errors = self.parseFlake8Output(result.decode())
            self.highlightCodeErrors(errors)
        except subprocess.CalledProcessError:
            pass
        remove("temp_file.py")

    def parseFlake8Output(self, output):
        errors = []
        for line in output.split('\n'):
            if line:
                parts = line.split(':')
                line_number = int(parts[1])
                column = int(parts[2])
                errors.append((line_number, column))
        return errors

    def highlightCodeErrors(self, errors):
        for (line, _) in errors:
            start_pos = self.document().findBlockByLineNumber(line - 1).position()
            text_cursor = QTextCursor(self.document())
            text_cursor.setPosition(start_pos)
            text_cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            self.error_format = self.text_edit.currentCharFormat()
            self.error_format.setBackground(Qt.red)
            text_cursor.setCharFormat(self.error_format)

    def analyzeCode(self):
        if self.toPlainText() != "":
            self.analyzer.analyze_code(self.toPlainText())
            self.dict = self.analyzer.get_auto_complete_dict()
            self.completer.update(self.dict)

    def insertCompletion(self, completion):
        tc = self.textCursor()
        extra = (len(completion) - len(self.completer.completionPrefix()))
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
        self.completer.popup().hide()

    def focusInEvent(self, event):
        if self.mode == 1:
            if self.completer:
                self.completer.setWidget(self)
        QPlainTextEdit.focusInEvent(self, event)

    def addText(self, text: str):
        if self.mode == 1:
            self.insertPlainText(text)
        else:
            hex_content = convert_to_hex(text)
            self.setPlainText(hex_content)

    def set_highlight_words(self, words, color):
        self.highlighter.set_patterns(words, color)

    def keyPressEvent(self, event):
        if self.mode == 1:
            tc = self.textCursor()
            if event.key() == Qt.Key_Tab:
                if self.completer.popup().isVisible():  # Если виджет автодополнения видим
                    inserted_text = self.completer.getSelected()  # Получаем выбранный текст из виджета автодополнения
                    if inserted_text:
                        cursor_position = tc.position()  # Получаем начальное положение курсора
                        tc.select(QTextCursor.WordUnderCursor)  # Выбираем слово, над которым находится курсор
                        tc.removeSelectedText()  # Удаляем текст, над которым находится курсор
                        self.setTextCursor(tc)  # Устанавливаем обновленное положение курсора
                        self.insertPlainText(inserted_text)  # Вставляем выбранный текст
                        self.completer.popup().hide()
                        return
                else:
                    self.insertPlainText(" " * self.tabWidth)

            if event.text() in ["'", '"', "(", "{", "[", ")", "}", "]"]:
                cursor = self.textCursor()
                if event.text() == '"':
                    self.insertPlainText('""')
                elif event.text() == "'":
                    self.insertPlainText("''")
                elif event.text() == "(":
                    self.insertPlainText("()")
                elif event.text() == "[":
                    self.insertPlainText("[]")
                elif event.text() == "{":
                    self.insertPlainText("{}")
                elif event.text() == "<":
                    self.insertPlainText("<>")
                elif event.text() == ")":
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor)
                elif event.text() == "]":
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor)
                elif event.text() == "}":
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor)
                elif event.text() == ">":
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor)
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor)
                self.setTextCursor(cursor)
                return
            elif event.key() in [Qt.Key_Enter, Qt.Key_Return] and self.language in ["python", "c", "cpp"]:
                self.completer.popup().hide()
                if self.language == "python":
                    # Вставляем новую строку
                    cursor = self.textCursor()
                    line = cursor.block().text()
                    # Считаем количество пробелов в начале текущей строки
                    spaces = len(line) - len(line.lstrip(' '))
                    indentation = ' ' * spaces
                    # Проверяем, заканчивается ли предыдущая строка на особые слова
                    if line.strip().endswith(('if', 'for', 'while', 'else', 'elif', ':')):
                        indentation += ' ' * self.tabWidth  # Добавляем отступ
                    self.insertPlainText('\n')
                    self.insertPlainText(indentation)
                elif self.language in ["c", "cpp"]:
                    cursor = self.textCursor()
                    line = cursor.block().text()
                    # Считаем количество пробелов в начале текущей строки
                    spaces = len(line) - len(line.lstrip(' '))
                    indentation = ' ' * spaces
                    cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                    symbol = cursor.selectedText()
                    if symbol == "{":
                        indentation += ' ' * self.tabWidth
                        self.insertPlainText("\n\n")  # Добавляем отступ
                        cursor.movePosition(QTextCursor.Up)
                        self.setTextCursor(cursor)
                        self.insertPlainText(indentation)
                    else:
                        self.insertPlainText("\n" + indentation)
                return
            else:
                if event.key() == Qt.Key_Backspace:
                    self.completer.popup().hide()  # Скрываем popup при удалении последнего символа
                if event.key() not in [Qt.Key_Up, Qt.Key_Down] and event.modifiers() not in [Qt.ControlModifier,
                                                                                             Qt.ShiftModifier]:
                    tc.select(QTextCursor.WordUnderCursor)
                    cr = self.cursorRect()
                    if event.text() not in [".", "[", "{", "("]:
                        if len(tc.selectedText()) > 0:
                            prefix = tc.selectedText()  # Получаем выбранный текст для установки в качестве префикса автодополнения
                            if "." in prefix:
                                prefix = prefix.split(".")[-1]
                            self.completer.setCompletionPrefix(prefix)
                            popup = self.completer.popup()
                            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                            cr.setWidth(self.completer.popup().sizeHintForColumn(
                                0) + self.completer.popup().verticalScrollBar().sizeHint().width())
                            self.completer.complete(cr)  # Запускаем автодополнение
                else:
                    self.completer.popup().hide()  # Если ничего не выбрано, скрываем всплывающий список
                super().keyPressEvent(event)
                return
        super().keyPressEvent(event)


class TextEdit(QPlainTextEdit):
    def __init__(self, parent=None, language="", settings={}):
        super(TextEdit, self).__init__(parent)
        self.language = language
        self.settings = settings
        self.welcome = False
        self.fontSize = int(self.settings["settings"]["fontsize"])
        self.second_color = self.settings["settings"]["second_color"]
        self.tabWidth = 4
        self.setFont(QFont("Courier New", self.fontSize))
        self.setStyleSheet(
            f"background-color: {self.second_color};\n"
            "color: #ffffff;\n"
            "padding: 20px;\n"
            "padding-top: 10px;\n"
            "letter-spacing:1px;\n"
            "width: 0px;\n"
            "border: none"
        )

    def addText(self, text: str):
        self.insertPlainText(text)


class CodeEdit(QWidget):
    def __init__(self, parent=None, language="", d=[], settings={}):
        super(CodeEdit, self).__init__(parent)
        self.language = language
        self.filename = ""
        self.fullfilepath = ""
        self.settings = settings
        self.welcome = False
        self.fontSize = int(self.settings["settings"]["fontsize"])
        self.second_color = self.settings["settings"]["second_color"]
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        if self.language in settings["languages"]:
            self.mode = self.settings["languages_type"][self.language]
            self.textedit = CodeTextEdit(self, language=language, d=d, settings=self.settings)
        else:
            self.mode = -1
            self.textedit = TextEdit(self, language=language, settings=self.settings)
        self.labelCount = QPlainTextEdit(self)
        self.labelCount.setReadOnly(True)
        self.labelCount.setStyleSheet(f"padding-left: 12px; color: #ABB2BF; width: 0px;\n padding-top: 10px;\n"
                                      f"background-color: {self.second_color}; padding-bottom: 20px; letter-spacing:1px; border: 2px solid {self.second_color}; border-right-color: #282C34;")
        self.labelCount.setFixedWidth(103)
        self.labelCount.setFont(QFont("Courier New", self.fontSize))
        self.changeCount(1)
        self.textedit.blockCountChanged.connect(self.changeCount)
        self.textedit.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.labelCount.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.layout.addWidget(self.labelCount, 1)
        self.layout.addWidget(self.textedit, 10)
        self.setLayout(self.layout)
        self.shortcutAdd = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self.shortcutAdd.activated.connect(self.addFontSize)
        self.shortcutPop = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcutPop.activated.connect(self.popFontSize)
        self.shortcutEnd = QShortcut(QKeySequence("Ctrl+Down"), self)
        self.shortcutEnd.activated.connect(self.moveCursorToEnd)
        self.shortcutStart = QShortcut(QKeySequence("Ctrl+Up"), self)
        self.shortcutStart.activated.connect(self.moveCursorToStart)

    def sync_scroll(self, value):
        self.textedit.verticalScrollBar().setValue(value)
        self.labelCount.verticalScrollBar().setValue(value)

    def changeCount(self, value):
        self.labelCount.setPlainText("")
        self.labelCount.insertPlainText("\n".join([f"{round(i + 1, 2):>4}" for i in range(self.textedit.blockCount())]))
        self.labelCount.verticalScrollBar().setValue(value)

    def addText(self, text):
        self.textedit.addText(text)

    def setPlainText(self, text):
        self.textedit.setPlainText(text)

    def toPlainText(self):
        return self.textedit.toPlainText()

    @pyqtSlot()
    def addFontSize(self):
        self.fontSize += 1
        self.textedit.setFont(QFont("Courier New", self.fontSize))
        self.labelCount.setFont(QFont("Courier New", self.fontSize))

    @pyqtSlot()
    def popFontSize(self):
        if self.fontSize > 1:
            self.fontSize -= 1
            self.textedit.setFont(QFont("Courier New", self.fontSize))
            self.labelCount.setFont(QFont("Courier New", self.fontSize))

    @pyqtSlot()
    def moveCursorToEnd(self):
        self.textedit.moveCursor(QTextCursor.End)
        self.labelCount.moveCursor(QTextCursor.End)

    @pyqtSlot()
    def moveCursorToStart(self):
        self.labelCount.moveCursor(QTextCursor.Start)
        self.textedit.moveCursor(QTextCursor.Start)


class WordHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, language):
        super(WordHighlighter, self).__init__(parent)
        self.language = language
        self.patterns = []
        self.set_patterns()

    def set_patterns(self):
        self.create_patterns()

    def create_patterns(self):
        try:
            for i in patterns[self.language]:
                self.patterns.append((i[0], QColor(i[1])))
            return self.patterns
        except:
            return []

    def highlightBlock(self, text):
        if self.patterns != []:
            for pattern, format in self.patterns:
                expression = QRegExp(pattern)
                index = expression.indexIn(text)
                while index >= 0:
                    length = expression.matchedLength()
                    self.setFormat(index, length, format)
                    index = expression.indexIn(text, index + length)


class MyCompleter(QCompleter):
    insertText = pyqtSignal(str)

    def __init__(self, d=[], backcolor="", fontsize=11, parent=None):
        QCompleter.__init__(self, d, parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)  # Нечувствительность к регистру
        self.setFilterMode(Qt.MatchContains)  # Фильтрация по вхождению
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.popup().setFixedWidth(200)
        self.highlighted.connect(self.setHighlighted)
        self.popup().setStyleSheet(f"font-size: {fontsize - 1}pt;"
                                   "QListView { background-color: " + backcolor + "; color: white; padding: 2px; border: 1px solid lightgray;} "
                                                                                  "QFrame {border: 1px solid #ccc; padding: 2px;}"
                                                                                  "QListView::item:selected { background-color: lightgray;}"
                                                                                  "QListView::item {height: 30px;}")

    def update(self, d):
        model = QStringListModel()
        model.setStringList(d)
        self.setModel(model)

    def complete(self, rect):
        # Рассчитываем позицию попапа относительно курсора
        point = QPoint(rect.left(), rect.top() + rect.height())
        global_point = rect.bottomLeft() + point

        # Перемещаем попап QCompleter
        self.popup().move(global_point)

        super().complete(rect)

    def setHighlighted(self, text):
        self.lastSelected = text

    def getSelected(self):
        return self.lastSelected


class CodeAnalyzer:
    def __init__(self, lang):
        self._lang = lang
        self.defined_names = keywords[self._lang]

    def analyze_code(self, code):
        if self._lang == "python":
            self.defined_names = keywords[self._lang]  # Сброс списка определенных имен
            # Анализируем текст кода, чтобы найти определения функций и переменных
            try:
                # Разбираем код в абстрактное синтаксическое дерево (AST)
                tree = ast.parse(code)

                # Обходим AST, чтобы найти все определения и импорты
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Если узел - определение функции, добавляем ее имя в словарь
                        if node.name not in self.defined_names:
                            self.defined_names += node.name
                    elif isinstance(node, ast.ClassDef):
                        # Если узел - определение класса, добавляем его имя в словарь
                        if node.name not in self.defined_names:
                            self.defined_names += node.name
                        for n in node.body:
                            if isinstance(n, ast.FunctionDef):
                                if node.name not in self.defined_names:
                                    self.defined_names += n.name
                    elif isinstance(node, ast.Import):
                        # Если узел - импорт, добавляем имена импортированных модулей в словарь
                        for alias in node.names:
                            if node.name not in self.defined_names:
                                self.defined_names += alias.name.split(".")[0]
            except:
                function_pattern = r'def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('
                self.defined_names += re.findall(function_pattern, code)
            variable_pattern = r'\b([A-Za-z_][A-Za-z0-9_]*)\b(?=[^\(]*\))'  # Регулярное выражение для определения переменных
            self.defined_names += re.findall(variable_pattern, code)
        elif self._lang == "c":
            c_language_dictionary = [
                "auto", "double", "int", "struct", "break", "else", "long", "switch",
                "case", "enum", "register", "typedef", "char", "extern", "return", "union",
                "continue", "for", "signed", "void", "do", "if", "static", "while",
                "default", "goto", "sizeof", "volatile", "const", "float", "short", "unsigned"
            ]

            c_standard_library = [
                "assert", "errno", "time", "stdlib", "stdio", "math", "string"  # И другие стандартные библиотеки C
            ]

            functions = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*\(', code)
            variables = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', code)
            '''
            import ply.lex as lex
            import ply.yacc as yacc
            tokens = (
                'VAR',  # Переменная
                'FUNC',  # Функция
                # Другие токены, такие как INT, FLOAT и т.д.
            )

            # Определение правил для токенов
            def t_VAR(t):
                r'[a-zA-Z_][a-zA-Z0-9_]*'
                # Добавляем переменную в список
                variables.append(t.value)
                return t

            def t_FUNC(t):
                r'[a-zA-Z_][a-zA-Z0-9_]*\('
                # Добавляем имя функции в список
                functions.append(t.value[:-1])
                return t

            # Другие правила для токенов

            # Запуск парсера
            def parse_c_code(code):
                lexer = lex.lex()
                lexer.input(code)
                for token in lexer:
                    pass  # Парсинг всех токенов

            # Пример использования парсера
            variables = []
            functions = []
            parse_c_code(code)
            self.defined_names += variables
            self.defined_names += functions'''
            self.defined_names += functions
            self.defined_names += c_language_dictionary
            self.defined_names += c_standard_library
        elif self._lang == "cpp":
            variable_pattern = r'\b\w+\s+\w+\s*=\s*.*;'
            function_pattern = r'\b\w+\s+\w+\(.*\)\s*{'

            # Извлечение переменных
            variables = re.findall(variable_pattern, code)

            # Извлечение функций
            functions = re.findall(function_pattern, code)
            self.defined_names += variables
            self.defined_names += functions

    def get_auto_complete_dict(self):
        return list(set([name for name in self.defined_names]))  # Возвращаем словарь для автодополнения
