# Golden vs twin

Golden: `djdarcy/repokit-throwaway-20261024-2`. Twin: `djdarcy/repokit-throwaway-20261024-3`.

## Tracked files

Only in the golden (old route):

- `.github/workflows/ci.yml`
- `.repokit.json`

Only in the twin (repokit):

- `.gitattributes`
- `.github/workflows/ci-python.yml`
- `.vscode/launch.json`
- `.vscode/settings.json`
- `__PKG__/cli.py`

In both: 25; identical after normalization: 10; differing: 15.

Identical: `.github/ISSUE_TEMPLATE/bug-report.md`, `.github/ISSUE_TEMPLATE/feature-request.md`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `.github/stale.yml`, `.github/workflows/release.yml`, `LICENSE`, `docs/.gitkeep`, `tests/one-offs/README.md`, `tests/output/.gitkeep`

### `.github/CODEOWNERS`

6 lines only in the golden, 7 only in the twin.

```diff
--- golden
+++ twin
@@ -2,13 +2,14 @@
 # the repo. Unless a later match takes precedence,
-# __OWNER__ will be requested for review when someone opens a pull request.
-*       @__OWNER__
+# __AUTHOR__ will be requested for review when someone opens a pull request.
+*       @__AUTHOR__
 
 # Core implementation
-*.py    @__OWNER__
+*.js    @__AUTHOR__
+*.py    @__AUTHOR__
 
 # Documentation
-/docs/   @__OWNER__
-*.md     @__OWNER__
+/docs/   @__AUTHOR__
+*.md     @__AUTHOR__
 
 # GitHub CI/CD
-/.github/ @__OWNER__
+/.github/ @__AUTHOR__
```

### `.github/FUNDING.yml`

3 lines only in the golden, 3 only in the twin.

```diff
--- golden
+++ twin
@@ -2,5 +2,5 @@
 
-github: __OWNER__
-ko_fi: __OWNER__
-buy_me_a_coffee: __OWNER__
+github: YOUR_GITHUB_USERNAME
+ko_fi: YOUR_GITHUB_USERNAME
+buy_me_a_coffee: YOUR_GITHUB_USERNAME
 
```

### `.github/release-template.md`

1 lines only in the golden, 1 only in the twin.

```diff
--- golden
+++ twin
@@ -27,3 +27,3 @@
 ```bash
-git clone https://github.com/__OWNER__/__NAME__.git
+git clone https://github.com/YOUR_GITHUB_USERNAME/__NAME__.git
 cd __NAME__
```

### `.gitignore`

24 lines only in the golden, 19 only in the twin.

```diff
--- golden
+++ twin
@@ -21,6 +21,3 @@
 # RepoKit standard private directories
-# NOTE: /private/ is excluded in consuming projects by the repokit
-# private-content protection block at the bottom of this file.
-# In the template itself, private/claude/.gitkeep is force-added
-# to preserve the directory structure.
+/private/
 /convos/
@@ -54,4 +51,4 @@
 .eggs/
-/lib/
-/lib64/
+lib/
+lib64/
 parts/
@@ -144,21 +141,19 @@
 # Add custom patterns below
-tests/output/*
-!tests/output/.gitkeep
-docs/images/bak/
-*.exe
-*.obj
 
-# Project-specific runtime files
-# (add project-specific ignores here)
+# Python (git-repokit language layer)
+__pycache__/
+*.py[cod]
+*.egg-info/
+.eggs/
+build/
+dist/
+.venv/
+venv/
+.pytest_cache/
+.mypy_cache/
+.ruff_cache/
+.coverage
+htmlcov/
 
-# RepoKit Private Content Protection (DO NOT REMOVE)
-CLAUDE.md
-.env.private
-**/private_*
-test-runs/
-private/temp/
-private/docs/
-test_runs/
-revisions/
-private/claude/
-private/notes/
+# Agent working state -- written by tools, never versioned
+CLAUDE.local.md
```

### `CHANGELOG.md`

5 lines only in the golden, 4 only in the twin.

```diff
--- golden
+++ twin
@@ -2,3 +2,3 @@
 
-All notable changes to this project will be documented in this file.
+All notable changes to __NAME__ are documented here.
 
@@ -11,6 +11,5 @@
 ### Added
+- The project's structure, from git-repokit.
 
-- Initial project structure from git-repokit-template.
-
-[Unreleased]: https://github.com/__OWNER__/__NAME__/compare/v0.1.0...HEAD
-[0.1.0]: https://github.com/__OWNER__/__NAME__/releases/tag/v0.1.0
+[Unreleased]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/compare/v0.1.0...HEAD
+[0.1.0]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/releases/tag/v0.1.0
```

### `CONTRIBUTING.md`

35 lines only in the golden, 19 only in the twin.

```diff
--- golden
+++ twin
@@ -4,46 +4,30 @@
 
-## Development Setup
+## Code of Conduct
 
-### Prerequisites
+Please note that this project is released with a Contributor Code of Conduct.
+By participating in this project you agree to abide by its terms.
 
-- **Python 3.10+**
-- **Git**
+## How Can I Contribute?
 
-### Clone and Install
+### Reporting Bugs
 
-```bash
-git clone https://github.com/__OWNER__/__NAME__.git
-cd __NAME__
-python -m venv .venv
-source .venv/bin/activate        # Linux/Mac
-# or: .venv\Scripts\activate     # Windows
-pip install -e ".[dev]"
-```
+This section guides you through submitting a bug report.
 
-### Run Tests
+### Suggesting Enhancements
 
-```bash
-python -m pytest tests/ -v
-```
+This section guides you through submitting an enhancement suggestion.
 
-## Project Structure
+### Pull Requests
 
-```
-__PKG__/
-  __init__.py         # Package initialization
-  __main__.py         # CLI entry (python -m __PKG__)
-  _version.py         # Version (PEP 440)
-tests/
-  conftest.py         # Shared fixtures
-  test_*.py           # Test files
-  one-offs/           # Quick checks, proof-of-concept scripts
-scripts/
-  repokit-common/     # Shared tools (git submodule)
-```
+The process described here has several goals:
 
-## Key Design Principles
+1. Maintain the project's quality
+2. Fix problems that are important to users
+3. Enable a sustainable system for maintainers to review contributions
 
-1. **Tests are important** -- write tests for new features
-2. **One-offs graduate** -- quick tests in `tests/one-offs/` can be promoted to proper tests
-3. **Cross-platform** -- works on Windows, Linux, macOS
-4. **Clean commits** -- use conventional commit format
+Please follow these steps to have your contribution considered by the maintainers:
+
+1. Fork the repository
+2. Create a new branch
+3. Make your changes
+4. Submit a pull request
```

### `README.md`

25 lines only in the golden, 43 only in the twin.

```diff
--- golden
+++ twin
@@ -2,7 +2,28 @@
 
-[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
-[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
-[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](docs/platform-support.md)
+[![GitHub Workflow Status][workflow-badge]][workflow-url]
+[![Version][version-badge]][version-url]
+[![Python][python-badge]][python-url]
+[![License][license-badge]][license-url]
+[![GitHub Discussions][discussions-badge]][discussions-url]
+
+[workflow-badge]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/actions/workflows/ci-python.yml/badge.svg
+[workflow-url]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/actions
+[version-badge]: https://img.shields.io/badge/version-1.0.0-blue
+[version-url]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/releases
+[python-badge]: https://img.shields.io/badge/python-%3E%3D3.7-darkgreen
+[python-url]: https://python.org/downloads
+[license-badge]: https://img.shields.io/badge/license-MIT-orange
+[license-url]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/blob/main/LICENSE
+[discussions-badge]: https://img.shields.io/badge/discussions-Welcome-lightgrey
+[discussions-url]: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/discussions
 
 A parity-check throwaway for git-repokit (safe to delete)
+
+## Overview
+
+## Features
+
+- Feature 1
+- Feature 2
+- Feature 3
 
@@ -11,11 +32,3 @@
 ```bash
-pip install __PKG__
-```
-
-### From Source
-
-```bash
-git clone https://github.com/__OWNER__/__NAME__.git
-cd __NAME__
-pip install -e ".[dev]"
+# Installation instructions here
 ```
@@ -25,3 +38,3 @@
 ```bash
-__NAME__ --help
+# Usage examples here
 ```
@@ -30,16 +43,18 @@
 
+### Prerequisites
+
+- List prerequisites here
+
+### Setup
+
 ```bash
-# Clone and install
-git clone https://github.com/__OWNER__/__NAME__.git
-cd __NAME__
-python -m venv .venv
-source .venv/bin/activate  # or .venv\Scripts\activate on Windows
-pip install -e ".[dev]"
+# Setup instructions here
+```
 
-# Run tests
-python -m pytest tests/ -v
+## Contributions
+Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on how to contribute.
 
-# Install git hooks (if using repokit-common submodule)
-bash scripts/repokit-common/install-hooks.sh
-```
+Like the project?
+
... (truncated)
```

### `ROADMAP.md`

7 lines only in the golden, 14 only in the twin.

```diff
--- golden
+++ twin
@@ -2,9 +2,16 @@
 
-The living roadmap is [Issue #1](https://github.com/__OWNER__/__NAME__/issues/1).
+The living roadmap for __NAME__ lives in the repository's first issue, kept pinned: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/issues/1. Notes and quick ideas go to the second: https://github.com/YOUR_GITHUB_USERNAME/__NAME__/issues/2.
 
-| Phase | Focus | Status |
-|-------|-------|--------|
-| 1 | Foundation | In progress |
-| 2 | Core features | Not started |
-| 3 | Refactor / modernization | Not started |
-| 4 | Advanced / future | Not started |
+This file points there so a reader of the tree finds the plan; the issue holds the detail and its history.
+
+## Now
+
+-
+
+## Next
+
+-
+
+## Later
+
+-
```

### `__PKG__/__init__.py`

1 lines only in the golden, 4 only in the twin.

```diff
--- golden
+++ twin
@@ -1,2 +1,5 @@
-"""__PKG__ - A new project."""
+"""__NAME__ - A parity-check throwaway for git-repokit (safe to delete)"""
+
 from ._version import __version__, __app_name__, PIP_VERSION
+
+__all__ = ["__version__", "__app_name__", "PIP_VERSION"]
```

### `__PKG__/__main__.py`

1 lines only in the golden, 3 only in the twin.

```diff
--- golden
+++ twin
@@ -1,4 +1,6 @@
 """Allow running as: python -m __PKG__"""
+
 from .cli import main
+
 if __name__ == "__main__":
-    main()
+    raise SystemExit(main())
```

### `__PKG__/_version.py`

5 lines only in the golden, 9 only in the twin.

```diff
--- golden
+++ twin
@@ -10,7 +10,10 @@
 
+To sync versions: python scripts/repokit-common/sync-versions.py
+To bump version: python scripts/repokit-common/sync-versions.py --bump patch
+
 Version levels:
   PROJECT_PHASE: Global project maturity (prealpha -> alpha -> beta -> stable).
-       Changes rarely, when the overall project hits a threshold.
+                 Changes rarely, when the overall project hits a threshold.
   PHASE:         Per-MINOR feature set maturity (alpha -> beta -> "" for stable).
-       Drops when a MINOR's feature set is complete.
+                 Drops when a MINOR's feature set is complete.
 """
@@ -22,2 +25,3 @@
 PHASE = ""  # Per-MINOR feature set: "" (stable), "alpha", "beta", "rc1", etc.
+PRE_RELEASE_NUM = 1  # PEP 440 pre-release number (e.g., a1, b2)
 
@@ -27,3 +31,3 @@
 # Auto-updated by git hooks - do not edit manually
-__version__ = "0.1.0_main_6-20261024-aaab0597"
+__version__ = "0.1.0"
 __app_name__ = "__NAME__"
@@ -64,3 +68,3 @@
     - Dev branch: 0.1.0_dev_3-20260404-hash -> 0.1.0.dev3
-    - Alpha: 0.1.0-alpha_main_3 -> 0.1.0a0
+    - Alpha: 0.1.0-alpha_main_3 -> 0.1.0a1
     """
@@ -69,3 +73,3 @@
     # Map phase to PEP 440 pre-release segment
-    phase_map = {"alpha": "a0", "beta": "b0"}
+    phase_map = {"alpha": f"a{PRE_RELEASE_NUM}", "beta": f"b{PRE_RELEASE_NUM}"}
     if PHASE:
```

### `docs/platform-support.md`

6 lines only in the golden, 10 only in the twin.

```diff
--- golden
+++ twin
@@ -1,7 +1,11 @@
-# Platform Support
+# Platform support
 
-| Platform | Status |
-|----------|--------|
-| Windows 10/11 | Tested |
-| Linux | Expected to work |
-| macOS | Expected to work |
+What __NAME__ is tested on, and what it is expected to run on.
+
+| Platform | Status | Notes |
+|---|---|---|
+| Windows 10/11 | tested | the development platform |
+| Linux (Ubuntu LTS) | expected | CI runs here |
+| macOS | expected | not routinely tested |
+
+Status words: **tested** means the suite runs there on every push; **expected** means nothing platform-specific is known to break but nobody runs the suite there routinely; **unsupported** means a known gap, named in Notes.
```

### `pyproject.toml`

5 lines only in the golden, 8 only in the twin.

```diff
--- golden
+++ twin
@@ -14,3 +14,3 @@
 ]
-keywords = ["repokit", "throwaway"]
+keywords = []
 classifiers = [
@@ -38,5 +38,5 @@
 [project.urls]
-Homepage = "https://github.com/__OWNER__/__NAME__"
-Repository = "https://github.com/__OWNER__/__NAME__"
-Issues = "https://github.com/__OWNER__/__NAME__/issues"
+Homepage = "https://github.com/YOUR_GITHUB_USERNAME/__NAME__"
+Repository = "https://github.com/YOUR_GITHUB_USERNAME/__NAME__"
+Issues = "https://github.com/YOUR_GITHUB_USERNAME/__NAME__/issues"
 
@@ -54,2 +54,5 @@
 testpaths = ["tests"]
+# The package imports from the project root without an install: the vendored
+# pre-push hook runs `python -P -m pytest`, which keeps the root off sys.path,
+# and the first push (`repokit create --github`) comes before any pip install.
 pythonpath = ["."]
@@ -62,3 +65,3 @@
 changelog = "CHANGELOG.md"
-repo-url = "https://github.com/__OWNER__/__NAME__"
+repo-url = "https://github.com/YOUR_GITHUB_USERNAME/__NAME__"
 tag-prefix = "v"
```

### `tests/conftest.py`

10 lines only in the golden, 1 only in the twin.

```diff
--- golden
+++ twin
@@ -3,3 +3,2 @@
 import pytest
-from pathlib import Path
 
@@ -8,3 +7,3 @@
 def tmp_project(tmp_path):
-    """Create a temporary project directory for testing."""
+    """A temporary project directory for a test to work in."""
     project_dir = tmp_path / "test_project"
@@ -12,9 +11 @@
     return project_dir
-
-
-@pytest.fixture
-def sample_data(tmp_path):
-    """Create sample data files for testing."""
-    data_dir = tmp_path / "data"
-    data_dir.mkdir()
-    return data_dir
```

### `tests/test_version.py`

2 lines only in the golden, 2 only in the twin.

```diff
--- golden
+++ twin
@@ -1,2 +1,2 @@
-"""Tests for version module."""
+"""Tests for the version module."""
 
@@ -20,3 +20,3 @@
 def test_phase_valid():
-    """PHASE is empty string (stable release) or a string like 'alpha', 'beta', 'rc1'."""
+    """PHASE is empty (a stable release) or a string like 'alpha', 'beta', 'rc1'."""
     assert isinstance(PHASE, str)
```

## Vault (private/) tracked files

Only in the golden (old route):

- `claude/.gitkeep`
- `claude/_maps/MOC-__NAME__-architecture.md`
- `claude/issues/issue_notes_ideas.md`
- `claude/issues/issue_roadmap.md`

Only in the twin (repokit):

- `claude/_maps/MOC-__NAME__.md`
- `claude/_todo/ACTIVE-WORK.md`

In both: 10; identical after normalization: 5; differing: 5.

Identical: `.gitignore`, `claude/commits/.gitkeep`, `claude/issues/.gitkeep`, `docs/.gitkeep`, `notes/.gitkeep`

### `CLAUDE.md`

21 lines only in the golden, 20 only in the twin.

```diff
--- golden
+++ twin
@@ -1,30 +1,29 @@
-# CLAUDE.md — `private/` (__NAME__ knowledge vault)
+# __NAME__ -- the private vault
 
-Guidance for working **inside this folder**. The project itself — architecture, build/test commands, workflows — is in the repo-root `CLAUDE.md` and the global `~/.claude/CLAUDE.md`. Nothing here repeats them.
+This folder is its own git repository, ignored by the project and never pushed. It holds the project's thinking: design analyses, postmortems, notes, issue drafts, commit messages, and the map an oracle session keeps.
 
-> **Scope rule:** this file carries only what a session needs *before* it would know to look at the vault. Anything the vault already maintains gets a pointer, never a copy — copies rot while the original moves on.
+## Layout
 
-## Where to start reading
+- `claude/` -- dated documents (`YYYY-MM-DD__HH-MM-SS__<type>__<topic>.md`); `claude/notes/`, `claude/issues/`, `claude/commits/` for the smaller kinds
+- `claude/_maps/MOC-__NAME__.md` -- the map of content: the project's arcs and the documents behind each
+- `claude/_oracle/` -- the oracle's index: `manifest.md` (every document, one line each), `concepts.md` (the project's own words), `backlinks.md` (generated)
+- `claude/_todo/` -- `OPEN-LOOPS.md` (deferred work, each with its next action) and `ACTIVE-WORK.md` (the working set)
 
-1. **`claude/_maps/MOC-__NAME__-architecture.md`** — the map: arcs, issue tables, and the maintained vault-structure table + naming conventions.
-2. **`claude/_todo/OPEN-LOOPS.md`** — outstanding work that is *not* a GitHub issue.
-3. **The newest `claude/*__whereweare.md`** — the resume point (none yet).
-4. **`claude/_oracle/`** — `manifest.md`, `concepts.md`, `backlinks.md` (generated). `/oracle` reads these instead of scanning the vault.
+## Conventions
 
-## Writing in the vault
+- Link with wikilinks relative to `claude/`: `[[notes/__YEAR__-01-01__00-00-00__both_topic]]`, never `../` paths.
+- Frontmatter on every document: `type`, `date`, `author`, `tags`.
+- A finished document's body is not edited; it is extended with a dated addendum.
+- Commit by named path; the vault is local-only.
 
-**Wikilinks resolve by vault-root path or bare filename — never `../` traversal.** `[[_todo/OPEN-LOOPS]]` works; `[[../../anything]]` is dead in the graph. No `.md` suffix in the target, no `[[#Heading]]` anchors, and inside markdown tables use alias-free `[[target]]`.
+## Three sessions per project
 
-**Regenerate the backlink index** after adding docs (from the project root; the script is vendored with repokit-common at `scripts/repokit-common/`):
+A project of any size runs three Claude Code sessions, each named `<PROJECT>__<YYYY-MM-DD>__<Role>`:
 
-```bash
-PYTHONIOENCODING=utf-8 python scripts/repokit-common/generate-backlinks.py private/claude --validate
-```
+| Role | Model | First command |
+|---|---|---|
+| Decisions | the strongest available | `/familiarize`, then the design work |
+| Work | Opus | the plan or goal the decisions session wrote |
+| Oracle | any | `/obsidian-update`, then `/obsidian-loop` |
 
-**Checkpoint before refreshing planning docs.** Commit their current state first so every refresh is a tracked diff. Archive a live GitHub issue body into `claude/issues/issue_NN_YYYY.MM.DD_00_pre-refresh-body.md` before replacing it.
-
-**Never alter the body of an existing dated doc.** Add frontmatter, a `## Related` section, or an addendum.
-
-## Related skills
-
-`/oracle` reads the vault · `/obsidian` captures notes · `/obsidian-update` re-syncs the map after work lands · `/obsidian-init` bootstraps one
+`repokit create` laid this skeleton and wrote the oracle's first prompt to `claude/_oracle/bootstrap-prompt.md`; the oracle session builds the map from it.
```

### `claude/_oracle/backlinks.md`

36 lines only in the golden, 2 only in the twin.

```diff
--- golden
+++ twin
@@ -1,39 +1,3 @@
----
-type: oracle-metadata
-purpose: Reverse-link index -- which documents reference each document
-generated-by: scripts/generate-backlinks.py
----
+# Backlinks
 
-# Backlinks Index
-
-Auto-generated reverse-link index. For each document, lists all documents that
-reference it via `[[wikilinks]]`. Regenerate with:
-
-```bash
-python scripts/generate-backlinks.py
-```
-
-**5** notes with backlinks, **8** total references
-
-## MOC-__NAME__-architecture
-
-- `concepts`
-- `manifest`
-
-## OPEN-LOOPS
-
-- `MOC-__NAME__-architecture`
-- `manifest`
-
-## manifest
-
-- `OPEN-LOOPS`
-- `concepts`
-
-## issue_notes_ideas
-
-- `MOC-__NAME__-architecture`
-
-## issue_roadmap
-
-- `MOC-__NAME__-architecture`
+Generated by `scripts/repokit-common/generate-backlinks.py private/claude`; do not edit by hand.
```

### `claude/_oracle/concepts.md`

16 lines only in the golden, 5 only in the twin.

```diff
--- golden
+++ twin
@@ -1,24 +1,12 @@
 ---
-type: oracle-metadata
+type: concepts
 date: __DATE__
-last_refreshed: __DATE__
 author: claude
-tags:
-  - oracle
-  - concepts
-  - index
 ---
 
-# Concept Index -- __NAME__
+# Concepts -- __NAME__'s own words
 
-> Concept -> document lookup. **Check here before grepping the vault.** Each entry names the documents where a concept is actually *designed or decided*, not merely mentioned.
->
-> Paths relative to `private/claude/`. Companions: [[_oracle/manifest|manifest]] (processing status), [[_oracle/backlinks|backlinks]] (generated reverse links), [[_maps/MOC-__NAME__-architecture|the MOC]] (narrative arcs).
+Terms this project coined or repurposed, each with the document that defines it.
 
----
-
-## Project tooling & process
-
-### The parity check
-This repository exists to be compared with a git-repokit twin.
-- `issues/issue_roadmap` -- **the stated purpose** (issue #1)
+| Term | Meaning | Defined in |
+|---|---|---|
```

### `claude/_oracle/manifest.md`

54 lines only in the golden, 4 only in the twin.

```diff
--- golden
+++ twin
@@ -1,64 +1,10 @@
 ---
-type: oracle-metadata
+type: manifest
 date: __DATE__
-last_refreshed: __DATE__
 author: claude
-tags:
-  - oracle
-  - manifest
 ---
 
-# Oracle Manifest -- __NAME__
+# Manifest -- every document in the vault, one line each
 
-> Processing status for every document and GitHub issue in the vault. The oracle reads this in Phase 1a to skip full vault scans. **Compare `ls` of the vault against this file to find unprocessed docs** -- anything on disk but absent here is **NEW**.
-
-**Status vocabulary**
-
-| Status | Meaning |
-|---|---|
-| `linked` | Classified (headers/frontmatter) and wikilinked from a MOC |
-| `linked+read` | As above, AND deep-read in full |
-| `read` | Read/classified, not yet worth a MOC link |
-| `synth` | Read and synthesized into a note or MOC section |
-| `NEW` | Present on disk, not yet processed |
-
-**Bootstrap note.** Created __DATE__ by `/obsidian-init` in the same pass as [[_maps/MOC-__NAME__-architecture|the MOC]]. Both issue bodies were read in full (they were written in this pass).
-
-**Also see:** [[_todo/OPEN-LOOPS|_todo/OPEN-LOOPS.md]] -- surface it in Phase 1a.
-
----
-
-## Top-level documents (0)
-
-None yet.
-
----
-
-## Subdirectories
-
-| Path | Count | Status | Note |
-|---|---|---|---|
-| `issues/` | 2 | linked+read | `issue_roadmap`, `issue_notes_ideas`: the bodies of #1 and #2 |
-| `commits/` | 0 | -- | empty |
-| `_maps/` | 1 | -- | the MOC |
-| `_oracle/` | 3 | -- | excluded from the count (metadata) |
-| `_todo/` | 1 | -- | OPEN-LOOPS |
-
----
-
-## GitHub Issues
-
-Repo: `__OWNER__/__NAME__`. Last synced **__DATE__**.
-
-### Open -- tracked
-
-| # | Title | Local file | Status |
-|---|---|---|---|
-| 1 | Roadmap | `issues/issue_roadmap.md` | linked+read |
-| 2 | Quick Notes -- Bugs, Features, Ideas | `issues/issue_notes_ideas.md` | linked+read |
-
----
-
-## Next processing pass
-
-1. Add rows as documents arrive; regenerate backlinks.
+| Document | Type | What it holds |
+|---|---|---|
```

### `claude/_todo/OPEN-LOOPS.md`

42 lines only in the golden, 3 only in the twin.

```diff
--- golden
+++ twin
@@ -3,3 +3,2 @@
 date: __DATE__
-last_refreshed: __DATE__
 author: claude
@@ -7,54 +6,9 @@
   - todo
-  - open-loops
-  - meta
 ---
 
-# Open Loops -- __NAME__
+# Open loops -- __NAME__
 
-> The single surface for outstanding work that is **not** already a GitHub issue: deferred decisions, dangling pointers, stale documents, and cleanup that keeps getting postponed. GitHub issues are the system of record for *product* work -- this file tracks what falls between the issues.
->
-> **Maintain it:** add a row whenever you defer something instead of finishing it. Remove the row when it lands. Record corrections rather than deleting superseded claims -- readers of older docs will expect the old framing.
+Deferred work: each row says what it is, why it waits, and the next action.
 
-Referenced from [[_oracle/manifest|the manifest]] so the oracle surfaces it in Phase 1a.
-
----
-
-## 1. Held -- decided, not yet executed
-
-| Item | Detail | Blocked on |
+| Loop | Status | Next action |
 |---|---|---|
-
----
-
-## 2. Stale -- documents that describe a past state as if current
-
-| Document | Problem | Fix |
-|---|---|---|
-
----
-
-## 3. Dangling pointers -- referenced but absent
-
-| Referenced by | Target | Status |
-|---|---|---|
-
----
-
-## 4. Needs triage
-
-| Item | Question |
-|---|---|
-
----
-
-## 5. Product work with no issue yet
-
----
-
-## 6. Known debt / through-line notes
-
----
-
-## Recently closed loops
-
-*(__DATE__)* vault bootstrapped by `/obsidian-init`
```

## The rest of the record

- **vendored** (same)
- **untracked** (DIFFERS)
  - golden: `["!! .pytest_cache/", "!! __PKG__/__pycache__/", "!! private/", "!! scripts/repokit-common/__pycache__/", "!! tests/__pycache__/"]`
  - twin: `["!! .pytest_cache/", "!! CLAUDE.md", "!! __PKG__/__pycache__/", "!! private/", "!! tests/__pycache__/", "?? .repokit.json"]`
- **hooks** (same)
- **branches** (DIFFERS)
  - golden: `["main", "origin", "origin/main"]`
  - twin: `["main", "origin/main"]`
- **remotes** (DIFFERS)
  - golden: `["origin\thttps://github.com/__OWNER__/__NAME__.git (fetch)", "repokit-common\thttps://github.com/DazzleTools/git-repokit-common.git (fetch)"]`
  - twin: `["origin\thttps://github.com/__OWNER__/__NAME__.git (fetch)"]`
- **commits** (DIFFERS)
  - golden: `["fix: pytest pythonpath so the pre-push hook can import the package", "feat: initial project setup with A parity-check throwaway for git-repokit (safe to delete)", "Merge commit '69cc38c6786cfbe221668ead71d220d2d54c7785' as 'scripts/repokit-common'", "Squashed 'scripts/repokit-common/' content from commit cb07f64", "feat: initialize project from git-repokit-template", "Initial commit"]`
  - twin: `["Initial repository setup with RepoKit", "Merge commit '67ecd4ed6374147bc8e88f9c703fa517e2123828' as 'scripts/repokit-common'", "Squashed 'scripts/repokit-common/' content from commit cb07f64", "Initial commit"]`
- **vault_commits** (DIFFERS)
  - golden: `["vault: /obsidian-init bootstrap (parent 6f75cc4)", "init: private workspace for __NAME__"]`
  - twin: `["init: private workspace for __NAME__"]`
- **vault_untracked** (DIFFERS)
  - golden: `[]`
  - twin: `["?? claude/_oracle/bootstrap-prompt.md", "?? claude/instructions/", "?? claude/issues/issue_notes.md", "?? claude/issues/issue_roadmap.md"]`

## GitHub, read back

- **environments** (same)
- **issues**: golden [(1, 'Roadmap', ['evergreen', 'pinned', 'roadmap']), (2, 'Quick Notes -- Bugs, Features, Ideas', ['evergreen', 'pinned', 'scratchpad'])]; twin [(1, 'Roadmap', ['evergreen', 'pinned', 'roadmap']), (2, 'Quick Notes -- Bugs, Features, Ideas', ['evergreen', 'pinned', 'scratchpad'])]
  - #1 body differs (21 diff lines); first lines:
    ```diff
    --- golden
    +++ twin
    @@ -3,3 +3 @@
    -Evergreen tracking issue for __NAME__ development priorities.
    -
    -This repository is a throwaway golden: a project made by the old route (git-repokit-template, `/create-project`, `/github-issues-setup`, `/obsidian-init`) so git-repokit can compare its own output against it.
    +Evergreen tracking issue for __NAME__ development priorities. The repository's `ROADMAP.md` points here; this issue holds the detail and its history.
    @@ -8,3 +6 @@
    -- [x] Repository created from git-repokit-template
    -- [ ] Project files customized
    -- [ ] Private vault initialized
    +- [ ] The first working version
    @@ -13 +9 @@
    -- [ ] (none planned: a comparison fixture)
    +- [ ] ...
    @@ -16 +12 @@
    -- [ ] (none planned)
    +- [ ] ...
    @@ -19 +15 @@
    -- [ ] (none planned)
    ```
  - #2 body differs (11 diff lines); first lines:
    ```diff
    --- golden
    +++ twin
    @@ -9 +9 @@
    -- (none yet)
    +-
    @@ -12 +12 @@
    -- Compare this golden with a `repokit create` twin, file by file and setting by setting.
    +-
    @@ -15 +15 @@
    -- Made by the old route on __DATE__ for git-repokit's parity check.
    +-
    ```
- **labels**: only in the golden ['accessibility', 'bug', 'documentation', 'duplicate', 'enhancement', 'good first issue', 'help wanted', 'invalid', 'question', 'wontfix']; only in the twin []; same name, different colour or description []
- **pinned** (same)
- **protection** (same)
- **prs** (DIFFERS)
  - golden: `[]`
  - twin: `[{"author": "app/dependabot", "number": 5, "title": "Bump actions/cache from 4 to 6"}, {"author": "app/dependabot", "number": 4, "title": "Bump actions/checkout from 4 to 7"}, {"author": "app/dependabot", "number": 3, "title": "Bump actions/setup-python from 5 to 7"}]`
- **repo** (DIFFERS)
  - golden: `{"defaultBranchRef": "main", "deleteBranchOnMerge": false, "description": "Golden: the old route, for git-repokit's parity check (throwaway; safe to delete)", "hasDiscussionsEnabled": true, "hasIssuesEnabled": true, "hasProjectsEnabled": true, "hasWikiEnabled": true, "homepageUrl": "", "isTemplate": false, "licenseInfo": "gpl-3.0", "repositoryTopics": ["repokit", "throwaway"], "visibility": "PRIVATE"}`
  - twin: `{"defaultBranchRef": "main", "deleteBranchOnMerge": false, "description": "A parity-check throwaway for git-repokit (safe to delete)", "hasDiscussionsEnabled": true, "hasIssuesEnabled": true, "hasProjectsEnabled": true, "hasWikiEnabled": true, "homepageUrl": "", "isTemplate": false, "licenseInfo": "gpl-3.0", "repositoryTopics": ["repokit", "throwaway"], "visibility": "PRIVATE"}`
- **runs** (DIFFERS)
  - golden: `["CI [push] -> failure", "CI [push] -> success", "Dependabot Updates [dynamic] -> success", "Dependabot Updates [dynamic] -> success", "Initialize from template [push] -> success"]`
  - twin: `["CI (Python) [pull_request] -> success", "CI (Python) [pull_request] -> success", "CI (Python) [pull_request] -> success", "CI (Python) [push] -> success", "Dependabot Updates [dynamic] -> success", "Dependabot Updates [dynamic] -> success", "Dependabot Updates [dynamic] -> success", "Dependabot Updates [dynamic] -> success"]`
