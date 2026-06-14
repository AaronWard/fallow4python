"""Cover the progress enabled (TTY) path and the package entry point."""
from __future__ import annotations

import io

import fallow4python.__main__  # noqa: F401  (import executes module body)
from fallow4python import progress
from fallow4python.progress import LiveProgress


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_progress_enabled_cycle(monkeypatch):
    fake = _FakeTTY()
    monkeypatch.setattr(progress.sys, "stderr", fake)
    with LiveProgress(["ruff", "mypy"], enabled=True) as p:
        assert p.enabled is True
        p.start("ruff")
        p.finish("ruff", "ran", 2)
        p.finish("mypy", "skipped", note="no config")
    assert fake.getvalue()  # something was rendered to the fake terminal


def test_progress_render_directly(monkeypatch):
    fake = _FakeTTY()
    monkeypatch.setattr(progress.sys, "stderr", fake)
    p = LiveProgress(["ruff"], enabled=True)
    p._start_ts = 0.0
    p._render()
    p._render(final=True)
    assert fake.getvalue()


def test_main_module_imported():
    assert hasattr(fallow4python.__main__, "main")
