"""Built-in, dependency-free duplicate-code (clone) detector."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .model import Finding, read_text, rel


def _normalized_code_lines(path: Path) -> List[Tuple[int, str]]:
    """Return (original_line_no, normalized_text) for meaningful code lines."""
    out: List[Tuple[int, str]] = []
    try:
        raw = read_text(path).splitlines()
    except OSError:
        return out
    for i, line in enumerate(raw, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append((i, re.sub(r"\s+", " ", stripped)))
    return out


Occurrence = Tuple[int, int, int, int, int]


def _hash_windows(files: Sequence[Path], window: int, min_chars: int
                  ) -> Dict[str, List[Occurrence]]:
    buckets: Dict[str, List[Occurrence]] = defaultdict(list)
    for fi, path in enumerate(files):
        lines = _normalized_code_lines(path)
        if len(lines) < window:
            continue
        for start in range(len(lines) - window + 1):
            chunk = lines[start:start + window]
            text = "\n".join(t for _, t in chunk)
            if len(text) < min_chars:
                continue
            h = hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
            buckets[h].append((fi, start, chunk[0][0], chunk[-1][0], len(text)))
    return buckets


def _clone_finding(occ: List[Occurrence], files: Sequence[Path], root: Path,
                   window: int) -> Optional[Tuple[Tuple, Finding]]:
    distinct = {(fi, start) for fi, start, *_ in occ}
    if len(distinct) < 2:
        return None
    locations = sorted({(o[0], o[2], o[3]) for o in occ})
    key = tuple(sorted((fi, sl) for fi, sl, _ in locations))
    span = occ[0][3] - occ[0][2] + 1
    loc_strs = [f"{rel(str(files[fi]), root)}:{sl}-{el}" for fi, sl, el in locations]
    primary = locations[0]
    severe = len(locations) >= 3 or span >= window * 2
    finding = Finding(
        tool="duplication", category="duplication",
        severity="warning" if severe else "info", rule="clone-family",
        message=f"duplicated block (~{span} lines) in {len(locations)} places: "
                + ", ".join(loc_strs[:4]) + (" ..." if len(loc_strs) > 4 else ""),
        file=rel(str(files[primary[0]]), root), line=primary[1],
        value=float(len(locations)),
    )
    return key, finding


def detect_duplication(root: Path, files: Sequence[Path], window: int = 6,
                       min_chars: int = 120) -> List[Finding]:
    """Hash sliding windows of normalized code, group clones, merge overlaps."""
    buckets = _hash_windows(files, window, min_chars)
    findings: List[Finding] = []
    seen: Set[Tuple] = set()
    for occ in buckets.values():
        if len(occ) < 2:
            continue
        built = _clone_finding(occ, files, root, window)
        if built is None or built[0] in seen:
            continue
        seen.add(built[0])
        findings.append(built[1])
    findings.sort(key=lambda f: (-(f.value or 0), f.file, f.line or 0))
    return _merge_overlapping_clones(findings)


def _clone_span(f: Finding) -> int:
    m = re.search(r"~(\d+) lines", f.message)
    return int(m.group(1)) if m else 1


def _merge_overlapping_clones(findings: List[Finding]) -> List[Finding]:
    """Drop clone findings whose primary location is subsumed by a larger family."""
    kept: List[Finding] = []
    occupied: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for f in findings:
        start = f.line or 0
        end = start + _clone_span(f)
        if any(s <= start <= e or s <= end <= e for s, e in occupied[f.file]):
            continue
        occupied[f.file].append((start, end))
        kept.append(f)
    return kept
