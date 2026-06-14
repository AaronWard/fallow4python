"""Orchestration: drive analyzers, coverage, and built-ins into one result."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from .analyzers import (
    detect_circular_imports, detect_duplication, discover_py_files,
)
from .coverage_run import coverage_via_tests
from .model import Finding, Metric, ToolRun, read_text
from .options import Options
from .parsers import parse_coverage
from .progress import LiveProgress
from .runner import run_spec
from .toolspecs import ToolSpec, _selected, _specs


def _run_specs(specs: List[ToolSpec], root: Path, target: Path, opts: Options,
               findings: List[Finding], metrics: List[Metric],
               prog: LiveProgress, runs: List[ToolRun]) -> None:
    for spec in specs:
        if not _selected(opts, spec.name):
            continue
        prog.start(spec.name)
        run = run_spec(spec, root, target, opts, findings, metrics)
        runs.append(run)
        prog.finish(spec.name, run.status, run.findings, note=run.detail)


def _coverage_text(root: Path, target: Path, opts: Options
                   ) -> Tuple[Optional[str], str, Optional[ToolRun]]:
    if opts.coverage_path:
        cov_path = Path(opts.coverage_path)
        if cov_path.is_file():
            return read_text(cov_path), str(cov_path), None
        return None, "", ToolRun("coverage", "skipped",
                                  f"file not found: {cov_path}")
    if opts.run_tests:
        text, detail = coverage_via_tests(root, target, opts)
        if text is None:
            return None, "", ToolRun("coverage", "skipped", detail)
        return text, detail, None
    return None, "", ToolRun("coverage", "skipped",
                             "tests skipped (--ignore-tests); coverage is n/a")


def _coverage_run(text: str, detail: str, root: Path, opts: Options,
                  findings: List[Finding], metrics: List[Metric]) -> ToolRun:
    try:
        fs, ms = parse_coverage(text, root, opts.coverage_min)
        findings += fs
        metrics += ms
        return ToolRun("coverage", "ingested", detail, len(fs))
    except Exception as exc:  # noqa: BLE001
        return ToolRun("coverage", "error", str(exc))


def _run_coverage(root: Path, target: Path, opts: Options,
                  findings: List[Finding], metrics: List[Metric],
                  prog: LiveProgress, runs: List[ToolRun]) -> None:
    if not _selected(opts, "coverage"):
        return
    prog.start("coverage")
    text, detail, run = _coverage_text(root, target, opts)
    if text is not None and run is None:
        run = _coverage_run(text, detail, root, opts, findings, metrics)
    if run is None:
        run = ToolRun("coverage", "skipped", "coverage not evaluated")
    runs.append(run)
    prog.finish("coverage", run.status, run.findings, note=run.detail)


def _run_builtin(name: str, detail: str, target: Path, opts: Options,
                 findings: List[Finding], prog: LiveProgress,
                 runs: List[ToolRun],
                 func: Callable[[Path, Sequence[Path]], List[Finding]]) -> None:
    if not _selected(opts, name):
        return
    prog.start(name)
    try:
        base = target if target.is_dir() else target.parent
        produced = func(base, discover_py_files(base))
        findings += produced
        run = ToolRun(name, "ran", detail, len(produced))
    except Exception as exc:  # noqa: BLE001
        run = ToolRun(name, "error", str(exc))
    runs.append(run)
    prog.finish(name, run.status, run.findings, note=run.detail)


def _planned_steps(specs: List[ToolSpec], opts: Options) -> List[str]:
    planned = [s.name for s in specs if _selected(opts, s.name)]
    for builtin in ("coverage", "duplication", "cycles"):
        if _selected(opts, builtin):
            planned.append(builtin)
    return planned


def orchestrate(root: Path, target: Path, opts: Options
                ) -> Tuple[List[Finding], List[Metric], List[ToolRun]]:
    findings: List[Finding] = []
    metrics: List[Metric] = []
    runs: List[ToolRun] = []
    specs = _specs(opts.radon_min_rank)
    with LiveProgress(_planned_steps(specs, opts),
                      enabled=not opts.no_color) as prog:
        _run_specs(specs, root, target, opts, findings, metrics, prog, runs)
        _run_coverage(root, target, opts, findings, metrics, prog, runs)
        _run_builtin("duplication", "built-in clone detector", target, opts,
                     findings, prog, runs, detect_duplication)
        _run_builtin("cycles", "built-in import-graph cycles", target, opts,
                     findings, prog, runs, detect_circular_imports)
    return findings, metrics, runs


def count_loc(target: Path) -> int:
    base = target if target.is_dir() else target.parent
    total = 0
    for path in discover_py_files(base):
        try:
            total += sum(1 for _ in path.open("r", encoding="utf-8",
                                              errors="replace"))
        except OSError:
            continue
    return total
