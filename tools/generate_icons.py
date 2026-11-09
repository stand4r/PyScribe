"""Generate VS Code-style file/folder icons (monochrome set) for the explorer.

VS Code uses a monochrome outline file icon, an outline folder icon and a small
set of solid colour brand glyphs for languages. This script writes those SVGs
into ``src/icons`` so the explorer no longer mixes styles.

Run:  python tools/generate_icons.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "icons"

STROKE = "#CCCCCC"
MUTED = "#8C8C8C"


def svg(body: str, size: int = 16, fill_stroke: str = STROKE) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 16 16" fill="none" stroke="{fill_stroke}" stroke-width="1" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


def solid(body: str, color: str, size: int = 16) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 16 16"><g fill="{color}">{body}</g></svg>'
    )


ICONS = {
    # Generic document: folded corner, drawn like VS Code's "file" codicon.
    "file.svg": svg(
        '<path d="M9.5 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5z"/>'
        '<path d="M9.5 1.5V5H13"/>'
    ),
    "folder.svg": svg(
        '<path d="M1.5 3.5A1 1 0 0 1 2.5 2.5h3.2l1.5 1.6h6.3a1 1 0 0 1 1 1v7.4a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z"/>'
    ),
    "text.svg": svg(
        '<path d="M9.5 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5z"/>'
        '<path d="M9.5 1.5V5H13"/>'
        '<path d="M5.5 8h5M5.5 10.5h5M5.5 13h3"/>',
        fill_stroke=MUTED,
    ),
    "markdown.svg": svg(
        '<path d="M9.5 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5z"/>'
        '<path d="M9.5 1.5V5H13"/>'
        '<path d="M4.8 12V8.2l1.5 1.7 1.5-1.7V12"/><path d="M10.2 8.2v2.6"/><path d="M9.3 10.2l0.9 1 0.9-1"/>',
        fill_stroke="#519ABA",
    ),
    # Language glyphs: solid brand-ish shapes, same 16px grid.
    "python.svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        '<path fill="#4B8BBE" d="M7.9 1c-1.6 0-2.9.3-2.9 1.9V4h3v.6H3.9C2.3 4.6 1 6 1 7.6s1 2.8 2.6 2.8h1V9c0-1.6 1-2.6 2.6-2.6h2.6C11.4 6.4 12 5.5 12 4V2.9C12 1.3 10.8 1 9.2 1z"/>'
        '<circle cx="6.3" cy="2.6" r=".6" fill="#1E1E1E"/>'
        '<path fill="#FFD43B" d="M8.1 15c1.6 0 2.9-.3 2.9-1.9V12h-3v-.6h4.1c1.6 0 2.9-1.4 2.9-3s-1-2.8-2.6-2.8h-1V6c0 1.6-1 2.6-2.6 2.6H6.2C4.6 8.6 4 9.5 4 11v1.1C4 13.7 5.2 15 8.1 15z"/>'
        '<circle cx="9.7" cy="13.4" r=".6" fill="#1E1E1E"/>'
        "</svg>"
    ),
    "javascript.svg": solid(
        '<path d="M2 1h12v14H2z" fill="#F1E05A"/><path d="M2 1h12v14H2z" fill-opacity=".18"/>'
        '<path fill="#1E1E1E" d="M7.2 11.3c0 .8-.5 1.3-1.4 1.3-.7 0-1.2-.3-1.5-.9l.8-.5c.2.3.4.5.7.5.3 0 .5-.1.5-.5V7.3h.9zM11.2 12.6c-.8 0-1.4-.4-1.6-1.1l.8-.5c.2.4.4.6.8.6.3 0 .5-.1.5-.4 0-.6-2-.6-2-2 0-.8.6-1.3 1.5-1.3.6 0 1.1.2 1.4.8l-.8.5c-.2-.3-.3-.4-.6-.4s-.5.1-.5.3c0 .6 2 .6 2 2 0 .9-.7 1.5-1.5 1.5z"/>',
        "#F1E05A",
    ),
    "typescript.svg": solid(
        '<path d="M2 1h12v14H2z"/>'
        '<path fill="#1E1E1E" d="M6.6 7.3H4.2v.9h1.2v4.4h.9V8.2h1.2zM10.6 12.6c-.8 0-1.4-.3-1.6-.9l.8-.5c.2.3.4.5.8.5.3 0 .5-.1.5-.4 0-.5-2-.5-2-1.9 0-.8.6-1.3 1.5-1.3.6 0 1 .2 1.3.7l-.7.5c-.2-.2-.3-.3-.6-.3s-.5.1-.5.3c0 .5 2 .5 2 1.9 0 .9-.7 1.4-1.5 1.4z"/>',
        "#3178C6",
    ),
    "json.svg": solid(
        '<path d="M2 1h12v14H2z" fill="#CBA32B"/>'
        '<path fill="#1E1E1E" d="M6.1 4c-.7 0-1 .4-1 1.1v1c0 .5-.3.8-.9.8v.6c.6 0 .9.3.9.8v1.6c0 .7.3 1.1 1 1.1h.5v-.7h-.3c-.3 0-.4-.2-.4-.5V8.5c0-.5-.2-.8-.6-.9.4-.1.6-.4.6-.9V5.1c0-.3.1-.5.4-.5h.3V4zM9.9 4H9.4v.7h.3c.3 0 .4.2.4.5v1.1c0 .5.2.8.6.9-.4.1-.6.4-.6.9v1.3c0 .3-.1.5-.4.5h-.3v.7h.5c.7 0 1-.4 1-1.1V8.3c0-.5.3-.8.9-.8v-.6c-.6 0-.9-.3-.9-.8v-1c0-.7-.3-1.1-1-1.1z"/>',
        "#CBA32B",
    ),
    "html.svg": solid(
        '<path d="M2 1h12v14H2z"/>'
        '<path fill="#1E1E1E" d="M5.3 5.2L3.6 8l1.7 2.8h1l-1.6-2.8 1.6-2.8zM9.7 5.2L8 8l1.7 2.8h1L9.1 8l1.6-2.8zM7.4 10.9h.9l.6-5.7h-.9z"/>',
        "#E44D26",
    ),
    "css.svg": solid(
        '<path d="M2 1h12v14H2z"/>'
        '<path fill="#1E1E1E" d="M6.6 5.3l.1 1H11v1H10l-.1 1.2h.9l-.1 1H5.6l.1-1h1.7l.1-1.2H5.3l-.2-2z"/>',
        "#2965F1",
    ),
    "c.svg": solid(
        '<path d="M2 1h12v14H2z"/>'
        '<path fill="#1E1E1E" d="M8.6 5.3c-1.6 0-2.6 1.1-2.6 2.7s1 2.7 2.6 2.7c.9 0 1.6-.4 2-1.1l-.8-.5c-.2.4-.6.7-1.2.7-.9 0-1.5-.7-1.5-1.8s.6-1.8 1.5-1.8c.5 0 .9.2 1.1.6l.8-.5c-.4-.6-1-1-1.9-1z"/>',
        "#599EFF",
    ),
    "cpp.svg": solid(
        '<path d="M2 1h12v14H2z"/>'
        '<path fill="#1E1E1E" d="M6.3 5.3c-1.4 0-2.3 1.1-2.3 2.7s.9 2.7 2.3 2.7c.8 0 1.4-.4 1.8-1l-.7-.4c-.2.3-.6.6-1 .6-.8 0-1.3-.7-1.3-1.8s.5-1.8 1.3-1.8c.4 0 .7.2.9.5l.7-.4c-.4-.6-.9-1-1.7-1zM12 6.4h-.9V5.6h-.8v.8h-.8v.8h.8v.8h.8v-.8h.9z"/>',
        "#9C033A",
    ),
    "git.svg": svg(
        '<path d="M4 3.5v7"/><path d="M4 10.5a2.5 2.5 0 0 0 2.5 2.5h3"/>'
        '<circle cx="4" cy="12.5" r="1.5"/><circle cx="4" cy="2.6" r="1.4"/><circle cx="10.9" cy="13" r="1.6"/>',
        fill_stroke="#E44D26",
    ),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in ICONS.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
