"""Public analyzer API: file discovery, duplication, and circular imports."""
from .cycles import detect_circular_imports
from .discovery import discover_py_files
from .duplication import detect_duplication

__all__ = ["discover_py_files", "detect_duplication", "detect_circular_imports"]
