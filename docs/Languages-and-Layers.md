# Languages and layers

Every project gets the same structure: README, CONTRIBUTING, CHANGELOG, LICENSE, `.github/`, `.gitignore`, `.gitattributes`, the vault and git-repokit-common. On top of that, `--language` and `--with` add the code type: the source files, build files, tests, CI workflow and VS Code debug configuration for what the project is.

## The short version

```bash
repokit list                                   # every language, preset and layer
repokit list python                            # one language
repokit create my-tool --language python       # the language's default preset
repokit create my-tool --with python/script    # a named preset (it implies its language)
repokit create my-tool --with claude-plugin    # a bare name, when only one language has it
repokit create my-tool --language python,c-cpp # two languages
```

## Languages and presets

A **preset** is a tested, named list of layers. Each language has a default preset, used when you name the language and nothing else.

| Preset | What it makes |
|---|---|
| **`python/pypi`** (Python's default) | `pyproject.toml` with a dynamic version, the package (`__init__`, `__main__`, `cli`, `_version`), tests, and a workflow that publishes to PyPI when a GitHub Release is published |
| `python/script` | A local tool: one module reading `VERSION`, its own small CI, no packaging |
| `python/setuppy` | `setup.py` and `requirements.txt`, the older shape |
| `python/claude-plugin` | A Claude Code plugin in `plugin/` whose hooks are Python, run through a small node launcher (Claude Code runs hooks with node); pytest tests; the marketplace manifest at the root |
| **`c-cpp/cmake-app`** (C/C++'s default) | CMake with presets, a vcpkg manifest, CTest, a version header at `include/<name>/version.h`, and CI on three operating systems |
| `c-cpp/msbuild` | A Visual Studio solution (Windows only) |
| `c-cpp/minimal` | One source file, with a `Makefile` and `build.bat` |
| **`js-ts/node-package`** (JS/TS's default) | An npm package in TypeScript: an exports map, `src/index.ts`, `node:test` tests, publish-on-release |
| `js-ts/script` | One `.js` file run with node, reading `VERSION`, no build step |
| `js-ts/claude-plugin` | A Claude Code plugin in `plugin/` with a SessionStart hook, `node:test` tests and the marketplace README; add `ts` for TypeScript |

`repokit list` also shows **planned** presets (`python/comfyui`, `python/django`, `python/qt`, `c-cpp/cmake-lib`, `c-cpp/qt`, `js-ts/web-vite-react`, `js-ts/obsidian-plugin`, `js-ts/browser-extension`, `js-ts/comfyui-frontend`). Naming one stops before anything is created and says it is not built yet.

`generic`, the default language, adds no code-type files.

Each preset's version lives in one place that the vendored version tool keeps in step: `_version.py` for a Python package, `VERSION` for scripts and plugins (and `package.json` or the plugin manifests beside it), and `version.h` for C/C++.

## `--with`: presets and layers

`--with` takes a comma-separated list (or the flag repeated). Each item is one of:

- **a preset:** `python/pypi`, `js-ts/claude-plugin`
- **a layer, with its language:** `c-cpp/qt`, `js-ts/ts`
- **a bare name,** when only one language has it: `setuppy`. A bare name two languages share (`qt`) is refused, naming both.

Every item implies its language, so `--with c-cpp/msbuild` needs no `--language`.

### Facets

Every layer answers one question about the project, its **facet**:

| Facet | The question | One or several? |
|---|---|---|
| `runtime` | Where does it run? | one |
| `dialect` | Which flavour of the language? (TypeScript) | one |
| `build` | How is it built or packaged? | one |
| `framework` | What does it use? (Qt, React) | several |
| `purpose` | What is it? (a Claude plugin, an npm package) | one |

repokit sorts a `--with` list by facet, fills in what each layer implies, and refuses two answers to a one-answer question, such as `pypi,setuppy`. A list that equals a preset is recorded as that preset; any other list is built by the same rules and noted once as not a tested preset. `repokit list` shows each language's facets and their choices.

## Several languages

`--language python,c-cpp` applies the languages' layers in the order given; the first is the **primary** language.

- With no `--with`, only the primary language's default preset applies. Two presets would both claim the build files and the settings, so the other languages add their language layer only, and the create names the command that would add a preset for each of them.
- `.vscode/` holds the primary language's debug configurations, and the create says so.
- A bare `--with claude-plugin` is the js-ts plugin, or the Python one with `--language python`. With both languages named it is refused as ambiguous, naming `python/claude-plugin` and `js-ts/claude-plugin`; name the one you mean.

## What every preset brings

- **Tests that pass on the first commit**, and a pre-push hook that runs them (`.repokit-common.toml` names the command).
- **A CI workflow:** `ci-python.yml` for Python, `ci-c-cpp.yml` for CMake, and so on. The README's CI badge names the workflow that exists, and a project with no CI gets no CI badge.
- **`.vscode/launch.json`:** Python with `debugpy` for the package, the script or the plugin hook, and pytest; C/C++ with `cppvsdbg` on Windows and `cppdbg` elsewhere, building first; JavaScript/TypeScript with node for the current file, `npm test`, the script or the plugin hook.
- **README and CONTRIBUTING commands** for the preset: install, usage, setup and tests.
- **The runtime minimum** in the README's badge and in the package metadata: Python 3.10, or the preset's Node version.

`.repokit.json` records the languages, the preset, and every layer in the order it was applied.

## How layers are applied

Layers live in `repokit/templates/layers/`: one folder per language under `languages/`, one per layer under `archetypes/<language>/<name>/`, and `manifest.toml`, which names them all.

- Layers apply in order: each language's layer, then the rest by facet.
- A later layer's file replaces an earlier one. A layer that does this on purpose lists the path under `overrides` in the manifest, and the tests treat any other same-path write as a collision.
- A file named `<name>.rkappend` is appended to `<name>` instead. That is how each language adds its lines to `.gitignore`.
- `__RK_NAME__` tokens in file names and contents become the project's values: `__RK_PROJECT__` (`my-tool`), `__RK_SNAKE__` (`my_tool`), `__RK_MACRO__` (`MY_TOOL`), `__RK_PASCAL__` (`MyTool`), `__RK_ORG__`, `__RK_DESCRIPTION__`, `__RK_AUTHOR__`, `__RK_EMAIL__`, `__RK_YEAR__`, `__RK_DATE__`, `__RK_GUID_PROJECT__`, `__RK_GUID_SOLUTION__` and the license fields.
- Files are written byte for byte, so a header's BOM or a `.sln`'s line endings come out as the layer holds them. Workflow files are copied unchanged; a token inside one is an error, because GitHub Actions' own `${{ }}` syntax lives there.

## Adding a language or a preset

A new language is a folder and a manifest entry, not code:

1. Make `languages/<lang>/` with the files every project in that language gets (its `.gitignore.rkappend`, CI, `.vscode/`).
2. Make `archetypes/<lang>/<name>/` for each layer.
3. In `manifest.toml`: a `[languages.<lang>]` entry with its default preset, a `[layers."<lang>/<name>"]` entry per layer with its facet (and `implies` and `overrides` where they apply), and an `[archetypes."<lang>/<name>"]` entry per preset listing its layer folders in order.
4. Mark anything not finished `stub = true`, so `repokit list` shows it as planned and a create refuses it.

`tests/test_layers_compositions.py` assembles every composition of each language's shipped layers, so a new layer that collides with another fails there as soon as it is in the manifest. Tests of what the preset's files contain (as `tests/test_layers_c_cpp.py` builds the C/C++ presets) are written per preset.
