"""Self-documenting prose for each Markdown report section.

Isolated from logic so the large string constants do not depress the
maintainability index of any module that actually does work.
"""
from __future__ import annotations

from typing import Dict, List

MD_EXPLAIN: Dict[str, str] = {
    "intro": (
        "This report is produced by **fallow4python**, a static-analysis "
        "aggregator for Python. It runs several independent quality tools, "
        "normalizes their output into one schema, and correlates the signals. "
        "Everything below is derived from static analysis of the source (plus "
        "test-coverage data only if it was supplied); no code is executed "
        "beyond an existing test suite. **Higher scores are always better, and "
        "`error` is more severe than `warning`, which is more severe than "
        "`info`.** Read the sections top to bottom: Health is the verdict, "
        "Insights are the prioritized to-do list, and Findings/Metrics are the "
        "supporting evidence."
    ),
    "health": (
        "A single 0-100 score for overall code health, plus a letter grade. "
        "**Higher is better.** Grade bands: A >= 90, B >= 80, C >= 70, "
        "D >= 60, F < 60. The score is a weighted average of up to four "
        "components, each independently scaled 0-100:\n"
        "\n"
        "- **coverage** (weight 0.30): percent of code lines exercised by the "
        "test suite. Shown only when coverage data is provided; else `n/a`.\n"
        "- **maintainability** (weight 0.25): mean of radon's Maintainability "
        "Index across files - a blend of volume, complexity, and length.\n"
        "- **complexity** (weight 0.20): the percent of functions that are "
        "*not* flagged as overly complex.\n"
        "- **cleanliness** (weight 0.25): the inverse of defect density, from "
        "errors and warnings per 1,000 lines of code, errors counted 3x.\n"
        "\n"
        "Any component that is `n/a` is dropped and the remaining weights are "
        "renormalized, so the final score is always out of 100."
    ),
    "verdict": (
        "A PASS / WARN / FAIL gate that judges a specific code change (a git "
        "diff), not the whole repository. **FAIL**: the change introduced new "
        "error-level problems on the exact lines it modified. **WARN**: the "
        "change touched files that already had issues but added no new errors. "
        "**PASS**: neither. Pre-existing problems do not by themselves block a "
        "change - only newly introduced ones do."
    ),
    "insights": (
        "Cross-tool correlations rather than raw output - the highest-value "
        "section. Each insight combines signals from multiple tools to point "
        "at a concrete action: **Concentrated problems** (one file flagged by "
        "several tools), **Likely safe to delete** (statically unused and "
        "barely covered), **Risk hotspot** (complex and undertested), and "
        "**Circular import**. Start your work here; the Findings table is the "
        "underlying evidence."
    ),
    "summary": (
        "Counts of every raw finding, broken down by **severity** (`error` = "
        "likely a real defect; `warning` = worth reviewing; `info` = "
        "low-confidence or stylistic) and by **category** (the kind of "
        "problem). The **Hotspot files** table ranks files by total finding "
        "count, so you know where to spend effort first."
    ),
    "metrics": (
        "Raw measured values, as distinct from findings - the numbers the "
        "Health components are computed from. For radon ranks, **A is best and "
        "F is worst**. `maintainability-index` runs 0-100 (higher = more "
        "maintainable). `complexity-functions` is the total number of "
        "functions analyzed."
    ),
    "findings": (
        "Every individual issue, grouped by category - the evidence layer. "
        "Columns: **Sev** = severity; **Changed** = `yes` if the issue sits on "
        "a line modified by the audited change; **Location** = file:line; "
        "**Tool** = which analyzer reported it; **Rule** = the specific check; "
        "**Message** = what is wrong. A practical fix order is highest "
        "severity first, within the files named as hotspots."
    ),
    "toolruns": (
        "Provenance - which analyzers ran, succeeded, failed, or were skipped, "
        "and how many findings each produced. A *skipped* tool means that "
        "dimension was **not assessed**. Absence of findings from a tool that "
        "did not run is not evidence that no problems exist there."
    ),
}


def md_explain(lines: List[str], key: str) -> None:
    """Append a section's explanation as a Markdown blockquote."""
    text = MD_EXPLAIN.get(key)
    if not text:
        return
    for line in text.split("\n"):
        lines.append(f"> {line}" if line else ">")
    lines.append("")
