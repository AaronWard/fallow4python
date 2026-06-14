"""Cover orchestrate coverage branches, coverage_run edges, and helpers.rel."""
from __future__ import annotations

from pathlib import Path

from fallow4python import coverage_run
from fallow4python.coverage_run import _has_coverage_config, _test_parts
from fallow4python.helpers import rel
from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.orchestrate import _coverage_run, _coverage_text, count_loc


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def test_coverage_text_explicit_file(tmp_path: Path):
    cov = tmp_path / "cov.json"
    cov.write_text('{"totals": {"percent_covered": 90.0}, "files": {}}',
                   encoding="utf-8")
    o = _opts(["scan", ".", "--coverage", str(cov)])
    text, detail, run = _coverage_text(tmp_path, tmp_path, o)
    assert text is not None and run is None


def test_coverage_text_missing_file(tmp_path: Path):
    o = _opts(["scan", ".", "--coverage", str(tmp_path / "nope.json")])
    _, _, run = _coverage_text(tmp_path, tmp_path, o)
    assert run is not None and run.status == "skipped"


def test_coverage_run_error(tmp_path: Path):
    run = _coverage_run(None, "d", tmp_path, _opts(["scan", "."]), [], [])  # type: ignore[arg-type]
    assert run.status == "error"


def test_has_coverage_config_oserror(tmp_path: Path):
    # A directory named pyproject.toml makes read_text raise OSError.
    (tmp_path / "pyproject.toml").mkdir()
    assert _has_coverage_config(tmp_path) is False


def test_test_parts_bad_quotes():
    assert _test_parts('pytest "unbalanced') == ["pytest"]
    assert _test_parts("") == ["pytest"]


def test_coverage_unlink_oserror(monkeypatch, tmp_path: Path):
    o = _opts(["scan", "."])
    monkeypatch.setattr(coverage_run.importlib.util, "find_spec",
                        lambda _: None)
    text, reason = coverage_run.coverage_via_tests(tmp_path, tmp_path, o)
    assert text is None and "coverage not installed" in reason


def test_count_loc_and_rel(tmp_pkg: Path):
    assert count_loc(tmp_pkg) > 0
    assert count_loc(tmp_pkg / "m.py") > 0
    assert rel("x.py", Path(".")) == "x.py"
