"""Tests for the built-in analyzers: duplication, cycles, discovery."""
from __future__ import annotations

from pathlib import Path

from fallow4python.cycles import detect_circular_imports
from fallow4python.discovery import discover_py_files
from fallow4python.duplication import detect_duplication


def _block(tag: str) -> str:
    return (f"def {tag}(items):\n"
            "    total = 0\n"
            "    for it in items:\n"
            "        if it > 0:\n"
            "            total += it * 2\n"
            "        else:\n"
            "            total -= it\n"
            "    return total\n")


def test_duplication_detects_clone(tmp_path: Path):
    (tmp_path / "a.py").write_text(_block("a"), encoding="utf-8")
    (tmp_path / "b.py").write_text(_block("b"), encoding="utf-8")
    files = discover_py_files(tmp_path)
    out = detect_duplication(tmp_path, files, window=4, min_chars=40)
    assert any(f.rule == "clone-family" for f in out)


def test_duplication_none_when_unique(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    out = detect_duplication(tmp_path, discover_py_files(tmp_path))
    assert out == []


def test_cycles_detects_circular(tmp_path: Path):
    (tmp_path / "p.py").write_text("import q\n", encoding="utf-8")
    (tmp_path / "q.py").write_text("import p\n", encoding="utf-8")
    out = detect_circular_imports(tmp_path, discover_py_files(tmp_path))
    assert any(f.rule == "circular-import" for f in out)


def test_cycles_none_when_acyclic(tmp_path: Path):
    (tmp_path / "p.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "q.py").write_text("import p\n", encoding="utf-8")
    out = detect_circular_imports(tmp_path, discover_py_files(tmp_path))
    assert out == []


def test_discovery_skips_ignored(tmp_path: Path):
    (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
    junk = tmp_path / ".venv"
    junk.mkdir()
    (junk / "skip.py").write_text("y = 2\n", encoding="utf-8")
    names = {p.name for p in discover_py_files(tmp_path)}
    assert "keep.py" in names and "skip.py" not in names
