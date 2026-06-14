"""Integration tests: drive the CLI end-to-end and exercise every renderer.

These run in ``--no-run`` mode so no external analyzers (ruff/mypy/...) are
needed — only the built-in duplication + circular-import analyzers run — which
keeps the tests hermetic while still covering main(), orchestrate()'s skip
paths, summarize(), the correlation engine, and all four output renderers.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from fallow4python.cli import (
    Finding,
    Metric,
    Palette,
    build_sarif,
    compute_health,
    main,
    render_human,
    render_markdown,
    render_summary,
    summarize,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A tiny package with a circular import and a duplicated block."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    block = (
        "    value = record.get('value')\n"
        "    total = value * 2\n"
        "    label = str(total) + '!'\n"
        "    extra = label.upper() + label.lower()\n"
        "    result = {'label': label, 'total': total, 'extra': extra}\n"
        "    return result\n"
    )
    (pkg / "a.py").write_text(
        "from pkg import b\n\ndef handle(record):\n" + block)
    (pkg / "b.py").write_text(
        "from pkg import a\n\ndef process(record):\n" + block)
    return tmp_path


def test_main_human_format(project, capsys):
    rc = main(["--no-run", "--no-color", str(project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Health" in out
    # built-in analyzers should still flag the seeded problems
    assert "Circular import" in out or "circular" in out.lower()


def test_main_summary_subcommand(project, capsys):
    rc = main(["summary", str(project), "--no-run", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Health" in out


def test_main_json_format_is_valid(project, capsys):
    rc = main(["--no-run", "--format", "json", str(project)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["schema_version"]
    assert "findings" in data and "summary" in data and "metrics" in data


def test_main_markdown_format(project, capsys):
    rc = main(["--no-run", "--format", "markdown", str(project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.lstrip().startswith("#")
    assert "## Health" in out and "## Findings" in out


def test_main_sarif_format(project, capsys):
    rc = main(["--no-run", "--format", "sarif", str(project)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["tool"]["driver"]["name"] == "fallow4python"


def test_main_fail_on_error_exit_code(project, capsys):
    # the seeded circular import is an error-level finding -> --fail-on error
    # should make the process exit non-zero on a full scan.
    rc = main(["--no-run", "--no-color", "--fail-on", "error", str(project)])
    capsys.readouterr()
    assert rc != 0


def test_main_writes_output_files(project, tmp_path, capsys):
    md = tmp_path / "out.md"
    js = tmp_path / "out.json"
    rc = main(["--no-run", "--markdown-out", str(md), "--json-out", str(js),
               "--no-color", str(project)])
    capsys.readouterr()
    assert rc == 0
    assert md.exists() and md.read_text().startswith("#")
    assert js.exists() and json.loads(js.read_text())["schema_version"]


def test_main_nonexistent_target():
    rc = main(["--no-run", "/no/such/path/here"])
    assert rc != 0


@pytest.mark.skipif(
    importlib.util.find_spec("coverage") is None
    or importlib.util.find_spec("pytest") is None,
    reason="needs coverage + pytest installed")
def test_run_tests_populates_coverage(tmp_path, capsys):
    """--run-tests should execute the suite under coverage and fold the result
    into the report without any --coverage flag."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "mod.py").write_text("def add(a, b):\n    return a + b\n")
    (proj / "test_mod.py").write_text(
        "from mod import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    rc = main(["--run-tests", "--no-run", "--format", "json", str(proj)])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    cov = [m for m in data["metrics"] if m["name"] == "total-line-coverage"]
    assert cov, "coverage metric should be present after --run-tests"
    assert cov[0]["value"] > 0


# --- renderers exercised directly with a rich report (insights + verdict) --- #

def _rich_report():
    findings = [
        Finding(tool="mypy", category="typing", severity="error",
                message="bad type", file="m.py", line=3),
        Finding(tool="radon", category="complexity", severity="error",
                rule="cyclomatic-complexity", message="too complex",
                file="m.py", line=10, rank="E", symbol="big"),
        Finding(tool="vulture", category="dead-code", severity="info",
                rule="dead-code", message="unused 'x'", file="m.py",
                line=20, symbol="x", confidence=90),
    ]
    metrics = [
        Metric(tool="coverage", name="total-line-coverage", value=40.0),
        Metric(tool="coverage", name="file-line-coverage", value=5.0, file="m.py"),
        Metric(tool="radon", name="maintainability-index", value=60.0, file="m.py"),
        Metric(tool="radon", name="complexity-functions", value=4.0),
    ]
    from fallow4python.cli import build_correlations
    health = compute_health(findings, metrics, loc=400)
    insights = build_correlations(findings, metrics)
    summary = summarize(findings, metrics, [], health)
    return {
        "_findings": findings,
        "_metrics": metrics,
        "insights": insights,
        "summary": summary,
        "verdict": None,
        "_max_per_section": 100,
    }


def test_render_markdown_contains_all_sections():
    md = render_markdown(_rich_report(), scope_label="")
    for heading in ("## Health", "## Insights", "## Summary",
                    "## Metrics", "## Findings"):
        assert heading in md


def test_render_human_and_summary_run():
    rep = _rich_report()
    pal = Palette(enabled=False)
    human = render_human(rep, pal, scope_label="")
    summ = render_summary(rep, pal, scope_label="")
    assert "Health" in human
    assert "Health" in summ


def test_sarif_levels_map_correctly():
    sarif = build_sarif(_rich_report())
    levels = {r["level"] for r in sarif["runs"][0]["results"]}
    # error -> error, info -> note
    assert "error" in levels and "note" in levels