"""Tests for parse_radon: cyclomatic complexity and maintainability index."""
from __future__ import annotations

import json
from pathlib import Path

from fallow4python.parse_radon import parse_radon_cc, parse_radon_mi

ROOT = Path("/repo")


def test_cc_json_flags_by_rank():
    data = {"/repo/a.py": [
        {"name": "big", "type": "function", "complexity": 14, "rank": "C",
         "lineno": 10},
        {"name": "ok", "type": "function", "complexity": 2, "rank": "A",
         "lineno": 1},
    ]}
    fs, ms = parse_radon_cc(json.dumps(data), ROOT, "C")
    assert len(fs) == 1 and fs[0].symbol == "big"
    assert ms[0].value == 2.0  # total functions seen


def test_cc_text_fallback():
    text = "a.py\n    F 10:0 big - C (14)\n    F 1:0 ok - A (2)"
    fs, _ = parse_radon_cc(text, ROOT, "C")
    assert len(fs) == 1 and fs[0].rank == "C"


def test_mi_json_metrics_and_finding():
    data = {"/repo/a.py": {"mi": 45.0, "rank": "A"},
            "/repo/b.py": {"mi": 8.0, "rank": "C"}}
    fs, ms = parse_radon_mi(json.dumps(data), ROOT, "C")
    assert {m.file for m in ms} == {"a.py", "b.py"}
    assert len(fs) == 1 and fs[0].file == "b.py"


def test_mi_text_fallback():
    fs, ms = parse_radon_mi("a.py - A (72.31)", ROOT, "C")
    assert ms[0].value == 72.31 and fs == []
