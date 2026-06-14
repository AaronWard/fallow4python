"""Tests for build_correlations - one case per insight kind."""
from __future__ import annotations

from fallow4python.correlate import build_correlations
from fallow4python.model import Finding, Metric


def _cov(file, pct):
    return Metric("coverage", "file-line-coverage", pct, unit="%", file=file)


def test_deletion_candidate():
    dead = Finding("vulture", "dead-code", "info", "unused function 'old'",
                   file="b.py", symbol="old", confidence=90)
    ins = build_correlations([dead], [_cov("b.py", 5.0)])
    assert any(i.kind == "deletion-candidate" for i in ins)


def test_risk_hotspot():
    cx = Finding("radon", "complexity", "warning", "complex", file="a.py",
                 rank="D", value=25.0, changed=True)
    ins = build_correlations([cx], [_cov("a.py", 30.0)])
    assert any(i.kind == "risk-hotspot" and i.severity == "error" for i in ins)


def test_worst_offender():
    fs = [Finding(t, "lint", "warning", "x", file="a.py")
          for t in ("ruff", "mypy", "vulture")]
    ins = build_correlations(fs, [])
    assert any(i.kind == "worst-offender" for i in ins)


def test_circular_import_insight():
    f = Finding("cycles", "architecture", "error", "a -> b -> a",
                rule="circular-import", file="a.py")
    ins = build_correlations([f], [])
    assert any(i.kind == "circular-import" for i in ins)


def test_no_spurious_insights():
    assert build_correlations([], []) == []
