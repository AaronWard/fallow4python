"""Human (terminal) and one-screen summary renderers."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .model import Finding, SEVERITY_ORDER, compact
from .palette import Palette, SEV_MARK

_SECTION_TITLES = [
    ("dead-code", "Dead code"), ("duplication", "Duplication"),
    ("complexity", "Complexity"), ("maintainability", "Maintainability"),
    ("dependencies", "Dependencies"), ("architecture", "Architecture"),
    ("typing", "Typing"), ("lint", "Lint"), ("coverage", "Coverage"),
]


def _grade_color(p: Palette, grade: str):
    if grade in ("A", "B"):
        return p.green
    if grade in ("C", "D"):
        return p.yellow
    return p.red


def _health_lines(p: Palette, s: Dict[str, Any]) -> List[str]:
    health = s["health"]
    grade = health.get("grade", "n/a")
    score = health.get("score")
    grade_c = _grade_color(p, grade)(f"{grade}")
    score_s = f"{score}" if score is not None else "n/a"
    out = [f"  Health: {grade_c}  ({score_s}/100)   "
           + p.dim(f"{s['finding_count']} findings, {health.get('loc', 0)} LOC")]
    parts = [f"{k} {v:.0f}" for k, v in health.get("components", {}).items()
             if v is not None]
    if parts:
        out.append(p.dim("          " + " | ".join(parts)))
    out.append("")
    return out


def _category_severities(findings: Sequence[Finding]) -> Dict[str, str]:
    cat_sev: Dict[str, str] = {}
    for f in findings:
        cur = cat_sev.get(f.category)
        if cur is None or SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[cur]:
            cat_sev[f.category] = f.severity
    return cat_sev


def _category_lines(p: Palette, s: Dict[str, Any],
                    findings: Sequence[Finding]) -> List[str]:
    by_cat = s["by_category"]
    cat_sev = _category_severities(findings)
    out: List[str] = []
    for cat, title in _SECTION_TITLES:
        n = by_cat.get(cat, 0)
        if not n:
            continue
        mark = SEV_MARK.get(cat_sev.get(cat, "info"), "-")
        colorize = p.red if mark == "x" else p.yellow if mark == "!" else p.dim
        out.append(f"  {colorize(mark)} {title:<16} {n}")
    out.append("")
    return out


def _insight_lines(p: Palette, insights: Sequence) -> List[str]:
    if not insights:
        return []
    out = [p.bold("  Insights")]
    for ins in insights[:12]:
        mk = SEV_MARK.get(ins.severity, "-")
        c = p.red if mk == "x" else p.yellow if mk == "!" else p.blue
        loc = (f" ({ins.file}{':' + str(ins.line) if ins.line else ''})"
               if ins.file else "")
        out.append(f"  {c(mk)} {ins.title}{p.dim(loc)}")
        out.append(p.dim(f"      {compact(ins.detail, 150)}"))
    if len(insights) > 12:
        out.append(p.dim(f"      ... {len(insights) - 12} more insights "
                         f"(see --json-out)"))
    out.append("")
    return out


def _hotspot_lines(p: Palette, s: Dict[str, Any]) -> List[str]:
    if not s["top_files"]:
        return []
    out = [p.bold("  Hotspot files")]
    for fname, count in s["top_files"][:6]:
        out.append(f"    {count:>3}  {fname}")
    out.append("")
    return out


def _verdict_detail(verdict: Dict[str, Any]) -> str:
    if verdict.get("scoped_to_changes"):
        return (f"{verdict['new_errors']} new error(s), "
                f"{verdict['changed_warnings']} warning(s) on changed lines; "
                f"{verdict['touched_errors']} touched + "
                f"{verdict['inherited_errors']} inherited error(s)")
    return (f"{verdict['new_errors']} error(s), "
            f"{verdict['changed_warnings']} warning(s)")


def _verdict_lines(p: Palette, report: Dict[str, Any]) -> List[str]:
    verdict = report.get("verdict")
    if not verdict:
        return []
    v = verdict["verdict"]
    vc = p.green if v == "pass" else p.yellow if v == "warn" else p.red
    return [f"  Verdict: {vc(v.upper())}   " + p.dim(_verdict_detail(verdict)), ""]


def _provenance_lines(p: Palette, s: Dict[str, Any]) -> List[str]:
    runs = s["tool_runs"]
    groups = [
        ("used", [r for r in runs if r["status"] in ("ran", "ingested")]),
        ("skipped", [r for r in runs if r["status"] == "skipped"]),
        ("errored", [r for r in runs if r["status"] == "error"]),
    ]
    out: List[str] = []
    for label, rs in groups:
        if rs:
            out.append(p.dim("  " + label + ": "
                             + ", ".join(r["name"] for r in rs)))
    return out


def render_human(report: Dict[str, Any], palette: Palette,
                 scope_label: str) -> str:
    s = report["summary"]
    lines = []
    if scope_label:
        lines.append(palette.dim(scope_label))
    lines.append("")
    lines += _health_lines(palette, s)
    lines += _category_lines(palette, s, report["_findings"])
    lines += _insight_lines(palette, report["insights"])
    lines += _hotspot_lines(palette, s)
    lines += _verdict_lines(palette, report)
    lines += _provenance_lines(palette, s)
    return "\n".join(lines).rstrip() + "\n"
