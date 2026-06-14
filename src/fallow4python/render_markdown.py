"""Markdown report renderer: one helper per section."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from .explain import md_explain
from .model import Finding, Insight, Metric, TOOL_VERSION, compact, location_str, md_escape


def _md_header(s: Dict[str, Any], scope_label: str) -> List[str]:
    L = ["# Python Codebase Intelligence Report", "",
         f"Generated: `{s['generated_at']}` - fallow4python v{TOOL_VERSION}"]
    if scope_label:
        L.append(f"\n> {scope_label}")
    L.append("")
    md_explain(L, "intro")
    return L


def _md_health(s: Dict[str, Any]) -> List[str]:
    health = s["health"]
    score = health.get("score")
    L = ["## Health", ""]
    md_explain(L, "health")
    L.append(f"**Grade {health.get('grade', 'n/a')}** "
             f"({score if score is not None else 'n/a'} / 100) - "
             f"{health.get('loc', 0)} lines of code - {s['finding_count']} findings")
    L += ["", "| Component | Score |", "|---|---:|"]
    for k, v in health.get("components", {}).items():
        L.append(f"| {k} | {v if v is not None else 'n/a'} |")
    L.append("")
    return L


def _md_verdict(report: Dict[str, Any]) -> List[str]:
    verdict = report.get("verdict")
    if not verdict:
        return []
    L = ["## Verdict", ""]
    md_explain(L, "verdict")
    if verdict.get("scoped_to_changes"):
        L.append(f"**{verdict['verdict'].upper()}** - "
                 f"{verdict['new_errors']} newly introduced error(s) and "
                 f"{verdict['changed_warnings']} warning(s) on changed lines; "
                 f"{verdict['touched_errors']} file-level error(s) in touched "
                 f"files, {verdict['inherited_errors']} inherited error(s) "
                 f"({verdict['inherited_total']} inherited findings total).")
    else:
        L.append(f"**{verdict['verdict'].upper()}** - "
                 f"{verdict['new_errors']} error(s) and "
                 f"{verdict['changed_warnings']} warning(s).")
    L.append("")
    return L


def _md_insights(insights: List[Insight]) -> List[str]:
    L = ["## Insights", ""]
    md_explain(L, "insights")
    if not insights:
        L += ["No correlated insights.", ""]
        return L
    for ins in insights:
        loc = (f" - `{ins.file}{':' + str(ins.line) if ins.line else ''}`"
               if ins.file else "")
        L.append(f"- **[{ins.severity}] {md_escape(ins.title)}**{loc}  ")
        L.append(f"  {md_escape(ins.detail)}")
    L.append("")
    return L


def _md_summary(s: Dict[str, Any]) -> List[str]:
    L = ["## Summary", ""]
    md_explain(L, "summary")
    L += ["| Severity | Count |", "|---|---:|"]
    for sev in ("error", "warning", "info"):
        L.append(f"| {sev} | {s['by_severity'].get(sev, 0)} |")
    L += ["", "| Category | Count |", "|---|---:|"]
    for cat, n in sorted(s["by_category"].items()):
        L.append(f"| {cat} | {n} |")
    L.append("")
    if s["top_files"]:
        L += ["### Hotspot files", "", "| File | Findings |", "|---|---:|"]
        for fname, n in s["top_files"]:
            L.append(f"| `{md_escape(fname)}` | {n} |")
        L.append("")
    return L


def _md_metrics(metrics: List[Metric]) -> List[str]:
    if not metrics:
        return []
    L = ["## Metrics", ""]
    md_explain(L, "metrics")
    L += ["| Tool | Metric | File | Value | Rank |", "|---|---|---|---:|:--:|"]
    for m in sorted(metrics, key=lambda m: (m.tool, m.name, m.file)):
        val = f"{m.value:.2f}{m.unit}"
        L.append(f"| {md_escape(m.tool)} | {md_escape(m.name)} | "
                 f"`{md_escape(m.file)}` | {md_escape(val)} | {md_escape(m.rank)} |")
    L.append("")
    return L


def _md_findings_table(items: List[Finding], cap: int) -> List[str]:
    L = ["| Sev | Changed | Location | Tool | Rule | Message |",
         "|---|:--:|---|---|---|---|"]
    for f in items[:cap]:
        L.append("| {} | {} | `{}` | {} | {} | {} |".format(
            f.severity, "yes" if f.changed else "", md_escape(location_str(f)),
            md_escape(f.tool), md_escape(f.rule), md_escape(compact(f.message))))
    if len(items) > cap:
        L.append(f"| info | | - | - | truncated | {len(items) - cap} more omitted |")
    return L


def _md_findings(findings: List[Finding], cap: int) -> List[str]:
    L = ["## Findings", ""]
    md_explain(L, "findings")
    grouped: Dict[str, List[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.category].append(f)
    if not grouped:
        L.append("No findings.")
    for cat in sorted(grouped):
        items = grouped[cat]
        L += [f"### {cat} ({len(items)})", ""]
        L += _md_findings_table(items, cap)
        L.append("")
    return L


def _md_toolruns(s: Dict[str, Any]) -> List[str]:
    L = ["## Tool runs", ""]
    md_explain(L, "toolruns")
    L += ["| Tool | Status | Findings | Detail |", "|---|---|---:|---|"]
    for r in s["tool_runs"]:
        L.append(f"| {md_escape(r['name'])} | {r['status']} | {r['findings']} | "
                 f"{md_escape(r['detail'])} |")
    L.append("")
    return L


def render_markdown(report: Dict[str, Any], scope_label: str) -> str:
    s = report["summary"]
    cap = report["_max_per_section"]
    L: List[str] = []
    L += _md_header(s, scope_label)
    L += _md_health(s)
    L += _md_verdict(report)
    L += _md_insights(report["insights"])
    L += _md_summary(s)
    L += _md_metrics(report["_metrics"])
    L += _md_findings(report["_findings"], cap)
    L += _md_toolruns(s)
    return "\n".join(L).rstrip() + "\n"
