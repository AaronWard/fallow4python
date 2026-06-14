# Python Codebase Intelligence Report

Generated: `2026-06-14T20:44:35.211006+00:00` · fallow4python v1.5.1

> This report is produced by **fallow4python**, a static-analysis aggregator for Python. It runs several independent quality tools, normalizes their output into one schema, and correlates the signals. Everything below is derived from static analysis of the source (plus test-coverage data only if it was supplied); no code is executed beyond an existing test suite. **Higher scores are always better, and `error` is more severe than `warning`, which is more severe than `info`.** Read the sections top to bottom: Health is the verdict, Insights are the prioritized to-do list, and Findings/Metrics are the supporting evidence.

## Health

> A single 0–100 score for overall code health, plus a letter grade. **Higher is better.** Grade bands: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60. The score is a weighted average of up to four components, each independently scaled 0–100:
>
> - **coverage** (weight 0.30): percent of code lines exercised by the test suite. Shown only when coverage data is provided; otherwise `n/a`.
> - **maintainability** (weight 0.25): mean of radon's Maintainability Index across files — a blend of code volume, complexity, and length. Higher means easier to change safely.
> - **complexity** (weight 0.20): the percent of functions that are *not* flagged as overly complex. 100 means no function exceeds the cyclomatic-complexity threshold.
> - **cleanliness** (weight 0.25): the inverse of defect density. Computed from errors and warnings per 1,000 lines of code, with errors counted 3× as heavily as warnings.
>
> Any component that is `n/a` is dropped and the remaining weights are renormalized, so the final score is always out of 100. **Implication:** the letter grade is a starting point, not the whole story — look at *which* component is low. A `0.0` cleanliness alongside otherwise decent components means a high *count* of lint/type findings relative to the codebase size, not necessarily deep structural rot; it floors at 0 once defect density is high enough.

**Grade C** (71.2 / 100) · 2939 lines of code · 40 findings

| Component | Score |
|---|---:|
| coverage | 69.1 |
| maintainability | 68.1 |
| complexity | 84.0 |
| cleanliness | 66.7 |

## Insights

> Cross-tool correlations rather than raw output — fallow4python's highest-value section. Each insight combines signals from multiple tools to point at a concrete action. Types you may see: **Concentrated problems** (one file is flagged by several different tools, so fixing it clears the most signal at once); **Likely safe to delete** (a symbol is both statically unused and barely covered at runtime); **Risk hotspot** (high complexity combined with low test coverage); **Circular import** (a dependency cycle between modules). **Implication:** start your work here. These are already prioritized; the Findings table below is the underlying evidence for them.

- **[warning] Concentrated problems: src/fallow4python/cli.py** — `src/fallow4python/cli.py`  
  28 findings from 3 tools (duplication, radon, vulture). A focused cleanup here clears the most signal.

## Summary

> Counts of every raw finding, broken down two ways. **By severity:** `error` = likely a real defect or type error that should be fixed; `warning` = a probable issue worth reviewing; `info` = low-confidence or stylistic. **By category:** the *kind* of problem — e.g. `typing`, `lint`, `dead-code`, `complexity`, `dependencies`, `duplication`. The **Hotspot files** table ranks files by total finding count. **Implication:** severity tells you urgency, category tells you what kind of work is required, and hotspots tell you where to spend effort first.

| Severity | Count |
|---|---:|
| error | 8 |
| warning | 25 |
| info | 7 |

| Category | Count |
|---|---:|
| complexity | 20 |
| coverage | 1 |
| dead-code | 7 |
| dependencies | 11 |
| duplication | 1 |

### Hotspot files

| File | Findings |
|---|---:|
| `src/fallow4python/cli.py` | 28 |
| `pyproject.toml` | 8 |
| `tests/test_integration.py` | 2 |
| `tests/test_fallow4python.py` | 1 |

## Metrics

> Raw measured values, as distinct from findings. These are the numbers the Health components are computed from, so you can verify or drill into the score. For radon ranks, **A is best and F is worst**. `maintainability-index` runs 0–100 (higher = more maintainable). `complexity-functions` is the total number of functions analyzed. **Implication:** if one file shows a poor metric, it usually explains a large share of the health deductions above.

| Tool | Metric | File | Value | Rank |
|---|---|---|---:|:--:|
| coverage | total-line-coverage | `` | 69.06% |  |
| radon | complexity-functions | `` | 125.00 |  |
| radon | maintainability-index | `src/fallow4python/__init__.py` | 100.00 | A |
| radon | maintainability-index | `src/fallow4python/__main__.py` | 81.86 | A |
| radon | maintainability-index | `tests/test_fallow4python.py` | 41.87 | A |
| radon | maintainability-index | `tests/test_integration.py` | 48.80 | A |

## Findings

> Every individual issue, grouped by category — the evidence layer. Each row is one problem reported by one tool. Columns: **Sev** = severity; **Changed** = `yes` if the issue sits on a line modified by the audited change (blank otherwise); **Location** = file:line; **Tool** = which analyzer reported it; **Rule** = the specific check that fired; **Message** = what is wrong. **Implication:** every count in Summary and every Insight traces back to rows here. A practical fix order is: highest severity first, within the files named as hotspots.

### complexity (20)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| error |  | `src/fallow4python/cli.py:960:0` | radon | cyclomatic-complexity | function `build_correlations` complexity 36 (rank E) |
| error |  | `src/fallow4python/cli.py:1048:0` | radon | cyclomatic-complexity | function `compute_health` complexity 23 (rank D) |
| error |  | `src/fallow4python/cli.py:1105:0` | radon | cyclomatic-complexity | function `compute_verdict` complexity 28 (rank D) |
| error |  | `src/fallow4python/cli.py:1201:0` | radon | cyclomatic-complexity | function `render_human` complexity 41 (rank F) |
| error |  | `src/fallow4python/cli.py:1421:0` | radon | cyclomatic-complexity | function `render_markdown` complexity 24 (rank D) |
| error |  | `src/fallow4python/cli.py:1892:0` | radon | cyclomatic-complexity | function `orchestrate` complexity 33 (rank E) |
| error |  | `src/fallow4python/cli.py:2256:0` | radon | cyclomatic-complexity | function `main` complexity 25 (rank D) |
| warning |  | `src/fallow4python/cli.py:311:0` | radon | cyclomatic-complexity | function `parse_ruff` complexity 14 (rank C) |
| warning |  | `src/fallow4python/cli.py:351:0` | radon | cyclomatic-complexity | function `parse_mypy` complexity 15 (rank C) |
| warning |  | `src/fallow4python/cli.py:426:0` | radon | cyclomatic-complexity | function `_deptry_finding` complexity 20 (rank C) |
| warning |  | `src/fallow4python/cli.py:487:0` | radon | cyclomatic-complexity | function `parse_radon_cc` complexity 17 (rank C) |
| warning |  | `src/fallow4python/cli.py:549:0` | radon | cyclomatic-complexity | function `parse_radon_mi` complexity 13 (rank C) |
| warning |  | `src/fallow4python/cli.py:637:0` | radon | cyclomatic-complexity | function `parse_coverage` complexity 14 (rank C) |
| warning |  | `src/fallow4python/cli.py:718:0` | radon | cyclomatic-complexity | function `detect_duplication` complexity 19 (rank C) |
| warning |  | `src/fallow4python/cli.py:814:0` | radon | cyclomatic-complexity | function `detect_circular_imports` complexity 20 (rank C) |
| warning |  | `src/fallow4python/cli.py:905:0` | radon | cyclomatic-complexity | function `git_changed_lines` complexity 14 (rank C) |
| warning |  | `src/fallow4python/cli.py:1153:0` | radon | cyclomatic-complexity | function `summarize` complexity 12 (rank C) |
| warning |  | `src/fallow4python/cli.py:1757:4` | radon | cyclomatic-complexity | method `_render` complexity 16 (rank C) |
| warning |  | `src/fallow4python/cli.py:1838:0` | radon | cyclomatic-complexity | function `_coverage_via_tests` complexity 15 (rank C) |
| warning |  | `src/fallow4python/cli.py:2024:0` | radon | cyclomatic-complexity | function `_run_tool` complexity 13 (rank C) |

### coverage (1)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| error |  | `-` | coverage | coverage-total | total coverage 69.06% below threshold 80% |

### dead-code (7)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| warning |  | `src/fallow4python/cli.py:862` | vulture | dead-code | unused variable 'nodes' |
| info |  | `src/fallow4python/cli.py:75` | vulture | dead-code | unused variable 'SEVERITY_RANK' |
| info |  | `src/fallow4python/cli.py:80` | vulture | dead-code | unused variable 'CATEGORIES' |
| info |  | `src/fallow4python/cli.py:154` | vulture | dead-code | unused variable 'details' |
| info |  | `src/fallow4python/cli.py:166` | vulture | dead-code | unused variable 'evidence' |
| info |  | `src/fallow4python/cli.py:176` | vulture | dead-code | unused variable 'duration_ms' |
| info |  | `src/fallow4python/cli.py:1629` | vulture | dead-code | unused variable 'ingest_only' |

### dependencies (11)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| warning |  | `pyproject.toml` | deptry | DEP002 | 'ruff' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'mypy' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'vulture' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'radon' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'deptry' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'xenon' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'import-linter' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'coverage' defined as a dependency but not used in the codebase |
| warning |  | `tests/test_fallow4python.py:13:1` | deptry | DEP003 | 'fallow4python' imported but it is a transitive dependency |
| warning |  | `tests/test_integration.py:14:1` | deptry | DEP003 | 'fallow4python' imported but it is a transitive dependency |
| warning |  | `tests/test_integration.py:155:5` | deptry | DEP003 | 'fallow4python' imported but it is a transitive dependency |

### duplication (1)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| info |  | `src/fallow4python/cli.py:312` | duplication | clone-family | duplicated block (~6 lines) in 2 places: src/fallow4python/cli.py:312-317, src/fallow4python/cli.py:352-357 |

## Tool runs

> Provenance — which analyzers actually ran, succeeded, failed, or were skipped, and how many findings each produced. **Implication:** this defines the report's coverage. A *skipped* tool means that dimension was **not assessed**: e.g. if coverage was skipped, the coverage component is `n/a` and there is no runtime evidence behind dead-code findings. Absence of findings from a tool that did not run is not evidence that no problems exist there.

| Tool | Status | Findings | Detail |
|---|---|---:|---|
| ruff | ran | 0 |  |
| mypy | ran | 0 |  |
| vulture | ran | 7 |  |
| radon-cc | ran | 20 |  |
| radon-mi | ran | 0 |  |
| deptry | ran | 11 |  |
| xenon | ran | 0 |  |
| import-linter | ran | 0 |  |
| coverage | ingested | 1 | ran `pytest` under coverage |
| duplication | ran | 1 | built-in clone detector |
| cycles | ran | 0 | built-in import-graph cycles |
