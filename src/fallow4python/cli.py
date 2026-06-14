"""fallow4python command-line entry point.

Orchestrates the analyzers, optionally scopes findings to a git diff, builds
the report, writes any requested side outputs, and prints the chosen format.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .correlate import build_correlations
from .gitdiff import git_changed_lines, mark_changed, resolve_base
from .health import compute_health, compute_verdict, summarize
from .model import SEVERITY_ORDER, finding_sort_key
from .options import COMMAND_TOOLS, Options, args_to_options, build_arg_parser
from .orchestrate import count_loc, orchestrate
from .palette import Palette
from .render_human import render_human
from .render_summary import render_summary
from .render_machine import build_json_envelope, build_sarif
from .render_markdown import render_markdown


def _normalize_command(args) -> Optional[int]:
    """Treat a bare path as the target; reject unknown commands."""
    if args.command in COMMAND_TOOLS:
        return None
    if args.target in (".", None):
        args.target = args.command
        args.command = "scan"
        return None
    print(f"fallow4python: unknown command '{args.command}' "
          f"(choose from {', '.join(COMMAND_TOOLS)}), or pass a single path",
          file=sys.stderr)
    return 2


def _apply_scope(findings: List, opts: Options, root: Path
                 ) -> Tuple[List, str, bool]:
    if not opts.base:
        return findings, "", False
    base_ref = resolve_base(opts.base, root)
    if base_ref is None:
        return findings, (f"(requested base '{opts.base}' not found; "
                          f"analyzing full tree)"), False
    changed = git_changed_lines(base_ref, root)
    if changed is None:
        return findings, (f"(could not diff against '{base_ref}'; "
                          f"analyzing full tree)"), False
    findings = mark_changed(findings, changed)
    label = (f"Audit scope: {len(changed)} changed file(s) vs {base_ref} - "
             f"{sum(1 for f in findings if f.changed)} findings in changed code")
    return findings, label, True


def _build_report(findings: List, metrics: List, runs: List, opts: Options,
                  target: Path, scoped: bool) -> Dict[str, Any]:
    findings.sort(key=finding_sort_key)
    health = compute_health(findings, metrics, count_loc(target))
    verdict = None
    if opts.command == "audit" or scoped:
        verdict = compute_verdict(findings, scoped, opts.gate)
    return {
        "summary": summarize(findings, metrics, runs, health),
        "insights": build_correlations(findings, metrics),
        "verdict": verdict,
        "_findings": findings,
        "_metrics": metrics,
        "_max_per_section": opts.max_per_section,
    }


def _write_side_outputs(report: Dict[str, Any], opts: Options,
                        scope_label: str) -> None:
    if opts.json_out:
        Path(opts.json_out).write_text(
            json.dumps(build_json_envelope(report), indent=2, sort_keys=True),
            encoding="utf-8")
    if opts.markdown_out:
        Path(opts.markdown_out).write_text(
            render_markdown(report, scope_label), encoding="utf-8")
    if opts.sarif_out:
        Path(opts.sarif_out).write_text(
            json.dumps(build_sarif(report), indent=2), encoding="utf-8")


def _print_primary(report: Dict[str, Any], opts: Options,
                   scope_label: str) -> None:
    use_color = (not opts.no_color) and sys.stdout.isatty()
    if opts.fmt == "json":
        print(json.dumps(build_json_envelope(report), indent=2, sort_keys=True))
    elif opts.fmt == "markdown":
        print(render_markdown(report, scope_label))
    elif opts.fmt == "sarif":
        print(json.dumps(build_sarif(report), indent=2))
    elif opts.command == "summary":
        print(render_summary(report, Palette(use_color), scope_label))
    else:
        print(render_human(report, Palette(use_color), scope_label))


def _exit_code(report: Dict[str, Any], opts: Options) -> int:
    verdict = report.get("verdict")
    if verdict is not None:
        return 1 if verdict["verdict"] == "fail" else 0
    if opts.fail_on != "none":
        threshold = SEVERITY_ORDER[opts.fail_on]
        if any(SEVERITY_ORDER.get(f.severity, 0) >= threshold
               for f in report["_findings"]):
            return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    early = _normalize_command(args)
    if early is not None:
        return early
    opts = args_to_options(args)
    target = Path(opts.target).resolve()
    if not target.exists():
        print(f"fallow4python: target does not exist: {target}", file=sys.stderr)
        return 2
    root = target if target.is_dir() else target.parent
    findings, metrics, runs = orchestrate(root, target, opts)
    findings, scope_label, scoped = _apply_scope(findings, opts, root)
    report = _build_report(findings, metrics, runs, opts, target, scoped)
    _write_side_outputs(report, opts, scope_label)
    _print_primary(report, opts, scope_label)
    return _exit_code(report, opts)


if __name__ == "__main__":
    raise SystemExit(main())
