"""Public health API: score, verdict, and summary, re-exported as one namespace."""
from .scoring import compute_health
from .summary import summarize
from .verdict import compute_verdict

__all__ = ["compute_health", "compute_verdict", "summarize"]
