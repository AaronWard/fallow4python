"""Cover cli.py: scope handling, audit verdict, and fail-on exit codes."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fallow4python.cli import main

git = pytest.importorskip("shutil").which("git")


def _make_circular(d: Path) -> None:
    pkg = d / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("from pkg import a\n", encoding="utf-8")


def test_fail_on_error(tmp_path: Path, capsys):
    _make_circular(tmp_path)
    code = main(["--no-run", "--ignore-tests", "--no-color", "--format", "json",
                 "--fail-on", "error", str(tmp_path)])
    capsys.readouterr()
    assert code == 1


def test_audit_verdict(tmp_path: Path, capsys):
    _make_circular(tmp_path)
    code = main(["audit", str(tmp_path), "--no-run", "--ignore-tests",
                 "--no-color", "--format", "human"])
    capsys.readouterr()
    assert code == 1


@pytest.mark.skipif(not git, reason="git not installed")
def test_scope_against_base(tmp_path: Path, capsys):
    def run(args):
        subprocess.run(args, cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    run(["git", "init", "-q"])
    run(["git", "config", "user.email", "t@t"])
    run(["git", "config", "user.name", "t"])
    run(["git", "add", "."])
    run(["git", "commit", "-qm", "init"])
    (tmp_path / "m.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    code = main(["--no-run", "--ignore-tests", "--no-color", "--base", "HEAD",
                 "--format", "human", str(tmp_path)])
    out = capsys.readouterr().out
    assert code in (0, 1) and "scope" in out.lower()


def test_missing_base(tmp_path: Path, capsys):
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    code = main(["--no-run", "--ignore-tests", "--no-color",
                 "--base", "nope-xyz", "--format", "json", str(tmp_path)])
    capsys.readouterr()
    assert code in (0, 1)
