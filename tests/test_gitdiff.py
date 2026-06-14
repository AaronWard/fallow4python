"""Tests for git integration, mocking subprocess and shutil.which."""
from __future__ import annotations

from pathlib import Path

from fallow4python import gitdiff
from fallow4python.gitdiff import (
    _hunk_lines, _target_path, git_changed_lines, mark_changed, resolve_base,
)
from fallow4python.model import Finding


def test_target_path():
    assert _target_path("+++ b/src/a.py") == "src/a.py"
    assert _target_path("+++ /dev/null") is None


def test_hunk_lines():
    changed = set()
    _hunk_lines("@@ -1,2 +3,2 @@", changed)
    assert changed == {3, 4}
    _hunk_lines("not a hunk", changed)
    assert changed == {3, 4}


def test_mark_changed():
    fs = [Finding("t", "c", "error", "m", file="a.py", line=3),
          Finding("t", "c", "error", "m", file="z.py", line=1)]
    out = mark_changed(fs, {"a.py": {3}})
    assert out[0].changed is True and out[1].changed is False


class _Proc:
    def __init__(self, code=0, out=""):
        self.returncode = code
        self.stdout = out


def test_git_changed_lines_mocked(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gitdiff.shutil, "which", lambda _: "/usr/bin/git")
    diff = ("+++ b/a.py\n@@ -0,0 +5,2 @@\n+x\n+y\n")

    def fake_run(args, **_):
        if args[1] == "merge-base":
            return _Proc(0, "abc123")
        return _Proc(0, diff)

    monkeypatch.setattr(gitdiff.subprocess, "run", fake_run)
    changed = git_changed_lines("main", tmp_path)
    assert changed == {"a.py": {5, 6}}


def test_git_changed_lines_no_git(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gitdiff.shutil, "which", lambda _: None)
    assert git_changed_lines("main", tmp_path) is None


def test_resolve_base(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gitdiff, "_git",
                        lambda *a, **k: _Proc(0))
    assert resolve_base("main", tmp_path) == "main"
    assert resolve_base(None, tmp_path) is None
