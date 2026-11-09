"""PyScribe core/analyzers/binary.py: application module and reusable component."""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core.project_intelligence import Issue, StructureEdge, StructureNode, SymbolInfo


@dataclass
class BinaryResult:
    format: str
    architecture: str
    bits: int
    entrypoint: int
    sections: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    nodes: List[StructureNode] = field(default_factory=list)
    edges: List[StructureEdge] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class BinaryAnalyzer:
    """Static executable inspection. Never executes the inspected binary."""

    EXTENSIONS = {".exe", ".dll", ".sys", ".efi", ".so", ".dylib", ".bin", ".elf", ".o", ".obj", ".a", ".apk", ".dex"}
    MAGIC = {
        b"MZ": "PE", b"\x7fELF": "ELF", b"\xfe\xed\xfa\xce": "Mach-O", b"\xce\xfa\xed\xfe": "Mach-O",
        b"\xfe\xed\xfa\xcf": "Mach-O", b"\xcf\xfa\xed\xfe": "Mach-O", b"\xca\xfe\xba\xbe": "Mach-O-FAT",
        b"\xca\xfe\xba\xbf": "Mach-O-FAT", b"dex\n": "DEX",
    }

    def __init__(self, root: Path):
        self.root = root

    @classmethod
    def looks_like_binary(cls, path: Path) -> bool:
        if path.suffix.lower() in cls.EXTENSIONS:
            return True
        try:
            with path.open("rb") as fh:
                head = fh.read(8)
            return any(head.startswith(magic) for magic in cls.MAGIC)
        except OSError:
            return False

    def analyze(self, path: Path) -> BinaryResult:
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        fmt = self._detect(data)
        result = BinaryResult(fmt, "unknown", 0, 0)
        result.metrics.update({"size": len(data), "sha256": sha256, "format": fmt, "entropy": self._entropy(data)})
        parsed = False
        try:
            import lief
            binary = lief.parse(str(path))
            if binary:
                parsed = True
                result = self._from_lief(path, binary, result)
        except Exception as exc:
            result.issues.append(Issue("info", "BIN001", f"LIEF parser unavailable or rejected file: {exc}", str(path), 1))
        if not parsed:
            self._raw_fallback(path, data, result)
        self._add_binary_nodes(path, result)
        result.metrics["parser"] = "lief" if parsed else "raw"
        result.metrics["suspicious_strings"] = sum(1 for _ in self._suspicious_strings(data))
        self._disassemble_sample(data, result)
        return result

    def _from_lief(self, path: Path, binary, result: BinaryResult) -> BinaryResult:
        try: result.architecture = str(binary.header.machine_type).split(".")[-1]
        except Exception: result.architecture = "unknown"
        try: result.bits = int(binary.header.identity_class.value) * 32 if int(binary.header.identity_class.value) in (1, 2) else 0
        except Exception: result.bits = 0
        try: result.entrypoint = int(binary.entrypoint)
        except Exception: result.entrypoint = 0
        try:
            result.format = str(binary.format).split(".")[-1]
        except Exception: pass
        try:
            for s in binary.sections:
                result.sections.append({"name": s.name, "size": int(s.size), "virtual_size": int(getattr(s, "virtual_size", 0)), "offset": int(getattr(s, "offset", 0)), "entropy": float(s.entropy) if hasattr(s, "entropy") else None, "flags": str(getattr(s, "flags", ""))})
        except Exception: pass
        try:
            result.imports.extend(sorted({str(x.name) for x in binary.imported_functions if getattr(x, "name", None)}))
        except Exception:
            try: result.imports.extend(sorted({str(x.name) for x in binary.imports if getattr(x, "name", None)}))
            except Exception: pass
        try: result.exports.extend(sorted({str(x.name) for x in binary.exported_functions if getattr(x, "name", None)}))
        except Exception:
            try: result.exports.extend(sorted({str(x.name) for x in binary.exported_functions}))
            except Exception: pass
        try:
            for s in binary.symbols:
                name = str(getattr(s, "name", ""))
                if not name:
                    continue
                result.symbols.append(SymbolInfo(name, "binary-symbol", str(path), int(getattr(s, "value", 0))))
        except Exception: pass
        result.metrics.update({"sections": len(result.sections), "imports": len(result.imports), "exports": len(result.exports), "symbols": len(result.symbols)})
        # Common hardening checks where LIEF exposes the required metadata.
        try:
            is_pe_app = (result.format == "PE" and "DLL" not in str(binary.header.characteristics))
            if is_pe_app and not result.exports:
                result.issues.append(Issue("info", "PE001", "PE executable has no exported symbols.", str(path), 1))
        except Exception: pass
        return result

    def _raw_fallback(self, path: Path, data: bytes, result: BinaryResult):
        for s in self._strings(data):
            if any(x in s.lower() for x in ("http://", "https://", "powershell", "cmd.exe", "/bin/sh", "createprocess", "virtualalloc")):
                result.issues.append(Issue("warning", "BIN010", f"Interesting embedded string: {s[:160]}", str(path), 1))
        result.metrics.update({"sections": 0, "imports": 0, "exports": 0, "symbols": 0})

    def _add_binary_nodes(self, path: Path, result: BinaryResult):
        root = f"binary:{path}"
        result.nodes.append(StructureNode(root, path.name, "binary", str(path), 1, "", result.format, result.architecture))
        for i, s in enumerate(result.sections):
            sid = f"{root}:section:{i}:{s['name']}"
            result.nodes.append(StructureNode(sid, s["name"], "section", str(path), 1, root, "", f"{s['size']} bytes"))
            result.edges.append(StructureEdge(root, sid, "contains"))
        for name in result.imports:
            iid = f"{root}:import:{name}"
            result.nodes.append(StructureNode(iid, name, "import", str(path), 1, root, "", "import"))
            result.edges.append(StructureEdge(root, iid, "imports"))
        for name in result.exports:
            eid = f"{root}:export:{name}"
            result.nodes.append(StructureNode(eid, name, "export", str(path), 1, root, "", "export"))
            result.edges.append(StructureEdge(root, eid, "exports"))

    def _disassemble_sample(self, data: bytes, result: BinaryResult):
        """Disassemble a bounded executable-section sample when Capstone is available."""
        try:
            from capstone import (Cs, CS_ARCH_ARM, CS_ARCH_ARM64, CS_ARCH_X86, CS_MODE_32, CS_MODE_64, CS_MODE_ARM, CS_MODE_ARM64)
        except Exception:
            result.metrics['disassembly'] = 'capstone-not-installed'
            return
        arch = str(result.architecture).lower()
        if 'aarch64' in arch or 'arm64' in arch:
            cs = Cs(CS_ARCH_ARM64, CS_MODE_ARM64)
        elif 'arm' in arch:
            cs = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        elif result.bits == 32:
            cs = Cs(CS_ARCH_X86, CS_MODE_32)
        else:
            cs = Cs(CS_ARCH_X86, CS_MODE_64)
        offset, size, address = 0, min(len(data), 65536), 0
        if result.sections:
            candidates = [s for s in result.sections if '.text' in str(s.get('name', '')).lower() or 'X' in str(s.get('flags', ''))]
            if candidates:
                sec = candidates[0]
                offset = max(0, int(sec.get('offset', 0)))
                size = min(int(sec.get('size', len(data) - offset)), 65536, max(0, len(data) - offset))
                address = result.entrypoint if result.entrypoint else offset
        sample = data[offset:offset + size]
        insns = list(cs.disasm(sample, address, count=512))
        result.metrics['disassembly_instructions'] = len(insns)
        result.metrics['disassembly_offset'] = offset
        result.metrics['mnemonics'] = sorted({i.mnemonic for i in insns})[:64]

    @staticmethod
    def _detect(data: bytes) -> str:
        for magic, name in BinaryAnalyzer.MAGIC.items():
            if data.startswith(magic): return name
        return "unknown"

    @staticmethod
    def _entropy(data: bytes) -> float:
        if not data: return 0.0
        freq = [0] * 256
        for b in data: freq[b] += 1
        n = len(data)
        return round(-sum((c/n) * math.log2(c/n) for c in freq if c), 4)

    @staticmethod
    def _strings(data: bytes):
        for m in re.finditer(rb"[ -~]{6,}", data):
            yield m.group(0).decode("ascii", errors="replace")

    def _suspicious_strings(self, data: bytes):
        for s in self._strings(data):
            if re.search(r"https?://|powershell|cmd\.exe|/bin/(?:sh|bash)|virtualalloc|createprocess", s, re.I):
                yield s
