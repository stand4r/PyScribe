keywords = {
        "ruby": ["alias", "and", "begin", "break", "case", "class", "def", "defined?", "do",
            "else", "elsif", "end", "ensure", "false", "for", "if", "in", "module", "next",
            "nil", "not", "or", "redo", "rescue", "retry", "return", "self", "super", "then",
            "true", "undef", "unless", "until", "when", "while", "yield"
        ]
}

for i, k in keywords.items():
    print(f'"{i}" :'+" {")
    for x in k:
        print("(r'"+r"\b"+x+r"\b'"+", '#c77a5a'),", end=" ")
    print("}, ")
    print()

