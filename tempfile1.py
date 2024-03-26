keywords = {
        "java": ["abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
                "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float",
                "for", "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native",
                "new", "package", "private", "protected", "public", "return", "short", "static", "strictfp",
                "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile",
                "while"
        ],
        "javascript": ["await", "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete",
                "do", "else", "enum", "export", "extends", "false", "finally", "for", "function", "if", "implements",
                "import", "in", "instanceof", "interface", "let", "new", "null", "package", "private", "protected",
                "public", "return", "super", "switch", "static", "this", "throw", "try", "typeof", "var", "void",
                "volatile", "while", "with", "yield"
        ],
        "kotlin": ["abstract", "annotation", "as", "break", "by", "catch", "class", "companion", "const",
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
        "kt": ["abstract", "any", "as", "async", "await", "boolean", "break", "case", "catch", "class",    
                "const", "continue", "debugger", "declare", "default", "delete", "do", "else", "enum",    
                "export", "extends", "false", "finally", "for", "from", "function", "get", "if", "implements",    
                "import", "in", "instanceof", "interface", "let", "module", "new", "null", "number", "of",    
                "package", "private", "protected", "public", "return", "set", "static", "string", "super",    
                "switch", "symbol", "this", "throw", "true", "try", "type", "typeof", "undefined", "var",    
                "void", "while", "with", "yield"
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
        "go": ["break", "case","chan", "const", "continue", "default", "defer", 
            "else", "fallthrough", "for", "func", "go", "goto", "if", "import", "interface", 
            "map", "package", "range", "return", "select", "struct", "switch", "type", "var"
        ],
        "lua":["and", "break","do", "else",
            "elseif", "end", "false", "for", "function", "if", "in", "local", "nil",
            "not", "or", "repeat", "return", "then", "true", "until", "while"
        ],
        "rust":[ "as", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if",
            "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub", "return", "self", "static",
            "struct", "super", "trait", "true", "type", "unsafe", "use", "where", "while"
        ]
}

for i, k in keywords.items():
    print(f'"{i}" :'+" {")
    for x in k:
        print("(r'"+r"\b"+x+r"\b'"+", '#c77a5a'),", end=" ")
    print("}, ")
    print()
