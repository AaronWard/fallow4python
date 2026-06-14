"""Correlation engine: join findings across tools into prioritized Insights."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Set

from .model import Finding, Insight, Metric, location_str

_SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


def _file_metric(metrics: Sequence[Metric], tool: str, name: str
                 ) -> Dict[str, float]:
    return {m.file: m.value for m in metrics
            if m.tool == tool and m.name == name and m.file}


def _deletion_candidates(dead: Sequence[Finding], cov: Dict[str, float]
                         ) -> List[Insight]:
    out: List[Insight] = []
    for f in dead:
        c = cov.get(f.file)
        if c is None or c >= 50:
            continue
        if (f.confidence or 0) >= 80 or c < 10:
            out.append(Insight(
                kind="deletion-candidate", severity="warning",
                title=f"Likely safe to delete: {f.symbol or f.message}",
                detail=f"{f.message} at {location_str(f)}; file coverage is "
                       f"{c:.0f}%, so it is unused statically and barely "
                       f"exercised at runtime.",
                file=f.file, line=f.line,
                evidence=[f"vulture: {f.message} ({f.confidence or '?'}% confidence)",
                          f"coverage: {c:.0f}% of {f.file}"]))
    return out


def _risk_reasons(f: Finding, cov: Dict[str, float]) -> List[str]:
    reasons = [f"radon: {f.message}"]
    c = cov.get(f.file)
    if c is not None and c < 70:
        reasons.append(f"coverage: only {c:.0f}% covered")
    if f.changed:
        reasons.append("changed in this diff")
    return reasons


def _risk_hotspots(complex_f: Sequence[Finding], cov: Dict[str, float]
                   ) -> List[Insight]:
    out: List[Insight] = []
    for f in complex_f:
        reasons = _risk_reasons(f, cov)
        if len(reasons) == 1:
            continue
        out.append(Insight(
            kind="risk-hotspot",
            severity="error" if f.rank in {"E", "F"} or f.changed else "warning",
            title=f"Risk hotspot: {f.symbol or 'block'} in {f.file}",
            detail="High complexity combined with " + " and ".join(reasons[1:])
                   + " - prioritize tests or a refactor before extending it.",
            file=f.file, line=f.line, evidence=reasons))
    return out


def _worst_offenders(findings: Sequence[Finding]) -> List[Insight]:
    by_file: Dict[str, Set[str]] = defaultdict(set)
    counts: Counter = Counter()
    for f in findings:
        if f.file:
            by_file[f.file].add(f.tool)
            counts[f.file] += 1
    out: List[Insight] = []
    for fname, tools in by_file.items():
        if len(tools) < 3:
            continue
        out.append(Insight(
            kind="worst-offender", severity="warning",
            title=f"Concentrated problems: {fname}",
            detail=f"{counts[fname]} findings from {len(tools)} tools "
                   f"({', '.join(sorted(tools))}). A focused cleanup here "
                   f"clears the most signal.",
            file=fname,
            evidence=[f"{counts[fname]} findings across {', '.join(sorted(tools))}"]))
    return out


def _circular_imports(findings: Sequence[Finding]) -> List[Insight]:
    return [Insight(kind="circular-import", severity="error",
                    title="Circular import", detail=f.message,
                    file=f.file, evidence=[f.message])
            for f in findings if f.rule == "circular-import"]


def build_correlations(findings: Sequence[Finding], metrics: Sequence[Metric]
                       ) -> List[Insight]:
    cov = _file_metric(metrics, "coverage", "file-line-coverage")
    dead = [f for f in findings if f.category == "dead-code"]
    complex_f = [f for f in findings
                 if f.category == "complexity" and f.rank in {"C", "D", "E", "F"}]
    insights = (_deletion_candidates(dead, cov)
                + _risk_hotspots(complex_f, cov)
                + _worst_offenders(findings)
                + _circular_imports(findings))
    insights.sort(key=lambda i: (_SEV_ORDER.get(i.severity, 3), i.kind, i.file))
    return insights
