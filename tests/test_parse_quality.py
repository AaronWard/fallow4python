"""Tests for parse_quality: xenon, import-linter, coverage."""
from __future__ import annotations

import json
from pathlib import Path

from fallow4python.parse_quality import (
    parse_coverage, parse_import_linter, parse_xenon,
)

ROOT = Path("/repo")


def test_xenon_file_and_generic():
    fs, _ = parse_xenon("/repo/a.py:3:0 block is too complex (C)", ROOT)
    assert fs and fs[0].file == "a.py" and fs[0].line == 3
    fs2, _ = parse_xenon("average complexity is too high", ROOT)
    assert fs2 and fs2[0].severity == "error"


def test_import_linter():
    fs, _ = parse_import_linter("Contract 'layers' broken: illegal import", ROOT)
    assert fs and fs[0].category == "architecture"
    assert parse_import_linter("all good", ROOT)[0] == []


def test_coverage_totals_and_files():
    data = {"totals": {"percent_covered": 72.0},
            "files": {"/repo/b.py": {"summary": {"percent_covered": 40.0,
                                                  "missing_lines": 6}}}}
    fs, ms = parse_coverage(json.dumps(data), ROOT, 80.0)
    assert any(m.name == "total-line-coverage" for m in ms)
    assert any(f.rule == "coverage-file" for f in fs)


def test_coverage_bad_json():
    fs, _ = parse_coverage("not json", ROOT, 80.0)
    assert fs and fs[0].rule == "parse-error"


def test_coverage_above_threshold_no_finding():
    data = {"totals": {"percent_covered": 95.0}, "files": {}}
    fs, ms = parse_coverage(json.dumps(data), ROOT, 80.0)
    assert fs == [] and ms[0].value == 95.0
