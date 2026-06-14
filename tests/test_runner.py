"""Tests for tool specifications and the per-spec runner."""
from __future__ import annotations

from pathlib import Path

from fallow4python import runner
from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.runner import (
    _ingest_candidates, _prepare_argv, _skip_reason, _try_ingest, run_spec,
)
from fallow4python.toolspecs import (
    _import_linter_configured, _selected, _specs,
)


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def _ruff_spec():
    return next(s for s in _specs("C") if s.name == "ruff")


def test_specs_and_selection():
    specs = _specs("C")
    assert {s.name for s in specs} >= {"ruff", "mypy", "radon-cc"}
    o = _opts(["scan", ".", "--tools", "ruff"])
    assert _selected(o, "ruff") and not _selected(o, "mypy")


def test_import_linter_configured(tmp_path: Path):
    assert not _import_linter_configured(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.importlinter]\n",
                                             encoding="utf-8")
    assert _import_linter_configured(tmp_path)


def test_prepare_argv_outfile():
    spec = next(s for s in _specs("C") if s.name == "deptry")
    argv, tmp_out = _prepare_argv(spec, Path("."))
    assert tmp_out is not None and "{OUTFILE}" not in " ".join(argv)
    tmp_out.unlink()


def test_ingest_candidates_and_try(tmp_path: Path):
    (tmp_path / "ruff.json").write_text(
        '[{"code":"F401","message":"x","filename":"a.py",'
        '"location":{"row":1,"column":1}}]', encoding="utf-8")
    o = _opts(["scan", ".", "--from-dir", str(tmp_path)])
    spec = _ruff_spec()
    assert _ingest_candidates(spec, o)
    res = _try_ingest(spec, tmp_path, o)
    assert res is not None and res[2].status == "ingested"


def test_skip_reason_no_run():
    o = _opts(["scan", ".", "--no-run"])
    assert _skip_reason(_ruff_spec(), Path("."), o) is not None


def test_run_spec_mocks_subprocess(monkeypatch, tmp_path: Path):
    class P:
        returncode = 0
        stdout = '[{"code":"F401","message":"x","filename":"a.py",' \
                 '"location":{"row":1,"column":1}}]'
        stderr = ""
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/bin/ruff")
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: P())
    o = _opts(["scan", "."])
    findings: list = []
    metrics: list = []
    run = run_spec(_ruff_spec(), tmp_path, tmp_path, o, findings, metrics)
    assert run.status == "ran" and findings
