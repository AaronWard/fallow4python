"""fallow4python - codebase intelligence for Python.

Orchestrates Python's quality tools, correlates their signals into
prioritized insights, audits changed code with a pass/fail verdict, and
emits a single report (human, Markdown, JSON, or SARIF).
"""
from .cli import main
from .model import TOOL_VERSION as __version__

__all__ = ["main", "__version__"]
