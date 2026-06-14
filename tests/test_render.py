"""Tests for the rendering layer (human, summary, markdown, json, sarif)."""
from __future__ import annotations

from fallow4python.explain import md_explain
from fallow4python.palette import SEV_MARK, Palette
from fallow4python.render_human import _grade_color, render_human
from fallow4python.render_machine import build_json_envelope, build_sarif
from fallow4python.render_markdown import render_markdown
from fallow4python.render_summary import render_summary


def test_palette_toggle():
    on, off = Palette(True), Palette(False)
    assert "\033[" in on.red("x") and off.red("x") == "x"
    assert SEV_MARK["error"] == "x"


def test_grade_color():
    p = Palette(False)
    for g in ("A", "B", "C", "D", "F", "n/a"):
        assert _grade_color(p, g)(g) == g


def test_render_human(report):
    out = render_human(report, Palette(False), "scope: src")
    assert "fallow4python" in out and "scope: src" in out


def test_render_summary(report):
    out = render_summary(report, Palette(False), "")
    assert "Health" in out and "Findings" in out


def test_render_markdown(report):
    out = render_markdown(report, "all files")
    assert out.startswith("#") and "Health" in out


def test_build_json_envelope(report):
    env = build_json_envelope(report)
    assert env["schema_version"] == "1.0"
    assert len(env["findings"]) == len(report["_findings"])


def test_build_sarif(report):
    doc = build_sarif(report)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"]


def test_md_explain():
    lines = []
    md_explain(lines, "health")
    assert lines  # known key appends prose
    before = list(lines)
    md_explain(lines, "no-such-key")
    assert lines == before  # unknown key is a no-op
