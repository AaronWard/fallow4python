# Python Codebase Intelligence Report

Generated: `2026-06-14T13:16:21.399422+00:00` · fallow4python v1.1.2

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

**Grade D** (60.9 / 100) · 2254 lines of code · 79 findings

| Component | Score |
|---|---:|
| coverage | n/a |
| maintainability | 90.9 |
| complexity | 76.5 |
| cleanliness | 18.4 |

## Insights

> Cross-tool correlations rather than raw output — fallow4python's highest-value section. Each insight combines signals from multiple tools to point at a concrete action. Types you may see: **Concentrated problems** (one file is flagged by several different tools, so fixing it clears the most signal at once); **Likely safe to delete** (a symbol is both statically unused and barely covered at runtime); **Risk hotspot** (high complexity combined with low test coverage); **Circular import** (a dependency cycle between modules). **Implication:** start your work here. These are already prioritized; the Findings table below is the underlying evidence for them.

- **[warning] Concentrated problems: src/fallow4python/cli.py** — `src/fallow4python/cli.py`  
  35 findings from 4 tools (duplication, radon, ruff, vulture). A focused cleanup here clears the most signal.

## Summary

> Counts of every raw finding, broken down two ways. **By severity:** `error` = likely a real defect or type error that should be fixed; `warning` = a probable issue worth reviewing; `info` = low-confidence or stylistic. **By category:** the *kind* of problem — e.g. `typing`, `lint`, `dead-code`, `complexity`, `dependencies`, `duplication`. The **Hotspot files** table ranks files by total finding count. **Implication:** severity tells you urgency, category tells you what kind of work is required, and hotspots tell you where to spend effort first.

| Severity | Count |
|---|---:|
| error | 14 |
| warning | 50 |
| info | 15 |

| Category | Count |
|---|---:|
| complexity | 38 |
| dead-code | 18 |
| dependencies | 16 |
| duplication | 1 |
| lint | 6 |

### Hotspot files

| File | Findings |
|---|---:|
| `src/fallow4python/cli.py` | 35 |
| `build/lib/fallow4python/cli.py` | 28 |
| `pyproject.toml` | 8 |

## Metrics

> Raw measured values, as distinct from findings. These are the numbers the Health components are computed from, so you can verify or drill into the score. For radon ranks, **A is best and F is worst**. `maintainability-index` runs 0–100 (higher = more maintainable). `complexity-functions` is the total number of functions analyzed. **Implication:** if one file shows a poor metric, it usually explains a large share of the health deductions above.

| Tool | Metric | File | Value | Rank |
|---|---|---|---:|:--:|
| radon | complexity-functions | `` | 162.00 |  |
| radon | maintainability-index | `build/lib/fallow4python/__init__.py` | 100.00 | A |
| radon | maintainability-index | `build/lib/fallow4python/__main__.py` | 81.86 | A |
| radon | maintainability-index | `src/fallow4python/__init__.py` | 100.00 | A |
| radon | maintainability-index | `src/fallow4python/__main__.py` | 81.86 | A |

## Findings

> Every individual issue, grouped by category — the evidence layer. Each row is one problem reported by one tool. Columns: **Sev** = severity; **Changed** = `yes` if the issue sits on a line modified by the audited change (blank otherwise); **Location** = file:line; **Tool** = which analyzer reported it; **Rule** = the specific check that fired; **Message** = what is wrong. **Implication:** every count in Summary and every Insight traces back to rows here. A practical fix order is: highest severity first, within the files named as hotspots.

### complexity (38)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| error |  | `build/lib/fallow4python/cli.py:919:0` | radon | cyclomatic-complexity | function `build_correlations` complexity 36 (rank E) |
| error |  | `build/lib/fallow4python/cli.py:1007:0` | radon | cyclomatic-complexity | function `compute_health` complexity 23 (rank D) |
| error |  | `build/lib/fallow4python/cli.py:1064:0` | radon | cyclomatic-complexity | function `compute_verdict` complexity 28 (rank D) |
| error |  | `build/lib/fallow4python/cli.py:1160:0` | radon | cyclomatic-complexity | function `render_human` complexity 41 (rank F) |
| error |  | `build/lib/fallow4python/cli.py:1380:0` | radon | cyclomatic-complexity | function `render_markdown` complexity 24 (rank D) |
| error |  | `build/lib/fallow4python/cli.py:1786:0` | radon | cyclomatic-complexity | function `orchestrate` complexity 31 (rank E) |
| error |  | `build/lib/fallow4python/cli.py:2121:0` | radon | cyclomatic-complexity | function `main` complexity 23 (rank D) |
| error |  | `src/fallow4python/cli.py:919:0` | radon | cyclomatic-complexity | function `build_correlations` complexity 36 (rank E) |
| error |  | `src/fallow4python/cli.py:1007:0` | radon | cyclomatic-complexity | function `compute_health` complexity 23 (rank D) |
| error |  | `src/fallow4python/cli.py:1064:0` | radon | cyclomatic-complexity | function `compute_verdict` complexity 28 (rank D) |
| error |  | `src/fallow4python/cli.py:1160:0` | radon | cyclomatic-complexity | function `render_human` complexity 41 (rank F) |
| error |  | `src/fallow4python/cli.py:1380:0` | radon | cyclomatic-complexity | function `render_markdown` complexity 24 (rank D) |
| error |  | `src/fallow4python/cli.py:1786:0` | radon | cyclomatic-complexity | function `orchestrate` complexity 31 (rank E) |
| error |  | `src/fallow4python/cli.py:2121:0` | radon | cyclomatic-complexity | function `main` complexity 23 (rank D) |
| warning |  | `build/lib/fallow4python/cli.py:284:0` | radon | cyclomatic-complexity | function `parse_ruff` complexity 15 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:324:0` | radon | cyclomatic-complexity | function `parse_mypy` complexity 15 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:399:0` | radon | cyclomatic-complexity | function `_deptry_finding` complexity 15 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:451:0` | radon | cyclomatic-complexity | function `parse_radon_cc` complexity 17 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:513:0` | radon | cyclomatic-complexity | function `parse_radon_mi` complexity 13 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:601:0` | radon | cyclomatic-complexity | function `parse_coverage` complexity 16 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:677:0` | radon | cyclomatic-complexity | function `detect_duplication` complexity 19 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:773:0` | radon | cyclomatic-complexity | function `detect_circular_imports` complexity 20 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:864:0` | radon | cyclomatic-complexity | function `git_changed_lines` complexity 14 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:1112:0` | radon | cyclomatic-complexity | function `summarize` complexity 12 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:1721:4` | radon | cyclomatic-complexity | method `_render` complexity 16 (rank C) |
| warning |  | `build/lib/fallow4python/cli.py:1904:0` | radon | cyclomatic-complexity | function `_run_tool` complexity 13 (rank C) |
| warning |  | `src/fallow4python/cli.py:284:0` | radon | cyclomatic-complexity | function `parse_ruff` complexity 15 (rank C) |
| warning |  | `src/fallow4python/cli.py:324:0` | radon | cyclomatic-complexity | function `parse_mypy` complexity 15 (rank C) |
| warning |  | `src/fallow4python/cli.py:399:0` | radon | cyclomatic-complexity | function `_deptry_finding` complexity 15 (rank C) |
| warning |  | `src/fallow4python/cli.py:451:0` | radon | cyclomatic-complexity | function `parse_radon_cc` complexity 17 (rank C) |
| warning |  | `src/fallow4python/cli.py:513:0` | radon | cyclomatic-complexity | function `parse_radon_mi` complexity 13 (rank C) |
| warning |  | `src/fallow4python/cli.py:601:0` | radon | cyclomatic-complexity | function `parse_coverage` complexity 16 (rank C) |
| warning |  | `src/fallow4python/cli.py:677:0` | radon | cyclomatic-complexity | function `detect_duplication` complexity 19 (rank C) |
| warning |  | `src/fallow4python/cli.py:773:0` | radon | cyclomatic-complexity | function `detect_circular_imports` complexity 20 (rank C) |
| warning |  | `src/fallow4python/cli.py:864:0` | radon | cyclomatic-complexity | function `git_changed_lines` complexity 14 (rank C) |
| warning |  | `src/fallow4python/cli.py:1112:0` | radon | cyclomatic-complexity | function `summarize` complexity 12 (rank C) |
| warning |  | `src/fallow4python/cli.py:1721:4` | radon | cyclomatic-complexity | method `_render` complexity 16 (rank C) |
| warning |  | `src/fallow4python/cli.py:1904:0` | radon | cyclomatic-complexity | function `_run_tool` complexity 13 (rank C) |

### dead-code (18)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| warning |  | `build/lib/fallow4python/cli.py:50` | vulture | dead-code | unused import 'itertools' |
| warning |  | `build/lib/fallow4python/cli.py:821` | vulture | dead-code | unused variable 'nodes' |
| warning |  | `src/fallow4python/cli.py:50` | vulture | dead-code | unused import 'itertools' |
| warning |  | `src/fallow4python/cli.py:821` | vulture | dead-code | unused variable 'nodes' |
| info |  | `build/lib/fallow4python/cli.py:74` | vulture | dead-code | unused variable 'SEVERITY_RANK' |
| info |  | `build/lib/fallow4python/cli.py:79` | vulture | dead-code | unused variable 'CATEGORIES' |
| info |  | `build/lib/fallow4python/cli.py:132` | vulture | dead-code | unused variable 'details' |
| info |  | `build/lib/fallow4python/cli.py:144` | vulture | dead-code | unused variable 'evidence' |
| info |  | `build/lib/fallow4python/cli.py:154` | vulture | dead-code | unused variable 'duration_ms' |
| info |  | `build/lib/fallow4python/cli.py:1588` | vulture | dead-code | unused variable 'ingest_only' |
| info |  | `build/lib/fallow4python/cli.py:1591` | vulture | dead-code | unused function '_run_subprocess' |
| info |  | `src/fallow4python/cli.py:74` | vulture | dead-code | unused variable 'SEVERITY_RANK' |
| info |  | `src/fallow4python/cli.py:79` | vulture | dead-code | unused variable 'CATEGORIES' |
| info |  | `src/fallow4python/cli.py:132` | vulture | dead-code | unused variable 'details' |
| info |  | `src/fallow4python/cli.py:144` | vulture | dead-code | unused variable 'evidence' |
| info |  | `src/fallow4python/cli.py:154` | vulture | dead-code | unused variable 'duration_ms' |
| info |  | `src/fallow4python/cli.py:1588` | vulture | dead-code | unused variable 'ingest_only' |
| info |  | `src/fallow4python/cli.py:1591` | vulture | dead-code | unused function '_run_subprocess' |

### dependencies (16)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| warning |  | `-` | deptry | DEP002 | 'ruff' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'mypy' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'vulture' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'radon' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'deptry' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'xenon' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'import-linter' defined as a dependency but not used in the codebase |
| warning |  | `-` | deptry | DEP002 | 'coverage' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'ruff' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'mypy' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'vulture' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'radon' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'deptry' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'xenon' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'import-linter' defined as a dependency but not used in the codebase |
| warning |  | `pyproject.toml` | deptry | DEP002 | 'coverage' defined as a dependency but not used in the codebase |

### duplication (1)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| info |  | `src/fallow4python/cli.py:285` | duplication | clone-family | duplicated block (~6 lines) in 2 places: src/fallow4python/cli.py:285-290, src/fallow4python/cli.py:325-330 |

### lint (6)

| Sev | Changed | Location | Tool | Rule | Message |
|---|:--:|---|---|---|---|
| warning |  | `src/fallow4python/cli.py:50:8` | ruff | F401 | `itertools` imported but unused |
| warning |  | `src/fallow4python/cli.py:2046:34` | ruff | E702 | Multiple statements on one line (semicolon) |
| warning |  | `src/fallow4python/cli.py:2047:37` | ruff | E702 | Multiple statements on one line (semicolon) |
| warning |  | `src/fallow4python/cli.py:2048:38` | ruff | E702 | Multiple statements on one line (semicolon) |
| warning |  | `src/fallow4python/cli.py:2049:35` | ruff | E702 | Multiple statements on one line (semicolon) |
| warning |  | `src/fallow4python/cli.py:2065:38` | ruff | E702 | Multiple statements on one line (semicolon) |

## Tool runs

> Provenance — which analyzers actually ran, succeeded, failed, or were skipped, and how many findings each produced. **Implication:** this defines the report's coverage. A *skipped* tool means that dimension was **not assessed**: e.g. if coverage was skipped, the coverage component is `n/a` and there is no runtime evidence behind dead-code findings. Absence of findings from a tool that did not run is not evidence that no problems exist there.

| Tool | Status | Findings | Detail |
|---|---|---:|---|
| ruff | ran | 6 |  |
| mypy | ran | 0 |  |
| vulture | ran | 18 |  |
| radon-cc | ran | 38 |  |
| radon-mi | ran | 0 |  |
| deptry | ran | 16 |  |
| xenon | ran | 0 |  |
| import-linter | ran | 0 |  |
| coverage | skipped | 0 | no --coverage json provided |
| duplication | ran | 1 | built-in clone detector |
| cycles | ran | 0 | built-in import-graph cycles |
