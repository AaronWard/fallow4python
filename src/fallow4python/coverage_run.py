"""Run a project's test suite under coverage.py to obtain a JSON report."""
from __future__ import annotations

import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from .model import read_text

if TYPE_CHECKING:
    from .options import Options


def _has_coverage_config(root: Path) -> bool:
    """True if the project already configures coverage's measured source."""
    if (root / ".coveragerc").is_file():
        return True
    for name, marker in (("pyproject.toml", "[tool.coverage"),
                         ("setup.cfg", "[coverage:")):
        p = root / name
        if not p.is_file():
            continue
        try:
            if marker in read_text(p):
                return True
        except OSError:
            pass
    return False


def _test_parts(test_command: str) -> List[str]:
    try:
        return shlex.split(test_command) or ["pytest"]
    except ValueError:
        return ["pytest"]


def _temp_file(suffix: str) -> str:
    fd, path = tempfile.mkstemp(prefix="fallow4python-", suffix=suffix)
    os.close(fd)
    return path


def _run_command(root: Path, target: Path, opts: "Options", data_path: str,
                 json_path: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, COVERAGE_FILE=data_path)
    run_cmd = [sys.executable, "-m", "coverage", "run"]
    if not _has_coverage_config(root):
        run_cmd += ["--source", str(target)]
    run_cmd += ["-m", *_test_parts(opts.test_command)]
    proc = subprocess.run(run_cmd, cwd=root, capture_output=True, text=True,
                          timeout=opts.timeout, env=env)
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", json_path],
                   cwd=root, capture_output=True, text=True,
                   timeout=opts.timeout, env=env)
    return proc


def _no_data_reason(proc: subprocess.CompletedProcess) -> str:
    err_lines = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()]
    tail = f": {err_lines[-1][:80]}" if err_lines else ""
    return f"test run produced no coverage data{tail}"


def _coverage_result(proc: subprocess.CompletedProcess, json_path: str,
                     test_command: str) -> Tuple[Optional[str], str]:
    jp = Path(json_path)
    if not jp.exists() or not jp.stat().st_size:
        return None, _no_data_reason(proc)
    return read_text(jp), f"ran `{test_command}` under coverage"


def coverage_via_tests(root: Path, target: Path, opts: "Options"
                       ) -> Tuple[Optional[str], str]:
    """Return (json_text, detail) or (None, reason) without clobbering .coverage."""
    if importlib.util.find_spec("coverage") is None:
        return None, "coverage not installed (pip install coverage)"
    data_path = _temp_file(".coverage")
    json_path = _temp_file(".json")
    try:
        proc = _run_command(root, target, opts, data_path, json_path)
        return _coverage_result(proc, json_path, opts.test_command)
    except subprocess.TimeoutExpired:
        return None, f"test run timed out after {opts.timeout}s"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    finally:
        for p in (data_path, json_path):
            try:
                os.unlink(p)
            except OSError:
                pass
