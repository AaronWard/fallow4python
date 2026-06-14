"""Branch coverage for runner: timeouts, errors, ingest, skip reasons."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fallow4python import runner
from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.runner import _run_tool, _skip_reason, _try_ingest, run_spec
from fallow4python.toolspecs import _specs


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def _spec(name):
    return next(s for s in _specs("C") if s.name == name)


def test_run_tool_timeout(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("ruff", 1)

    monkeypatch.setattr(runner.subprocess, "run", boom)
    run = _run_tool(_spec("ruff"), tmp_path, tmp_path, _opts(["scan", "."]),
                    [], [])
    assert run.status == "error" and "timed out" in run.detail


def test_run_tool_generic_error(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise OSError("denied")

    monkeypatch.setattr(runner.subprocess, "run", boom)
    run = _run_tool(_spec("ruff"), tmp_path, tmp_path, _opts(["scan", "."]),
                    [], [])
    assert run.status == "error" and "denied" in run.detail


def test_try_ingest_error(tmp_path: Path):
    bad = tmp_path / "ruff.json"
    bad.write_text("[not valid", encoding="utf-8")
    o = _opts(["scan", ".", "--ruff", str(bad)])
    res = _try_ingest(_spec("ruff"), tmp_path, o)
    # malformed JSON falls through to ruff's text parser -> still a run record
    assert res is not None and res[2].status in ("ingested", "error")


def test_skip_reason_not_installed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    reason = _skip_reason(_spec("ruff"), tmp_path, _opts(["scan", "."]))
    assert reason is not None and "not installed" in reason


def test_skip_reason_needs_config(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/bin/lint-imports")
    reason = _skip_reason(_spec("import-linter"), tmp_path, _opts(["scan", "."]))
    assert reason is not None and "import-linter" in reason


def test_run_spec_deptry_outfile(monkeypatch, tmp_path: Path):
    def fake_run(argv, **kw):
        out = argv[argv.index("--json-output") + 1]
        Path(out).write_text(
            '[{"error":{"code":"DEP002","message":"unused"},"module":"x"}]',
            encoding="utf-8")

        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    monkeypatch.setattr(runner.shutil, "which", lambda _: "/bin/deptry")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    findings: list = []
    run = run_spec(_spec("deptry"), tmp_path, tmp_path, _opts(["scan", "."]),
                   findings, [])
    assert run.status == "ran" and findings
