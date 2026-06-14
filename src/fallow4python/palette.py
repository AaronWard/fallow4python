"""ANSI color palette and shared severity glyphs for terminal renderers."""
from __future__ import annotations

SEV_MARK = {"error": "x", "warning": "!", "info": "-"}


class Palette:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _w(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def red(self, t: str) -> str:
        return self._w("31", t)

    def yellow(self, t: str) -> str:
        return self._w("33", t)

    def green(self, t: str) -> str:
        return self._w("32", t)

    def blue(self, t: str) -> str:
        return self._w("36", t)

    def bold(self, t: str) -> str:
        return self._w("1", t)

    def dim(self, t: str) -> str:
        return self._w("2", t)
