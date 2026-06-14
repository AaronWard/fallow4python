"""Public parser API: external tool output -> (findings, metrics).

Implementations live in focused submodules (lint, deps, radon, quality); this
module re-exports them as one stable namespace for the orchestrator.
"""
from .parse_deps import parse_deptry, severity_for_deptry
from .parse_lint import parse_mypy, parse_ruff, parse_vulture, severity_for_ruff
from .parse_quality import parse_coverage, parse_import_linter, parse_xenon
from .parse_radon import parse_radon_cc, parse_radon_mi

__all__ = [
    "parse_ruff", "parse_mypy", "parse_vulture", "parse_deptry",
    "parse_radon_cc", "parse_radon_mi", "parse_xenon", "parse_import_linter",
    "parse_coverage", "severity_for_ruff", "severity_for_deptry",
]
