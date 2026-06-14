"""Cover renderer truncation/verdict branches and lint text-fallback continues."""
from __future__ import annotations

from pathlib import Path

from fallow4python.correlate import build_correlations
from fallow4python.health import compute_health, compute_verdict, summarize
from fallow4python.model import Finding, Metric, ToolRun
from fallow4python.palette import Palette
from fallow4python.parse_lint import parse_mypy, parse_vulture
from fallow4python.render_human import render_human
from fallow4python.render_markdown import render_markdown
from fallow4python.render_summary import render_summary


def _many_findings():
    out = []
    for i in range(15):
        out.append(Finding("cycles", "architecture", "error",
                           f"circular import {i}", rule="circular-import",
                           file=f"m{i}.py", symbol=f"m{i}"))
    out.append(Finding("ruff", "lint", "warning", "x", rule="F401", file="a.py"))
    return out


def _report(findings, scoped):
    metrics = [Metric("radon", "maintainability-index", 60.0, file="a.py")]
    health = compute_health(findings, metrics, 500)
    return {
        "summary": summarize(findings, metrics,
                             [ToolRun("ruff", "ran", "", 1)], health),
        "insights": build_correlations(findings, metrics),
        "verdict": compute_verdict(findings, scoped, "all"),
        "_findings": findings, "_metrics": metrics, "_max_per_section": 1,
    }


def test_human_truncation_and_fullscan_verdict():
    rep = _report(_many_findings(), scoped=False)
    out = render_human(rep, Palette(False), "Scope: demo")
    assert "more insights" in out and "error(s)" in out and "Scope: demo" in out


def test_summary_with_scope():
    rep = _report(_many_findings(), scoped=True)
    assert "demo" in render_summary(rep, Palette(False), "demo")


def test_markdown_truncation():
    rep = _report(_many_findings(), scoped=True)
    md = render_markdown(rep, "Scope: demo")
    assert "omitted" in md and "VERDICT" not in md or "**" in md


def test_lint_text_skips_noise():
    fs, _ = parse_mypy("a.py:9:3: error: bad [x]\nrandom noise line\n", Path("."))
    assert len(fs) == 1
    fs2, _ = parse_vulture("b.py:2: unused x (90% confidence)\nnoise\n", Path("."))
    assert len(fs2) == 1
