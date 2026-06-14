"""Cover fallback and edge branches in the quality and radon parsers."""
from __future__ import annotations

import json
from pathlib import Path

from fallow4python.parse_quality import (
    parse_coverage, parse_import_linter, parse_xenon,
)
from fallow4python.parse_radon import _mi_pair, parse_radon_cc, parse_radon_mi

ROOT = Path(".")


def test_xenon_blank_and_generic():
    fs, _ = parse_xenon("\n\nmodule too complex average rank C\n", ROOT)
    assert fs and fs[0].severity == "error"


def test_import_linter_no_match():
    assert parse_import_linter("everything is fine\n", ROOT) == ([], [])


def test_coverage_total_missing_percent():
    fs, ms = parse_coverage(json.dumps({"totals": {}, "files": {}}), ROOT, 80)
    assert fs == [] and ms == []


def test_coverage_not_json():
    fs, _ = parse_coverage("not json", ROOT, 80)
    assert fs and fs[0].rule == "parse-error"


def test_coverage_file_branches():
    data = {"totals": {"percent_covered": 95.0},
            "files": {
                "good.py": {"summary": {"percent_covered": 99.0}},
                "bad.py": {"summary": {"percent_covered": 10.0,
                                       "missing_lines": 7}},
                "nopct.py": {"summary": {}},
                "../outside.py": {"summary": {"percent_covered": 1.0}},
            }}
    fs, ms = parse_coverage(json.dumps(data), ROOT, 80)
    files = {f.file for f in fs}
    assert "bad.py" in files and "good.py" not in files
    assert any(m.file == "good.py" for m in ms)


def test_mi_pair_scalar():
    assert _mi_pair(72.5) == (72.5, "")


def test_radon_cc_text_fallback():
    text = ("module.py\n"
            "    F 3:0 big - C (12)\n"
            "    F 9:0 ok - A (2)\n")
    fs, _ = parse_radon_cc(text, ROOT, "C")
    assert len(fs) == 1 and fs[0].rank == "C"


def test_radon_mi_text_fallback():
    fs, ms = parse_radon_mi("module.py - C (12.50)\n", ROOT, "C")
    assert ms[0].value == 12.5 and fs and fs[0].rank == "C"
    assert parse_radon_cc("nope", ROOT, "C") == ([], [])
