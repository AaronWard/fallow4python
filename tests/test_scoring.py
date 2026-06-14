"""Tests for scoring, verdict, and summary."""
from __future__ import annotations

from fallow4python.scoring import _grade, compute_health
from fallow4python.summary import summarize
from fallow4python.verdict import compute_verdict


def test_grade_bands():
    assert _grade(None) == "n/a"
    assert _grade(95) == "A" and _grade(85) == "B" and _grade(75) == "C"
    assert _grade(65) == "D" and _grade(10) == "F"


def test_compute_health(findings, metrics):
    h = compute_health(findings, metrics, 1000)
    comp = h["components"]
    assert comp["coverage"] == 87.5
    assert comp["maintainability"] == 60.0  # mean of 55 and 65
    assert comp["complexity"] is not None
    assert h["score"] is not None and h["grade"] in "ABCDF"


def test_health_handles_missing():
    h = compute_health([], [], 0)
    assert h["components"]["coverage"] is None
    assert h["components"]["maintainability"] is None


def test_verdict_full_scan(findings):
    v = compute_verdict(findings, False, "changed")
    assert v["verdict"] == "fail"  # has an error
    assert not v["scoped_to_changes"]


def test_verdict_scoped_new_error(findings):
    v = compute_verdict(findings, True, "changed")
    assert v["scoped_to_changes"]
    assert v["new_errors"] >= 1 and v["verdict"] == "fail"


def test_verdict_scoped_clean():
    v = compute_verdict([], True, "all")
    assert v["verdict"] == "pass"


def test_summarize(findings, metrics, runs):
    h = compute_health(findings, metrics, 1000)
    s = summarize(findings, metrics, runs, h)
    assert s["finding_count"] == len(findings)
    assert s["max_severity"] == "error"
    assert s["by_severity"]["error"] >= 1
    assert "ruff" in s["by_tool"]
