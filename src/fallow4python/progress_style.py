"""Color palette, glyphs, and styling helpers for the live progress display."""
from __future__ import annotations

from typing import List, Tuple

TURQ = [159, 122, 80, 44, 37, 30]
GOLD = 220
GOLD_HI = 214
DIM = 66
SPINNER = "\u2838\u283d\u283b\u28bf\u287f\u281f\u282f\u28b7"
BAR_FULL = "\u25b0"
BAR_EMPTY = "\u25b1"

STATE_ICON = {
    "pending": ("\u25cc", DIM), "done": ("\u25cf", 44),
    "ingested": ("\u25cf", 44), "ran": ("\u25cf", 44),
    "skipped": ("\u25cb", DIM), "error": ("\u25b2", GOLD_HI),
}


def c(code: int, text: str) -> str:
    return f"\033[38;5;{code}m{text}\033[0m"


def wordmark(text: str, phase: float, final: bool) -> str:
    n = len(TURQ)
    hi = -1 if final else int(phase * len(text)) % max(len(text), 1)
    out: List[str] = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
        elif i == hi:
            out.append(c(GOLD, ch))
        else:
            out.append(c(TURQ[int(i / max(len(text) - 1, 1) * (n - 1))], ch))
    return "".join(out)


def bar_tone(i: int, filled: int) -> int:
    return TURQ[min(int(i / max(filled, 1) * len(TURQ)), len(TURQ) - 1)]


def state_glyph(state: str) -> Tuple[str, int]:
    return STATE_ICON.get(state, ("\u25cc", DIM))
