# fallow4python

**Codebase intelligence for Python.** One command runs your quality tools, correlates their signals into prioritized insights, audits changed code with a pass/fail verdict, and emits a single report — human, Markdown, JSON, or SARIF.

`fallow4python` is a [Fallow](https://fallow.tools/)-style tool for Python: zero-config and `pip install`-able, with the engine itself written in pure standard library. Point it at a repo and it tells you what's wrong, where the problems concentrate, and what's safe to delete.

```
$ fallow4python
fallow4python - python codebase intelligence

  Health: B  (82.4/100)   31 findings, 4120 LOC
          coverage 78 | maintainability 85 | complexity 91 | cleanliness 74

  ! Complexity       4
  - Dead code        9
  x Architecture     1

  Insights
  x Circular import (app/services.py)
      circular import among 2 modules: app.services -> app.models -> app.services
  ! Risk hotspot (app/billing.py)
      high complexity (rank D) and only 34% covered — likely to break silently
  - Likely safe to delete (app/legacy.py:88)
      unused symbol `old_handler`, 0% covered at runtime
```

---

## Why

Python has excellent quality tools, but they don't talk to each other. You run `ruff`, then `mypy`, then `vulture`, then `radon`, then `deptry`, read five different output formats, and still have to figure out which problems actually matter. Nothing tells you that a function flagged as "unused" is *also* untested (so it's genuinely safe to delete), or that the one file three tools keep flagging is where you should spend your afternoon.

`fallow4python` runs the tools for you, normalizes everything into one schema, and **correlates the signals** — turning a pile of raw warnings into a ranked, actionable picture of codebase health. It also adds two capabilities the standard Python toolchain lacks entirely: **duplicate-code detection** and **circular-import detection**.

## Features

- **Zero-config orchestration.** Runs `ruff`, `mypy`, `vulture`, `radon` (complexity + maintainability), `deptry`, and `xenon` itself. No setup, no glue scripts.
- **Two built-in analyzers, no dependencies.** Clone-family duplication detection (hashed, normalized sliding windows) and circular-import detection (AST import graph + Tarjan strongly-connected-components). Pure stdlib.
- **A correlation engine.** Combines findings across tools into high-leverage *Insights*: "likely safe to delete," "risk hotspot," "concentrated problems," "circular import."
- **Change-scoped audits.** `fallow4python audit --base origin/main` parses the git diff, scopes findings to the lines you actually changed, and returns a **PASS / WARN / FAIL** verdict with a real exit code — a CI gate that judges the diff, not the whole repo.
- **One health score.** A transparent 0–100 score and letter grade, built from coverage, maintainability, complexity, and cleanliness.
- **Four output formats.** Colored terminal output, Markdown, a versioned JSON envelope, and SARIF 2.1.0 for GitHub code scanning.
- **Self-documenting reports.** Every section of the Markdown report explains what it measures and what it implies — readable by a teammate or an LLM with zero prior context.
- **Live animated progress.** While the analyzers run, a colored, animated checklist shows each tool's status in real time (TTY-only; rendered to stderr, so it never touches piped report output, and disabled by `--no-color`).
- **Bring-your-own-output mode.** Already run the tools in CI? Feed `fallow4python` their saved output with `--from-dir` and skip re-running them.

## Install

```bash
pip install fallow4python
```

This installs the `fallow4python` command and pulls in the analyzers it orchestrates (`ruff`, `mypy`, `vulture`, `radon`, `deptry`, `xenon`), so it works out of the box:

```bash
fallow4python --help
fallow4python            # scan the current directory
```

For the optional analyzers — `import-linter` (only runs when a contract is configured) and `coverage` (only needed when you pass `--coverage`) — install the extra:

```bash
pip install "fallow4python[full]"
```

### From source

```bash
git clone https://github.com/your-org/fallow4python
cd fallow4python
pip install -r requirements.txt   # the analyzer tools
pip install -e .                  # the fallow4python command (editable)
```

## Requirements

- **Python 3.9+**.
- `fallow4python`'s own code is **pure standard library** — the dependencies it declares are the external analyzer tools it shells out to. Any analyzer that isn't installed is simply skipped and noted in the report, and in `--from-dir`/`--no-run` mode you don't need any of them.
- `git` is required only for `audit` and other change-scoped runs.

You can also run it without installing, straight from a checkout:

```bash
python -m fallow4python --help
```

## Quick start

```bash
fallow4python                              # full scan of the current directory
fallow4python summary                      # one-screen health grade + counts
fallow4python path/to/project              # scan a specific path
fallow4python dead-code                    # just the deletion candidates
fallow4python audit --base origin/main     # gate a change set, with a verdict + exit code
fallow4python --coverage coverage.json     # feed runtime coverage for delete-confidence
fallow4python --format markdown --markdown-out report.md   # write a Markdown report
```

## Subcommands

| Command | What it does |
|---|---|
| `scan` *(default)* | Run everything, correlate, and report on the whole codebase. |
| `audit` | Change-scoped run against a git base ref; emits a PASS/WARN/FAIL verdict. Ideal for CI / PRs. |
| `health` | Just the health score and component breakdown. |
| `dead-code` | Only the dead-code findings and deletion-candidate insights. |
| `summary` | A compact one-screen overview — grade, component bars, and finding counts. |

## The health score

A single 0–100 number and letter grade. **Higher is better.** It's a weighted average of up to four components, each independently scaled 0–100:

| Component | Weight | What it measures |
|---|---:|---|
| coverage | 0.30 | Percent of lines exercised by the test suite. Requires `--coverage`; otherwise `n/a`. |
| maintainability | 0.25 | Mean of radon's Maintainability Index across files (volume + complexity + length). |
| complexity | 0.20 | Percent of functions *not* flagged as overly complex. |
| cleanliness | 0.25 | Inverse of weighted defect density — errors and warnings per 1,000 LOC, errors counted 3×. |

Any component that is `n/a` (e.g. coverage with no test run) is dropped, and the remaining weights are renormalized so the score is always out of 100.

**Grade bands:** A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 60 · F < 60.

The grade is a starting point, not the whole story — read which component is low. A `0.0` cleanliness alongside otherwise-decent components usually means a high *count* of lint/type findings relative to size, not deep structural rot.

## Insights (the correlation engine)

Raw findings tell you *what* a single tool saw. Insights combine tools to tell you what to *do*:

- **Likely safe to delete** — a symbol is both statically unused (vulture) *and* unexercised at runtime (coverage). Static-unused alone is a guess; add runtime evidence and it becomes a confident deletion.
- **Risk hotspot** — high cyclomatic complexity combined with low coverage: the code most likely to break silently.
- **Concentrated problems** — one file flagged by several different tools. Fixing it clears the most signal per unit of effort.
- **Circular import** — a dependency cycle between modules, detected from the AST import graph.

Insights are the recommended starting point; the Findings table is the underlying evidence for each one.

## Change audits & CI gating

`fallow4python audit` judges a *change*, not the whole repository:

```bash
fallow4python audit --base origin/main
```

- **FAIL** — the change introduced new error-level problems on the lines it modified.
- **WARN** — the change touched files with pre-existing issues but added no new errors.
- **PASS** — neither.

It exits non-zero on FAIL, so it drops straight into CI. Use `--gate all` to additionally fail on inherited (pre-existing) errors, or `--fail-on {info,warning,error}` for a severity threshold on a full scan.

### GitHub Actions example

```yaml
name: fallow4python
on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # fallow4python needs history for the diff
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install fallow4python
      - run: fallow4python audit --base origin/${{ github.base_ref }}

  # Optional: upload SARIF so findings annotate the PR inline
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install fallow4python
      - run: fallow4python --format sarif --sarif-out fallow4python.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: fallow4python.sarif
```

## Output formats

| Format | Flag | Use |
|---|---|---|
| Human | *(default)* | Colored terminal summary for local use. |
| Markdown | `--format markdown` / `--markdown-out FILE` | A self-documenting report for PRs, docs, or handing to an LLM. |
| JSON | `--format json` / `--json-out FILE` | A versioned envelope (`schema_version` 1.0) for piping into other tooling. |
| SARIF | `--format sarif` / `--sarif-out FILE` | SARIF 2.1.0 for GitHub code scanning / inline annotations. |

You can write several at once: `--json-out a.json --markdown-out b.md --sarif-out c.sarif`.

## Bring-your-own-output mode

If your CI already runs these tools, point `fallow4python` at the saved output instead of re-running anything:

```bash
fallow4python --from-dir .quality --no-run --markdown-out report.md
```

`fallow4python` looks for the conventional filenames each tool produces in that directory (e.g. `ruff.json`, `mypy.txt`, `vulture.txt`, `radon-cc.json`, `radon-mi.json`, `deptry.json`, `xenon.txt`, `coverage.json`). You can also point at individual files with the per-tool flags: `--ruff`, `--mypy`, `--vulture`, `--radon-cc`, `--radon-mi`, `--deptry`, `--xenon`, `--import-linter`, `--coverage`.

## Configuration reference

| Flag | Default | Description |
|---|---|---|
| `--base REF` | `origin/main` → `main` | Git base ref for a change-scoped audit. |
| `--tools LIST` | all | Comma-separated subset of tools/analyzers to run. |
| `--from-dir DIR` | — | Ingest pre-saved tool outputs from this directory. |
| `--no-run` | off | Don't run any tools; ingest saved output only. |
| `--coverage FILE` | — | Path to a coverage.py JSON report (enables the coverage component + delete-confidence). |
| `--coverage-min N` | 80 | Coverage threshold below which a file is considered undertested. |
| `--radon-min-rank {A–F}` | C | Complexity rank at or worse than which a function is flagged. |
| `--fail-on {none,info,warning,error}` | none | Exit non-zero if any finding reaches this severity. |
| `--gate {changed,all}` | changed | In `audit`: gate on changed code only, or also fail on inherited errors. |
| `--format {human,markdown,json,sarif}` | human | Format written to stdout. |
| `--json-out` / `--markdown-out` / `--sarif-out` | — | Write that format to a file (in addition to stdout). |
| `--max-per-section N` | 100 | Cap rows per category in the report. |
| `--no-color` | off | Disable ANSI color. |
| `--timeout N` | 300 | Per-tool subprocess timeout, in seconds. |

## How it works

`fallow4python` runs each analyzer as a subprocess, parses its native output (preferring JSON, falling back to text), and maps every result into a common `Finding` / `Metric` schema tagged with a category (`lint`, `typing`, `dead-code`, `complexity`, `maintainability`, `dependencies`, `duplication`, `architecture`, `coverage`). The two built-in analyzers run in-process:

- **Duplication** hashes overlapping windows of normalized source lines and groups matching windows into clone families, merging adjacent matches.
- **Circular imports** builds a module dependency graph from the AST (resolving relative imports) and reports every strongly-connected component with more than one node.

The correlation engine then joins findings across tools by file and symbol to produce Insights, and the health scorer reduces everything to the four-component score above.

## Testing

The suite is plain `pytest`; coverage is measured with `coverage.py`:

```bash
pip install -e ".[dev]"
coverage run -m pytest          # run the tests under coverage
coverage report                 # see line coverage
```

### Coverage runs by default

A scan runs your test suite under `coverage.py` automatically and folds the
result into the health score — no flag needed:

```bash
fallow4python                 # runs `pytest` under coverage, scores it
```

To skip the test run (faster, or in environments without a runner), pass
`--ignore-tests`; the `coverage` component then becomes `n/a` and the score
renormalizes over the remaining three components:

```bash
fallow4python --ignore-tests
```

Override the runner with `--test-command` (anything runnable via
`coverage run -m`):

```bash
fallow4python --test-command "pytest -q tests"
fallow4python --test-command "unittest discover"
```

This requires `coverage` (and your test runner) installed in the same
environment as fallow4python — `pip install coverage pytest`, or
`pip install "fallow4python[dev]"`. It uses a private coverage data file (never
clobbering your `.coverage`), respects your `[tool.coverage.run]` config when
present, ignores files outside the scanned tree, and skips gracefully if
coverage isn't available. You can also supply a pre-made report instead:

```bash
coverage run -m pytest && coverage json -o coverage.json
fallow4python --coverage coverage.json
```