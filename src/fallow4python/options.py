"""Command-line options: dataclass, argument parser, and per-command presets."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Optional, Set


@dataclass
class Options:
    command: str
    target: str
    base: Optional[str]
    tools: Optional[Set[str]]
    from_dir: Optional[str]
    explicit_inputs: Dict[str, str]
    coverage_path: Optional[str]
    coverage_min: float
    run_tests: bool
    test_command: str
    radon_min_rank: str
    fail_on: str
    gate: str
    fmt: str
    json_out: Optional[str]
    markdown_out: Optional[str]
    sarif_out: Optional[str]
    max_per_section: int
    no_run: bool
    no_color: bool
    timeout: int


COMMAND_TOOLS: Dict[str, Optional[Set[str]]] = {
    "scan": None,
    "audit": None,
    "health": {"radon-cc", "radon-mi", "xenon", "duplication"},
    "dead-code": {"vulture", "deptry", "duplication"},
    "summary": None,
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fallow4python",
        description="Codebase intelligence for Python: orchestrate quality "
                    "tools, correlate the signals, audit changed code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="scan",
                        help="scan (default), audit, health, dead-code, "
                             "summary; or a path to analyze")
    parser.add_argument("target", nargs="?", default=".",
                        help="path to analyze (default: current directory)")
    parser.add_argument("--base", help="git base ref for change-scoped audit")
    parser.add_argument("--tools", help="comma-separated subset of tools to run")
    parser.add_argument("--from-dir",
                        help="ingest pre-saved tool outputs from this directory")
    parser.add_argument("--ruff")
    parser.add_argument("--mypy")
    parser.add_argument("--vulture")
    parser.add_argument("--radon-cc")
    parser.add_argument("--radon-mi")
    parser.add_argument("--deptry")
    parser.add_argument("--xenon")
    parser.add_argument("--import-linter")
    parser.add_argument("--coverage", help="path to coverage.py JSON report")
    parser.add_argument("--ignore-tests", action="store_true",
                        help="do NOT run the test suite for coverage")
    parser.add_argument("--test-command", default="pytest",
                        help="module + args run under `coverage run -m`")
    parser.add_argument("--coverage-min", type=float, default=80.0)
    parser.add_argument("--radon-min-rank", default="C", choices=list("ABCDEF"))
    parser.add_argument("--fail-on", default="none",
                        choices=["none", "info", "warning", "error"],
                        help="exit non-zero if any finding reaches this severity")
    parser.add_argument("--gate", default="changed", choices=["changed", "all"],
                        help="audit gate scope")
    parser.add_argument("--format", dest="fmt", default="human",
                        choices=["human", "markdown", "json", "sarif"])
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    parser.add_argument("--sarif-out")
    parser.add_argument("--max-per-section", type=int, default=100)
    parser.add_argument("--no-run", action="store_true",
                        help="do not run tools; only ingest saved outputs")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--timeout", type=int, default=300,
                        help="per-tool subprocess timeout in seconds")
    return parser


_EXPLICIT = ("ruff", "mypy", "vulture", "radon_cc", "radon_mi", "deptry",
             "xenon", "import_linter")


def _explicit_inputs(args: argparse.Namespace) -> Dict[str, str]:
    explicit: Dict[str, str] = {}
    for attr in _EXPLICIT:
        val = getattr(args, attr)
        if val:
            explicit[attr.replace("_", "-")] = val
    return explicit


def args_to_options(args: argparse.Namespace) -> Options:
    tools: Optional[Set[str]] = None
    if args.tools:
        tools = {t.strip() for t in args.tools.split(",") if t.strip()}
    base = args.base
    if args.command == "audit" and not base:
        base = "origin/main"
    if tools is None:
        tools = COMMAND_TOOLS.get(args.command)
    return Options(
        command=args.command, target=args.target, base=base, tools=tools,
        from_dir=args.from_dir, explicit_inputs=_explicit_inputs(args),
        coverage_path=args.coverage, coverage_min=args.coverage_min,
        run_tests=not args.ignore_tests, test_command=args.test_command,
        radon_min_rank=args.radon_min_rank, fail_on=args.fail_on, gate=args.gate,
        fmt=args.fmt, json_out=args.json_out, markdown_out=args.markdown_out,
        sarif_out=args.sarif_out, max_per_section=args.max_per_section,
        no_run=args.no_run, no_color=args.no_color, timeout=args.timeout,
    )
