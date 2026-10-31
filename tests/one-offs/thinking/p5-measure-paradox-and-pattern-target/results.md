# Measure: git-repokit-common consumers -- non-JSON version copies, and the Python default (2026-10-30)

For the design "paradox language + git-repokit-common pattern target". Script: `probe.py` (read-only; uses git-repokit-common main's own `repokit_config` for settings and language rules). Raw output: `results-raw.txt`.

## Questions, and what they decide

- **Q1.** Does any consumer carry its version in a non-JSON text file beside its version source, kept by hand? This decides whether the "pattern" extra-target is an improvement for all consumers or only for new Paradox projects (djdarcy's bar for shared tooling).
- **Q2.** Which consumers are treated as Python by the hooks only because nothing says otherwise? This decides whether "stop assuming Python" is a general fix.

## Method, and its check

- **Consumers:** every folder under `C:\code` (depth 6, skipping `node_modules`, `.git`, `site-packages`, venvs, `__pycache__`, `dist`, `build`) holding `repokit_config.py` or `sync-versions.py`, deduplicated by `git rev-parse --path-format=absolute --git-common-dir`.
- **The method failed its check on the first run.** Without `--path-format=absolute`, git answered relative to the subfolder, distinct repos collapsed onto wrong keys (21 rows), and git-repokit, claude-bookmarks and dazzle-claude-code-patcher were missing.
- **Known answers after the fix:** git-repokit appears, detected as Python. claude-bookmarks (TypeScript; its root has no `tsconfig.json`) appears as treated-as-Python-by-default, its known Q261023-01 symptom.

## Reconciliation

- 68 copies found = 3 not inside a repository (`claude-projects/_staged-check`, two `dazzlecmd/github* - Copy` / `github.2026.6.21` backups) + 65 copies in **50 repositories** (worktrees and nested copies deduplicated).
- 50 rows reported.

## Q1 -- non-JSON version copies

| Repository | Version source | Other copy | State |
|---|---|---|---|
| `unctools\local` | `unctools/_version.py` = 0.3.0 | `setup.py` version = 0.1.1 | **drifted** |

- **The count:** 1 of 50. 2 of 50 already use JSON `extra-targets` (claude-bookmarks 1, claude-session-logger 2).
- **Patterns probed:** `Cargo.toml`, `CMakeLists.txt` `project(... VERSION)`, `project.godot`, `*.csproj`, `descriptor.mod`, `setup.cfg`, `setup.py`, `*.iss`, `*.nsi`, at the root and one folder down.
- **Gap:** the version source was not resolved for 5 repositories (claude-session-logger's vault, ComfyUI-DazzleKSampler and its backup, Dazzle-Locate32, git-repokit). Their rows can miss a drifted copy, not invent one.

## Q2 -- treated as Python by default

- No consumer declares `languages`.
- **9 of 50** have no Python package marker at their root, yet the hooks treat them as Python:
  - claude-bookmarks;
  - claude-session-logger (`github`, and its `local\private` vault);
  - dazzle-claude-code-config-personal and -public, and their two `bak` copies;
  - Dazzle-Locate32;
  - git-repokit-common itself.
- **Some of the 9 do hold Python files** (tooling, scripts), so "not a Python package" is not the same as "no Python". The question is what the hooks should *check*, not what the repository contains.
- The other 41 are detected from their markers: 37 Python, 2 Python + JavaScript, 2 JavaScript (aichatnav and its public copy).

## Verdict

- **The pattern target, measured:** one existing consumer with a hand-kept, already-drifted copy, plus every future Paradox, Rust, CMake or Godot project. Modest today, general in shape: it adds a target kind and changes no default.
- **The Python default affects 9 of 50 consumers, about one in five.** A project that declares nothing and shows no markers gets Python checks. Declaring `languages` explicitly (repokit's create can write it) is the fix that doesn't change anyone's current behavior; changing the default would.
- **Unmeasured:** whether those 9 *want* the Python checks (some run Python tooling), and copies deeper than one folder.
