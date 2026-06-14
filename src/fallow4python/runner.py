"""Run a single analyzer as a subprocess, or ingest its saved output."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .model import Finding, Metric, ToolRun, read_text
from .options import Options
from .toolspecs import (
    INGEST_FILENAMES, ToolSpec, _import_linter_configured,
)


def _ingest_candidates(spec: ToolSpec, opts: Options) -> List[Path]:
    candidates: List[Path] = []
    explicit = opts.explicit_inputs.get(spec.name)
    if explicit:
        candidates.append(Path(explicit))
    if opts.from_dir:
        for fn in INGEST_FILENAMES.get(spec.name, []):
            candidates.append(Path(opts.from_dir) / fn)
    return candidates


def _try_ingest(spec: ToolSpec, root: Path, opts: Options
                ) -> Optional[Tuple[List[Finding], List[Metric], ToolRun]]:
    for path in _ingest_candidates(spec, opts):
        if not path.is_file():
            continue
        try:
            fs, ms = spec.parser(read_text(path), root)
            return fs, ms, ToolRun(spec.name, "ingested", str(path), len(fs))
        except Exception as exc:  # noqa: BLE001
            return [], [], ToolRun(spec.name, "error", f"{path}: {exc}")
    return None


def _tool_text(proc: subprocess.CompletedProcess, tmp_out: Optional[Path]) -> str:
    if tmp_out and tmp_out.exists() and tmp_out.stat().st_size:
        text = read_text(tmp_out)
    else:
        text = proc.stdout
    if not text.strip() and proc.stdout.strip():
        text = proc.stdout
    return text


def _prepare_argv(spec: ToolSpec, target: Path) -> Tuple[List[str], Optional[Path]]:
    argv = spec.argv(target)
    if not spec.output_to_file:
        return argv, None
    tmp = tempfile.NamedTemporaryFile(prefix="fallow4python-", suffix=".json",
                                      delete=False)
    tmp.close()
    tmp_out = Path(tmp.name)
    return [a.replace("{OUTFILE}", str(tmp_out)) for a in argv], tmp_out


def _run_tool(spec: ToolSpec, root: Path, target: Path, opts: Options,
              findings: List[Finding], metrics: List[Metric]) -> ToolRun:
    start = datetime.now()
    argv, tmp_out = _prepare_argv(spec, target)
    try:
        proc = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                              timeout=opts.timeout)
        fs, ms = spec.parser(_tool_text(proc, tmp_out), root)
        findings += fs
        metrics += ms
        dur = int((datetime.now() - start).total_seconds() * 1000)
        return ToolRun(spec.name, "ran", "", len(fs), dur)
    except subprocess.TimeoutExpired:
        return ToolRun(spec.name, "error", f"timed out after {opts.timeout}s")
    except Exception as exc:  # noqa: BLE001
        return ToolRun(spec.name, "error", str(exc))
    finally:
        if tmp_out and tmp_out.exists():
            try:
                tmp_out.unlink()
            except OSError:
                pass


def _skip_reason(spec: ToolSpec, root: Path, opts: Options) -> Optional[str]:
    if opts.no_run:
        return "no-run mode and no saved output"
    if not shutil.which(spec.executable):
        return f"{spec.executable} not installed"
    if spec.needs_config and not _import_linter_configured(root):
        return "no import-linter config found"
    return None


def run_spec(spec: ToolSpec, root: Path, target: Path, opts: Options,
             findings: List[Finding], metrics: List[Metric]) -> ToolRun:
    ingested = _try_ingest(spec, root, opts)
    if ingested is not None:
        fs, ms, run = ingested
        findings += fs
        metrics += ms
        return run
    reason = _skip_reason(spec, root, opts)
    if reason is not None:
        return ToolRun(spec.name, "skipped", reason)
    return _run_tool(spec, root, target, opts, findings, metrics)
