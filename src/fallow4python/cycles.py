"""Built-in circular-import detector: import graph + Tarjan SCC."""
from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

from .model import Finding, read_text, rel


def _module_name(path: Path, root: Path) -> str:
    parts = os.path.relpath(path, root).replace("\\", "/").split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(p for p in parts if p)


def _resolve_relative(current: str, module: Optional[str], level: int
                      ) -> Optional[str]:
    if level == 0:
        return module
    base_parts = current.split(".")
    if len(base_parts) < level:
        return None
    base = base_parts[:len(base_parts) - level]
    if module:
        base = base + module.split(".")
    return ".".join(base) if base else None


def _import_targets(node: ast.AST, name: str) -> List[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        resolved = _resolve_relative(name, node.module, node.level or 0)
        if resolved:
            return [resolved] + [f"{resolved}.{a.name}" for a in node.names]
    return []


def _nearest_known(target: str, known: Set[str]) -> Optional[str]:
    cand = target
    while cand and cand not in known:
        cand = cand.rpartition(".")[0]
    return cand or None


def _import_graph(modules: Dict[str, Path]) -> Dict[str, Set[str]]:
    known = set(modules)
    graph: Dict[str, Set[str]] = defaultdict(set)
    for name, path in modules.items():
        try:
            tree = ast.parse(read_text(path))
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(tree):
            for target in _import_targets(node, name):
                cand = _nearest_known(target, known)
                if cand and cand != name:
                    graph[name].add(cand)
    return graph


def detect_circular_imports(root: Path, files: Sequence[Path]) -> List[Finding]:
    modules: Dict[str, Path] = {}
    for p in files:
        name = _module_name(p, root)
        if name:
            modules[name] = p
    graph = _import_graph(modules)
    findings: List[Finding] = []
    for comp in _tarjan_scc(graph):
        if len(comp) < 2:
            continue
        members = sorted(comp)
        chain = " -> ".join(members) + f" -> {members[0]}"
        findings.append(Finding(
            tool="cycles", category="architecture", severity="error",
            rule="circular-import",
            message=f"circular import among {len(members)} modules: {chain}",
            file=rel(str(modules[members[0]]), root), symbol=members[0],
        ))
    return findings


def _tarjan_scc(graph: Dict[str, Set[str]]) -> List[Set[str]]:
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    counter = [0]
    stack: List[str] = []
    lowlink: Dict[str, int] = {}
    index: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    result: List[Set[str]] = []

    def pop_component(v: str) -> None:
        comp: Set[str] = set()
        while True:
            w = stack.pop()
            on_stack[w] = False
            comp.add(w)
            if w == v:
                break
        result.append(comp)

    def strongconnect(v: str) -> None:
        index[v] = lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in graph.get(v, ()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            pop_component(v)

    for v in list(graph.keys()):
        if v not in index:
            strongconnect(v)
    return result
