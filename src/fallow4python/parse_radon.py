"""Parsers for radon output: cyclomatic complexity (cc) and the MI index."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .model import (
    Finding, Metric, normalize_path, rank_at_least, rank_from_cc, rel,
    safe_json_loads, severity_for_radon_rank, to_float, to_int,
)

Parsed = Tuple[List[Finding], List[Metric]]


# --- cc -------------------------------------------------------------------- #

def _radon_cc_message(btype: str, name: str, cc: Optional[float], rank: str) -> str:
    if cc is not None:
        return f"{btype} `{name}` complexity {cc:g} (rank {rank})"
    return f"{btype} `{name}` rank {rank}"


def _radon_cc_block(b: Dict[str, Any], filename: str, root: Path,
                    min_rank: str) -> Optional[Finding]:
    cc = to_float(b.get("complexity"))
    rank = str(b.get("rank") or rank_from_cc(cc)).upper()
    if not rank or not rank_at_least(rank, min_rank):
        return None
    name = str(b.get("name") or "<unknown>")
    btype = str(b.get("type") or "block")
    return Finding(
        tool="radon", category="complexity",
        severity=severity_for_radon_rank(rank),
        rule="cyclomatic-complexity",
        message=_radon_cc_message(btype, name, cc, rank),
        file=rel(normalize_path(filename), root),
        line=to_int(b.get("lineno")), column=to_int(b.get("col_offset")),
        symbol=name, rank=rank, value=cc, raw=json.dumps(b, sort_keys=True),
    )


def _radon_cc_from_json(data: Dict[str, Any], root: Path, min_rank: str) -> Parsed:
    out: List[Finding] = []
    total = 0
    for filename, blocks in data.items():
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            total += 1
            f = _radon_cc_block(b, filename, root, min_rank)
            if f is not None:
                out.append(f)
    metrics = [Metric(tool="radon", name="complexity-functions",
                      value=float(total),
                      details=f"flagged={len(out)} at rank>={min_rank}")]
    return out, metrics


_RADON_CC_TEXT = re.compile(
    r"^\s*(?P<kind>[CFM])\s+(?P<line>\d+):(?P<col>\d+)\s+"
    r"(?P<name>.+?)\s+-\s+(?P<rank>[A-F])\s+\((?P<cc>\d+)\)"
)


def parse_radon_cc(text: str, root: Path, min_rank: str) -> Parsed:
    data = safe_json_loads(text)
    if isinstance(data, dict):
        return _radon_cc_from_json(data, root, min_rank)
    out: List[Finding] = []
    current = ""
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _RADON_CC_TEXT.match(line)
        if not m:
            if not line.startswith((" ", "\t")):
                current = line.strip()
            continue
        rank = m.group("rank")
        if not rank_at_least(rank, min_rank):
            continue
        cc = to_float(m.group("cc"))
        name = m.group("name")
        out.append(Finding(
            tool="radon", category="complexity",
            severity=severity_for_radon_rank(rank), rule="cyclomatic-complexity",
            message=f"`{name}` complexity {cc:g} (rank {rank})",
            file=rel(normalize_path(current), root),
            line=to_int(m.group("line")), column=to_int(m.group("col")),
            symbol=name, rank=rank, value=cc, raw=line,
        ))
    return out, []


# --- mi -------------------------------------------------------------------- #

def _mi_pair(result: Any) -> Tuple[Optional[float], str]:
    if isinstance(result, dict):
        return to_float(result.get("mi") or result.get("value")), \
            str(result.get("rank") or "").upper()
    return to_float(result), ""


def _radon_mi_from_json(data: Dict[str, Any], root: Path, min_rank: str) -> Parsed:
    out: List[Finding] = []
    metrics: List[Metric] = []
    for filename, result in data.items():
        mi, rank = _mi_pair(result)
        if mi is None:
            continue
        f = rel(normalize_path(filename), root)
        metrics.append(Metric(tool="radon", name="maintainability-index",
                              value=mi, file=f, rank=rank))
        if rank and rank_at_least(rank, min_rank):
            out.append(Finding(
                tool="radon", category="maintainability",
                severity=severity_for_radon_rank(rank),
                rule="maintainability-index",
                message=f"maintainability index {mi:g} (rank {rank})",
                file=f, rank=rank, value=mi,
                raw=json.dumps(result, sort_keys=True)))
    return out, metrics


_RADON_MI_TEXT = re.compile(r"^(?P<file>.+?)\s+-\s+(?P<rank>[A-F])\s+\((?P<mi>[\d.]+)\)")


def parse_radon_mi(text: str, root: Path, min_rank: str) -> Parsed:
    data = safe_json_loads(text)
    if isinstance(data, dict):
        return _radon_mi_from_json(data, root, min_rank)
    out: List[Finding] = []
    metrics: List[Metric] = []
    for line in text.splitlines():
        m = _RADON_MI_TEXT.match(line.strip())
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
                file=f, rank=rank, value=mi, raw=line))
    return out, metrics
