"""Tests for parse_deps: deptry."""
from __future__ import annotations

import json
from pathlib import Path

from fallow4python.parse_deps import parse_deptry, severity_for_deptry

ROOT = Path("/repo")


def test_severity():
    assert severity_for_deptry("DEP001") == "error"
    assert severity_for_deptry("DEP002") == "warning"


def test_deptry_json_nested_and_dedup():
    data = {"results": [
        {"error": {"code": "DEP002", "message": "unused 'x'"}, "module": "x"},
        {"error": {"code": "DEP002", "message": "unused 'x'"}, "module": "x"},
    ]}
    fs, _ = parse_deptry(json.dumps(data), ROOT)
    assert len(fs) == 1 and fs[0].rule == "DEP002"


def test_deptry_ignores_non_findings():
    # bare code dict without module/location/error is not a real finding
    fs, _ = parse_deptry(json.dumps({"code": "DEP002"}), ROOT)
    assert fs == []


def test_deptry_text_fallback():
    fs, _ = parse_deptry("pyproject.toml: DEP003 transitive 'y'", ROOT)
    assert fs and fs[0].rule == "DEP003"
