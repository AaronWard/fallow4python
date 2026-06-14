"""Tests for parse_lint: ruff, mypy, vulture (JSON + text fallback)."""
from __future__ import annotations

import json
from pathlib import Path

from fallow4python.parse_lint import (
    parse_mypy, parse_ruff, parse_vulture, severity_for_ruff,
)

ROOT = Path("/repo")


def test_severity_for_ruff():
    assert severity_for_ruff("E999", "") == "error"
    assert severity_for_ruff("F821", "") == "error"
    assert severity_for_ruff("F401", "unused") == "warning"
    assert severity_for_ruff("", "SyntaxError here") == "error"


def test_ruff_json():
    data = [{"code": "F401", "message": "unused", "filename": "/repo/a.py",
             "location": {"row": 2, "column": 5}}]
    fs, _ = parse_ruff(json.dumps(data), ROOT)
    assert fs[0].rule == "F401" and fs[0].file == "a.py" and fs[0].line == 2


def test_ruff_text_fallback():
    fs, _ = parse_ruff("/repo/a.py:3:1: F401 unused import", ROOT)
    assert fs and fs[0].rule == "F401" and fs[0].line == 3


def test_mypy_json_and_note():
    data = [{"severity": "note", "message": "n", "file": "/repo/a.py", "line": 1},
            {"severity": "error", "message": "e", "file": "/repo/a.py",
             "line": 2, "code": "arg-type"}]
    fs, _ = parse_mypy(json.dumps(data), ROOT)
    assert fs[0].severity == "info" and fs[1].severity == "error"


def test_mypy_text():
    fs, _ = parse_mypy("/repo/a.py:4:2: error: bad [arg-type]", ROOT)
    assert fs[0].rule == "arg-type" and fs[0].line == 4


def test_vulture_text_confidence():
    text = ("/repo/b.py:2: unused function 'old' (90% confidence)\n"
            "/repo/b.py:8: unused variable 'z' (60% confidence)")
    fs, _ = parse_vulture(text, ROOT)
    assert fs[0].severity == "warning" and fs[1].severity == "info"
