"""Shared fixtures for the fallow4python test-suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from fallow4python.correlate import build_correlations
from fallow4python.health import compute_health, compute_verdict, summarize
from fallow4python.model import Finding, Metric, ToolRun


@pytest.fixture
def findings():
    return [
        Finding("ruff", "lint", "warning", "unused import", rule="F401",
                file="a.py", line=3, column=1),
        Finding("mypy", "typing", "error", "bad type", rule="arg-type",
                file="a.py", line=9, changed=True),
        Finding("vulture", "dead-code", "info", "unused function 'old'",
                file="b.py", line=2, symbol="old", confidence=90),
        Finding("radon", "complexity", "warning",
                "function `big` complexity 14 (rank C)", rule="cyclomatic-complexity",
                file="b.py", line=20, symbol="big", rank="C", value=14.0),
        Finding("cycles", "architecture", "error",
                "circular import among 2 modules: a -> b -> a",
                rule="circular-import", file="a.py", symbol="a"),
    ]


@pytest.fixture
def metrics():
    return [
        Metric("coverage", "total-line-coverage", 87.5, unit="%"),
        Metric("coverage", "file-line-coverage", 40.0, unit="%", file="b.py"),
        Metric("radon", "maintainability-index", 55.0, file="a.py", rank="A"),
        Metric("radon", "maintainability-index", 65.0, file="b.py", rank="A"),
        Metric("radon", "complexity-functions", 20.0, details="flagged=1"),
    ]


@pytest.fixture
def runs():
    return [
        ToolRun("ruff", "ran", "", 1, 12),
        ToolRun("mypy", "ran", "", 1, 30),
        ToolRun("import-linter", "skipped", "no config"),
        ToolRun("deptry", "error", "boom"),
    ]


@pytest.fixture
def report(findings, metrics, runs):
    health = compute_health(findings, metrics, 1000)
    return {
        "summary": summarize(findings, metrics, runs, health),
        "insights": build_correlations(findings, metrics),
        "verdict": compute_verdict(findings, True, "changed"),
        "_findings": findings,
        "_metrics": metrics,
        "_max_per_section": 100,
    }


@pytest.fixture
def tmp_pkg(tmp_path: Path) -> Path:
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    (tmp_path / "n.py").write_text("import m\n\n\ndef g():\n    return 2\n",
                                   encoding="utf-8")
    return tmp_path
