"""Small pure helpers: parsing, normalization, ranking, and sorting."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import IGNORE_DIRS, RADON_RANK_ORDER, SEVERITY_ORDER
from .records import Finding


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_path(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\\", "/")


def rel(path: str, root: Path) -> str:
    """Best-effort relative path for stable, readable reporting."""
    if not path:
        return ""
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except (ValueError, OSError):
        return normalize_path(path)


def to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_dict(value: Any) -> Dict[str, Any]:
    """Return value if it's a dict, else an empty dict (narrows JSON results)."""
    return value if isinstance(value, dict) else {}


def _json_lines(text: str) -> Optional[List[Any]]:
    records: List[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            return None
    return records or None


def safe_json_loads(text: str) -> Optional[Any]:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return _json_lines(stripped)


def compact(message: str, max_len: int = 180) -> str:
    message = " ".join(str(message).split())
    if len(message) <= max_len:
        return message
    return message[: max_len - 1].rstrip() + "\u2026"


def md_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def rank_at_least(rank: str, minimum: str) -> bool:
    return (RADON_RANK_ORDER.get(rank.upper(), 999)
            >= RADON_RANK_ORDER.get(minimum.upper(), 999))


def rank_from_cc(complexity: Optional[float]) -> str:
    if complexity is None:
        return ""
    for ceiling, letter in ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E")):
        if complexity <= ceiling:
            return letter
    return "F"


def severity_for_radon_rank(rank: str) -> str:
    rank = rank.upper()
    if rank in {"D", "E", "F"}:
        return "error"
    if rank == "C":
        return "warning"
    return "info"


def location_str(f: Finding) -> str:
    loc = f.file or "-"
    if f.line is not None:
        loc += f":{f.line}"
        if f.column is not None:
            loc += f":{f.column}"
    return loc


def finding_sort_key(f: Finding):
    return (
        0 if f.changed else 1,
        -SEVERITY_ORDER.get(f.severity, 0),
        f.tool, f.file, f.line or 0, f.column or 0, f.rule,
    )


def exclude_dir_names() -> str:
    """Comma-separated dir names (for tools matching on name, e.g. radon -i)."""
    return ",".join(sorted(IGNORE_DIRS))


def exclude_globs() -> str:
    """Comma-separated path globs covering rooted and nested matches."""
    pats: List[str] = []
    for d in sorted(IGNORE_DIRS):
        pats.append(f"{d}/*")
        pats.append(f"*/{d}/*")
    return ",".join(pats)


def exclude_regex() -> str:
    """A regex matching any ignored directory (for tools taking a regex)."""
    names = "|".join(re.escape(d) for d in sorted(IGNORE_DIRS))
    return rf"(^|/)({names})(/|$)"
