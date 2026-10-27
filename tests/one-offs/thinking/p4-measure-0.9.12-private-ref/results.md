# 0.9.12 measure: the ambiguous `private` ref, what reaches the public branches, and a create that writes into its parent

Measured 2026-10-25 against git-repokit 0.9.11 (`2a9f55a`). Every create, reset and adopt here ran in throwaway repositories the probes made under `%TEMP%`; the fix was tried in a scratch COPY of the package; the checkout and every real repository were untouched (djdarcy: "Please be very careful with reset hard as we could lose real work. It sholud be tested against a dummy repo." / "Or be making sure you actually backup things first."). The adopt probe copies each dummy project before adopt runs and compares against the copy.

## Question

Which git calls break when a branch and a folder share the name `private`, and once the reset succeeds, does any private file reach a public branch? This decides the fix's shape and whether the cleaning step behind the reset, which has never run, is safe to switch on. It also decides whether the README's known-issue note can come out.

## Method

| Script | What it does | Known-answer check |
|---|---|---|
| `probe.py` | A: a tiny repo with branch `private` and folder `private/`, each candidate git command run. B: real creates of all five private-branch strategies, with the shipped code and with a scratch copy that adds `--` after the two `reset --hard <branch>` calls. C: each branch's tree classified for private paths | the `private` branch itself must show its private files (CLAUDE.md and the three instruction files), or the classifier is broken |
| `trace_vscode.py` | one verbose patched create, the private branch's history file by file | explained a file-count mismatch (below) |
| `probe_adopt.py` | adopt on dummy projects with untracked `.env`, logs, `.bak`, editor settings and notes; with and without `private/`; shipped and patched; each compared with its pre-adopt copy | committed files must survive unchanged (they did) |
| `probe_parent_repo.py` | a `minimal` and a `simple --branch-dir-main public` create inside a dummy parent repository; the parent's HEAD and index before and after | the parent's own commit must stay its HEAD if nothing reaches it |
| `summarize.py` | prints `probe.py`'s report | -- |

**A method error, caught and fixed:** the first `probe.py` run copied the package skipping every `.vscode` folder, which also dropped the layer templates' `.vscode/launch.json`; the patched private branch then had 23 files against the shipped 24, which looked like the cleaning step deleting a file. `trace_vscode.py` showed the cleanup removed nothing, and the copy was fixed to skip only the top-level `repokit/.vscode/`. After the fix both private branches have 24 files.

## Results

### A. Which git commands are ambiguous (branch `private` + folder `private/`)

| Command | Exit | Ambiguous |
|---|---|---|
| `git reset --hard private` | 128 | yes |
| `git log -1 private` | 128 | yes |
| `git reset --hard private --` / `refs/heads/private` | 0 | no |
| `git log -1 private --` | 0 | no |
| `git rev-parse private`, `ls-tree private`, `merge-base main private`, `checkout private` | 0 | no |

In `repokit/`, the calls that pass a branch name to `reset --hard` are `repo_manager.py:1670` (`_create_clean_public_branch`, `source_branch`) and the multi-line call near `:2063` (`private_branch`). No `git log <branch>` call exists in `repokit/`. `rev-parse <branch>` (`:2018`, `:2112`) and `checkout <branch>` are not ambiguous.

### B. Creates, shipped vs. with `--` on the two resets

| Strategy | Shipped: ambiguous / ERROR lines | Shipped public branches | Patched: ambiguous / ERROR | Patched public branches (files, private files) |
|---|---|---|---|---|
| standard | 5 / 10 | main 6 files, the rest 1 | 0 / 0 | main, dev, staging, test, live: 20 each, 0 private |
| simple | 2 / 4 | main 6, dev 1 | 0 / 0 | main, dev: 20, 0 private |
| gitflow | 4 / 8 | main 6, the rest 1 | 0 / 0 | main, develop, release, hotfix: 20, 0 private |
| github-flow | 1 / 2 | main 6 | 0 / 0 | main: 20, 0 private |
| minimal | 1 / 2 | main 1 | 0 / 0 | main: 20, 0 private |

**Reconciliation:** the private branch has 24 files in both runs, 4 of them private (`CLAUDE.md`, three `private/claude/instructions/*`). 24 − 4 = 20, every patched public branch. All five shipped creates exit 0 despite the errors.

The cleaning step that the fix switches on (`_create_clean_public_branch` → `git rm --cached` of `BranchContext.check_private_files`, then `_cleanup_sensitive_files(branch_context=<public>)`) ran on every public branch and reported "Cleaned 0 sensitive files". **But it is a hazard by design:** for a public branch, `_cleanup_sensitive_files` walks `self.repo_root` and deletes from disk every file matching `DEFAULT_SENSITIVE_PATTERNS` (`.env*`, `*.log`, `*.bak`, `*.tmp`, `*~`, `logs/*`, `revisions/*`, `Clipboard Text*`, `nul`) plus config patterns. In the private-branch layout `repo_root` is `<name>/local`, the private checkout. A fresh create holds only what repokit just wrote, so nothing matched; anything that ever reaches this path with a person's files present would lose them from disk. Only the non-adopt path calls it (`repo_manager.py:1443`).

### C. adopt (the "selective" path; the fix does not touch it)

| Run | Exit | Lost from the project folder | Changed | Secrets in any branch |
|---|---|---|---|---|
| shipped, no `private/` | 0 | none | none | none |
| shipped, with `private/` | 0 | none | none | none |
| patched, no `private/` | 0 | none | none | none |
| patched, with `private/` | 0 | none | none | none |

All six branches have 15 files. Two notes: adopt prompts "Continue with adoption? Changes should be committed first" when untracked files exist (the probe answered y, as a person would); and a project's own `private/` folder is not committed to the private branch (it is gitignored), which belongs with issue #16's three modes. Each run logged one ERROR line (the known spurious "Git command failed: RepoKit Pre-Commit Check").

### D. A create writes into an enclosing repository

`_setup_github_integration` uses `self.github_root = <name>/github` regardless of `--branch-dir-main` or whether `main` has a worktree (`repo_manager.py:73`), creates that folder early (`:244`), copies `.github/` into it and runs `git status`, `git add .github` and `git commit` with that folder as cwd (`:1104-1109`). When it is not a worktree, git walks up to the nearest enclosing repository:

| Create inside a dummy parent repository | Parent HEAD moved | Parent commits added |
|---|---|---|
| `--branch-strategy minimal` | yes | "Add GitHub configuration files" |
| `--branch-strategy simple --branch-dir-main public` | yes | "Add GitHub configuration files" |

This is the cause of the stray `<name>/github/` folder holding only `.github/` (seen in the docs pass and the checklist sweep), and it commits into someone else's repository. The home-directory repository (`C:\Users\Extreme`) holds no such commit (checked: 0 since 2026-10-20) because its `.gitignore` starts with `*`, which ignored the `git add`.

### E. Why the suite did not catch any of it

`tests/test_branch_strategies.py` checks the strategy table, the parser and the push lists; its one real create (`minimal`) asserts the branch names only. No test inspects a public branch's tree, the ERROR lines, or an enclosing repository, and the create exits 0 when a public branch fails, so `assert_repokit_success` passes.

## Verdict

- The README's warning can come out with `--` (or `refs/heads/`) on the two `reset --hard` calls: measured, all five strategies clean, no private file in any public branch.
- The fix switches on a working-folder deletion step that has never run against a person's files. It deleted nothing here, but its design deletes from the private checkout; the fix should come with that step confined to the index (or removed), and with tests that put sensitive files in the working folder and check they survive.
- Two more defects belong in the same version: a public branch failing must fail the create, and `_setup_github_integration` must never run git outside the project (derive the main worktree from `git worktree list`, and skip when `main` has none).
- Not measured: the `--private-mode nested` combination after the fix (issue #16), and the `:2063` reset's caller in a real flow (it updates existing worktree branches; it fired zero times in these creates).
