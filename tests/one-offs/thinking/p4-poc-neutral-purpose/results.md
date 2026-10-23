# p4-poc-neutral-purpose: can a purpose be language-neutral?

**Question.** The claude-plugin purpose is mostly language-neutral (marketplace manifest, plugin manifest, marketplace README) with per-language parts (hook scripts, hooks.json, tests). Today it exists only as `js-ts/claude-plugin`, so `--language python --with claude-plugin` is refused, though claude-session-logger is exactly that shape. How should the layer type system express it?

**Candidates.** (A) a second per-language layer that duplicates the neutral files; (B) a pseudo-language key, `any`, holding the neutral files, which per-language layers imply, with the resolver never treating `any` as a project language; (C) a purpose layer that declares the languages it serves, with per-language subfolders. B was built; A and C were measured by argument and count.

**Files.** `patch_b.py` builds `layers_b.py` from the production resolver by exact string replacement (the whole candidate is those edits); `poc.py` runs the arms and writes `results_run.md`; `results_run_round1.md` is the method-broken round; `baseline_pytest.txt` and `b3_pytest.txt` are the three layer test files on the production tree and on a scratch copy with the patched resolver. Production source untouched throughout.

## Round 1: method-broken

The control was aimed at the implies path: candidate B's manifest through the UNPATCHED resolver, predicting `any` would leak into the project's languages. It did not leak. Reading the resolver again: the implies step appends an implied layer but never registers its language; only a layer named directly as a token does. So the predicted failure could not happen by that path, the control passed, and by the rule no round 1 result counts. A second instrument error in the same round: the B2 prediction omitted the language layer's own file. And one real finding: the ambiguity message listed `any/claude-plugin` as a candidate, an awkwardness the candidate had to close.

## Round 2: survived

Control re-aimed at the direct token `--with any/claude-plugin`: the unpatched resolver leaks (`languages=['python', 'any']`), as predicted. Results count.

| arm | prediction | observation | verdict |
|---|---|---|---|
| control | unpatched resolver leaks `any` on the direct token | `['python', 'any']` | failed as predicted |
| B0 | at most 10 changed lines | +8 -2 (five edits: known_languages, explicit refusal, implied no-op, bare-candidates, catalogue) | held |
| B1a | python + bare claude-plugin | languages `['python']`, names `python, python/claude-plugin, any/claude-plugin`, preset recognised | held |
| B1b | js-ts + bare claude-plugin | languages `['js-ts']`, names `js-ts, js-ts/node, js-ts/claude-plugin, any/claude-plugin`, preset recognised | held |
| B1c | `--language any` refused; python,js-ts + bare name ambiguous between the two real languages only | both messages as predicted; `any/` absent | held |
| B1d | `list python` shows claude-plugin under purpose; no `any:` section; `known_languages` omits any | as predicted | held |
| B1e | patched resolver, direct token | languages `['python']` | held |
| B2 | assembly for python = 3 neutral + 3 python + VERSION; no neutral path in two folders | exactly those 7; duplicates none | held |
| B3 | the three layer test files pass on the patched resolver as on production (49 passed, 101 s baseline) | first run 47 passed, 1 skipped, 1 failed: the scratch copy lacked `MANIFEST.in`, `setup.py` and a `.git`; completed, 48 passed, 1 failed, and the failure is production's, not the candidate's (see the finding below) | held, with one pre-existing defect exposed |
| C | measured | 11 `split("/")` sites read the key prefix as the language; A duplicates 3 neutral files | measured |

## Reading

- **B survives** at ten changed lines, zero duplicated files, and both languages resolving a bare `claude-plugin` to their own preset. The pseudo-language is invisible to `--language`, to `repokit list`, to the ambiguity message and to the project's language list; it is only a folder convention (`archetypes/any/<name>`) plus `pseudo = true` in the manifest.
- **A** costs nothing in the resolver and three duplicated files per neutral purpose, which drift; it is the fallback if B's `any` key reads as too clever.
- **C** would touch eleven sites where the key prefix is the language, plus assemble; it buys nothing B does not, and it changes the one invariant the whole resolver leans on (a layer key is `lang/name`).
- **Known limit, unchanged by any candidate:** two product languages and a bare purpose name stay ambiguous; the person names `python/claude-plugin` or `js-ts/claude-plugin`.
- **A finding beyond the question:** production's implies step never registers an implied layer's language. Today no layer implies across languages, so nothing depends on it; B relies on it only in the sense that the pseudo-language must not be registered, which the explicit no-op now guarantees either way.

## A defect found on the way (production, not the candidate)

`test_the_wheel_ships_every_layer_file_including_dotfiles` asserts `archetypes/c-cpp/cmake-app/.github/workflows/ci.yml` is in the wheel. That file was renamed `ci-c-cpp.yml` at v0.7.3; on disk only the new name exists. The test passes on the production checkout because the ignored `build/lib/` directory still holds the OLD file from a wheel built before the rename, and setuptools reuses `build/lib`, so the stale `ci.yml` rides into every wheel built from this checkout. The scratch copy had no `build/`, built an honest wheel, and the stale assertion failed. Two fixes for Phase 4: the test asserts `ci-c-cpp.yml` and also `in_wheel <= on_disk` (the reverse inclusion, which would have caught the stale file); and a wheel is built from a clean checkout or after removing `build/`. Measured 2026-10-22 21:00: `build/lib/.../workflows/` holds both `ci-c-cpp.yml` and `ci.yml`.

## Fallback

B fails -> A (duplicate the neutral files into `python/claude-plugin`, with a test that the neutral files of the two layers are byte-identical, so drift is caught).
