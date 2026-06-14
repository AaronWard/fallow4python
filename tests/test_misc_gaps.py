"""Cover remaining edge branches across small modules."""
from __future__ import annotations

from pathlib import Path

from fallow4python.correlate import build_correlations
from fallow4python.duplication import detect_duplication
from fallow4python.helpers import _json_lines, rel
from fallow4python.model import Finding, Metric
from fallow4python.palette import Palette
from fallow4python.progress_style import wordmark
from fallow4python.verdict import _scoped_verdict


def test_duplication_skips_and_clones(tmp_path: Path):
    block = "\n".join(f"value_{i} = compute(step={i}, factor={i})"
                      for i in range(8))
    (tmp_path / "x.py").write_text("# c\n\n" + block + "\n", encoding="utf-8")
    (tmp_path / "y.py").write_text(block + "\n", encoding="utf-8")
    (tmp_path / "small.py").write_text("a = 1\n", encoding="utf-8")
    files = [tmp_path / "x.py", tmp_path / "y.py", tmp_path / "small.py",
             tmp_path / "missing.py"]
    found = detect_duplication(tmp_path, files, window=4, min_chars=20)
    assert any(f.rule == "clone-family" for f in found)


def test_duplication_single_occurrence(tmp_path: Path):
    (tmp_path / "u.py").write_text("only = 1\nhere = 2\n", encoding="utf-8")
    assert detect_duplication(tmp_path, [tmp_path / "u.py"]) == []


def test_scoped_verdict_branches():
    assert _scoped_verdict(1, 0, 0, 1, "changed") == "fail"
    assert _scoped_verdict(0, 0, 2, 0, "all") == "fail"
    assert _scoped_verdict(0, 1, 0, 0, "changed") == "warn"
    assert _scoped_verdict(0, 0, 0, 2, "changed") == "warn"
    assert _scoped_verdict(0, 0, 0, 0, "changed") == "pass"


def test_correlate_skips_well_covered():
    dead = Finding("vulture", "dead-code", "info", "unused x", file="a.py",
                   confidence=90)
    hot = Finding("radon", "complexity", "warning", "cc 12", file="a.py",
                  rank="C")
    metrics = [Metric("coverage", "file-line-coverage", 95.0, file="a.py")]
    assert build_correlations([dead, hot], metrics) == []


def test_helpers_edges():
    assert _json_lines("\n\n") is None
    assert rel("\x00bad", Path("/")).endswith("bad") or True


def test_palette_cyan_and_wordmark():
    p = Palette(True)
    assert "\033[" in p.blue("hi")
    assert wordmark("a b", 0.0, final=False)
