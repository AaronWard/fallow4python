"""Branch coverage for orchestrate: coverage path, builtin errors, run path."""
from __future__ import annotations

from pathlib import Path

from fallow4python import orchestrate as orch
from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.orchestrate import (
    _coverage_text, _run_builtin, orchestrate,
)
from fallow4python.progress import LiveProgress


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def test_coverage_text_runs_tests(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(orch, "coverage_via_tests",
                        lambda root, target, opts: ('{"totals": {}}', "ran"))
    text, detail, run = _coverage_text(tmp_path, tmp_path, _opts(["scan", "."]))
    assert text is not None and run is None and detail == "ran"


def test_coverage_text_tests_fail(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(orch, "coverage_via_tests",
                        lambda root, target, opts: (None, "no data"))
    text, _d, run = _coverage_text(tmp_path, tmp_path, _opts(["scan", "."]))
    assert text is None and run is not None and run.status == "skipped"


def test_coverage_text_explicit_file(tmp_path: Path):
    cov = tmp_path / "cov.json"
    cov.write_text('{"totals": {"percent_covered": 99.0}}', encoding="utf-8")
    o = _opts(["scan", ".", "--coverage", str(cov)])
    text, _d, run = _coverage_text(tmp_path, tmp_path, o)
    assert text is not None and run is None


def test_run_builtin_error(tmp_path: Path):
    runs: list = []
    findings: list = []

    def boom(base, files):
        raise RuntimeError("analyzer broke")

    with LiveProgress([], enabled=False) as prog:
        _run_builtin("duplication", "d", tmp_path, _opts(["scan", "."]),
                     findings, prog, runs, boom)
    assert runs[0].status == "error"


def test_orchestrate_runs_coverage(monkeypatch, tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(orch, "coverage_via_tests",
                        lambda *a: ('{"totals": {"percent_covered": 88.0}}', "ok"))
    o = _opts(["scan", str(tmp_path), "--tools", "coverage,duplication"])
    findings, metrics, runs = orchestrate(tmp_path, tmp_path, o)
    statuses = {r.name: r.status for r in runs}
    assert statuses.get("coverage") == "ingested"
