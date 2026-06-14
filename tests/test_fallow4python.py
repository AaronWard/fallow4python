"""Unit tests for fallow4python.

These exercise the pure logic that does the real work: the per-tool parsers,
the two built-in analyzers (duplication + circular imports), the correlation
engine, the health score, the audit verdict, and the report serializers.
External-tool orchestration and git are intentionally not unit-tested here
(they shell out); the parsers are tested directly with captured tool output.
"""
from pathlib import Path

import pytest

from fallow4python.cli import (
    Finding,
    Metric,
    build_correlations,
    build_json_envelope,
    build_sarif,
    compute_health,
    compute_verdict,
    detect_circular_imports,
    detect_duplication,
    exclude_dir_names,
    exclude_globs,
    exclude_regex,
    normalize_path,
    parse_coverage,
    parse_deptry,
    parse_radon_cc,
    parse_ruff,
    rel,
    safe_json_loads,
    severity_for_deptry,
    summarize,
    to_int,
)

ROOT = Path("/project")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def test_to_int_handles_junk():
    assert to_int("12") == 12
    assert to_int(12) == 12
    assert to_int(None) is None
    assert to_int("not-a-number") is None


def test_safe_json_loads_returns_none_on_garbage():
    assert safe_json_loads("not json") is None
    assert safe_json_loads('{"a": 1}') == {"a": 1}


def test_normalize_and_rel_paths():
    assert normalize_path("a\\b\\c.py") == "a/b/c.py"
    assert rel("/project/src/mod.py", ROOT) == "src/mod.py"
    # paths outside root come back as a relative path with parent segments
    assert rel("/elsewhere/mod.py", ROOT) == "../elsewhere/mod.py"


def test_severity_for_deptry():
    # missing dependency is an error; the rest are warnings
    assert severity_for_deptry("DEP001") == "error"
    assert severity_for_deptry("DEP002") == "warning"
    assert severity_for_deptry("DEP003") == "warning"


def test_exclude_helpers_include_build_and_venv():
    names = exclude_dir_names().split(",")
    assert "build" in names and ".venv" in names and "dist" in names
    globs = exclude_globs()
    assert "build/*" in globs and "*/build/*" in globs
    # mypy-style regex should match a build path segment
    import re
    rx = re.compile(exclude_regex())
    assert rx.search("build/lib/pkg/mod.py")
    assert rx.search("src/pkg/build/x.py")
    assert not rx.search("src/pkg/mod.py")


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #

def test_parse_ruff_json():
    text = """[
      {"code": "F401", "message": "'os' imported but unused",
       "filename": "/project/src/m.py",
       "location": {"row": 3, "column": 8}}
    ]"""
    findings, metrics = parse_ruff(text, ROOT)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "ruff" and f.category == "lint" and f.rule == "F401"
    assert f.file == "src/m.py" and f.line == 3


def test_parse_deptry_no_double_count():
    """Regression test for the recursive-JSON double-count bug.

    deptry emits one object per finding with a nested ``error`` sub-dict. The
    parser must NOT also emit a second finding for that inner ``error`` dict.
    """
    text = """[
      {"error": {"code": "DEP002",
                 "message": "'ruff' defined as a dependency but not used"},
       "module": "ruff", "location": {"file": "pyproject.toml"}},
      {"error": {"code": "DEP002",
                 "message": "'mypy' defined as a dependency but not used"},
       "module": "mypy", "location": {"file": "pyproject.toml"}}
    ]"""
    findings, _ = parse_deptry(text, ROOT)
    assert len(findings) == 2  # exactly one per dependency, not four
    assert all(f.file.endswith("pyproject.toml") for f in findings)
    assert all(f.tool == "deptry" and f.rule == "DEP002" for f in findings)
    # no phantom empty-file rows
    assert not any(f.file in ("", "-") for f in findings)


def test_parse_radon_cc_findings_and_total_metric():
    # radon cc -j shape: {file: [ {name, rank, complexity, lineno, type}, ... ]}
    text = """{
      "/project/src/m.py": [
        {"name": "simple", "rank": "A", "complexity": 2, "lineno": 1, "type": "function"},
        {"name": "tangled", "rank": "E", "complexity": 35, "lineno": 10, "type": "function"}
      ]
    }"""
    findings, metrics = parse_radon_cc(text, ROOT, min_rank="C")
    # only the rank-E function is flagged at threshold C
    cc = [f for f in findings if f.rule == "cyclomatic-complexity"]
    assert len(cc) == 1
    assert cc[0].symbol == "tangled" and cc[0].rank == "E"
    # a total-functions metric must be emitted (drives the health score)
    total = [m for m in metrics if m.name == "complexity-functions"]
    assert total and total[0].value == 2


def test_parse_coverage_metrics_and_threshold():
    text = """{
      "totals": {"percent_covered": 42.0},
      "files": {
        "/project/src/m.py": {"summary": {"percent_covered": 42.0, "missing_lines": 7}}
      }
    }"""
    findings, metrics = parse_coverage(text, ROOT, min_percent=80.0)
    assert any(m.name == "total-line-coverage" and m.value == 42.0 for m in metrics)
    assert any(m.name == "file-line-coverage" and m.file == "src/m.py" for m in metrics)
    # 42% is >10 below the 80 threshold -> error severity
    cov_findings = [f for f in findings if f.category == "coverage"]
    assert cov_findings and any(f.severity == "error" for f in cov_findings)


# --------------------------------------------------------------------------- #
# Built-in analyzers
# --------------------------------------------------------------------------- #

def test_detect_duplication(tmp_path):
    block = (
        "def handler(record):\n"
        "    value = record.get('value')\n"
        "    total = value * 2\n"
        "    label = str(total) + '!'\n"
        "    result = {'label': label, 'total': total}\n"
        "    return result\n"
    )
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("import os\n\n" + block)
    b.write_text("import sys\n\n" + block)
    findings = detect_duplication(tmp_path, [a, b])
    assert findings, "expected a clone family to be detected"
    assert all(f.category == "duplication" for f in findings)


def test_detect_circular_imports(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from pkg import b\n")
    (pkg / "b.py").write_text("from pkg import a\n")
    files = [pkg / "__init__.py", pkg / "a.py", pkg / "b.py"]
    findings = detect_circular_imports(tmp_path, files)
    assert findings, "expected a circular import to be detected"
    assert findings[0].rule == "circular-import"


def test_no_circular_import_when_acyclic(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from pkg import b\n")
    (pkg / "b.py").write_text("x = 1\n")
    files = [pkg / "__init__.py", pkg / "a.py", pkg / "b.py"]
    assert detect_circular_imports(tmp_path, files) == []


# --------------------------------------------------------------------------- #
# Health score
# --------------------------------------------------------------------------- #

def _mi(file, value):
    return Metric(tool="radon", name="maintainability-index", value=value, file=file)


def test_compute_health_all_components():
    metrics = [
        Metric(tool="coverage", name="total-line-coverage", value=80.0),
        _mi("m.py", 80.0),
        Metric(tool="radon", name="complexity-functions", value=10.0),
    ]
    findings = [
        Finding(tool="radon", category="complexity", severity="error",
                rule="cyclomatic-complexity", message="x", rank="E"),
    ]
    h = compute_health(findings, metrics, loc=1000)
    comps = h["components"]
    assert comps["coverage"] == 80.0
    assert comps["maintainability"] == 80.0
    # 1 of 10 functions flagged -> 90% complexity health
    assert comps["complexity"] == 90.0
    assert h["grade"] in {"A", "B", "C", "D", "F"}
    assert 0 <= h["score"] <= 100


def test_compute_health_renormalizes_when_coverage_missing():
    """With no coverage metric, the score must still be out of 100 (the 0.30
    coverage weight is dropped and the rest renormalize)."""
    metrics = [
        _mi("m.py", 70.0),
        Metric(tool="radon", name="complexity-functions", value=10.0),
    ]
    h = compute_health([], metrics, loc=1000)
    assert h["components"]["coverage"] is None
    # maintainability 70 (.25) + complexity 100 (.20) + cleanliness 100 (.25)
    # over weight 0.70 = (17.5 + 20 + 25) / 0.70 = 89.3
    assert h["score"] == pytest.approx(89.3, abs=0.2)


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #

def test_verdict_full_scan():
    findings = [Finding(tool="mypy", category="typing", severity="error", message="x")]
    v = compute_verdict(findings, scoped_to_changes=False, gate="changed")
    assert v["verdict"] == "fail"
    v2 = compute_verdict(
        [Finding(tool="ruff", category="lint", severity="warning", message="x")],
        scoped_to_changes=False, gate="changed")
    assert v2["verdict"] == "warn"
    assert compute_verdict([], scoped_to_changes=False, gate="changed")["verdict"] == "pass"


def test_verdict_changed_scope_new_error_fails():
    findings = [Finding(tool="mypy", category="typing", severity="error",
                        message="bad", line=10, changed=True)]
    v = compute_verdict(findings, scoped_to_changes=True, gate="changed")
    assert v["verdict"] == "fail" and v["new_errors"] == 1


def test_verdict_inherited_error_does_not_fail_changed_gate():
    findings = [Finding(tool="mypy", category="typing", severity="error",
                        message="old", line=10, changed=False)]
    v = compute_verdict(findings, scoped_to_changes=True, gate="changed")
    assert v["verdict"] == "pass"
    assert v["inherited_errors"] == 1 and v["new_errors"] == 0
    # but the 'all' gate should fail on inherited errors
    v_all = compute_verdict(findings, scoped_to_changes=True, gate="all")
    assert v_all["verdict"] == "fail"


# --------------------------------------------------------------------------- #
# Correlation engine
# --------------------------------------------------------------------------- #

def test_deletion_candidate_insight():
    findings = [Finding(tool="vulture", category="dead-code", severity="info",
                        rule="dead-code", message="unused function 'old'",
                        symbol="old", file="src/m.py", line=5, confidence=90)]
    metrics = [Metric(tool="coverage", name="file-line-coverage",
                      value=5.0, file="src/m.py")]
    insights = build_correlations(findings, metrics)
    assert any(i.kind == "deletion-candidate" for i in insights)


def test_concentrated_problems_insight():
    findings = [
        Finding(tool="ruff", category="lint", severity="warning", message="a", file="src/m.py"),
        Finding(tool="mypy", category="typing", severity="error", message="b", file="src/m.py"),
        Finding(tool="vulture", category="dead-code", severity="info", message="c", file="src/m.py"),
    ]
    insights = build_correlations(findings, [])
    worst = [i for i in insights if i.kind == "worst-offender"]
    assert worst and worst[0].file == "src/m.py"


def test_circular_import_insight():
    findings = [Finding(tool="fallow4python", category="architecture", severity="error",
                        rule="circular-import", message="cycle: a -> b -> a", file="a.py")]
    insights = build_correlations(findings, [])
    assert any(i.kind == "circular-import" for i in insights)


# --------------------------------------------------------------------------- #
# Summary + serializers
# --------------------------------------------------------------------------- #

def _sample_report():
    findings = [
        Finding(tool="mypy", category="typing", severity="error", message="e", file="m.py", line=1),
        Finding(tool="ruff", category="lint", severity="warning", message="w", file="m.py", line=2),
    ]
    metrics = [Metric(tool="radon", name="maintainability-index", value=70.0, file="m.py")]
    health = compute_health(findings, metrics, loc=500)
    summary = summarize(findings, metrics, [], health)
    return {
        "_findings": findings,
        "_metrics": metrics,
        "insights": [],
        "summary": summary,
        "verdict": None,
    }


def test_summarize_counts():
    rep = _sample_report()
    s = rep["summary"]
    assert s["by_severity"]["error"] == 1
    assert s["by_severity"]["warning"] == 1
    assert s["max_severity"] == "error"
    assert s["finding_count"] == 2


def test_json_envelope_has_schema_version():
    env = build_json_envelope(_sample_report())
    assert env["schema_version"]
    assert "findings" in env and "summary" in env


def test_sarif_structure():
    sarif = build_sarif(_sample_report())
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "fallow4python"
    assert len(run["results"]) == 2
