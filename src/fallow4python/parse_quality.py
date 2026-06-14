"""Parsers for xenon, import-linter, and coverage.py JSON output."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .model import Finding, Metric, as_dict, normalize_path, rel, safe_json_loads, to_float

Parsed = Tuple[List[Finding], List[Metric]]


# --- xenon ----------------------------------------------------------------- #

_XENON_FILE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):?\s*(?P<msg>.+)$")
_XENON_GENERIC = re.compile(
    r"\b(error|failed|too complex|complexity|rank [C-F]|average)\b", re.I)


def parse_xenon(text: str, root: Path) -> Parsed:
    out: List[Finding] = []
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        m = _XENON_FILE.match(s)
        if m:
            out.append(Finding(
                tool="xenon", category="complexity", severity="error",
                rule="complexity-threshold", message=m.group("msg"),
                file=rel(normalize_path(m.group("file")), root),
                line=int(m.group("line")), column=int(m.group("col")), raw=line))
        elif _XENON_GENERIC.search(s):
            out.append(Finding(
                tool="xenon", category="complexity", severity="error",
                rule="complexity-threshold", message=s, line=idx, raw=line))
    return out, []


# --- import-linter --------------------------------------------------------- #

_IMPORT_LINTER = re.compile(
    r"\b(broken|violation|violated|illegal import|forbidden|not allowed"
    r"|contract.*failed)\b", re.I)


def parse_import_linter(text: str, root: Path) -> Parsed:
    out: List[Finding] = []
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s and _IMPORT_LINTER.search(s):
            out.append(Finding(
                tool="import-linter", category="architecture", severity="error",
                rule="architecture", message=s, line=idx, raw=line))
    return out, []


# --- coverage -------------------------------------------------------------- #

def _coverage_severity(pct: float, min_percent: float) -> str:
    return "error" if pct < max(0.0, min_percent - 10) else "warning"


def _coverage_total(totals: Dict[str, Any], min_percent: float) -> Parsed:
    pct = to_float(totals.get("percent_covered"))
    if pct is None:
        return [], []
    metrics = [Metric(tool="coverage", name="total-line-coverage",
                      value=pct, unit="%", details="overall")]
    if pct >= min_percent:
        return [], metrics
    return [Finding(
        tool="coverage", category="coverage",
        severity=_coverage_severity(pct, min_percent),
        rule="coverage-total", value=pct,
        message=f"total coverage {pct:.2f}% below threshold {min_percent:.0f}%",
    )], metrics


def _missing_lines(info: Dict[str, Any], summary: Dict[str, Any]) -> Optional[int]:
    missing = summary.get("missing_lines")
    if missing is None and isinstance(info.get("missing_lines"), list):
        missing = len(info["missing_lines"])
    return missing


def _coverage_file(filename: str, info: Dict[str, Any], root: Path,
                   min_percent: float) -> Parsed:
    f = rel(normalize_path(filename), root)
    if f.startswith(".."):  # outside the scanned tree; reporting it is noise
        return [], []
    summary = as_dict(info.get("summary"))
    pct = to_float(summary.get("percent_covered"))
    if pct is None:
        return [], []
    metrics = [Metric(tool="coverage", name="file-line-coverage",
                      value=pct, unit="%", file=f)]
    if pct >= min_percent:
        return [], metrics
    missing = _missing_lines(info, summary)
    tail = f"; {missing} lines missing" if missing is not None else ""
    return [Finding(
        tool="coverage", category="coverage",
        severity=_coverage_severity(pct, min_percent),
        rule="coverage-file", file=f, value=pct,
        message=f"coverage {pct:.2f}% below {min_percent:.0f}%{tail}",
    )], metrics


def parse_coverage(text: str, root: Path, min_percent: float) -> Parsed:
    data = safe_json_loads(text)
    if not isinstance(data, dict):
        return [Finding(tool="coverage", category="reporting", severity="error",
                        rule="parse-error",
                        message="coverage input was not valid JSON")], []
    findings, metrics = _coverage_total(as_dict(data.get("totals")), min_percent)
    for filename, info in as_dict(data.get("files")).items():
        if not isinstance(info, dict):
            continue
        fs, ms = _coverage_file(filename, info, root, min_percent)
        findings += fs
        metrics += ms
    return findings, metrics
