# 0.10.3 acceptance checks, as run (2026-11-07)

Both scripts were run from a scratch copy (each writes `run/` and `run-l2/` beside itself; copy them out of the repository before re-running). They used git-repokit-common's committed `main` (0.4.3) as the vendored copy.

| Check | Predicted (design) | Measured |
|---|---|---|
| AC1 the suite | green; about 15 new tests | **429 passed, 14 skipped, 1 xfailed** (with git-repokit-common 0.4.4 committed); `tests/test_private_modes.py` holds 30 |
| AC2 G4 against the build | the same results, plus `git push origin private` refused | as predicted, all as tests in `test_private_modes.py`: plain add, safe-merge, a hand merge refused, public history clean, and the push of `private` refused once git-repokit-common 0.4.4 (`5df9f42`) is the vendored copy |
| AC3 `create x --branch-strategy simple` | `private_mode: nested-branch`; `private/.git`; `convos/` `revisions/` tracked on private once used; public trees clean | as predicted (`ac_checks.py`): plain add staged `convos/a.md` and `revisions/old.py`; main and dev history hold no private path |
| AC4 `create x` (main-only) | identical to 0.10.2 apart from the dependency | identical file for file, except `.repokit.json` (version, timestamp, and the new `private_exposure` field) |
| AC5 `create x --private-mode branch` (main-only) | refused, naming the fixes | exit 1; no folder written; names `--branch-strategy` and `--private-mode nested` |
| AC6 wheel in a fresh 3.10 venv | installs dazzle-lib and dazzle-loglib; `repokit --version` 0.10.3 | Python 3.10.19 venv: dazzle-lib 0.8.2, dazzle-loglib 0.3.3, `RepoKit 0.10.3`; the continuum loads |

**The L2 probe (`probe_l2.py`).** Before the fix, on a `minimal` create, `repokit setup-guardrails` on `main` wrote `revisions/` into `.git/info/exclude`. Back on `private`, `check-ignore` named that line, and a plain add skipped `revisions/x.md`. After the fix, a test pins it (`test_guardrails_on_a_public_branch_never_hide_the_promoted_folders`).
