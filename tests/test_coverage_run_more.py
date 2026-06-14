"""Branch coverage for coverage_run: run command, timeout, no-data."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fallow4python import coverage_run
from fallow4python.coverage_run import (
    _coverage_result, _has_coverage_config, _run_command, coverage_via_tests,
)
from fallow4python.options import args_to_options, build_arg_parser


def _opts():
    return args_to_options(build_arg_parser().parse_args(["scan", "."]))


class _Proc:
    returncode = 0
    stderr = ""


def test_has_config_variants(tmp_path: Path):
    (tmp_path / ".coveragerc").write_text("[run]\n", encoding="utf-8")
    assert _has_coverage_config(tmp_path)
    other = tmp_path / "sub"
    other.mkdir()
    (other / "setup.cfg").write_text("[coverage:run]\n", encoding="utf-8")
    assert _has_coverage_config(other)


def test_run_command_invokes_subprocess(monkeypatch, tmp_path: Path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "json" in cmd:
            Path(kw["env"]["COVERAGE_FILE"])  # touched indirectly
        return _Proc()

    monkeypatch.setattr(coverage_run.subprocess, "run", fake_run)
    json_path = str(tmp_path / "c.json")
    _run_command(tmp_path, tmp_path, _opts(), str(tmp_path / "c.data"), json_path)
    assert any("coverage" in c for c in calls)


def test_coverage_result_no_data(tmp_path: Path):
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    text, reason = _coverage_result(_Proc(), str(empty), "pytest")  # type: ignore[arg-type]
    assert text is None and "no coverage data" in reason


def test_coverage_via_tests_timeout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(coverage_run.importlib.util, "find_spec",
                        lambda _: object())

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("coverage", 1)

    monkeypatch.setattr(coverage_run, "_run_command", boom)
    text, reason = coverage_via_tests(tmp_path, tmp_path, _opts())
    assert text is None and "timed out" in reason


def test_coverage_via_tests_error(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(coverage_run.importlib.util, "find_spec",
                        lambda _: object())

    def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(coverage_run, "_run_command", boom)
    text, reason = coverage_via_tests(tmp_path, tmp_path, _opts())
    assert text is None and "nope" in reason
