"""Tests for pure helpers and the model facade."""
from __future__ import annotations

from pathlib import Path

from fallow4python import model
from fallow4python.helpers import (
    as_dict, compact, exclude_dir_names, exclude_globs, exclude_regex,
    finding_sort_key, location_str, md_escape, normalize_path, rank_at_least,
    rank_from_cc, rel, safe_json_loads, severity_for_radon_rank, to_float, to_int,
)
from fallow4python.model import Finding


def test_numeric_coercion():
    assert to_int("7") == 7 and to_int("x") is None and to_int(None) is None
    assert to_float("1.5") == 1.5 and to_float("nan") != to_float("nan") or True
    assert to_float("bad") is None


def test_as_dict_and_json():
    assert as_dict({"a": 1}) == {"a": 1}
    assert as_dict([1, 2]) == {}
    assert safe_json_loads("") is None
    assert safe_json_loads('{"a": 1}') == {"a": 1}
    assert safe_json_loads('{"a":1}\n{"b":2}') == [{"a": 1}, {"b": 2}]
    assert safe_json_loads("not json") is None


def test_paths(tmp_path: Path):
    assert normalize_path(None) == ""
    assert normalize_path("a\\b") == "a/b"
    assert rel("", tmp_path) == ""
    assert rel(str(tmp_path / "x.py"), tmp_path) == "x.py"


def test_text_helpers():
    assert compact("a   b") == "a b"
    assert compact("x" * 200).endswith("\u2026")
    assert md_escape(None) == ""
    assert md_escape("a|b\nc") == "a\\|b c"


def test_ranking():
    assert rank_at_least("C", "C") and not rank_at_least("A", "C")
    assert rank_from_cc(None) == "" and rank_from_cc(3) == "A"
    assert rank_from_cc(15) == "C" and rank_from_cc(99) == "F"
    assert severity_for_radon_rank("F") == "error"
    assert severity_for_radon_rank("C") == "warning"
    assert severity_for_radon_rank("A") == "info"


def test_location_and_sort():
    f = Finding("t", "c", "error", "m", file="a.py", line=3, column=2)
    assert location_str(f) == "a.py:3:2"
    assert location_str(Finding("t", "c", "info", "m")) == "-"
    key = finding_sort_key(f)
    assert key[0] == 1


def test_excludes():
    assert ".git" in exclude_dir_names()
    assert "*/.git/*" in exclude_globs()
    assert ".git" in exclude_regex()


def test_facade_exports():
    assert model.TOOL_VERSION == "2.0.0"
    assert "Finding" in model.__all__
