"""Normalized data records produced and consumed across fallow4python."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


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
    changed: bool = False
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
    status: str
    detail: str = ""
    findings: int = 0
    duration_ms: Optional[int] = None
