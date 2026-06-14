"""Audit verdict: pass | warn | fail, full-scan or scoped to a git diff."""
from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from .model import Finding


def _verdict_full_scan(findings: Sequence[Finding]) -> Dict[str, Any]:
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    verdict = "fail" if errors else ("warn" if warnings else "pass")
    return {"verdict": verdict, "scoped_to_changes": False,
            "new_errors": errors, "changed_warnings": warnings,
            "touched_errors": 0, "inherited_errors": 0, "inherited_total": 0}


def _scoped_verdict(new_errors: int, touched_errors: int, inherited_errors: int,
                    changed: int, gate: str) -> str:
    if new_errors:
        return "fail"
    if gate == "all" and (inherited_errors or touched_errors):
        return "fail"
    if changed or touched_errors:
        return "warn"
    return "pass"


def _error_counts(changed: Sequence[Finding]) -> Tuple[int, int]:
    """Return (new_errors_on_changed_lines, file_level_errors_in_touched_files)."""
    new = sum(1 for f in changed
              if f.severity == "error" and f.line is not None)
    touched = sum(1 for f in changed
                  if f.severity == "error" and f.line is None)
    return new, touched


def _scoped_counts(changed: Sequence[Finding], inherited: Sequence[Finding]
                   ) -> Dict[str, int]:
    new_errors, touched_errors = _error_counts(changed)
    return {
        "new_errors": new_errors,
        "touched_errors": touched_errors,
        "changed_warnings": sum(1 for f in changed if f.severity == "warning"),
        "inherited_errors": sum(1 for f in inherited if f.severity == "error"),
    }


def _verdict_scoped(findings: Sequence[Finding], gate: str) -> Dict[str, Any]:
    changed = [f for f in findings if f.changed]
    inherited = [f for f in findings if not f.changed]
    c = _scoped_counts(changed, inherited)
    verdict = _scoped_verdict(c["new_errors"], c["touched_errors"],
                              c["inherited_errors"], len(changed), gate)
    return {"verdict": verdict, "scoped_to_changes": True,
            "inherited_total": len(inherited), **c}


def compute_verdict(findings: Sequence[Finding], scoped_to_changes: bool,
                    gate: str) -> Dict[str, Any]:
    """Verdict: pass | warn | fail, optionally scoped to changed lines."""
    if not scoped_to_changes:
        return _verdict_full_scan(findings)
    return _verdict_scoped(findings, gate)
