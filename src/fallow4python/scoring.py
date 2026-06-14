"""The 0-100 health score and its four weighted components."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .model import Finding, Metric

_WEIGHTS = {"coverage": 0.30, "maintainability": 0.25,
            "complexity": 0.20, "cleanliness": 0.25}


def _coverage_component(metrics: Sequence[Metric]) -> Optional[float]:
    return next((m.value for m in metrics
                 if m.tool == "coverage" and m.name == "total-line-coverage"), None)


def _maintainability_component(metrics: Sequence[Metric]) -> Optional[float]:
    mis = [m.value for m in metrics if m.name == "maintainability-index"]
    return (sum(mis) / len(mis)) if mis else None


def _complexity_component(findings: Sequence[Finding], metrics: Sequence[Metric]
                          ) -> Optional[float]:
    flagged = sum(1 for f in findings if f.rule == "cyclomatic-complexity")
    total = next((m.value for m in metrics
                  if m.tool == "radon" and m.name == "complexity-functions"), None)
    if not total or total <= 0:
        return None
    return max(0.0, 100.0 * (1.0 - flagged / total))


def _cleanliness_component(findings: Sequence[Finding], loc: int) -> float:
    kloc = max(loc / 1000.0, 0.001)
    err = sum(1 for f in findings if f.severity == "error")
    warn = sum(1 for f in findings if f.severity == "warning")
    density = (err * 3 + warn) / kloc
    return max(0.0, 100.0 - min(density * 2.0, 100.0))


def _grade(score: Optional[float]) -> str:
    if score is None:
        return "n/a"
    for cutoff, g in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return g
    return "F"


def _weighted_score(sub: Dict[str, Optional[float]]) -> Optional[float]:
    num = den = 0.0
    for key, weight in _WEIGHTS.items():
        val = sub.get(key)
        if val is not None:
            num += val * weight
            den += weight
    return round(num / den, 1) if den else None


def compute_health(findings: Sequence[Finding], metrics: Sequence[Metric],
                   loc: int) -> Dict[str, Any]:
    """A transparent 0-100 health score from coverage, MI, complexity, density."""
    sub: Dict[str, Optional[float]] = {
        "coverage": _coverage_component(metrics),
        "maintainability": _maintainability_component(metrics),
        "complexity": _complexity_component(findings, metrics),
        "cleanliness": _cleanliness_component(findings, loc),
    }
    score = _weighted_score(sub)
    return {
        "score": score,
        "grade": _grade(score),
        "components": {k: (round(v, 1) if v is not None else None)
                       for k, v in sub.items()},
        "loc": loc,
    }
