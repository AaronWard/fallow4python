"""Cover cycles.py: relative imports, __init__ modules, syntax errors, SCC."""
from __future__ import annotations

import ast
from pathlib import Path

from fallow4python.analyzers import discover_py_files
from fallow4python.cycles import (
    _import_targets, _module_name, _resolve_relative, detect_circular_imports,
)


def test_module_name_init(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    init = pkg / "__init__.py"
    init.write_text("", encoding="utf-8")
    assert _module_name(init, tmp_path) == "pkg"
    assert _module_name(pkg / "m.py", tmp_path) == "pkg.m"


def test_resolve_relative():
    assert _resolve_relative("a.b.c", "x", 0) == "x"
    assert _resolve_relative("a", None, 3) is None
    assert _resolve_relative("a.b.c", "d", 1) == "a.b.d"
    assert _resolve_relative("a.b", None, 2) is None or _resolve_relative(
        "a.b", None, 2) == ""


def test_import_targets_from():
    node = ast.parse("from .sib import thing").body[0]
    assert "pkg.sib" in _import_targets(node, "pkg.mod")


def test_detect_circular_and_syntax(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("from pkg import a\n", encoding="utf-8")
    (pkg / "broken.py").write_text("def (oops\n", encoding="utf-8")
    files = discover_py_files(tmp_path)
    found = detect_circular_imports(tmp_path, files)
    assert any(f.rule == "circular-import" for f in found)
