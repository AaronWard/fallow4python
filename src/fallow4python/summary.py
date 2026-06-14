"""Aggregate findings, metrics, and provenance into a report summary."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Sequence

from .model import Finding, Metric, SEVERITY_ORDER, TOOL_VERSION, ToolRun


def _max_severity(findings: Sequence[Finding]) -> str:
    if not findings:
        return "none"
    return max((f.severity for f in findings),
               key=lambda s: SEVERITY_ORDER.get(s, 0))


def _summary_buckets(findings: Sequence[Finding]) -> Dict[str, Any]:
    by_file: Counter = Counter(f.file for f in findings if f.file)
    return {
        "by_severity": {s: sum(1 for f in findings if f.severity == s)
                        for s in ("error", "warning", "info")},
        "by_tool": dict(sorted(Counter(f.tool for f in findings).items())),
        "by_category": dict(sorted(Counter(f.category for f in findings).items())),
        "top_files": by_file.most_common(10),
    }


def summarize(findings: Sequence[Finding], metrics: Sequence[Metric],
              runs: Sequence[ToolRun], health: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_version": TOOL_VERSION,
        "health": health,
        "finding_count": len(findings),
        "changed_findings": sum(1 for f in findings if f.changed),
        "metric_count": len(metrics),
        "max_severity": _max_severity(findings),
        "tool_runs": [asdict(r) for r in runs],
        **_summary_buckets(findings),
    }
