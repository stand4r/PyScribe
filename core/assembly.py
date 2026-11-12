"""Source outline and bundled Windows x86 assembly build plans."""
import re
import sys
from pathlib import Path

EXTENSIONS = {".asm", ".nasm", ".fasm"}
LABEL = re.compile(
    r"^\s*([A-Za-z_.$?@][\w.$?@]*)(?:\s*:|\s+(?:db|dw|dd|dq|resb|resw|resd|resq|equ)\b)",
    re.I,
)
INCLUDE = re.compile(r"""^\s*%?include\s+['"]([^'"]+)['"]""", re.I)
FASM_FORMAT = re.compile(r"^\s*format\s+(PE64|PE)(?=\s|$)", re.I | re.M)
BITS = re.compile(r"^\s*\[?bits\s+(16|32|64)\b", re.I | re.M)


def outline(text):
    labels, includes = [], []
    for number, line in enumerate(text.splitlines(), 1):
        label = LABEL.match(line)
        if label:
            labels.append((label[1], number, label.start(1)))
        include = INCLUDE.match(line)
        if include:
            includes.append(include[1])
    return labels, includes


def windows_build(source: Path, scratch: Path, arguments: list[str]):
    """Return argv lists for the assembler, optional PE wrapper, and program."""
    if sys.platform != "win32":
        raise ValueError("Встроенный запуск ассемблера доступен на Windows.")
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    tools = root / "third_party" / "assembly"
    fasm = tools / "fasm" / "fasm.exe"
    nasm = tools / "nasm" / "nasm.exe"
    if not (fasm.is_file() and nasm.is_file()):
        raise ValueError("В сборке PyScribe отсутствуют NASM или FASM.")

    text = source.read_text(encoding="utf-8-sig")
    directives = "\n".join(line.split(";", 1)[0] for line in text.splitlines())
    pe = FASM_FORMAT.search(directives)
    executable = scratch / "program.exe"
    include = str(tools / "fasm" / "INCLUDE")
    (scratch / "source.asm").write_text(text, encoding="utf-8")
    if source.suffix.lower() == ".fasm" or (pe and source.suffix.lower() != ".nasm"):
        if not pe:
            raise ValueError("Для запуска FASM укажите format PE или format PE64.")
        return [[str(fasm), "source.asm", "program.exe"], [str(executable), *arguments]], include

    mode = BITS.search(directives)
    bits = int(mode[1]) if mode else 64
    if bits == 16:
        raise ValueError("Для запуска NASM используйте BITS 32 или BITS 64.")
    (scratch / "mode.inc").write_text(f"BITS {bits}\n", encoding="ascii")
    header, macro = ("PE64", "win64a.inc") if bits == 64 else ("PE", "win32a.inc")
    # Run the flat payload as a Windows ABI function returning a code in EAX.
    invoke = ("sub rsp, 40\n call payload\n mov ecx, eax\n call [ExitProcess]"
              if bits == 64 else "call payload\n push eax\n call [ExitProcess]")
    (scratch / "launcher.asm").write_text(
        f"format {header} console\nentry start\ninclude '{macro}'\n"
        f"section '.text' code readable executable\nstart:\n {invoke}\n"
        "align 16\npayload:\n file 'program.bin'\n"
        "section '.idata' import data readable writeable\n"
        " library kernel32,'KERNEL32.DLL'\n import kernel32,ExitProcess,'ExitProcess'\n",
        encoding="ascii",
    )
    return [
        [str(nasm), "-f", "bin", "-p", "mode.inc", "-I", str(source.parent) + "/", "source.asm", "-o", "program.bin"],
        [str(fasm), "launcher.asm", "program.exe"],
        [str(executable), *arguments],
    ], include
