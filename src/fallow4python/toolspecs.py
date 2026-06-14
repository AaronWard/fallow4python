"""Specifications for each external analyzer and small selection helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .model import (
    Finding, Metric, exclude_dir_names, exclude_globs, exclude_regex, read_text,
)
from .options import Options
from .parsers import (
    parse_deptry, parse_import_linter, parse_mypy, parse_radon_cc,
    parse_radon_mi, parse_ruff, parse_vulture, parse_xenon,
)

Parser = Callable[[str, Path], Tuple[List[Finding], List[Metric]]]


@dataclass
class ToolSpec:
    name: str
    executable: str
    argv: Callable[[Path], List[str]]
    parser: Parser
    needs_config: bool = False
    output_to_file: Optional[str] = None


def _specs(min_rank: str) -> List[ToolSpec]:
    return [
        ToolSpec("ruff", "ruff",
                 lambda t: ["ruff", "check", "--output-format=json",
                            "--exclude", exclude_globs(), str(t)], parse_ruff),
        ToolSpec("mypy", "mypy",
                 lambda t: ["mypy", "--no-error-summary", "--show-column-numbers",
                            "--no-color-output", "--hide-error-context",
                            "--exclude", exclude_regex(), str(t)], parse_mypy),
        ToolSpec("vulture", "vulture",
                 lambda t: ["vulture", "--exclude", exclude_globs(), str(t)],
                 parse_vulture),
        ToolSpec("radon-cc", "radon",
                 lambda t: ["radon", "cc", "-i", exclude_dir_names(), "-j", str(t)],
                 lambda text, r: parse_radon_cc(text, r, min_rank)),
        ToolSpec("radon-mi", "radon",
                 lambda t: ["radon", "mi", "-i", exclude_dir_names(), "-j", str(t)],
                 lambda text, r: parse_radon_mi(text, r, min_rank)),
        ToolSpec("deptry", "deptry",
                 lambda t: ["deptry", ".", "--json-output", "{OUTFILE}"],
                 parse_deptry, output_to_file="deptry"),
        ToolSpec("xenon", "xenon",
                 lambda t: ["xenon", "--max-absolute", "B", "--max-modules", "A",
                            "--max-average", "A", str(t)], parse_xenon),
        ToolSpec("import-linter", "lint-imports",
                 lambda t: ["lint-imports"], parse_import_linter,
                 needs_config=True),
    ]


INGEST_FILENAMES = {
    "ruff": ["ruff.json", "ruff.txt"],
    "mypy": ["mypy.json", "mypy.txt"],
    "vulture": ["vulture.txt"],
    "radon-cc": ["radon_cc.json", "radon-cc.json"],
    "radon-mi": ["radon_mi.json", "radon-mi.json"],
    "deptry": ["deptry.json", "deptry.txt"],
    "xenon": ["xenon.txt"],
    "import-linter": ["import_linter.txt", "import-linter.txt"],
}


def _import_linter_configured(root: Path) -> bool:
    for name in ("setup.cfg", "pyproject.toml", ".importlinter",
                 "importlinter.ini"):
        p = root / name
        if p.is_file() and "importlinter" in read_text(p).replace("-", "").lower():
            return True
    return (root / ".importlinter").is_file()


def _selected(opts: Options, name: str) -> bool:
    return not opts.tools or name in opts.tools
