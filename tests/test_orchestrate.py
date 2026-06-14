"""Tests for orchestration helpers: planned steps, count_loc, coverage text."""
from __future__ import annotations

from pathlib import Path

from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.orchestrate import (
    _coverage_text, _planned_steps, count_loc, orchestrate,
)
from fallow4python.toolspecs import _specs


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def test_planned_steps_full():
    steps = _planned_steps(_specs("C"), _opts(["scan", "."]))
    assert "ruff" in steps and "coverage" in steps and "cycles" in steps


def test_planned_steps_subset():
    steps = _planned_steps(_specs("C"), _opts(["scan", ".", "--tools", "ruff"]))
    assert steps == ["ruff"]


def test_count_loc(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("z = 3\n", encoding="utf-8")
    assert count_loc(tmp_path) == 3


def test_coverage_text_ignore_tests(tmp_path: Path):
    o = _opts(["scan", ".", "--ignore-tests"])
    text, _detail, run = _coverage_text(tmp_path, tmp_path, o)
    assert text is None and run is not None and run.status == "skipped"


def test_coverage_text_explicit_missing(tmp_path: Path):
    o = _opts(["scan", ".", "--coverage", str(tmp_path / "none.json")])
    text, _detail, run = _coverage_text(tmp_path, tmp_path, o)
    assert text is None and run is not None and run.status == "skipped"


def test_orchestrate_no_run(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    o = _opts(["scan", str(tmp_path), "--no-run", "--ignore-tests",
               "--tools", "ruff,duplication,cycles"])
    findings, metrics, runs = orchestrate(tmp_path, tmp_path, o)
    statuses = {r.name: r.status for r in runs}
    assert statuses["ruff"] == "skipped"
    assert "duplication" in statuses and "cycles" in statuses
