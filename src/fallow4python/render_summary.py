"""Compact one-screen summary renderer."""
from __future__ import annotations

from typing import Any, Dict, List

from .palette import Palette
from .render_human import _grade_color


def _summary_component_lines(p: Palette, health: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for k, v in health.get("components", {}).items():
        bar = ""
        if v is not None:
            filled = int(round(v / 10))
            bar = "#" * filled + "." * (10 - filled)
        out.append(f"    {k:<16} {bar}  {v if v is not None else 'n/a'}")
    return out


def render_summary(report: Dict[str, Any], palette: Palette,
                   scope_label: str) -> str:
    s = report["summary"]
    health = s["health"]
    p = palette
    grade = health.get("grade", "n/a")
    score = health.get("score")
    grade_c = _grade_color(p, grade)(grade)
    lines = [p.bold("fallow4python summary")]
    if scope_label:
        lines.append(p.dim(scope_label))
    lines.append(f"  Health {grade_c} ({score if score is not None else 'n/a'}"
                 f"/100) - {health.get('loc', 0)} LOC")
    lines += _summary_component_lines(p, health)
    lines.append("")
    sev = s["by_severity"]
    lines.append(f"  Findings: {s['finding_count']}  "
                 f"(err {sev['error']}, warn {sev['warning']}, info {sev['info']})")
    cats = ", ".join(f"{k} {v}" for k, v in sorted(s["by_category"].items()))
    if cats:
        lines.append(p.dim("  " + cats))
    return "\n".join(lines) + "\n"
