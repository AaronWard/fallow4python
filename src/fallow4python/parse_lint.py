"""Parsers for the lint-family tools: ruff, mypy, vulture."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .model import Finding, Metric, as_dict, normalize_path, rel, safe_json_loads, to_int

Parsed = Tuple[List[Finding], List[Metric]]


# --- ruff ------------------------------------------------------------------ #

def severity_for_ruff(code: str, message: str) -> str:
    code = code or ""
    msg = message.lower()
    if code == "E999" or code.startswith("F82"):
        return "error"
    if "syntaxerror" in msg or "syntax error" in msg:
        return "error"
    return "warning"


def _ruff_from_obj(item: Dict[str, Any], root: Path) -> Finding:
    loc = as_dict(item.get("location"))
    code = str(item.get("code") or "")
    msg = str(item.get("message") or "")
    return Finding(
        tool="ruff", category="lint", severity=severity_for_ruff(code, msg),
        rule=code, message=msg,
        file=rel(normalize_path(item.get("filename") or item.get("file")), root),
        line=to_int(loc.get("row") or item.get("line")),
        column=to_int(loc.get("column") or item.get("column")),
        raw=json.dumps(item, sort_keys=True),
    )


_RUFF_TEXT = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s*"
    r"(?:(?P<code>[A-Z]+[0-9]+)\s+)?(?P<msg>.+)$"
)


def parse_ruff(text: str, root: Path) -> Parsed:
    data = safe_json_loads(text)
    if isinstance(data, list):
        return [_ruff_from_obj(i, root) for i in data if isinstance(i, dict)], []
    out: List[Finding] = []
    for line in text.splitlines():
        m = _RUFF_TEXT.match(line.strip())
        if not m:
            continue
        code = m.group("code") or ""
        out.append(Finding(
            tool="ruff", category="lint",
            severity=severity_for_ruff(code, m.group("msg") or ""),
            rule=code, message=m.group("msg") or "",
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")), raw=line,
        ))
    return out, []


# --- mypy ------------------------------------------------------------------ #

def _norm_mypy_severity(sev: str) -> str:
    sev = sev.lower()
    if sev == "note":
        return "info"
    return "warning" if sev.startswith("warn") else "error"


def _mypy_from_obj(item: Dict[str, Any], root: Path) -> Finding:
    return Finding(
        tool="mypy", category="typing",
        severity=_norm_mypy_severity(str(item.get("severity") or "error")),
        rule=str(item.get("code") or ""), message=str(item.get("message") or ""),
        file=rel(normalize_path(item.get("file")), root),
        line=to_int(item.get("line")), column=to_int(item.get("column")),
        raw=json.dumps(item, sort_keys=True),
    )


_MYPY_TEXT = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<col>\d+))?:\s*"
    r"(?P<sev>error|note|warning):\s*"
    r"(?P<msg>.*?)(?:\s+\[(?P<code>[^\]]+)\])?$"
)


def parse_mypy(text: str, root: Path) -> Parsed:
    data = safe_json_loads(text)
    if isinstance(data, list):
        return [_mypy_from_obj(i, root) for i in data if isinstance(i, dict)], []
    out: List[Finding] = []
    for line in text.splitlines():
        m = _MYPY_TEXT.match(line.strip())
        if not m:
            continue
        out.append(Finding(
            tool="mypy", category="typing",
            severity=_norm_mypy_severity(m.group("sev")),
            rule=m.group("code") or "", message=m.group("msg") or "",
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")), raw=line,
        ))
    return out, []


# --- vulture --------------------------------------------------------------- #

_VULTURE_TEXT = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s*"
    r"(?P<kind>unused [^(]+?)\s*\((?P<conf>\d+)% confidence\)"
)


def parse_vulture(text: str, root: Path) -> Parsed:
    out: List[Finding] = []
    for line in text.splitlines():
        m = _VULTURE_TEXT.match(line.strip())
        if not m:
            continue
        conf = to_int(m.group("conf"))
        sev = "warning" if (conf is not None and conf >= 80) else "info"
        out.append(Finding(
            tool="vulture", category="dead-code", severity=sev,
            rule="dead-code", message=m.group("kind").strip(),
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), confidence=conf, raw=line,
        ))
    return out, []
