"""Cover remaining runner.py branches: ingest errors and run_spec ingest path."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fallow4python import runner
from fallow4python.options import args_to_options, build_arg_parser
from fallow4python.runner import _tool_text, _try_ingest, run_spec
from fallow4python.toolspecs import ToolSpec, _specs


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def _ruff_spec():
    return next(s for s in _specs("C") if s.name == "ruff")


def test_try_ingest_parser_error(tmp_path: Path):
    bad = ToolSpec("ruff", "ruff", lambda t: ["ruff"],
                   parser=lambda text, root: (_ for _ in ()).throw(ValueError("x")))
    (tmp_path / "ruff.json").write_text("[]", encoding="utf-8")
    o = _opts(["scan", ".", "--from-dir", str(tmp_path)])
    res = _try_ingest(bad, tmp_path, o)
    assert res is not None and res[2].status == "error"


def test_try_ingest_missing_then_present(tmp_path: Path):
    o = _opts(["scan", ".", "--from-dir", str(tmp_path)])
    assert _try_ingest(_ruff_spec(), tmp_path, o) is None  # nothing on disk


def test_run_spec_ingests(tmp_path: Path):
    (tmp_path / "ruff.json").write_text(
        '[{"code":"F401","message":"x","filename":"a.py",'
        '"location":{"row":1,"column":1}}]', encoding="utf-8")
    o = _opts(["scan", ".", "--from-dir", str(tmp_path)])
    findings: list = []
    run = run_spec(_ruff_spec(), tmp_path, tmp_path, o, findings, [])
    assert run.status == "ingested" and findings


def test_tool_text_fallback():
    class P:
        stdout = "from-stdout"
    assert _tool_text(P(), None) == "from-stdout"
    assert _tool_text(P(), Path("/nonexistent-xyz")) == "from-stdout"


def test_run_tool_timeout(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ruff", timeout=1)
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/bin/ruff")
    monkeypatch.setattr(runner.subprocess, "run", boom)
    o = _opts(["scan", "."])
    run = run_spec(_ruff_spec(), tmp_path, tmp_path, o, [], [])
    assert run.status == "error" and "timed out" in run.detail
