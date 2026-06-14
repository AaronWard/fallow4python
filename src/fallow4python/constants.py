"""Shared constants and ordering tables."""
from __future__ import annotations

SCHEMA_VERSION = "1.0"
TOOL_VERSION = "2.0.0"

SEVERITY_ORDER = {"info": 1, "warning": 2, "error": 3}
RADON_RANK_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
    "build", "dist", ".eggs", "site-packages", ".quality", ".idea", ".vscode",
}
