"""Git integration: changed files/lines, change-marking, base-ref resolution."""
from __future__ import annotations

import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from .model import Finding

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


def _git(args: List[str], root: Path, timeout: int
         ) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(args, cwd=root, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None


def _diff_ref(base: str, root: Path) -> str:
    merge_base = _git(["git", "merge-base", base, "HEAD"], root, 30)
    if merge_base and merge_base.returncode == 0:
        return merge_base.stdout.strip()
    return base


def _target_path(line: str) -> Optional[str]:
    path = line[4:].strip()
    if path == "/dev/null":
        return None
    return path[2:] if path.startswith("b/") else path


def _hunk_lines(line: str, changed: Set[int]) -> None:
    m = _HUNK.match(line)
    if not m:
        return
    start = int(m.group("start"))
    count = int(m.group("count")) if m.group("count") else 1
    for ln in range(start, start + max(count, 1)):
        changed.add(ln)


def git_changed_lines(base: str, root: Path) -> Optional[Dict[str, Set[int]]]:
    """Return {relative_path: {changed line numbers}} for base..worktree."""
    if not shutil.which("git"):
        return None
    diff = _git(["git", "diff", "--no-color", "--unified=0",
                 _diff_ref(base, root)], root, 60)
    if diff is None or diff.returncode != 0:
        return None
    changed: Dict[str, Set[int]] = defaultdict(set)
    current: Optional[str] = None
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            current = _target_path(line)
        elif line.startswith("@@") and current:
            _hunk_lines(line, changed[current])
    return dict(changed)


def _is_changed(f: Finding, changed: Dict[str, Set[int]]) -> bool:
    if not f.file or f.file not in changed:
        return False
    return f.line is None or f.line in changed[f.file]


def mark_changed(findings: List[Finding], changed: Dict[str, Set[int]]
                 ) -> List[Finding]:
    """Return a new list with ``changed`` set on findings touching the diff."""
    return [Finding(**{**asdict(f), "changed": _is_changed(f, changed)})
            for f in findings]


def resolve_base(base: Optional[str], root: Path) -> Optional[str]:
    """Pick the first git base ref that actually resolves."""
    if not base:
        return None
    candidates = [base]
    if base == "origin/main":
        candidates += ["main", "origin/master", "master", "HEAD~1"]
    for ref in candidates:
        check = _git(["git", "rev-parse", "--verify", ref], root, 15)
        if check is None:
            return None
        if check.returncode == 0:
            return ref
    return None
