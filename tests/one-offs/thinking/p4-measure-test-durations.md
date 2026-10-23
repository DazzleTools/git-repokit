# Measure: where the suite's seven minutes go (2026-10-22)

Raw run: `p4-measure-test-durations.txt` (`python -m pytest -q --durations=40 -rs`, production tree at `31f2d18` with the wheel-test edit not yet collected). Question: djdarcy's pre-push ran 193 tests in 403.86 s; what costs the time, and does the quick/complete split he asked for already have a lever?

## Numbers

| What | Measured |
|---|---|
| Full suite | 193 passed, 13 skipped, 1 xfailed in 395.70 s |
| The 40 slowest tests | 261.57 s of the 395.70 (66%) |
| Floor of one CLI test | 5.1 to 5.7 s (every `TestBareCreate`, `TestCLICommands`, js-ts and most layer tests sit there) |
| The slowest single tests | 18.5 s (bare python preset installs and runs its tests), 12.5 s (CI attributes and changelog), 10.7 s (cmake-app configures, builds, ctest), 9.7 s (script floor), 8.8 s (languages stack) |
| `repokit create demo --language python --no-push` at the shell, vendoring from the sibling | 2.9 s |
| the same with `REPOKIT_COMMON_SOURCE=off` | 2.4 s |
| `--language generic`, vendoring off | 1.6 s |
| `pytest -m unit` (106 tests) | 3.66 s |
| classes | unit 106, integration 89, live 12 (of 207 collected) |
| skips | 8 live GitHub tests (`REPOKIT_LIVE_GITHUB=1` runs them), 4 live create tests, 1 adopt test that writes nothing |

## Reading

- **The time is the integration class.** 89 tests at a 4 to 6 s floor is roughly 400 s; the unit class is four seconds. The split djdarcy asked for is already in the conftest (`unit` / `integration` / `live`, assigned automatically) and in `tests/run_tests.py --unit`. The hook's lever is `test-command` in `.repokit-common.toml`: the unit class on every push, the complete suite in CI and before a tag. Nothing has to be dropped to get there.
- **The floor is the harness, not the tool.** A create at the shell is 2.9 s with vendoring; a test that does one create is 5.1 to 5.7 s. About half of every integration test is the harness: a fresh interpreter per test (`python -m repokit` imports), a temporary HOME, and git on Windows initialising two repositories (the project and its vault) with hooks. Vendoring itself is 0.5 s. Candidates for the floor, each a measure of its own: in-process invocation for the tests that do not need a real subprocess; one shared created project per class where the tests only read it (the js-ts and layer tests are the obvious group); `git init` with fewer refs and no hook install where the hooks are not under test.
- **The top five are legitimate.** They install a package and run its tests, build with CMake, or run node; they are the end-to-end proofs and belong to the complete suite, not the quick one. `/test-cleanup` is not where the seconds are: the suite has few redundant tests; it has an expensive floor multiplied by 89.
- **Order for Phase 4:** (1) the hook runs the unit class, CI the complete suite -- a settings change and a README line; (2) a measure of the floor's parts (interpreter, HOME, two `git init`s, hooks) on one bare create; (3) shared fixtures for the read-only groups, which is where a real halving would come from. `/test-scenarios` over the suite is useful for what the quick battery would miss, not for speed.

## A second defect, found by the wheel-test fix

The fixed `test_the_wheel_ships_every_layer_file_including_dotfiles` (reverse inclusion `in_wheel <= on_disk`) fails on this checkout naming not only the stale `ci.yml` but `archetypes/python/pypi/**/__pycache__/*.pyc`: stale bytecode under the layer tree in `build/lib/` ships in the wheel as well. Removing `build/` clears both; the test now keeps them out.
