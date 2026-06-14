"""Tests for the progress display: styling helpers and row composition."""
from __future__ import annotations

from fallow4python.progress import LiveProgress
from fallow4python.progress_style import (
    bar_tone, c, state_glyph, wordmark,
)


def test_style_helpers():
    assert c(44, "x").endswith("x\033[0m")
    assert "\033[" in wordmark("abc", 0.5, final=False)
    assert wordmark("abc", 0.0, final=True)
    assert 0 <= bar_tone(0, 4) < 256
    glyph, code = state_glyph("error")
    assert glyph and isinstance(code, int)
    assert state_glyph("mystery")[0]  # fallback


def test_liveprogress_noop():
    # not a TTY under pytest -> disabled, methods are safe no-ops
    with LiveProgress(["ruff", "mypy"], enabled=True) as p:
        p.start("ruff")
        p.finish("ruff", "ran", 2)
        p.finish("missing", "ran")
    assert p.enabled is False


def test_compose_rows_directly():
    p = LiveProgress(["ruff", "mypy", "cycles"], enabled=False)
    p._start_ts = 0.0
    p.state["ruff"] = "running"
    p.state["mypy"] = "ran"
    p._set_detail("mypy", "ran", 3, "")
    rows = p._compose(final=False)
    assert len(rows) == 6 and any("scanning" in r for r in rows)
    assert p._bar_row(1, 3, final=True)
    assert "ruff" in p._step_row("ruff", "*")
    assert "mypy" in p._step_row("mypy", "*")
    assert "cycles" in p._step_row("cycles", "*")  # pending branch
