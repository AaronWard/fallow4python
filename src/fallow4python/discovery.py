"""Source-file discovery, skipping conventional non-source directories."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .model import IGNORE_DIRS


def discover_py_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in IGNORE_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".py"):
                files.append(Path(dirpath) / name)
    return files
