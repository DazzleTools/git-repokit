# git-repokit

[![PyPI](https://img.shields.io/pypi/v/git-repokit?color=green)](https://pypi.org/project/git-repokit/)
[![Release Date](https://img.shields.io/github/release-date/DazzleTools/git-repokit?color=green)](https://github.com/DazzleTools/git-repokit/releases)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/git-repokit?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pypistats.org/packages/git-repokit)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Discussions](https://img.shields.io/github/discussions/DazzleTools/git-repokit)](https://github.com/DazzleTools/git-repokit/discussions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](docs/platform-support.md)

**One `repokit` command creates a project that is ready to work in (including the structure, the code for its language, the tooling and hooks, a private notes vault, a license, and the repository on GitHub with its labels and first issues).**

`repokit create` replaces the hand-run route of copying a template repository, running its setup, then setting up GitHub and the notes by hand. Every piece is optional and configurable, so your own house style lives in one config file, and a create becomes one short command.

## What a project gets

A full create (the [Quick Start](#-quick-start) below) produces:

- **The structure:** README, CONTRIBUTING, CHANGELOG, LICENSE, `.gitignore`, `.gitattributes`, `docs/`, `tests/`, `scripts/`, and, if you ask for them, ROADMAP, a funding file, Dependabot, a stale-issue policy and PR and release templates.
- **The code for its language:** a Python package with `pyproject.toml` and a CLI, a CMake or Visual Studio C/C++ project, a TypeScript npm package, a Claude Code plugin, a Paradox game mod (Crusader Kings III and others), and more. Each comes with tests, a CI workflow and a VS Code debug configuration where it has something to run, from the first commit. The project's settings name its languages, so the hooks run the right checks. See [Languages and layers](docs/Languages-and-Layers.md).
- **A README that names the project:** the real GitHub owner, badges for the release, the Python or Node minimum and the license, install and test commands for the preset, and a License section at the end.
- **The tooling:** [git-repokit-common](https://github.com/DazzleTools/git-repokit-common) vendored at `scripts/repokit-common/`, with git hooks that keep version numbers in step, keep private files out of public commits, and run the tests before a push.
- **A private vault:** `private/` is its own git repository, ignored by the project, for notes, design documents, postmortems, conversations (`convos/`) and old revisions (`revisions/`); run logs go to `private/logs/`, kept on disk and never versioned. It starts with a map, an index for an oracle session and a to-do board. See [The vault](docs/The-Vault.md).
- **The repository on GitHub** (with `--github`): created with your `gh` login and pushed. It gets the standard labels, Roadmap and Quick Notes as issues #1 and #2 (pinned), discussions and topics. See [GitHub setup](docs/GitHub-Setup.md).

## 📦 Installation

Python 3.10 or newer. The command is `repokit`.

```bash
pip install git-repokit
# or the same tool under its DazzleTools alias
pip install dazzle-git-repokit
```

`--github` also needs the [GitHub CLI](https://cli.github.com/), logged in once with `gh auth login`.

From source:

```bash
git clone https://github.com/DazzleTools/git-repokit.git
cd git-repokit
pip install -e ".[dev]"     # with the test and lint tools
```

## 🎯 Quick Start

### A full project, on GitHub

This is the most common create: a Python package with everything turned on, published to GitHub with its labels, first issues and topics.

```bash
repokit create my-tool --language python --license gpl-3.0-or-later \
  --description "What my-tool does, in one sentence" \
  --extras all \
  --github --github-setup labels,issues,pin,discussions,topics \
  --topics cli,python
```

You get a private GitHub repository under your `gh` login (add `--public` for a public one, `--org MyOrg` for an organization), with `main` pushed, the labels made, and issues #1 (Roadmap) and #2 (Quick Notes) pinned. Locally, `my-tool/` holds the project and its vault in `my-tool/private/`. [GitHub setup](docs/GitHub-Setup.md) lists the few steps that are still done by hand afterwards.

### The same create from your house config

Put the choices you make every time in `~/.repokit/config.json`:

```json
{
  "license": "gpl-3.0-or-later",
  "license_private": "all-rights-reserved",
  "extras": ["all"],
  "github_setup": ["labels", "issues", "pin", "discussions", "topics"],
  "github": {"username": "your-login"}
}
```

Then the full create is:

```bash
repokit create my-tool --language python --github \
  --description "What my-tool does, in one sentence" --topics cli,python
```

Every key is listed in [Configuration](docs/Configuration.md).

### A multi-branch project

The private-branch model keeps all your working history on a local-only `private` branch, and moves finished work to public branches that are checked out beside it:

```bash
repokit create my-app --branch-strategy standard --language python --license mit --github
```

```
my-app/
  local/     the repository, on the private branch: work here
  dev/       the dev branch
  github/    the main branch
```

Then the day-to-day loop is:

```bash
cd my-app/local                     # work and commit on private, notes and all
git add -A && git commit -m "Add the parser"

cd ../dev                           # bring the work to dev, without the private files
repokit safe-merge private --preview
repokit safe-merge private
git commit -m "Add the parser"

cd ../github                        # and on to main when it is ready
repokit safe-merge dev
git commit -m "Release the parser"
git push
```

`safe-merge` leaves out the private content (`private/`, `CLAUDE.md`, `revisions/`, ...), and the hooks refuse it on a public branch if it ever gets staged. `--github` pushes only the public branches. Other layouts: `simple` (private, dev, main), `gitflow`, `github-flow`, and your own with `--branches` and `--worktrees`; see [Branch strategies](#branch-strategies) below.

### Other common creates

```bash
# Local only: no GitHub, nothing pushed
repokit create my-tool --language python --license mit

# A Claude Code plugin (hooks in JavaScript; add --language python for Python hooks)
repokit create my-plugin --with claude-plugin --license apache-2.0 --github

# A C/C++ app with CMake, or a Visual Studio solution
repokit create my-app --language c-cpp --license bsd-3-clause
repokit create my-app --with c-cpp/msbuild --license gpl-3.0-or-later

# A TypeScript npm package
repokit create my-lib --language js-ts --license mpl-2.0

# A Crusader Kings III mod: the mod in mod/, the repository's own files above it
repokit create my-mod --language paradox --license mit

# A one-file Python script, no packaging, given away to the public domain
repokit create my-script --with python/script --license unlicense

# Several pieces in one --with, comma-separated; repokit puts them in order
repokit create my-plugin --with claude-plugin,ts --license mit              # a Claude Code plugin in TypeScript
repokit create my-lib --with node,ts,node-package --license isc             # the same layers as --with js-ts/node-package
repokit create my-app --with c-cpp/cmake-app,python/script --license mit    # two languages, a preset for each

# A private project: all rights reserved, evaluation-only, your own terms, or no LICENSE at all
repokit create my-work --language python --license all-rights-reserved
repokit create my-work --language python --license proprietary-evaluation
repokit create my-work --language python --license file=../terms/client-terms.txt
repokit create my-sketch --license none

# What every language offers, and the license catalogue
repokit list
```

The catalogue has every license GitHub and GitLab offer when you create a repository, beyond the ones above: `lgpl-3.0`, `agpl-3.0`, `epl-2.0`, `0bsd`, `cc0-1.0` and more, with the texts from [choosealicense.com](https://choosealicense.com/licenses/), which also helps you pick one. `repokit list` prints every id, ready to copy. Two more are for software you are not giving away: `all-rights-reserved`, and `proprietary-evaluation`, which allows evaluation and non-commercial use until you revoke it, forbids everything else, and optionally provides an email for permission requests.

## Choosing the code type

`--language` picks the language: `python`, `c-cpp`, `js-ts`, or `generic` (the default, which adds no code). Each language has a default preset, and `--with` picks another one, such as `python/claude-plugin` or `c-cpp/msbuild`. `--with` also takes a comma-separated list of presets and single layers (`--with claude-plugin,ts`). A name can be bare when only one language has it, and is qualified when two do: `script` is refused as ambiguous, `python/script` is not. `repokit list` shows every preset and layer, including the planned ones.

| Language | Default preset | Other presets |
|---|---|---|
| `python` | `python/pypi`: a package with `pyproject.toml`, a CLI, tests, and publish-on-release | `python/script`, `python/setuppy`, `python/claude-plugin` |
| `c-cpp` | `c-cpp/cmake-app`: CMake presets, vcpkg, CTest, a version header | `c-cpp/msbuild`, `c-cpp/minimal` |
| `js-ts` | `js-ts/node-package`: a TypeScript npm package with `node:test` | `js-ts/script`, `js-ts/claude-plugin` |

Several languages stack: `--language python,c-cpp`. The details, and how to add a language, are in [Languages and layers](docs/Languages-and-Layers.md).

## The license

A license is required. `--license <id>` writes `LICENSE` from a catalogue of the licenses GitHub and GitLab offer (`mit`, `apache-2.0`, `gpl-3.0`, `gpl-3.0-or-later`, `bsd-3-clause`, ...), plus `all-rights-reserved` and `proprietary-evaluation` for a private project. `--license file=<path>` copies a text as it is, and `--license none` writes no file. The holder and year come from your git identity and the clock, and the license also populates in `pyproject.toml` or the plugin manifest. With `license` set in the config, you can leave the flag off.

## Branch strategies

repokit has two ways to keep private work private:

- **`main-only` (the default):** the project folder is the repository, on `main`, and `private/` is its own nested git repository that the project ignores. One branch, no merging rules to learn.
- **The private-branch model:** your working history lives on a local-only `private` branch in `<name>/local/`, and the public branches are git worktrees in sibling folders. You move finished work across with `repokit safe-merge`, which leaves the private content behind. This is the model repokit was first built for, and it suits projects with several release stages or several people.

| `--branch-strategy` | Public branches | Checked out in folders | Flow |
|---|---|---|---|
| `main-only` | main | the project folder itself | commit on main |
| `standard` | dev, staging, test, live, main | `dev/`, `github/` (main) | private -> dev -> test / staging -> main -> live |
| `simple` | dev, main | `github/` (main) | private -> dev -> main |
| `gitflow` | develop, release, hotfix, main | `develop/`, `github/` (main) | private -> develop -> release -> main, with hotfixes |
| `github-flow` | main | `github/` (main) | private -> main |
| `minimal` | main | none (switch branches in `local/`) | private -> main |

```bash
# A GitFlow project on GitHub
repokit create my-lib --branch-strategy gitflow --language python --license mit --github

# Your own branches, with worktrees for two of them (name a private-branch
# strategy too, or the project gets no private branch)
repokit create my-app --branch-strategy simple --branches main,develop,qa,production \
  --worktrees main,develop --license mit
```

The guards for the private-branch model: `repokit check-guardrails` shows what is protected, `repokit setup-guardrails` installs the hooks in a project repokit did not make, and `repokit safe-merge-dev` merges between development branches while keeping their history out of the public ones. The [Branch strategies](docs/Branch-Strategies.md) guide covers each layout, and the [Workflow guide](docs/Workflow-Guide.md) covers the day-to-day work.

## Existing projects

```bash
repokit analyze ./my-project                              # what repokit would do, changing nothing
repokit adopt ./my-project --dry-run                      # preview adopting a git repository in place
repokit adopt ./my-project --language python --migration-strategy safe --backup
repokit migrate ./my-folder --dry-run                     # add repokit's folders and files to a folder
```

`adopt` fills in what the project lacks. It keeps the project's own license file (`LICENSE`, `LICENSE.md`, `COPYING`, ...); with none, it writes the license your config names, or adopts the project without one and says so. `--license` is only for choosing one (it replaces the project's own file). It keeps the repository's history and sets up the private-branch layout (`--branch-strategy standard` unless you name another): your folder stays on the `private` branch, with `main` and `dev` checked out in sibling folders. The `safe` strategy keeps every existing file and adds what is missing beside it. `repokit setup-guardrails` adds the private-content hooks to a project repokit did not create. The [Adoption guide](docs/Adoption-Guide.md) and the [Migration guide](docs/Migration-Guide.md) walk through each case.

## All commands

| Command | What it does |
|---|---|
| `create` | Create a new project |
| `list` | List the languages, presets and layers |
| `analyze` | Report what repokit would do with an existing folder |
| `adopt` | Add repokit's structure to an existing git repository, in place |
| `migrate` | Add repokit's standard folders, files and hooks to an existing folder |
| `publish` | Publish an existing repository to GitHub or GitLab |
| `bootstrap` | Write a script that sets repokit up |
| `init-config` | Write a `.repokit.json` |
| `store-credentials` | Store a GitHub or GitLab token for `--publish-to` |
| `setup-guardrails`, `check-guardrails` | Install, or check, the private-content protection |
| `safe-merge`, `safe-merge-dev` | Merge branches without carrying private content across |
| `clean-history`, `analyze-history` | Find, or remove, sensitive data in a repository's history |
| `manage-gitkeep` | Add or remove `.gitkeep` files |
| `list-templates` | List the template files |

`repokit <command> --help` shows each command's options and examples.

## 🧪 Testing

```bash
python -m pytest -q             # the full suite, about ten minutes
python -m pytest -q -m unit     # the unit tests, a few seconds
```

Every run is isolated from your git config, home directory and tokens. A `git push` runs the unit tests through the vendored pre-push hook; CI runs the unit tests on Python 3.10 to 3.13, on Linux and Windows. [tests/README.md](tests/README.md) covers the test classes and the live GitHub tests.

## 📚 Documentation

- [Configuration](docs/Configuration.md): every config key, and the flag that matches it
- [Languages and layers](docs/Languages-and-Layers.md): presets, `--with`, and adding a language
- [GitHub setup](docs/GitHub-Setup.md): `--github`, `--github-setup`, and what GitHub has no API for
- [The vault](docs/The-Vault.md): `private/`, its first files, and the sessions that use it
- [Branch strategies](docs/Branch-Strategies.md): main-only and the private-branch model
- [Workflow guide](docs/Workflow-Guide.md): day-to-day work under the private-branch strategies
- [Deployment demo](docs/Deployment-Demo.md): worked examples, from a new project to GitHub
- [Adoption guide](docs/Adoption-Guide.md) and [Migration guide](docs/Migration-Guide.md): existing projects
- [Recipes and how-tos](docs/Recipes-And-Howtos.md): commands for common cases
- [Auth guide](docs/Auth-Guide.md): the `gh` login, and tokens for `--publish-to`
- [Platform support](docs/platform-support.md): what runs where, and what each platform needs
- [Why repokit exists](docs/Why-RepoKit-Exists.md)

The [documentation guide](docs/README.md) suggests a reading order.

## Contributing

Contributions are welcome! See the [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

Like the project?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djdarcy)

## Related Projects

- [git-repokit-common](https://github.com/DazzleTools/git-repokit-common) - The shared scripts and git hooks every project gets at `scripts/repokit-common/`: version sync, private-content checks, tests before a push, `gh_issue_full.py`. repokit vendors it into each project it creates, and into itself
- [git-repokit-template](https://github.com/DazzleTools/git-repokit-template) - The template repository repokit grew from: copy it, run its setup, then finish GitHub and the notes by hand. `repokit create --language python` reproduces its project tree, and a regression test keeps the two in step
- [dazzlecmd](https://github.com/DazzleTools/dazzlecmd) - The DazzleTools CLI (`dz`). Its `dz private-init` first made `private/` its own repository; repokit's vault is a port of it
- [github-traffic-tracker](https://github.com/djdarcy/github-traffic-tracker) - Traffic history beyond GitHub's 14 days (`ghtraf`). `--github-setup traffic` prints its setup commands, and the `installs` and `views` badges read its counts

## Acknowledgments

- Inspired by modern DevOps practices and GitOps workflows
  - https://nvie.com/posts/a-successful-git-branching-model/
  - https://trunkbaseddevelopment.com/
  - https://docs.github.com/en/get-started/quickstart/github-flow
  - https://martinfowler.com/articles/continuousIntegration.html
  - https://www.atlassian.com/continuous-delivery
  - https://www.perforce.com/blog/vcs/best-branching-strategies-high-velocity-development
- Built for developers who value consistency and automation
- Special thanks to the open-source community writ large

## License

git-repokit, Copyright (C) 2025-2026 Dustin Darcy

Licensed under the MIT License (MIT) -- see [LICENSE](LICENSE).
