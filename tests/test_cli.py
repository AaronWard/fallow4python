"""End-to-end tests for cli.main across formats and edge cases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fallow4python.cli import _normalize_command, main
from fallow4python.options import build_arg_parser


def _pkg(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    return tmp_path


COMMON = ["--no-run", "--ignore-tests", "--no-color",
          "--tools", "ruff,duplication,cycles"]


def test_main_json(tmp_path, capsys):
    code = main(["scan", str(_pkg(tmp_path)), "--format", "json", *COMMON])
    out = capsys.readouterr().out
    doc = json.loads(out)
    assert code == 0 and doc["schema_version"] == "1.0"


@pytest.mark.parametrize("fmt", ["human", "markdown", "sarif"])
def test_main_formats(tmp_path, capsys, fmt):
    code = main(["scan", str(_pkg(tmp_path)), "--format", fmt, *COMMON])
    assert code == 0 and capsys.readouterr().out.strip()


def test_main_summary_command(tmp_path, capsys):
    code = main(["summary", str(_pkg(tmp_path)), *COMMON])
    assert code == 0 and "Health" in capsys.readouterr().out


def test_main_side_outputs(tmp_path):
    pkg = _pkg(tmp_path)
    jpath = tmp_path / "o.json"
    main(["scan", str(pkg), "--json-out", str(jpath),
          "--markdown-out", str(tmp_path / "o.md"),
          "--sarif-out", str(tmp_path / "o.sarif"), *COMMON])
    assert json.loads(jpath.read_text())["schema_version"] == "1.0"


def test_main_unknown_command(capsys):
    code = main(["definitely-not-a-command", "some-target"])
    assert code == 2 and "unknown command" in capsys.readouterr().err


def test_main_missing_target(capsys):
    code = main(["scan", "/no/such/path/here", *COMMON])
    assert code == 2 and "does not exist" in capsys.readouterr().err


def test_main_fail_on(tmp_path, capsys):
    # vulture-style dead code won't trigger; force via fail_on with a real finding
    pkg = _pkg(tmp_path)
    (pkg / "bad.py").write_text("import os\n", encoding="utf-8")
    code = main(["scan", str(pkg), "--fail-on", "error", "--format", "json",
                 "--no-run", "--ignore-tests", "--no-color",
                 "--tools", "cycles"])
    assert code == 0  # no errors present from cycles alone


def test_normalize_bare_path():
    args = build_arg_parser().parse_args(["src"])
    assert _normalize_command(args) is None
    assert args.command == "scan" and args.target == "src"
