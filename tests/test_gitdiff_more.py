"""Cover gitdiff.py using a real temp git repo and mocked subprocess failures."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fallow4python import gitdiff
from fallow4python.gitdiff import (
    _git, _hunk_lines, _target_path, git_changed_lines, mark_changed,
    resolve_base,
)
from fallow4python.model import Finding

git = pytest.importorskip("shutil").which("git")


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.mark.skipif(not git, reason="git not installed")
def test_real_repo_diff(tmp_path: Path):
    _run(["git", "init", "-q"], tmp_path)
    _run(["git", "config", "user.email", "t@t"], tmp_path)
    _run(["git", "config", "user.name", "t"], tmp_path)
    f = tmp_path / "m.py"
    f.write_text("a = 1\n", encoding="utf-8")
    _run(["git", "add", "."], tmp_path)
    _run(["git", "commit", "-qm", "init"], tmp_path)
    f.write_text("a = 1\nb = 2\n", encoding="utf-8")
    base = resolve_base("HEAD", tmp_path)
    assert base == "HEAD"
    changed = git_changed_lines(base, tmp_path)
    assert changed is not None
    assert "m.py" in changed
    marked = mark_changed([Finding("t", "c", "warning", "x", file="m.py",
                                   line=2)], changed)
    assert marked[0].changed


def test_target_path_and_hunk():
    assert _target_path("+++ /dev/null") is None
    assert _target_path("+++ b/src/x.py") == "src/x.py"
    seen: set = set()
    _hunk_lines("@@ -1,0 +4,3 @@", seen)
    assert seen == {4, 5, 6}
    _hunk_lines("not a hunk", seen)


def test_git_exception(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise OSError("no git")
    monkeypatch.setattr(subprocess, "run", boom)
    assert _git(["git", "x"], tmp_path, 5) is None
    assert resolve_base("origin/main", tmp_path) is None


def test_changed_lines_no_git(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gitdiff.shutil, "which", lambda _: None)
    assert git_changed_lines("HEAD", tmp_path) is None
