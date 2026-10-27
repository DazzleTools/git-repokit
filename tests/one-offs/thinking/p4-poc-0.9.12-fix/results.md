# 0.9.12 POC: the four-part fix -- survived

Run 2026-10-25 by `poc.py` against git-repokit 0.9.11 (`2a9f55a`). Every change was a text replacement in a scratch COPY of `repokit/`, each asserting its anchor matched exactly once; every create ran in a throwaway repository under `%TEMP%` with HOME isolated and commits unsigned. The checkout was never edited. Inputs: the measure in `../p4-measure-0.9.12-private-ref/results.md`.

## The fix under test

1. `--` after the two `git reset --hard <branch>` calls (`repo_manager.py:1670`, and the multi-line one near `:2063`).
2. `_cleanup_sensitive_files` never walks the working folder; its git-index clean (which already keeps files on disk with `git rm --cached`) is unchanged.
3. `_setup_github_integration` finds the default branch's worktree from `git worktree list --porcelain` and returns when there is none; `<name>/github` is no longer created ahead of time.
4. A public branch that fails to build, or fails verification, is an ERROR and the create raises after switching back to the private branch, so it exits non-zero.

Test scaffolding in the copies only (not part of the fix): `RK_POC_PLANT` writes files into `local/` just before the public branches are cut; `RK_POC_FAIL=<branch>` raises when that branch is built.

## Arms

| Arm | Prediction (written first) | Observed | Verdict |
|---|---|---|---|
| P1 standard | 0 ambiguous, 0 ERROR; each public branch = private minus its private files; none private | exit 0, 0/0; private 24 (4 private); dev, live, main, staging, test 20 each | pass |
| P1 simple | same | main, dev 20 | pass |
| P1 gitflow | same | main, develop, release, hotfix 20 | pass |
| P1 github-flow | same | main 20 | pass |
| P1 minimal | same | main 20 | pass |
| P2 fix | planted `.env`, `app.log`, `logs/run.log` survive on disk, in no public tree | all three on disk; in a public tree: no | pass |
| **P2 control** (`--` alone) | the cleanup deletes them | **all three deleted from `local/`** | failed as predicted |
| P3 fix | inside a dummy parent repository, the parent's HEAD and index unchanged; no stray `github/` | minimal: parent unmoved, folders `local` only; simple `--branch-dir-main public`: unmoved, `local`, `public` | pass |
| P3 control (shipped) | the parent's HEAD moves | moved in both; a `github/` folder in both | failed as predicted |
| P4 fix | a forced failure cutting `dev` exits non-zero | exit 1 (3 ERROR lines) | pass |
| P4 control (`--` alone) | exits 0 | exit 0 (1 ERROR line) | failed as predicted |

**Reconciliation (P1):** private 24 files = 20 project files + 4 private files (`CLAUDE.md` and three `private/claude/instructions/*`). The 4 are committed to the private branch after the public branches are cut (`_generate_ai_templates` runs after `_create_initial_commit`), so no public branch ever had them; 24 − 4 = 20 for every public branch.

## Verdict: survived

The fix held against attempts to break it. Every control arm failed as predicted, so the method can detect failure.

**The finding that matters:** the obvious one-line fix (`--` alone) would have shipped a data-loss bug. With the reset working, the existing cleanup deletes every untracked file matching the sensitive patterns (`.env*`, `*.log`, `logs/*`, `*.bak`, ...) from the person's private working folder. The `--` fix must not ship without part 2.

## Not settled here

- `--private-mode nested` with a multi-branch strategy after the fix (issue #16).
- The second reset (`:2063`, updating existing branches to match private) fired zero times in these creates; its `--` is the same change but unexercised by these runs.
- Whether the redundant `.github` copy step should go entirely (the public branches now carry `.github` from the private branch, so the step finds nothing to commit when `main` has a worktree).
- Proper tests, written for the build: these are throwaway scripts, and the build must re-derive them as regression tests.
