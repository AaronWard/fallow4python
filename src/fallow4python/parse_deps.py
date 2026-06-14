"""Parser for deptry dependency findings."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .model import Finding, Metric, as_dict, normalize_path, rel, safe_json_loads, to_int

Parsed = Tuple[List[Finding], List[Metric]]


def _walk_json(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk_json(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_json(v)


def severity_for_deptry(code: str) -> str:
    return "error" if code == "DEP001" else "warning"


def _deptry_code(obj: Dict[str, Any], error: Optional[Dict[str, Any]]) -> str:
    return str((error or {}).get("code") or obj.get("code")
               or obj.get("error_code") or "")


def _deptry_is_real(obj: Dict[str, Any], error: Optional[Dict[str, Any]]) -> bool:
    # A nested ``error`` sub-dict carries the code but no module/location; only
    # a genuine top-level finding wraps an ``error`` dict or names a module.
    if error is not None:
        return True
    return bool(obj.get("module") or obj.get("location") or obj.get("file"))


def _deptry_message(obj: Dict[str, Any], error: Optional[Dict[str, Any]]) -> str:
    return str((error or {}).get("message") or obj.get("message")
               or obj.get("description") or "")


def _deptry_file(obj: Dict[str, Any], loc: Dict[str, Any]) -> str:
    return loc.get("file") or obj.get("file") or obj.get("module") or ""


def _deptry_finding(obj: Dict[str, Any], root: Path) -> Optional[Finding]:
    error = obj.get("error") if isinstance(obj.get("error"), dict) else None
    code = _deptry_code(obj, error)
    if not code.startswith("DEP") or not _deptry_is_real(obj, error):
        return None
    loc = as_dict(obj.get("location"))
    return Finding(
        tool="deptry", category="dependencies",
        severity=severity_for_deptry(code), rule=code,
        message=_deptry_message(obj, error),
        file=rel(normalize_path(_deptry_file(obj, loc)), root),
        line=to_int(loc.get("line") or obj.get("line")),
        column=to_int(loc.get("column") or obj.get("column")),
        raw=json.dumps(obj, sort_keys=True),
    )


_DEPTRY_TEXT = re.compile(
    r"^(?P<file>.+?)(?::(?P<line>\d+))?(?::(?P<col>\d+))?:\s*"
    r"(?P<code>DEP\d+)\s+(?P<msg>.+)$"
)


def _deptry_from_json(data: Any, root: Path) -> List[Finding]:
    out: List[Finding] = []
    seen: Set[Tuple] = set()
    for obj in _walk_json(data):
        f = _deptry_finding(obj, root)
        if f is None:
            continue
        key = (f.rule, f.message, f.file, f.line)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def parse_deptry(text: str, root: Path) -> Parsed:
    data = safe_json_loads(text)
    if data is not None:
        out = _deptry_from_json(data, root)
        if out:
            return out, []
    text_out: List[Finding] = []
    for line in text.splitlines():
        m = _DEPTRY_TEXT.match(line.strip())
        if not m:
            continue
        code = m.group("code")
        text_out.append(Finding(
            tool="deptry", category="dependencies",
            severity=severity_for_deptry(code), rule=code, message=m.group("msg"),
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")), raw=line,
        ))
    return text_out, []
