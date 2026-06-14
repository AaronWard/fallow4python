"""Tests for coverage_via_tests and its helpers (mocking subprocess)."""
from __future__ import annotations

from pathlib import Path

from fallow4python import coverage_run
from fallow4python.coverage_run import (
    _has_coverage_config, _no_data_reason, _test_parts, coverage_via_tests,
)
from fallow4python.options import build_arg_parser
from fallow4python.options import args_to_options


def _opts():
    return args_to_options(build_arg_parser().parse_args(["scan", "."]))


def test_has_coverage_config(tmp_path: Path):
    assert not _has_coverage_config(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.run]\n",
                                             encoding="utf-8")
    assert _has_coverage_config(tmp_path)


def test_test_parts():
    assert _test_parts("pytest -q") == ["pytest", "-q"]
    assert _test_parts("") == ["pytest"]


def test_no_data_reason():
    class P:
        stderr = "line1\nboom: failure\n"
    assert "failure" in _no_data_reason(P())


def test_coverage_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(coverage_run.importlib.util, "find_spec",
                        lambda _: None)
    text, reason = coverage_via_tests(tmp_path, tmp_path, _opts())
    assert text is None and "coverage not installed" in reason


def test_coverage_success(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(coverage_run.importlib.util, "find_spec",
                        lambda _: object())

    def fake_run(root, target, opts, data_path, json_path):
        Path(json_path).write_text('{"totals": {"percent_covered": 91.0}}',
                                   encoding="utf-8")

        class P:
            returncode = 0
            stderr = ""
        return P()

    monkeypatch.setattr(coverage_run, "_run_command", fake_run)
    text, detail = coverage_via_tests(tmp_path, tmp_path, _opts())
    assert text is not None and "91.0" in text
