"""Live, colored, animated analyzer-progress checklist (stderr, TTY-aware)."""
from __future__ import annotations

import sys
import threading
import time
from typing import Any, Dict, List, Optional, Sequence

from .progress_style import (
    BAR_EMPTY, BAR_FULL, DIM, GOLD, SPINNER, TURQ, bar_tone, c, state_glyph,
    wordmark,
)


class LiveProgress:
    """A live animated checklist of analyzer steps; no-op unless on a TTY."""

    def __init__(self, steps: Sequence[str], enabled: bool):
        self.enabled = enabled and sys.stderr.isatty()
        self.order: List[str] = list(steps)
        self.state: Dict[str, str] = {s: "pending" for s in self.order}
        self.detail: Dict[str, str] = {s: "" for s in self.order}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_ts = 0.0
        self._lines = 0
        self._tick = 0

    def __enter__(self) -> "LiveProgress":
        if not self.enabled:
            return self
        self._start_ts = time.monotonic()
        sys.stderr.write("\033[?25l")
        sys.stderr.flush()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread:
            self._thread.join()
        with self._lock:
            self._render(final=True)
        sys.stderr.write("\033[?25h\n")
        sys.stderr.flush()

    def start(self, step: str) -> None:
        if self.enabled:
            with self._lock:
                if step in self.state:
                    self.state[step] = "running"

    def _set_detail(self, step: str, status: str, count: Optional[int],
                    note: str) -> None:
        if count is not None and status in ("done", "ran", "ingested"):
            self.detail[step] = f"{count} finding{'s' if count != 1 else ''}"
        elif note:
            self.detail[step] = note

    def finish(self, step: str, status: str, count: Optional[int] = None,
               note: str = "") -> None:
        if not self.enabled:
            return
        with self._lock:
            if step in self.state:
                self.state[step] = status
                self._set_detail(step, status, count, note)

    def _loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                self._render()
            self._tick += 1
            time.sleep(0.08)

    def _header_rows(self, frame: str, phase: float, final: bool,
                     elapsed: float) -> List[str]:
        pip = c(44, "\u25cf") if final else c(GOLD, frame)
        title = wordmark("fallow4python", phase, final)
        verb = "complete" if final else "scanning"
        return [f"  {pip}  {title}   \033[2m{verb}\033[0m"
                f"   \033[2m{elapsed:5.1f}s\033[0m"]

    def _bar_cell(self, i: int, filled: int, comet: int, final: bool) -> str:
        if i >= filled:
            return c(DIM, BAR_EMPTY)
        if i == comet and not final:
            return c(GOLD, BAR_FULL)
        return c(bar_tone(i, filled), BAR_FULL)

    def _bar_row(self, done: int, total: int, final: bool) -> str:
        width = 18
        filled = int(round(width * done / max(total, 1)))
        comet = self._tick % width
        cells = [self._bar_cell(i, filled, comet, final) for i in range(width)]
        return f"     {''.join(cells)}  \033[2m{done} / {total}\033[0m"

    def _step_row(self, step: str, frame: str) -> str:
        st = self.state[step]
        if st == "running":
            return f"     {c(GOLD, frame)} {c(TURQ[2], f'{step:<15}')} \033[2m\u2026\033[0m"
        glyph, code = state_glyph(st)
        icon = c(code, glyph)
        if st == "pending":
            return f"     {icon} {c(DIM, f'{step:<15}')} "
        tail = f"\033[2m{self.detail.get(step) or st}\033[0m"
        return f"     {icon} {c(code, f'{step:<15}')} {tail}"

    def _compose(self, final: bool) -> List[str]:
        frame = SPINNER[self._tick % len(SPINNER)]
        phase = (self._tick % 48) / 48.0
        done = sum(1 for s in self.order
                   if self.state[s] not in ("pending", "running"))
        elapsed = time.monotonic() - self._start_ts
        rows = self._header_rows(frame, phase, final, elapsed)
        rows.append(self._bar_row(done, len(self.order), final))
        rows.append("")
        rows += [self._step_row(s, frame) for s in self.order]
        return rows

    def _render(self, final: bool = False) -> None:
        rows = self._compose(final)
        buf: List[str] = []
        if self._lines:
            buf.append(f"\033[{self._lines}A")
        for row in rows:
            buf.append("\033[2K" + row + "\n")
        sys.stderr.write("".join(buf))
        sys.stderr.flush()
        self._lines = len(rows)
