#!/usr/bin/env python3
"""
fallow4python - codebase intelligence for Python.

A "Fallow for Python": one command that runs your quality toolchain, parses
every output into a single model, correlates the signals into actionable
insights, optionally scopes everything to the code you just changed, and emits
a unified report for humans, CI, and agents.

It does three things the individual tools do not:

  1. Orchestrates (zero-config). It finds and runs the tools that are installed
     (ruff, mypy, vulture, radon, deptry, xenon, import-linter) and ingests
     coverage you supply. No need to wire up nine commands and save nine files.
     You can still ingest pre-saved outputs with --from-dir for CI artifacts.

  2. Adds what the standard tools miss. Two built-in, dependency-free analyzers:
        * duplication  - clone families (repeated logic) across the tree
        * cycles       - circular imports in the intra-project import graph
     Plus a correlation pass that cross-references signals, e.g. "dead AND
     uncovered" => high-confidence deletion candidate, "complex AND changed AND
     undertested" => risk hotspot.

  3. Reviews changes, not just snapshots. `fallow4python audit --base main` scopes
     findings to changed files/lines via git and returns a pass/warn/fail
     verdict - a PR risk gate for human- and AI-generated code.

Output formats: human (terminal), markdown, json (agent-friendly envelope),
and sarif (GitHub code scanning). Pure standard library; Python 3.9+.

Subcommands:
    fallow4python scan [path]            Full-codebase analysis (default).
    fallow4python audit [path] --base R  Changed-code review with a verdict.
    fallow4python health [path]          Complexity + maintainability + refactor targets.
    fallow4python dead-code [path]       Cleanup candidates (dead code + unused deps).
    fallow4python summary [path]         One-screen health snapshot.

Examples:
    fallow4python                                  # full scan of the cwd, human output
    fallow4python summary                          # quick health grade
    fallow4python audit --base origin/main         # PR gate, verdict + exit code
    fallow4python scan --coverage .coverage.json --json-out report.json
    fallow4python scan --from-dir .quality --markdown-out quality-report.md
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SCHEMA_VERSION = "1.0"
TOOL_VERSION = "1.1.2"

# --------------------------------------------------------------------------- #
# Ordering / constants
# --------------------------------------------------------------------------- #

SEVERITY_ORDER = {"info": 1, "warning": 2, "error": 3}
SEVERITY_RANK = {1: "info", 2: "warning", 3: "error"}

RADON_RANK_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}

# Categories used across the model. Kept stable so JSON consumers can rely on them.
CATEGORIES = (
    "lint",
    "typing",
    "dead-code",
    "complexity",
    "maintainability",
    "dependencies",
    "duplication",
    "architecture",
    "coverage",
    "reporting",
)

# Directories we never descend into for the built-in analyzers.
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
    "build", "dist", ".eggs", "site-packages", ".quality", ".idea", ".vscode",
}


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Finding:
    """A single normalized problem reported by some tool or analyzer."""
    tool: str
    category: str
    severity: str
    message: str
    rule: str = ""
    file: str = ""
    line: Optional[int] = None
    column: Optional[int] = None
    symbol: str = ""
    rank: str = ""
    value: Optional[float] = None
    confidence: Optional[int] = None
    changed: bool = False  # touched by the diff in audit mode
    raw: str = ""


@dataclass(frozen=True)
class Metric:
    """A measured value (coverage %, maintainability index, complexity, LOC)."""
    tool: str
    name: str
    value: float
    unit: str = ""
    file: str = ""
    rank: str = ""
    details: str = ""


@dataclass
class Insight:
    """A correlated, cross-tool conclusion - the 'intelligence' layer."""
    kind: str
    severity: str
    title: str
    detail: str
    file: str = ""
    line: Optional[int] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class ToolRun:
    """Provenance for a single tool: was it run, ingested, skipped, or errored?"""
    name: str
    status: str  # ran | ingested | skipped | error
    detail: str = ""
    findings: int = 0
    duration_ms: Optional[int] = None


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

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


def safe_json_loads(text: str) -> Optional[Any]:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    records: List[Any] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            return None
    return records or None


def compact(message: str, max_len: int = 180) -> str:
    message = " ".join(str(message).split())
    return message if len(message) <= max_len else message[: max_len - 1].rstrip() + "\u2026"


def md_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def rank_at_least(rank: str, minimum: str) -> bool:
    return RADON_RANK_ORDER.get(rank.upper(), 999) >= RADON_RANK_ORDER.get(minimum.upper(), 999)


def rank_from_cc(complexity: Optional[float]) -> str:
    if complexity is None:
        return ""
    bounds = ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E"))
    for ceiling, letter in bounds:
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


def finding_sort_key(f: Finding) -> Tuple[int, int, str, str, int, int, str]:
    return (
        0 if f.changed else 1,                      # changed findings first
        -SEVERITY_ORDER.get(f.severity, 0),
        f.tool,
        f.file,
        f.line or 0,
        f.column or 0,
        f.rule,
    )


# --------------------------------------------------------------------------- #
# Parsers: external tools -> Findings/Metrics
# Each parser takes the raw text and the project root, returns (findings, metrics).
# --------------------------------------------------------------------------- #

def severity_for_ruff(code: str, message: str) -> str:
    code = code or ""
    msg = message.lower()
    if code == "E999" or code.startswith("F82"):
        return "error"
    if "syntaxerror" in msg or "syntax error" in msg:
        return "error"
    return "warning"


def parse_ruff(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            loc = item.get("location") if isinstance(item.get("location"), dict) else {}
            code = str(item.get("code") or "")
            msg = str(item.get("message") or "")
            out.append(Finding(
                tool="ruff", category="lint",
                severity=severity_for_ruff(code, msg),
                rule=code, message=msg,
                file=rel(normalize_path(item.get("filename") or item.get("file")), root),
                line=to_int(loc.get("row") or item.get("line")),
                column=to_int(loc.get("column") or item.get("column")),
                raw=json.dumps(item, sort_keys=True),
            ))
        return out, []
    pat = re.compile(
        r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s*"
        r"(?:(?P<code>[A-Z]+[0-9]+)\s+)?(?P<msg>.+)$"
    )
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        code = m.group("code") or ""
        out.append(Finding(
            tool="ruff", category="lint",
            severity=severity_for_ruff(code, m.group("msg") or ""),
            rule=code, message=m.group("msg") or "",
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")),
            raw=line,
        ))
    return out, []


def parse_mypy(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity") or "error").lower()
            norm = "info" if sev == "note" else ("warning" if sev.startswith("warn") else "error")
            out.append(Finding(
                tool="mypy", category="typing", severity=norm,
                rule=str(item.get("code") or ""),
                message=str(item.get("message") or ""),
                file=rel(normalize_path(item.get("file")), root),
                line=to_int(item.get("line")), column=to_int(item.get("column")),
                raw=json.dumps(item, sort_keys=True),
            ))
        return out, []
    pat = re.compile(
        r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<col>\d+))?:\s*"
        r"(?P<sev>error|note|warning):\s*"
        r"(?P<msg>.*?)(?:\s+\[(?P<code>[^\]]+)\])?$"
    )
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        raw_sev = m.group("sev").lower()
        sev = "info" if raw_sev == "note" else ("warning" if raw_sev == "warning" else "error")
        out.append(Finding(
            tool="mypy", category="typing", severity=sev,
            rule=m.group("code") or "", message=m.group("msg") or "",
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")),
            raw=line,
        ))
    return out, []


def parse_vulture(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    out: List[Finding] = []
    pat = re.compile(
        r"^(?P<file>.+?):(?P<line>\d+):\s*"
        r"(?P<kind>unused [^(]+?)\s*\((?P<conf>\d+)% confidence\)"
    )
    for line in text.splitlines():
        m = pat.match(line.strip())
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


def _walk_json(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk_json(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_json(v)


def severity_for_deptry(code: str) -> str:
    # DEP001: missing dependency (imported, not declared) -> breaks installs.
    return "error" if code == "DEP001" else "warning"


def _deptry_finding(obj: Dict[str, Any], root: Path) -> Optional[Finding]:
    error = obj.get("error") if isinstance(obj.get("error"), dict) else {}
    loc = obj.get("location") if isinstance(obj.get("location"), dict) else {}
    code = str(error.get("code") or obj.get("code") or obj.get("error_code") or "")
    if not code.startswith("DEP"):
        return None
    msg = str(error.get("message") or obj.get("message") or obj.get("description") or "")
    file_v = loc.get("file") or obj.get("file") or obj.get("module") or ""
    return Finding(
        tool="deptry", category="dependencies",
        severity=severity_for_deptry(code), rule=code, message=msg,
        file=rel(normalize_path(file_v), root),
        line=to_int(loc.get("line") or obj.get("line")),
        column=to_int(loc.get("column") or obj.get("column")),
        raw=json.dumps(obj, sort_keys=True),
    )


def parse_deptry(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    if data is not None:
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
        if out:
            return out, []
    pat = re.compile(
        r"^(?P<file>.+?)(?::(?P<line>\d+))?(?::(?P<col>\d+))?:\s*"
        r"(?P<code>DEP\d+)\s+(?P<msg>.+)$"
    )
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        code = m.group("code")
        out.append(Finding(
            tool="deptry", category="dependencies",
            severity=severity_for_deptry(code), rule=code, message=m.group("msg"),
            file=rel(normalize_path(m.group("file")), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")), raw=line,
        ))
    return out, []


def parse_radon_cc(text: str, root: Path, min_rank: str) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    total_blocks = 0
    if isinstance(data, dict):
        for filename, blocks in data.items():
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                total_blocks += 1
                cc = to_float(b.get("complexity"))
                rank = str(b.get("rank") or rank_from_cc(cc)).upper()
                if not rank or not rank_at_least(rank, min_rank):
                    continue
                name = str(b.get("name") or "<unknown>")
                btype = str(b.get("type") or "block")
                msg = (f"{btype} `{name}` complexity {cc:g} (rank {rank})"
                       if cc is not None else f"{btype} `{name}` rank {rank}")
                out.append(Finding(
                    tool="radon", category="complexity",
                    severity=severity_for_radon_rank(rank),
                    rule="cyclomatic-complexity", message=msg,
                    file=rel(normalize_path(filename), root),
                    line=to_int(b.get("lineno")), column=to_int(b.get("col_offset")),
                    symbol=name, rank=rank, value=cc,
                    raw=json.dumps(b, sort_keys=True),
                ))
        metrics = [Metric(tool="radon", name="complexity-functions",
                          value=float(total_blocks),
                          details=f"flagged={len(out)} at rank>={min_rank}")]
        return out, metrics
    current = ""
    block = re.compile(
        r"^\s*(?P<kind>[CFM])\s+(?P<line>\d+):(?P<col>\d+)\s+"
        r"(?P<name>.+?)\s+-\s+(?P<rank>[A-F])\s+\((?P<cc>\d+)\)"
    )
    for line in text.splitlines():
        if not line.strip():
            continue
        m = block.match(line)
        if m:
            rank = m.group("rank")
            if not rank_at_least(rank, min_rank):
                continue
            cc = to_float(m.group("cc"))
            name = m.group("name")
            out.append(Finding(
                tool="radon", category="complexity",
                severity=severity_for_radon_rank(rank),
                rule="cyclomatic-complexity",
                message=f"`{name}` complexity {cc:g} (rank {rank})",
                file=rel(normalize_path(current), root),
                line=to_int(m.group("line")), column=to_int(m.group("col")),
                symbol=name, rank=rank, value=cc, raw=line,
            ))
        elif not line.startswith((" ", "\t")):
            current = line.strip()
    return out, []


def parse_radon_mi(text: str, root: Path, min_rank: str) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    metrics: List[Metric] = []
    if isinstance(data, dict):
        for filename, result in data.items():
            if isinstance(result, dict):
                mi = to_float(result.get("mi") or result.get("value"))
                rank = str(result.get("rank") or "").upper()
            else:
                mi, rank = to_float(result), ""
            if mi is None:
                continue
            f = rel(normalize_path(filename), root)
            metrics.append(Metric(tool="radon", name="maintainability-index",
                                   value=mi, unit="", file=f, rank=rank))
            if rank and rank_at_least(rank, min_rank):
                out.append(Finding(
                    tool="radon", category="maintainability",
                    severity=severity_for_radon_rank(rank),
                    rule="maintainability-index",
                    message=f"maintainability index {mi:g} (rank {rank})",
                    file=f, rank=rank, value=mi,
                    raw=json.dumps(result, sort_keys=True),
                ))
        return out, metrics
    pat = re.compile(r"^(?P<file>.+?)\s+-\s+(?P<rank>[A-F])\s+\((?P<mi>[\d.]+)\)")
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        f = rel(normalize_path(m.group("file")), root)
        mi = to_float(m.group("mi"))
        rank = m.group("rank")
        if mi is not None:
            metrics.append(Metric(tool="radon", name="maintainability-index",
                                   value=mi, file=f, rank=rank))
        if rank_at_least(rank, min_rank):
            out.append(Finding(
                tool="radon", category="maintainability",
                severity=severity_for_radon_rank(rank),
                rule="maintainability-index",
                message=f"maintainability index {mi:g} (rank {rank})",
                file=f, rank=rank, value=mi, raw=line,
            ))
    return out, metrics


def parse_xenon(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    out: List[Finding] = []
    file_line = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):?\s*(?P<msg>.+)$")
    generic = re.compile(r"\b(error|failed|too complex|complexity|rank [C-F]|average)\b", re.I)
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        m = file_line.match(s)
        if m:
            out.append(Finding(
                tool="xenon", category="complexity", severity="error",
                rule="complexity-threshold", message=m.group("msg"),
                file=rel(normalize_path(m.group("file")), root),
                line=to_int(m.group("line")), column=to_int(m.group("col")), raw=line,
            ))
        elif generic.search(s):
            out.append(Finding(
                tool="xenon", category="complexity", severity="error",
                rule="complexity-threshold", message=s, line=idx, raw=line,
            ))
    return out, []


def parse_import_linter(text: str, root: Path) -> Tuple[List[Finding], List[Metric]]:
    out: List[Finding] = []
    suspicious = re.compile(
        r"\b(broken|violation|violated|illegal import|forbidden|not allowed|contract.*failed)\b",
        re.I,
    )
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s and suspicious.search(s):
            out.append(Finding(
                tool="import-linter", category="architecture", severity="error",
                rule="architecture", message=s, line=idx, raw=line,
            ))
    return out, []


def parse_coverage(text: str, root: Path, min_percent: float
                   ) -> Tuple[List[Finding], List[Metric]]:
    data = safe_json_loads(text)
    out: List[Finding] = []
    metrics: List[Metric] = []
    if not isinstance(data, dict):
        return [Finding(tool="coverage", category="reporting", severity="error",
                        rule="parse-error", message="coverage input was not valid JSON")], []
    totals = data.get("totals") if isinstance(data.get("totals"), dict) else {}
    total_pct = to_float(totals.get("percent_covered"))
    if total_pct is not None:
        metrics.append(Metric(tool="coverage", name="total-line-coverage",
                              value=total_pct, unit="%", details="overall"))
        if total_pct < min_percent:
            sev = "error" if total_pct < max(0.0, min_percent - 10) else "warning"
            out.append(Finding(
                tool="coverage", category="coverage", severity=sev,
                rule="coverage-total", value=total_pct,
                message=f"total coverage {total_pct:.2f}% below threshold {min_percent:.0f}%",
            ))
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    for filename, info in files.items():
        if not isinstance(info, dict):
            continue
        summary = info.get("summary") if isinstance(info.get("summary"), dict) else {}
        pct = to_float(summary.get("percent_covered"))
        if pct is None:
            continue
        f = rel(normalize_path(filename), root)
        metrics.append(Metric(tool="coverage", name="file-line-coverage",
                              value=pct, unit="%", file=f))
        if pct < min_percent:
            missing = summary.get("missing_lines")
            if missing is None and isinstance(info.get("missing_lines"), list):
                missing = len(info["missing_lines"])
            sev = "error" if pct < max(0.0, min_percent - 10) else "warning"
            tail = f"; {missing} lines missing" if missing is not None else ""
            out.append(Finding(
                tool="coverage", category="coverage", severity=sev,
                rule="coverage-file", file=f, value=pct,
                message=f"coverage {pct:.2f}% below {min_percent:.0f}%{tail}",
            ))
    return out, metrics


# --------------------------------------------------------------------------- #
# Built-in analyzers (no external dependency): duplication + circular imports
# --------------------------------------------------------------------------- #

def discover_py_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".py"):
                files.append(Path(dirpath) / name)
    return files


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
        # Collapse internal whitespace so formatting differences don't hide clones.
        norm = re.sub(r"\s+", " ", stripped)
        out.append((i, norm))
    return out


def detect_duplication(root: Path, files: Sequence[Path], window: int = 6,
                       min_chars: int = 120) -> List[Finding]:
    """
    Token-light clone detection. Hash sliding windows of normalized code lines,
    group identical windows occurring in 2+ distinct locations, then merge
    consecutive overlapping windows into clone 'families'.
    """
    # hash -> list of (file_index, start_norm_idx, start_line, end_line, text_len)
    buckets: Dict[str, List[Tuple[int, int, int, int, int]]] = defaultdict(list)
    per_file_lines: List[List[Tuple[int, str]]] = []
    for fi, path in enumerate(files):
        lines = _normalized_code_lines(path)
        per_file_lines.append(lines)
        if len(lines) < window:
            continue
        for start in range(len(lines) - window + 1):
            chunk = lines[start:start + window]
            text = "\n".join(t for _, t in chunk)
            if len(text) < min_chars:
                continue
            h = hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
            buckets[h].append((fi, start, chunk[0][0], chunk[-1][0], len(text)))

    findings: List[Finding] = []
    seen_pairs: Set[Tuple] = set()
    for h, occ in buckets.items():
        if len(occ) < 2:
            continue
        # Require occurrences in genuinely different spots (file or far-apart lines).
        distinct = {(fi, start) for fi, start, *_ in occ}
        if len(distinct) < 2:
            continue
        locations = sorted({(occ_i[0], occ_i[2], occ_i[3]) for occ_i in occ})
        key = tuple(sorted((fi, sl) for fi, sl, _ in locations))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        span = occ[0][3] - occ[0][2] + 1
        loc_strs = [f"{rel(str(files[fi]), root)}:{sl}-{el}" for fi, sl, el in locations]
        primary = locations[0]
        findings.append(Finding(
            tool="duplication", category="duplication",
            severity="warning" if len(locations) >= 3 or span >= window * 2 else "info",
            rule="clone-family",
            message=f"duplicated block (~{span} lines) in {len(locations)} places: "
                    + ", ".join(loc_strs[:4]) + (" ..." if len(loc_strs) > 4 else ""),
            file=rel(str(files[primary[0]]), root), line=primary[1],
            value=float(len(locations)),
        ))
    # Keep only the most substantial families to avoid noise; sort by places then span.
    findings.sort(key=lambda f: (-(f.value or 0), f.file, f.line or 0))
    return _merge_overlapping_clones(findings)


def _merge_overlapping_clones(findings: List[Finding]) -> List[Finding]:
    """Drop clone findings whose primary location is subsumed by a larger family."""
    kept: List[Finding] = []
    occupied: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for f in findings:
        start = f.line or 0
        # crude span recovery from message "~N lines"
        m = re.search(r"~(\d+) lines", f.message)
        span = int(m.group(1)) if m else 1
        end = start + span
        overlap = any(s <= start <= e or s <= end <= e for s, e in occupied[f.file])
        if overlap:
            continue
        occupied[f.file].append((start, end))
        kept.append(f)
    return kept


def _module_name(path: Path, root: Path) -> str:
    relp = os.path.relpath(path, root)
    parts = relp.replace("\\", "/").split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    return ".".join(p for p in parts if p)


def _resolve_relative(current: str, module: Optional[str], level: int) -> Optional[str]:
    if level == 0:
        return module
    base_parts = current.split(".")
    # `from . import x` inside package pkg.sub.mod -> base is pkg.sub
    trim = level
    if len(base_parts) < trim:
        return None
    base = base_parts[:len(base_parts) - trim] if trim <= len(base_parts) else []
    if module:
        base = base + module.split(".")
    return ".".join(base) if base else None


def detect_circular_imports(root: Path, files: Sequence[Path]) -> List[Finding]:
    modules: Dict[str, Path] = {}
    for p in files:
        name = _module_name(p, root)
        if name:
            modules[name] = p
    known: Set[str] = set(modules)

    graph: Dict[str, Set[str]] = defaultdict(set)
    for name, path in modules.items():
        try:
            tree = ast.parse(read_text(path))
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(tree):
            targets: List[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative(name, node.module, node.level or 0)
                if resolved:
                    targets = [resolved] + [f"{resolved}.{a.name}" for a in node.names]
            for t in targets:
                # Map an import to the nearest known module (handles `import pkg.mod`
                # and `from pkg import mod` resolving to pkg.mod or pkg).
                cand = t
                while cand and cand not in known:
                    cand = cand.rpartition(".")[0]
                if cand and cand in known and cand != name:
                    graph[name].add(cand)

    cycles = _tarjan_scc(graph, known)
    findings: List[Finding] = []
    for comp in cycles:
        if len(comp) < 2:
            continue
        members = sorted(comp)
        primary = members[0]
        findings.append(Finding(
            tool="cycles", category="architecture", severity="error",
            rule="circular-import",
            message=f"circular import among {len(members)} modules: " + " -> ".join(members) + f" -> {members[0]}",
            file=rel(str(modules[primary]), root),
            symbol=primary,
        ))
    return findings


def _tarjan_scc(graph: Dict[str, Set[str]], nodes: Set[str]) -> List[Set[str]]:
    index_counter = [0]
    stack: List[str] = []
    lowlink: Dict[str, int] = {}
    index: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    result: List[Set[str]] = []

    import sys as _sys
    _sys.setrecursionlimit(max(10000, _sys.getrecursionlimit()))

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in graph.get(v, ()):  # noqa
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp: Set[str] = set()
            while True:
                w = stack.pop()
                on_stack[w] = False
                comp.add(w)
                if w == v:
                    break
            result.append(comp)

    for v in list(graph.keys()):
        if v not in index:
            strongconnect(v)
    return result


# --------------------------------------------------------------------------- #
# Git integration: changed files + changed lines
# --------------------------------------------------------------------------- #

def git_changed_lines(base: str, root: Path) -> Optional[Dict[str, Set[int]]]:
    """Return {relative_path: {changed line numbers}} for the diff base..worktree."""
    if not shutil.which("git"):
        return None
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", base, "HEAD"], cwd=root,
            capture_output=True, text=True, timeout=30,
        )
        ref = merge_base.stdout.strip() if merge_base.returncode == 0 else base
        diff = subprocess.run(
            ["git", "diff", "--no-color", "--unified=0", ref],
            cwd=root, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if diff.returncode != 0:
        return None
    changed: Dict[str, Set[int]] = defaultdict(set)
    current: Optional[str] = None
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            current = None if path == "/dev/null" else path[2:] if path.startswith("b/") else path
        elif line.startswith("@@") and current:
            m = hunk.match(line)
            if not m:
                continue
            start = int(m.group("start"))
            count = int(m.group("count")) if m.group("count") else 1
            for ln in range(start, start + max(count, 1)):
                changed[current].add(ln)
    return dict(changed)


def mark_changed(findings: List[Finding], changed: Dict[str, Set[int]]) -> List[Finding]:
    """Return a new list with `changed` set on findings touching the diff."""
    changed_files = set(changed)
    out: List[Finding] = []
    for f in findings:
        is_changed = False
        if f.file and f.file in changed_files:
            if f.line is None:
                is_changed = True  # file-level finding on a changed file
            elif f.line in changed[f.file]:
                is_changed = True
        out.append(Finding(**{**asdict(f), "changed": is_changed}))
    return out


# --------------------------------------------------------------------------- #
# Correlation engine: cross-tool insights
# --------------------------------------------------------------------------- #

def build_correlations(findings: Sequence[Finding], metrics: Sequence[Metric]
                       ) -> List[Insight]:
    insights: List[Insight] = []

    file_cov: Dict[str, float] = {}
    for m in metrics:
        if m.tool == "coverage" and m.name == "file-line-coverage" and m.file:
            file_cov[m.file] = m.value
    file_mi: Dict[str, float] = {}
    for m in metrics:
        if m.tool == "radon" and m.name == "maintainability-index" and m.file:
            file_mi[m.file] = m.value

    dead = [f for f in findings if f.category == "dead-code"]
    complex_f = [f for f in findings if f.category == "complexity" and f.rank in {"C", "D", "E", "F"}]

    # 1. High-confidence deletion candidates: dead code in poorly covered files.
    for f in dead:
        cov = file_cov.get(f.file)
        conf_ok = (f.confidence or 0) >= 80
        if cov is not None and cov < 50 and (conf_ok or cov < 10):
            insights.append(Insight(
                kind="deletion-candidate", severity="warning",
                title=f"Likely safe to delete: {f.symbol or f.message}",
                detail=f"{f.message} at {location_str(f)}; file coverage is "
                       f"{cov:.0f}%, so it is unused statically and barely exercised at runtime.",
                file=f.file, line=f.line,
                evidence=[f"vulture: {f.message} ({f.confidence or '?'}% confidence)",
                          f"coverage: {cov:.0f}% of {f.file}"],
            ))

    # 2. Risk hotspots: complex + (undertested or changed).
    for f in complex_f:
        cov = file_cov.get(f.file)
        reasons = [f"radon: {f.message}"]
        risky = False
        if cov is not None and cov < 70:
            reasons.append(f"coverage: only {cov:.0f}% covered")
            risky = True
        if f.changed:
            reasons.append("changed in this diff")
            risky = True
        if risky:
            insights.append(Insight(
                kind="risk-hotspot",
                severity="error" if f.rank in {"E", "F"} or f.changed else "warning",
                title=f"Risk hotspot: {f.symbol or 'block'} in {f.file}",
                detail="High complexity combined with " + " and ".join(reasons[1:]) +
                       " - prioritize tests or a refactor before extending it.",
                file=f.file, line=f.line, evidence=reasons,
            ))

    # 3. Multi-tool worst offenders: files flagged by 3+ distinct tools.
    by_file: Dict[str, Set[str]] = defaultdict(set)
    counts: Counter = Counter()
    for f in findings:
        if f.file:
            by_file[f.file].add(f.tool)
            counts[f.file] += 1
    for fname, tools in by_file.items():
        if len(tools) >= 3:
            insights.append(Insight(
                kind="worst-offender", severity="warning",
                title=f"Concentrated problems: {fname}",
                detail=f"{counts[fname]} findings from {len(tools)} tools "
                       f"({', '.join(sorted(tools))}). A focused cleanup here clears the most signal.",
                file=fname,
                evidence=[f"{counts[fname]} findings across {', '.join(sorted(tools))}"],
            ))

    # 4. Architecture: surface every circular import as an insight (high value).
    for f in findings:
        if f.rule == "circular-import":
            insights.append(Insight(
                kind="circular-import", severity="error",
                title="Circular import", detail=f.message,
                file=f.file, evidence=[f.message],
            ))

    order = {"error": 0, "warning": 1, "info": 2}
    insights.sort(key=lambda i: (order.get(i.severity, 3), i.kind, i.file))
    return insights


# --------------------------------------------------------------------------- #
# Health score
# --------------------------------------------------------------------------- #

def compute_health(findings: Sequence[Finding], metrics: Sequence[Metric],
                   loc: int) -> Dict[str, Any]:
    """A transparent 0-100 health score from coverage, complexity, MI, density."""
    sub: Dict[str, Optional[float]] = {}

    cov = next((m.value for m in metrics
                if m.tool == "coverage" and m.name == "total-line-coverage"), None)
    sub["coverage"] = cov  # already 0-100

    mis = [m.value for m in metrics if m.name == "maintainability-index"]
    sub["maintainability"] = (sum(mis) / len(mis)) if mis else None  # radon MI is 0-100

    flagged_cc = sum(1 for f in findings if f.rule == "cyclomatic-complexity")
    total_cc = next((m.value for m in metrics
                     if m.tool == "radon" and m.name == "complexity-functions"), None)
    if total_cc and total_cc > 0:
        sub["complexity"] = max(0.0, 100.0 * (1.0 - flagged_cc / total_cc))
    else:
        sub["complexity"] = None

    kloc = max(loc / 1000.0, 0.001)
    err = sum(1 for f in findings if f.severity == "error")
    warn = sum(1 for f in findings if f.severity == "warning")
    weighted = err * 3 + warn  # weighted defect density per KLOC
    density = weighted / kloc
    sub["cleanliness"] = max(0.0, 100.0 - min(density * 2.0, 100.0))

    weights = {"coverage": 0.30, "maintainability": 0.25,
               "complexity": 0.20, "cleanliness": 0.25}
    num = den = 0.0
    for key, w in weights.items():
        val = sub.get(key)
        if val is not None:
            num += val * w
            den += w
    score = round(num / den, 1) if den else None

    def grade(s: Optional[float]) -> str:
        if s is None:
            return "n/a"
        for cutoff, g in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
            if s >= cutoff:
                return g
        return "F"

    return {
        "score": score,
        "grade": grade(score),
        "components": {k: (round(v, 1) if v is not None else None) for k, v in sub.items()},
        "loc": loc,
    }


# --------------------------------------------------------------------------- #
# Verdict (for audit / fail-on)
# --------------------------------------------------------------------------- #

def compute_verdict(findings: Sequence[Finding], scoped_to_changes: bool,
                    gate: str) -> Dict[str, Any]:
    """Verdict: pass | warn | fail.

    In change scope, the hard-fail trigger is a *newly introduced* line-level
    error (a type error, syntax error, or over-threshold complexity on a changed
    line). Pre-existing file-level issues in a touched file (a circular import,
    low coverage) are surfaced and downgraded to a warning unless gate == 'all',
    so a routine edit does not fail on inherited debt.
    """
    if not scoped_to_changes:
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        verdict = "fail" if errors else ("warn" if warnings else "pass")
        return {"verdict": verdict, "scoped_to_changes": False,
                "new_errors": errors, "changed_warnings": warnings,
                "touched_errors": 0, "inherited_errors": 0, "inherited_total": 0}

    changed = [f for f in findings if f.changed]
    inherited = [f for f in findings if not f.changed]
    new_errors = sum(1 for f in changed if f.severity == "error" and f.line is not None)
    touched_errors = sum(1 for f in changed if f.severity == "error" and f.line is None)
    changed_warnings = sum(1 for f in changed if f.severity == "warning")
    inherited_errors = sum(1 for f in inherited if f.severity == "error")

    if new_errors:
        verdict = "fail"
    elif gate == "all" and (inherited_errors or touched_errors):
        verdict = "fail"
    elif changed or touched_errors:
        verdict = "warn"
    else:
        verdict = "pass"
    return {
        "verdict": verdict,
        "scoped_to_changes": True,
        "new_errors": new_errors,
        "changed_warnings": changed_warnings,
        "touched_errors": touched_errors,
        "inherited_errors": inherited_errors,
        "inherited_total": len(inherited),
    }


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #

def summarize(findings: Sequence[Finding], metrics: Sequence[Metric],
              runs: Sequence[ToolRun], health: Dict[str, Any]) -> Dict[str, Any]:
    by_severity = Counter(f.severity for f in findings)
    by_tool = Counter(f.tool for f in findings)
    by_category = Counter(f.category for f in findings)
    by_file: Counter = Counter(f.file for f in findings if f.file)
    max_sev = "none"
    if findings:
        max_sev = max((f.severity for f in findings),
                      key=lambda s: SEVERITY_ORDER.get(s, 0))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_version": TOOL_VERSION,
        "health": health,
        "finding_count": len(findings),
        "changed_findings": sum(1 for f in findings if f.changed),
        "metric_count": len(metrics),
        "max_severity": max_sev,
        "by_severity": {s: by_severity.get(s, 0) for s in ("error", "warning", "info")},
        "by_tool": dict(sorted(by_tool.items())),
        "by_category": dict(sorted(by_category.items())),
        "top_files": by_file.most_common(10),
        "tool_runs": [asdict(r) for r in runs],
    }


# --------------------------------------------------------------------------- #
# Reporters
# --------------------------------------------------------------------------- #

class Palette:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _w(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def red(self, t): return self._w("31", t)
    def yellow(self, t): return self._w("33", t)
    def green(self, t): return self._w("32", t)
    def blue(self, t): return self._w("36", t)
    def bold(self, t): return self._w("1", t)
    def dim(self, t): return self._w("2", t)


SEV_MARK = {"error": "x", "warning": "!", "info": "-"}


def render_human(report: Dict[str, Any], palette: Palette, scope_label: str) -> str:
    s = report["summary"]
    health = s["health"]
    lines: List[str] = []
    p = palette

    lines.append(p.bold("fallow4python - python codebase intelligence"))
    if scope_label:
        lines.append(p.dim(scope_label))
    lines.append("")

    # Health banner
    grade = health.get("grade", "n/a")
    score = health.get("score")
    grade_c = (p.green if grade in ("A", "B") else p.yellow if grade in ("C", "D") else p.red)(
        f"{grade}")
    score_s = f"{score}" if score is not None else "n/a"
    lines.append(f"  Health: {grade_c}  ({score_s}/100)   "
                 + p.dim(f"{s['finding_count']} findings, {health.get('loc', 0)} LOC"))
    comp = health.get("components", {})
    parts = [f"{k} {v:.0f}" for k, v in comp.items() if v is not None]
    if parts:
        lines.append(p.dim("          " + " | ".join(parts)))
    lines.append("")

    # Category breakdown, Fallow-style sections.
    section_titles = [
        ("dead-code", "Dead code"),
        ("duplication", "Duplication"),
        ("complexity", "Complexity"),
        ("maintainability", "Maintainability"),
        ("dependencies", "Dependencies"),
        ("architecture", "Architecture"),
        ("typing", "Typing"),
        ("lint", "Lint"),
        ("coverage", "Coverage"),
    ]
    by_cat = s["by_category"]
    cat_sev: Dict[str, str] = {}
    for f in report["_findings"]:
        cur = cat_sev.get(f.category)
        if cur is None or SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[cur]:
            cat_sev[f.category] = f.severity
    for cat, title in section_titles:
        n = by_cat.get(cat, 0)
        if not n:
            continue
        mark = SEV_MARK.get(cat_sev.get(cat, "info"), "-")
        colorize = (p.red if mark == "x" else p.yellow if mark == "!" else p.dim)
        lines.append(f"  {colorize(mark)} {title:<16} {n}")
    lines.append("")

    # Insights - the differentiator.
    insights = report["insights"]
    if insights:
        lines.append(p.bold("  Insights"))
        for ins in insights[:12]:
            mk = SEV_MARK.get(ins.severity, "-")
            c = (p.red if mk == "x" else p.yellow if mk == "!" else p.blue)
            loc = f" ({ins.file}{':' + str(ins.line) if ins.line else ''})" if ins.file else ""
            lines.append(f"  {c(mk)} {ins.title}{p.dim(loc)}")
            lines.append(p.dim(f"      {compact(ins.detail, 150)}"))
        if len(insights) > 12:
            lines.append(p.dim(f"      ... {len(insights) - 12} more insights (see --json-out)"))
        lines.append("")

    # Top files
    if s["top_files"]:
        lines.append(p.bold("  Hotspot files"))
        for fname, count in s["top_files"][:6]:
            lines.append(f"    {count:>3}  {fname}")
        lines.append("")

    # Verdict (audit) or fail-on note
    verdict = report.get("verdict")
    if verdict:
        v = verdict["verdict"]
        vc = (p.green if v == "pass" else p.yellow if v == "warn" else p.red)
        if verdict.get("scoped_to_changes"):
            detail = (f"{verdict['new_errors']} new error(s), "
                      f"{verdict['changed_warnings']} warning(s) on changed lines; "
                      f"{verdict['touched_errors']} touched + "
                      f"{verdict['inherited_errors']} inherited error(s)")
        else:
            detail = (f"{verdict['new_errors']} error(s), "
                      f"{verdict['changed_warnings']} warning(s)")
        lines.append(f"  Verdict: {vc(v.upper())}   " + p.dim(detail))
        lines.append("")

    # Tool provenance
    runs = s["tool_runs"]
    ran = [r for r in runs if r["status"] in ("ran", "ingested")]
    skipped = [r for r in runs if r["status"] == "skipped"]
    errored = [r for r in runs if r["status"] == "error"]
    prov = []
    if ran:
        prov.append("used: " + ", ".join(r["name"] for r in ran))
    if skipped:
        prov.append("skipped: " + ", ".join(r["name"] for r in skipped))
    if errored:
        prov.append("errored: " + ", ".join(r["name"] for r in errored))
    for line in prov:
        lines.append(p.dim("  " + line))
    return "\n".join(lines).rstrip() + "\n"


# Self-documenting prose placed under each report heading. Written so a reader
# (human or LLM) with zero prior context can interpret every number and act on
# it. Each entry explains what the section measures AND what it implies.
MD_EXPLAIN: Dict[str, str] = {
    "intro": (
        "This report is produced by **fallow4python**, a static-analysis aggregator for "
        "Python. It runs several independent quality tools, normalizes their "
        "output into one schema, and correlates the signals. Everything below is "
        "derived from static analysis of the source (plus test-coverage data only "
        "if it was supplied); no code is executed beyond an existing test suite. "
        "**Higher scores are always better, and `error` is more severe than "
        "`warning`, which is more severe than `info`.** Read the sections top to "
        "bottom: Health is the verdict, Insights are the prioritized to-do list, "
        "and Findings/Metrics are the supporting evidence."
    ),
    "health": (
        "A single 0–100 score for overall code health, plus a letter grade. "
        "**Higher is better.** Grade bands: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, "
        "F < 60. The score is a weighted average of up to four components, each "
        "independently scaled 0–100:\n"
        "\n"
        "- **coverage** (weight 0.30): percent of code lines exercised by the "
        "test suite. Shown only when coverage data is provided; otherwise `n/a`.\n"
        "- **maintainability** (weight 0.25): mean of radon's Maintainability "
        "Index across files — a blend of code volume, complexity, and length. "
        "Higher means easier to change safely.\n"
        "- **complexity** (weight 0.20): the percent of functions that are *not* "
        "flagged as overly complex. 100 means no function exceeds the "
        "cyclomatic-complexity threshold.\n"
        "- **cleanliness** (weight 0.25): the inverse of defect density. Computed "
        "from errors and warnings per 1,000 lines of code, with errors counted "
        "3× as heavily as warnings.\n"
        "\n"
        "Any component that is `n/a` is dropped and the remaining weights are "
        "renormalized, so the final score is always out of 100. **Implication:** "
        "the letter grade is a starting point, not the whole story — look at "
        "*which* component is low. A `0.0` cleanliness alongside otherwise decent "
        "components means a high *count* of lint/type findings relative to the "
        "codebase size, not necessarily deep structural rot; it floors at 0 once "
        "defect density is high enough."
    ),
    "verdict": (
        "A PASS / WARN / FAIL gate that judges a specific code change (a git "
        "diff), not the whole repository. **FAIL**: the change introduced new "
        "error-level problems on the exact lines it modified. **WARN**: the "
        "change touched files that already had issues but added no new errors of "
        "its own. **PASS**: neither. **Implication:** this is meant as a "
        "merge/CI gate. Pre-existing ('inherited') problems do not by themselves "
        "block a change — only newly introduced ones do — so a PASS does not mean "
        "the file is clean, only that the change did not make it worse."
    ),
    "insights": (
        "Cross-tool correlations rather than raw output — fallow4python's highest-value "
        "section. Each insight combines signals from multiple tools to point at a "
        "concrete action. Types you may see: **Concentrated problems** (one file "
        "is flagged by several different tools, so fixing it clears the most "
        "signal at once); **Likely safe to delete** (a symbol is both statically "
        "unused and barely covered at runtime); **Risk hotspot** (high complexity "
        "combined with low test coverage); **Circular import** (a dependency "
        "cycle between modules). **Implication:** start your work here. These are "
        "already prioritized; the Findings table below is the underlying evidence "
        "for them."
    ),
    "summary": (
        "Counts of every raw finding, broken down two ways. **By severity:** "
        "`error` = likely a real defect or type error that should be fixed; "
        "`warning` = a probable issue worth reviewing; `info` = low-confidence or "
        "stylistic. **By category:** the *kind* of problem — e.g. `typing`, "
        "`lint`, `dead-code`, `complexity`, `dependencies`, `duplication`. The "
        "**Hotspot files** table ranks files by total finding count. "
        "**Implication:** severity tells you urgency, category tells you what kind "
        "of work is required, and hotspots tell you where to spend effort first."
    ),
    "metrics": (
        "Raw measured values, as distinct from findings. These are the numbers "
        "the Health components are computed from, so you can verify or drill into "
        "the score. For radon ranks, **A is best and F is worst**. "
        "`maintainability-index` runs 0–100 (higher = more maintainable). "
        "`complexity-functions` is the total number of functions analyzed. "
        "**Implication:** if one file shows a poor metric, it usually explains a "
        "large share of the health deductions above."
    ),
    "findings": (
        "Every individual issue, grouped by category — the evidence layer. Each "
        "row is one problem reported by one tool. Columns: **Sev** = severity; "
        "**Changed** = `yes` if the issue sits on a line modified by the audited "
        "change (blank otherwise); **Location** = file:line; **Tool** = which "
        "analyzer reported it; **Rule** = the specific check that fired; "
        "**Message** = what is wrong. **Implication:** every count in Summary and "
        "every Insight traces back to rows here. A practical fix order is: "
        "highest severity first, within the files named as hotspots."
    ),
    "toolruns": (
        "Provenance — which analyzers actually ran, succeeded, failed, or were "
        "skipped, and how many findings each produced. **Implication:** this "
        "defines the report's coverage. A *skipped* tool means that dimension was "
        "**not assessed**: e.g. if coverage was skipped, the coverage component is "
        "`n/a` and there is no runtime evidence behind dead-code findings. Absence "
        "of findings from a tool that did not run is not evidence that no problems "
        "exist there."
    ),
}


def _md_explain(L: List[str], key: str) -> None:
    """Append the explanation for a section as a Markdown blockquote."""
    text = MD_EXPLAIN.get(key)
    if not text:
        return
    for line in text.split("\n"):
        L.append(f"> {line}" if line else ">")
    L.append("")


def render_markdown(report: Dict[str, Any], scope_label: str) -> str:
    s = report["summary"]
    health = s["health"]
    findings: List[Finding] = report["_findings"]
    metrics: List[Metric] = report["_metrics"]
    insights: List[Insight] = report["insights"]
    L: List[str] = []

    L.append("# Python Codebase Intelligence Report")
    L.append("")
    L.append(f"Generated: `{s['generated_at']}` · fallow4python v{TOOL_VERSION}")
    if scope_label:
        L.append(f"\n> {scope_label}")
    L.append("")
    _md_explain(L, "intro")

    # Health
    L.append("## Health")
    L.append("")
    _md_explain(L, "health")
    score = health.get("score")
    L.append(f"**Grade {health.get('grade', 'n/a')}** "
             f"({score if score is not None else 'n/a'} / 100) · "
             f"{health.get('loc', 0)} lines of code · {s['finding_count']} findings")
    L.append("")
    L.append("| Component | Score |")
    L.append("|---|---:|")
    for k, v in health.get("components", {}).items():
        L.append(f"| {k} | {v if v is not None else 'n/a'} |")
    L.append("")

    verdict = report.get("verdict")
    if verdict:
        L.append("## Verdict")
        L.append("")
        _md_explain(L, "verdict")
        if verdict.get("scoped_to_changes"):
            L.append(f"**{verdict['verdict'].upper()}** — "
                     f"{verdict['new_errors']} newly introduced error(s) and "
                     f"{verdict['changed_warnings']} warning(s) on changed lines; "
                     f"{verdict['touched_errors']} file-level error(s) in touched files, "
                     f"{verdict['inherited_errors']} inherited error(s) "
                     f"({verdict['inherited_total']} inherited findings total).")
        else:
            L.append(f"**{verdict['verdict'].upper()}** — "
                     f"{verdict['new_errors']} error(s) and "
                     f"{verdict['changed_warnings']} warning(s).")
        L.append("")

    # Insights
    L.append("## Insights")
    L.append("")
    _md_explain(L, "insights")
    if not insights:
        L.append("No correlated insights.")
    else:
        for ins in insights:
            loc = f" — `{ins.file}{':' + str(ins.line) if ins.line else ''}`" if ins.file else ""
            L.append(f"- **[{ins.severity}] {md_escape(ins.title)}**{loc}  ")
            L.append(f"  {md_escape(ins.detail)}")
    L.append("")

    # Summary tables
    L.append("## Summary")
    L.append("")
    _md_explain(L, "summary")
    L.append("| Severity | Count |")
    L.append("|---|---:|")
    for sev in ("error", "warning", "info"):
        L.append(f"| {sev} | {s['by_severity'].get(sev, 0)} |")
    L.append("")
    L.append("| Category | Count |")
    L.append("|---|---:|")
    for cat, n in sorted(s["by_category"].items()):
        L.append(f"| {cat} | {n} |")
    L.append("")
    if s["top_files"]:
        L.append("### Hotspot files")
        L.append("")
        L.append("| File | Findings |")
        L.append("|---|---:|")
        for fname, n in s["top_files"]:
            L.append(f"| `{md_escape(fname)}` | {n} |")
        L.append("")

    # Metrics
    if metrics:
        L.append("## Metrics")
        L.append("")
        _md_explain(L, "metrics")
        L.append("| Tool | Metric | File | Value | Rank |")
        L.append("|---|---|---|---:|:--:|")
        for m in sorted(metrics, key=lambda m: (m.tool, m.name, m.file)):
            val = f"{m.value:.2f}{m.unit}"
            L.append(f"| {md_escape(m.tool)} | {md_escape(m.name)} | "
                     f"`{md_escape(m.file)}` | {md_escape(val)} | {md_escape(m.rank)} |")
        L.append("")

    # Detailed findings grouped by category
    L.append("## Findings")
    L.append("")
    _md_explain(L, "findings")
    grouped: Dict[str, List[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.category].append(f)
    if not grouped:
        L.append("No findings. 🎉")
    for cat in sorted(grouped):
        items = grouped[cat]
        L.append(f"### {cat} ({len(items)})")
        L.append("")
        L.append("| Sev | Changed | Location | Tool | Rule | Message |")
        L.append("|---|:--:|---|---|---|---|")
        for f in items[: report["_max_per_section"]]:
            L.append("| {} | {} | `{}` | {} | {} | {} |".format(
                f.severity, "yes" if f.changed else "",
                md_escape(location_str(f)), md_escape(f.tool),
                md_escape(f.rule), md_escape(compact(f.message))))
        if len(items) > report["_max_per_section"]:
            L.append(f"| info | | - | - | truncated | "
                     f"{len(items) - report['_max_per_section']} more omitted |")
        L.append("")

    # Provenance
    L.append("## Tool runs")
    L.append("")
    _md_explain(L, "toolruns")
    L.append("| Tool | Status | Findings | Detail |")
    L.append("|---|---|---:|---|")
    for r in s["tool_runs"]:
        L.append(f"| {md_escape(r['name'])} | {r['status']} | {r['findings']} | "
                 f"{md_escape(r['detail'])} |")
    L.append("")
    return "\n".join(L).rstrip() + "\n"


def build_json_envelope(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": report["summary"],
        "verdict": report.get("verdict"),
        "insights": [asdict(i) for i in report["insights"]],
        "metrics": [asdict(m) for m in report["_metrics"]],
        "findings": [asdict(f) for f in report["_findings"]],
    }


SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}


def build_sarif(report: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Finding] = report["_findings"]
    rules: Dict[str, Dict[str, Any]] = {}
    results: List[Dict[str, Any]] = []
    for f in findings:
        rule_id = f"{f.tool}/{f.rule or f.category}"
        rules.setdefault(rule_id, {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": f"{f.tool} {f.category}"},
            "properties": {"category": f.category, "tool": f.tool},
        })
        result: Dict[str, Any] = {
            "ruleId": rule_id,
            "level": SARIF_LEVEL.get(f.severity, "note"),
            "message": {"text": f.message},
            "properties": {"changed": f.changed, "rank": f.rank,
                           "confidence": f.confidence},
        }
        if f.file:
            region: Dict[str, Any] = {}
            if f.line is not None:
                region["startLine"] = f.line
            if f.column is not None:
                region["startColumn"] = f.column
            loc: Dict[str, Any] = {"physicalLocation": {
                "artifactLocation": {"uri": f.file}}}
            if region:
                loc["physicalLocation"]["region"] = region
            result["locations"] = [loc]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "fallow4python",
                "version": TOOL_VERSION,
                "informationUri": "https://example.invalid/fallow4python",
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }


# --------------------------------------------------------------------------- #
# Orchestration: run installed tools or ingest saved outputs
# --------------------------------------------------------------------------- #

@dataclass
class ToolSpec:
    name: str
    executable: str
    argv: Callable[[Path], List[str]]
    parser: Callable[[str, Path], Tuple[List[Finding], List[Metric]]]
    needs_config: bool = False        # e.g. import-linter
    output_to_file: Optional[str] = None  # flag token for tools that write a file
    ingest_only: bool = False         # e.g. coverage


def _run_subprocess(argv: List[str], root: Path, timeout: int) -> Tuple[int, str, str]:
    proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.returncode and proc.stderr or proc.stderr


# --------------------------------------------------------------------------- #
# Live animated progress (stdlib-only, rendered to stderr, TTY-aware)
# --------------------------------------------------------------------------- #

# 256-color (8-bit) palette. We deliberately avoid 24-bit truecolor because
# common terminals (e.g. macOS Terminal.app) don't support it and mangle the
# escapes into the wrong hue. 256-color is supported essentially everywhere.
#
# Scheme: a turquoise ramp (light -> deep) as the primary color, with gold as
# the single accent (the active spinner and the highlight sweeping the bar).
_TURQ = [159, 122, 80, 44, 37, 30]   # pale aqua -> deep teal
_GOLD = 220                          # accent: active / sweep
_GOLD_HI = 214                       # accent, stronger (errors)
_DIM = 66                            # muted teal-grey for idle / skipped
_SPINNER = "⣾⣽⣻⢿⡿⣟⣯⣷"
_BAR_FULL = "▰"
_BAR_EMPTY = "▱"


def _c(code: int, text: str) -> str:
    return f"\033[38;5;{code}m{text}\033[0m"


def _wordmark(text: str, phase: float, final: bool) -> str:
    """Turquoise wordmark with a single gold cell shimmering across it."""
    n = len(_TURQ)
    hi = -1 if final else int(phase * len(text)) % max(len(text), 1)
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
            continue
        if i == hi:
            out.append(_c(_GOLD, ch))
        else:
            out.append(_c(_TURQ[int(i / max(len(text) - 1, 1) * (n - 1))], ch))
    return "".join(out)


class LiveProgress:
    """A live, colored, animated checklist of analyzer steps.

    No-op unless ``enabled``. All output goes to stderr so it never corrupts a
    report written to stdout. A daemon thread animates the spinner / gradient
    while the main thread blocks on each analyzer subprocess.
    """

    # Glyph + 256-color code per state. Turquoise for resolved/idle, gold for
    # the active spinner and (a stronger gold) for errors so they stand out.
    _STATE_ICON = {
        "pending": ("◌", _DIM),
        "running": (None, None),       # animated gold spinner
        "done":    ("●", 44),
        "ingested":("●", 44),
        "ran":     ("●", 44),
        "skipped": ("○", _DIM),
        "error":   ("▲", _GOLD_HI),
    }

    def __init__(self, steps: Sequence[str], enabled: bool):
        self.enabled = enabled and sys.stderr.isatty()
        self.order: List[str] = list(steps)
        self.state: Dict[str, str] = {s: "pending" for s in self.order}
        self.detail: Dict[str, str] = {s: "" for s in self.order}
        self._active: Optional[str] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_ts = 0.0
        self._lines = 0
        self._tick = 0

    # -- lifecycle ---------------------------------------------------------- #
    def __enter__(self) -> "LiveProgress":
        if not self.enabled:
            return self
        self._start_ts = time.monotonic()
        sys.stderr.write("\033[?25l")  # hide cursor
        sys.stderr.flush()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread:
            self._thread.join()
        with self._lock:
            self._render(final=True)
        sys.stderr.write("\033[?25h\n")  # show cursor + spacer
        sys.stderr.flush()

    # -- state updates ------------------------------------------------------ #
    def start(self, step: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            if step in self.state:
                self.state[step] = "running"
                self._active = step

    def finish(self, step: str, status: str, count: Optional[int] = None,
               note: str = "") -> None:
        if not self.enabled:
            return
        with self._lock:
            if step in self.state:
                self.state[step] = status
                if count is not None and status in ("done", "ran", "ingested"):
                    self.detail[step] = f"{count} finding{'s' if count != 1 else ''}"
                elif note:
                    self.detail[step] = note
            if self._active == step:
                self._active = None

    # -- rendering ---------------------------------------------------------- #
    def _loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                self._render()
            self._tick += 1
            time.sleep(0.08)

    def _render(self, final: bool = False) -> None:
        frame = _SPINNER[self._tick % len(_SPINNER)]
        phase = (self._tick % 48) / 48.0
        done = sum(1 for s in self.order
                   if self.state[s] not in ("pending", "running"))
        total = len(self.order)
        elapsed = time.monotonic() - self._start_ts

        rows: List[str] = []

        # Header: a leading pip, a shimmering wordmark, a status verb + clock.
        pip = _c(44, "●") if final else _c(_GOLD, frame)
        title = _wordmark("fallow4python", phase, final)
        verb = "complete" if final else "scanning"
        rows.append(f"  {pip}  {title}   \033[2m{verb}\033[0m"
                    f"   \033[2m{elapsed:5.1f}s\033[0m")

        # Progress bar on its own line: turquoise fill (light->deep), a gold
        # highlight sweeping the filled segment, muted empties.
        width = 18
        filled = int(round(width * done / max(total, 1)))
        comet = self._tick % width
        cells = []
        for i in range(width):
            if i < filled:
                tone = _TURQ[min(int(i / max(filled, 1) * len(_TURQ)),
                                 len(_TURQ) - 1)]
                if i == comet and not final:
                    cells.append(_c(_GOLD, _BAR_FULL))
                else:
                    cells.append(_c(tone, _BAR_FULL))
            else:
                cells.append(_c(_DIM, _BAR_EMPTY))
        rows.append(f"     {''.join(cells)}  \033[2m{done} / {total}\033[0m")
        rows.append("")

        # Per-step checklist.
        for step in self.order:
            st = self.state[step]
            if st == "running":
                icon = _c(_GOLD, frame)
                name = _c(_TURQ[2], f"{step:<15}")
                tail = "\033[2m…\033[0m"
            else:
                glyph, code = self._STATE_ICON.get(st, ("◌", _DIM))
                icon = _c(code, glyph or "◌")
                if st == "pending":
                    name = _c(_DIM, f"{step:<15}")
                    tail = ""
                else:
                    name = _c(code, f"{step:<15}")
                    tail = f"\033[2m{self.detail.get(step) or st}\033[0m"
            rows.append(f"     {icon} {name} {tail}")

        # Move cursor to the top of the previously-drawn block, clear, redraw.
        buf: List[str] = []
        if self._lines:
            buf.append(f"\033[{self._lines}A")
        for row in rows:
            buf.append("\033[2K" + row + "\n")
        sys.stderr.write("".join(buf))
        sys.stderr.flush()
        self._lines = len(rows)


def orchestrate(root: Path, target: Path, opts: "Options"
                ) -> Tuple[List[Finding], List[Metric], List[ToolRun]]:
    findings: List[Finding] = []
    metrics: List[Metric] = []
    runs: List[ToolRun] = []

    min_rank = opts.radon_min_rank
    cov_min = opts.coverage_min

    specs: List[ToolSpec] = [
        ToolSpec("ruff", "ruff",
                 lambda t: ["ruff", "check", "--output-format=json", str(t)],
                 parse_ruff),
        ToolSpec("mypy", "mypy",
                 lambda t: ["mypy", "--no-error-summary", "--show-column-numbers",
                            "--no-color-output", "--hide-error-context", str(t)],
                 parse_mypy),
        ToolSpec("vulture", "vulture",
                 lambda t: ["vulture", str(t)], parse_vulture),
        ToolSpec("radon-cc", "radon",
                 lambda t: ["radon", "cc", "-j", str(t)],
                 lambda text, r: parse_radon_cc(text, r, min_rank)),
        ToolSpec("radon-mi", "radon",
                 lambda t: ["radon", "mi", "-j", str(t)],
                 lambda text, r: parse_radon_mi(text, r, min_rank)),
        ToolSpec("deptry", "deptry",
                 lambda t: ["deptry", str(t), "--json-output", "{OUTFILE}"],
                 parse_deptry, output_to_file="deptry"),
        ToolSpec("xenon", "xenon",
                 lambda t: ["xenon", "--max-absolute", "B", "--max-modules", "A",
                            "--max-average", "A", str(t)],
                 parse_xenon),
        ToolSpec("import-linter", "lint-imports",
                 lambda t: ["lint-imports"], parse_import_linter, needs_config=True),
    ]

    selected = opts.tools

    # The full ordered set of steps, so the live display can show what's coming.
    planned = [s.name for s in specs if not selected or s.name in selected]
    for builtin in ("coverage", "duplication", "cycles"):
        if not selected or builtin in selected:
            planned.append(builtin)

    with LiveProgress(planned, enabled=not opts.no_color) as prog:
        for spec in specs:
            if selected and spec.name not in selected:
                continue
            prog.start(spec.name)
            # Ingest mode: read a saved file if present in from_dir.
            ingested = _try_ingest(spec, root, opts)
            if ingested is not None:
                fs, ms, run = ingested
                findings += fs
                metrics += ms
                runs.append(run)
                prog.finish(spec.name, run.status, run.findings, note=run.detail)
                continue
            if opts.no_run:
                run = ToolRun(spec.name, "skipped", "no-run mode and no saved output")
            elif not shutil.which(spec.executable):
                run = ToolRun(spec.name, "skipped", f"{spec.executable} not installed")
            elif spec.needs_config and not _import_linter_configured(root):
                run = ToolRun(spec.name, "skipped", "no import-linter config found")
            else:
                run = _run_tool(spec, root, target, opts, findings, metrics)
            runs.append(run)
            prog.finish(spec.name, run.status, run.findings, note=run.detail)

        # Coverage is ingest-only (it needs a test run to produce data).
        if (not selected or "coverage" in selected) and opts.coverage_path:
            prog.start("coverage")
            cov_path = Path(opts.coverage_path)
            if cov_path.is_file():
                try:
                    fs, ms = parse_coverage(read_text(cov_path), root, cov_min)
                    findings += fs
                    metrics += ms
                    run = ToolRun("coverage", "ingested", str(cov_path), len(fs))
                except Exception as exc:  # noqa: BLE001
                    run = ToolRun("coverage", "error", str(exc))
            else:
                run = ToolRun("coverage", "skipped", f"file not found: {cov_path}")
            runs.append(run)
            prog.finish("coverage", run.status, run.findings, note=run.detail)
        elif not opts.coverage_path and (not selected or "coverage" in selected):
            prog.start("coverage")
            run = ToolRun("coverage", "skipped", "no --coverage json provided")
            runs.append(run)
            prog.finish("coverage", run.status, note=run.detail)

        # Built-in analyzers (no external dependency).
        if not selected or "duplication" in selected:
            prog.start("duplication")
            try:
                files = discover_py_files(target if target.is_dir() else target.parent)
                dups = detect_duplication(root, files)
                findings += dups
                run = ToolRun("duplication", "ran", "built-in clone detector", len(dups))
            except Exception as exc:  # noqa: BLE001
                run = ToolRun("duplication", "error", str(exc))
            runs.append(run)
            prog.finish("duplication", run.status, run.findings, note=run.detail)
        if not selected or "cycles" in selected:
            prog.start("cycles")
            try:
                files = discover_py_files(target if target.is_dir() else target.parent)
                cyc = detect_circular_imports(root, files)
                findings += cyc
                run = ToolRun("cycles", "ran", "built-in import-graph cycles", len(cyc))
            except Exception as exc:  # noqa: BLE001
                run = ToolRun("cycles", "error", str(exc))
            runs.append(run)
            prog.finish("cycles", run.status, run.findings, note=run.detail)

    return findings, metrics, runs


def _run_tool(spec: ToolSpec, root: Path, target: Path, opts: "Options",
              findings: List[Finding], metrics: List[Metric]) -> ToolRun:
    start = datetime.now()
    tmp_out: Optional[Path] = None
    try:
        argv = spec.argv(target)
        if spec.output_to_file:
            tmp = tempfile.NamedTemporaryFile(
                prefix="fallow4python-", suffix=".json", delete=False)
            tmp.close()
            tmp_out = Path(tmp.name)
            argv = [a.replace("{OUTFILE}", str(tmp_out)) for a in argv]
        proc = subprocess.run(argv, cwd=root, capture_output=True,
                              text=True, timeout=opts.timeout)
        text = read_text(tmp_out) if (tmp_out and tmp_out.exists() and tmp_out.stat().st_size) \
            else proc.stdout
        if not text.strip() and proc.stdout.strip():
            text = proc.stdout
        fs, ms = spec.parser(text, root)
        findings += fs
        metrics += ms
        dur = int((datetime.now() - start).total_seconds() * 1000)
        return ToolRun(spec.name, "ran", "", len(fs), dur)
    except subprocess.TimeoutExpired:
        return ToolRun(spec.name, "error", f"timed out after {opts.timeout}s")
    except Exception as exc:  # noqa: BLE001
        return ToolRun(spec.name, "error", str(exc))
    finally:
        if tmp_out and tmp_out.exists():
            try:
                tmp_out.unlink()
            except OSError:
                pass


# Map tool name -> candidate filenames when ingesting a saved directory.
INGEST_FILENAMES = {
    "ruff": ["ruff.json", "ruff.txt"],
    "mypy": ["mypy.json", "mypy.txt"],
    "vulture": ["vulture.txt"],
    "radon-cc": ["radon_cc.json", "radon-cc.json"],
    "radon-mi": ["radon_mi.json", "radon-mi.json"],
    "deptry": ["deptry.json", "deptry.txt"],
    "xenon": ["xenon.txt"],
    "import-linter": ["import_linter.txt", "import-linter.txt"],
}


def _try_ingest(spec: ToolSpec, root: Path, opts: "Options"
                ) -> Optional[Tuple[List[Finding], List[Metric], ToolRun]]:
    # Explicit per-tool path overrides take priority.
    explicit = opts.explicit_inputs.get(spec.name)
    candidates: List[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if opts.from_dir:
        for fn in INGEST_FILENAMES.get(spec.name, []):
            candidates.append(Path(opts.from_dir) / fn)
    for path in candidates:
        if path.is_file():
            try:
                fs, ms = spec.parser(read_text(path), root)
                return fs, ms, ToolRun(spec.name, "ingested", str(path), len(fs))
            except Exception as exc:  # noqa: BLE001
                return [], [], ToolRun(spec.name, "error", f"{path}: {exc}")
    return None


def _import_linter_configured(root: Path) -> bool:
    for name in ("setup.cfg", "pyproject.toml", ".importlinter", "importlinter.ini"):
        p = root / name
        if p.is_file() and "importlinter" in read_text(p).replace("-", "").lower():
            return True
    return (root / ".importlinter").is_file()


def count_loc(target: Path) -> int:
    base = target if target.is_dir() else target.parent
    total = 0
    for path in discover_py_files(base):
        try:
            total += sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return total


# --------------------------------------------------------------------------- #
# Options + CLI
# --------------------------------------------------------------------------- #

@dataclass
class Options:
    command: str
    target: str
    base: Optional[str]
    tools: Optional[Set[str]]
    from_dir: Optional[str]
    explicit_inputs: Dict[str, str]
    coverage_path: Optional[str]
    coverage_min: float
    radon_min_rank: str
    fail_on: str
    gate: str
    fmt: str
    json_out: Optional[str]
    markdown_out: Optional[str]
    sarif_out: Optional[str]
    max_per_section: int
    no_run: bool
    no_color: bool
    timeout: int


# Preset tool selections per subcommand. None means "everything available".
COMMAND_TOOLS: Dict[str, Optional[Set[str]]] = {
    "scan": None,
    "audit": None,
    "health": {"radon-cc", "radon-mi", "xenon", "duplication"},
    "dead-code": {"vulture", "deptry", "duplication"},
    "summary": None,
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fallow4python",
        description="Codebase intelligence for Python: orchestrate quality tools, "
                    "correlate the signals, audit changed code, one report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="scan",
                        choices=list(COMMAND_TOOLS),
                        help="scan (default), audit, health, dead-code, summary")
    parser.add_argument("target", nargs="?", default=".",
                        help="path to analyze (default: current directory)")

    parser.add_argument("--base", help="git base ref for change-scoped audit "
                                        "(default for `audit`: origin/main then main)")
    parser.add_argument("--tools", help="comma-separated subset of tools/analyzers to run")

    parser.add_argument("--from-dir", help="ingest pre-saved tool outputs from this directory")
    parser.add_argument("--ruff"); parser.add_argument("--mypy")
    parser.add_argument("--vulture"); parser.add_argument("--radon-cc")
    parser.add_argument("--radon-mi"); parser.add_argument("--deptry")
    parser.add_argument("--xenon"); parser.add_argument("--import-linter")
    parser.add_argument("--coverage", help="path to coverage.py JSON report")

    parser.add_argument("--coverage-min", type=float, default=80.0)
    parser.add_argument("--radon-min-rank", default="C",
                        choices=list("ABCDEF"))
    parser.add_argument("--fail-on", default="none",
                        choices=["none", "info", "warning", "error"],
                        help="exit non-zero if any finding reaches this severity")
    parser.add_argument("--gate", default="changed", choices=["changed", "all"],
                        help="audit: 'changed' gates on changed code only; "
                             "'all' also fails on inherited errors")

    parser.add_argument("--format", dest="fmt", default="human",
                        choices=["human", "markdown", "json", "sarif"],
                        help="format written to stdout (default: human)")
    parser.add_argument("--json-out"); parser.add_argument("--markdown-out")
    parser.add_argument("--sarif-out")
    parser.add_argument("--max-per-section", type=int, default=100)
    parser.add_argument("--no-run", action="store_true",
                        help="do not run tools; only ingest saved outputs")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--timeout", type=int, default=300,
                        help="per-tool subprocess timeout in seconds")
    return parser


def args_to_options(args: argparse.Namespace) -> Options:
    tools = None
    if args.tools:
        tools = {t.strip() for t in args.tools.split(",") if t.strip()}
    explicit = {}
    for name, val in (("ruff", args.ruff), ("mypy", args.mypy),
                      ("vulture", args.vulture), ("radon-cc", args.radon_cc),
                      ("radon-mi", args.radon_mi), ("deptry", args.deptry),
                      ("xenon", args.xenon), ("import-linter", args.import_linter)):
        if val:
            explicit[name] = val
    base = args.base
    if args.command == "audit" and not base:
        base = "origin/main"  # resolved/fallback handled at diff time
    if tools is None:
        tools = COMMAND_TOOLS.get(args.command)
    return Options(
        command=args.command, target=args.target, base=base, tools=tools,
        from_dir=args.from_dir, explicit_inputs=explicit,
        coverage_path=args.coverage, coverage_min=args.coverage_min,
        radon_min_rank=args.radon_min_rank, fail_on=args.fail_on, gate=args.gate,
        fmt=args.fmt, json_out=args.json_out, markdown_out=args.markdown_out,
        sarif_out=args.sarif_out, max_per_section=args.max_per_section,
        no_run=args.no_run, no_color=args.no_color, timeout=args.timeout,
    )


def resolve_base(opts: Options, root: Path) -> Optional[str]:
    """Pick a usable git base ref for audits."""
    if not opts.base:
        return None
    candidates = [opts.base]
    if opts.base == "origin/main":
        candidates += ["main", "origin/master", "master", "HEAD~1"]
    for ref in candidates:
        try:
            check = subprocess.run(["git", "rev-parse", "--verify", ref],
                                   cwd=root, capture_output=True, text=True, timeout=15)
            if check.returncode == 0:
                return ref
        except (subprocess.SubprocessError, OSError):
            return None
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    opts = args_to_options(args)

    target = Path(opts.target).resolve()
    if not target.exists():
        print(f"fallow4python: target does not exist: {target}", file=sys.stderr)
        return 2
    root = target if target.is_dir() else target.parent

    # Run everything.
    findings, metrics, runs = orchestrate(root, target, opts)

    # Change scope (audit, or any command given --base).
    scope_label = ""
    scoped = False
    if opts.base:
        base_ref = resolve_base(opts, root)
        if base_ref is None:
            scope_label = f"(requested base '{opts.base}' not found; analyzing full tree)"
        else:
            changed = git_changed_lines(base_ref, root)
            if changed is None:
                scope_label = f"(could not diff against '{base_ref}'; analyzing full tree)"
            else:
                findings = mark_changed(findings, changed)
                scoped = True
                n_files = len(changed)
                scope_label = (f"Audit scope: {n_files} changed file(s) vs {base_ref} · "
                               f"{sum(1 for f in findings if f.changed)} findings in changed code")

    findings.sort(key=finding_sort_key)
    loc = count_loc(target)
    health = compute_health(findings, metrics, loc)
    insights = build_correlations(findings, metrics)
    summary = summarize(findings, metrics, runs, health)

    verdict = None
    if opts.command == "audit" or scoped:
        verdict = compute_verdict(findings, scoped, opts.gate)

    report = {
        "summary": summary,
        "insights": insights,
        "verdict": verdict,
        "_findings": findings,
        "_metrics": metrics,
        "_max_per_section": opts.max_per_section,
    }

    # Side outputs.
    if opts.json_out:
        Path(opts.json_out).write_text(
            json.dumps(build_json_envelope(report), indent=2, sort_keys=True),
            encoding="utf-8")
    if opts.markdown_out:
        Path(opts.markdown_out).write_text(render_markdown(report, scope_label),
                                          encoding="utf-8")
    if opts.sarif_out:
        Path(opts.sarif_out).write_text(
            json.dumps(build_sarif(report), indent=2), encoding="utf-8")

    # Primary (stdout) output.
    use_color = (not opts.no_color) and sys.stdout.isatty()
    if opts.fmt == "json":
        print(json.dumps(build_json_envelope(report), indent=2, sort_keys=True))
    elif opts.fmt == "markdown":
        print(render_markdown(report, scope_label))
    elif opts.fmt == "sarif":
        print(json.dumps(build_sarif(report), indent=2))
    else:
        if opts.command == "summary":
            print(render_summary(report, Palette(use_color), scope_label))
        else:
            print(render_human(report, Palette(use_color), scope_label))

    # Exit code.
    if verdict is not None:
        return 1 if verdict["verdict"] == "fail" else 0
    if opts.fail_on != "none":
        threshold = SEVERITY_ORDER[opts.fail_on]
        if any(SEVERITY_ORDER.get(f.severity, 0) >= threshold for f in findings):
            return 1
    return 0


def render_summary(report: Dict[str, Any], palette: Palette, scope_label: str) -> str:
    s = report["summary"]
    health = s["health"]
    p = palette
    grade = health.get("grade", "n/a")
    score = health.get("score")
    grade_c = (p.green if grade in ("A", "B") else p.yellow if grade in ("C", "D") else p.red)(grade)
    lines = [p.bold("fallow4python summary")]
    if scope_label:
        lines.append(p.dim(scope_label))
    lines.append(f"  Health {grade_c} ({score if score is not None else 'n/a'}/100) · "
                 f"{health.get('loc', 0)} LOC")
    comp = health.get("components", {})
    for k, v in comp.items():
        bar = ""
        if v is not None:
            filled = int(round(v / 10))
            bar = "#" * filled + "." * (10 - filled)
        lines.append(f"    {k:<16} {bar}  {v if v is not None else 'n/a'}")
    lines.append("")
    lines.append(f"  Findings: {s['finding_count']}  "
                 f"(err {s['by_severity']['error']}, "
                 f"warn {s['by_severity']['warning']}, "
                 f"info {s['by_severity']['info']})")
    cats = ", ".join(f"{k} {v}" for k, v in sorted(s["by_category"].items()))
    if cats:
        lines.append(p.dim("  " + cats))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())