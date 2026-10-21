# RepoKit

[![GitHub Workflow Status](https://github.com/djdarcy/git-repokit/actions/workflows/main.yml/badge.svg)](https://github.com/djdarcy/git-repokit/actions)
[![Version](https://img.shields.io/badge/version-0.6.0-blue)](https://github.com/djdarcy/git-repokit/releases)
[![Python](https://img.shields.io/badge/python-%3E%3D3.7-darkgreen)](https://python.org/downloads)
[![License](https://img.shields.io/badge/license-MIT-orange)](https://github.com/djdarcy/git-repokit/blob/main/LICENSE)
[![GitHub Discussions](https://img.shields.io/badge/discussions-Welcome-lightgrey)](https://github.com/djdarcy/git-repokit/discussions)

**Transform chaotic code folders into professional, organized repositories that work seamlessly with GitHub and teams.**

RepoKit automates the creation of standardized Git repositories with professional structure, worktree-based and branching workflows, and GitHub/Gitlab/etc deployment pipelines. Whether you're starting fresh or organizing existing code, RepoKit provides the structure and tools for professional development.

## Why RepoKit?

**Before**: Scattered files, no organization, deployment nightmares  
**After**: Professional structure, team-ready, GitHub-ready, portfolio-worthy

> **New to RepoKit?** Read [Why RepoKit Exists](docs/Why-RepoKit-Exists.md) for the complete picture.

## Features

### Core Capabilities
- **Universal Bootstrap System**: Analyze and migrate ANY project to RepoKit structure
- **Standardized Repository Structure**: Consistent directory layout with standard folders
- **Branch Strategies**: a single `main` branch with private notes kept out of git, or the multi-branch model (main, dev, staging, test, live, and a local-only private branch)
- **Worktree Management**: Git worktrees for efficient branch isolation and parallel development
- **Private Content Protection**: Secure local-only content that never gets pushed
- **GitHub/GitLab Integration**: Automated repository creation and deployment
- **AI Development Integration**: Built-in Claude AI assistance with workflow documentation
- **Two template systems**: the structure every project gets, then the code type on top -- a language layer and, below it, layers named by the choice they answer (how it is built, what it uses, what it is), composed with `--with` or taken whole as a preset (`--language python,c-cpp`, `--with c-cpp/cmake-app`, `--with cmake-lib,qt`); `repokit list` shows them; a new language is a folder and a manifest entry, not code
- **Comprehensive Test Framework**: Unit, integration, and end-to-end testing

### Universal Project Support
- **Empty Projects**: Start fresh with optimal structure
- **Existing Code**: Preserve your files while adding RepoKit benefits  
- **Git Repositories**: Maintain full history while upgrading workflow
- **Complex Projects**: Handle multi-branch, multi-contributor scenarios
- **Legacy Codebases**: Safe migration with conflict resolution

## 📦 Installation

```bash
# Install from source
git clone https://github.com/djdarcy/git-repokit.git
cd git-repokit

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Or install for regular use
pip install -e .
```

## 🎯 Quick Start

### Create a New Project
```bash
# Basic project creation
repokit create my-awesome-project --language python

# A C/C++ project: the language's layer plus its default archetype (cmake-app)
repokit create my-tool --language c-cpp

# A preset names its language; several languages stack in the order given
repokit create my-tool --with c-cpp/msbuild
repokit create my-tool --language python,c-cpp

# Compose layers below the language (bare names when unique; the tool orders them)
repokit create my-tool --with setuppy
repokit list            # every language's presets and layers, one screen

# Create and deploy to GitHub in one command
repokit create my-project --language python --publish-to github --private-repo

# Create with AI integration
repokit create my-project --ai claude --publish-to github
```

### Languages and archetypes (the code-type layers)

Every project gets the same structure (README, CONTRIBUTING, `.github/`, `.gitignore`, the vault, repokit-common). `--language` adds the code type on top, from `repokit/templates/layers/`: each language has a layer and a default archetype, and an archetype (`--with LANG/NAME`) adds its own layer and implies its language. With several languages and no `--with`, the first language is the primary one and only its default archetype applies (two archetypes would both claim the settings and build files); the other languages add their language layers. A later layer's file replaces an earlier one; a file named `<name>.rkappend` is appended instead (so each language adds its lines to `.gitignore`); `__RK_NAME__` tokens in file names and contents become the project's names (`my-tool`, `my_tool`, `MY_TOOL`, `MyTool`, the author, the year, a GUID). Workflow files are copied unchanged. Files are written byte for byte, so a header's BOM or a `.sln`'s line endings are what the layer holds. `repokit list` prints the known languages, presets and layers; an unknown name, or one whose layer is not built yet, stops before anything is created and names what is known. `generic` (the default) adds no code-type files.

`--with` takes a list. A token is a preset (`python/pypi`, the tested lists in the table below), a layer qualified by its language (`c-cpp/qt`), or a bare name when only one language has it (`setuppy`; `qt` is refused naming both). Every layer belongs to a **facet**, the question it answers -- where it runs, which dialect, how it is built or packaged, what it uses, what it is -- and the tool orders a list by facet, fills in what a layer implies (its language at least), and refuses two answers to a one-answer question (`pypi,setuppy`). A list that equals a preset is recorded as that preset in `.repokit.json`; any other list is assembled by the rules and noted once as not a tested preset. `.repokit.json` records `layers`, every layer in the order applied.

CI comes from the layers too: `ci-python.yml` with the Python layer (a matrix of pytest runs and a build), `ci-c-cpp.yml` with the cmake-app archetype (CMake, CTest on three operating systems); the README's workflow badge names the file that exists, and a project with no CI has no workflow badge. The structure writes `.gitattributes` (line-ending normalisation, and `scripts/repokit-common/** linguist-vendored` so GitHub does not count the vendored tooling as the project's language) and a `CHANGELOG.md` with the first version's heading and links, which git-repokit-common's version tool expects.

| Language | Default archetype | Archetypes |
|---|---|---|
| `python` | `python/pypi` (`pyproject.toml` with a dynamic version, the package with `cli.py` and `_version.py`, tests, the publish-on-release workflow -- the shape of git-repokit-template's projects) | `python/setuppy` (`setup.py` + `requirements.txt`, the output before 0.7.1); `python/script` (one module reading `VERSION`, its own small CI, no packaging -- the simple-projects floor); `python/comfyui`, `python/django`, `python/qt` announced |
| `c-cpp` | `c-cpp/cmake-app` (CMake presets, a vcpkg manifest, CTest, a build-time version stamp, CI) | `c-cpp/msbuild` (a Visual Studio solution), `c-cpp/minimal` (one source file, `Makefile` + `build.bat`); `c-cpp/cmake-lib` and `c-cpp/qt` announced. All three build as generated with Visual Studio 2022's tools (`tests/test_layers_c_cpp.py`); the version lives in `include/<name>/version.h`, which CMake, the `.rc` resource and the code all read |
| `javascript` | -- | planned as the js-ts layer |

### Adopt an Existing Project
```bash
# Analyze what RepoKit will do
repokit analyze .

# Adopt in-place with safe strategy
repokit adopt . --publish-to github --private-repo

# Migrate to new structure (creates copy)
repokit migrate ./old-project ./new-project
```

## 🔧 Common Use Cases

### 1. Brand New Python Project
```bash
# Create project with GitHub deployment
repokit create awesome-api \
  --language python \
  --description "My awesome Python API" \
  --publish-to github \
  --private-repo \
  --ai claude
```

### 2. Existing Project Migration
```bash
# First, analyze your project
cd existing-project
repokit analyze .

# Then adopt with recommended settings
repokit adopt . \
  --migration-strategy safe \
  --publish-to github \
  --organization my-company
```

### 3. Legacy Project Modernization
```bash
# Analyze complex project
repokit analyze ./legacy-app

# Adopt with careful conflict handling
repokit adopt ./legacy-app \
  --strategy safe \
  --branch-strategy gitflow \
  --dry-run  # Preview changes first
```

### 4. Multi-Language Monorepo
```bash
# Create with custom structure
repokit create platform \
  --language generic \
  --directories "backend,frontend,shared,docs,infra" \
  --branches "main,develop,release,hotfix" \
  --publish-to github
```

## 📊 Project Analysis

RepoKit can analyze any project and provide migration recommendations:

```bash
repokit analyze /path/to/project

# Output includes:
# - Project type (empty, source_no_git, git_with_history, etc.)
# - Detected primary language
# - Migration complexity (low/medium/high)
# - Recommended migration strategy
# - Recommended branch strategy
# - Step-by-step migration plan
```

## 🌳 Branch Strategies

RepoKit supports multiple branching strategies.

### Main-only (the default)
```
main
```
`repokit create my-project` makes the project folder the repository, on `main`, with:
- `private/` as **its own git repository** (ignored by the project; linked into every worktree);
- [git-repokit-common](https://github.com/DazzleTools/git-repokit-common) vendored at `scripts/repokit-common/`, with its hooks installed (version sync, private-content checks, test gating).

`--no-common` skips git-repokit-common; `--private-mode branch` keeps private work on a private branch only.

### The private-branch model

These keep your working history on a local-only `private` branch (repository in `<name>/local/`, `main` in `<name>/github/`) and move finished work to the public branches -- squashed, fast-forwarded, or selectively. A valid workflow, and RepoKit's original one, but more involved: hooks refuse private files on public branches to keep mistakes from leaking. See [docs/Branch-Strategies.md](docs/Branch-Strategies.md).

With `--with-common`, these strategies also get git-repokit-common's hooks, configured to refuse private files on the public branches. `repokit setup-guardrails` installs the same hooks in an existing project.

### Standard
```
private → dev → main → test → staging → live
```

### Simple
```
private → dev → main
```

### GitFlow
```
private → feature/* → develop → release/* → main
                  ↘                    ↗
                    hotfix/* →  →  → ↗
```

### GitHub Flow
```
private → feature/* → main
```

### Custom
```bash
repokit create my-project \
  --branches "main,develop,qa,production" \
  --worktrees "main,develop"
```

## 🔐 GitHub/GitLab Integration

### With the gh CLI (simplest)

```bash
gh auth login                                   # once
repokit create my-project --github              # private repo under your account, main pushed
repokit create my-project --github --public --org MyOrg
```

git-repokit uses gh's login, so no token is configured here. Only public branches are pushed; a private branch never leaves your machine.

### Through the REST API with a token

### Initial Setup
```bash
# Store GitHub credentials (one time)
repokit store-credentials --publish-to github --token YOUR_TOKEN

# Or use environment variable
export GITHUB_TOKEN=YOUR_TOKEN
```

### Automatic Deployment
```bash
# Create and deploy in one command
repokit create my-project --publish-to github --private-repo

# Deploy to organization
repokit create team-project \
  --publish-to github \
  --organization my-company \
  --private-repo
```

## 🤖 AI Integration

RepoKit includes Claude AI integration for enhanced development:

```bash
# Create project with AI assistance
repokit create my-project --ai claude

# This adds:
# - CLAUDE.md with project context
# - Development workflow instructions
# - Problem-solving methodology (The Process)
# - Private documentation structure
```

## 📁 Directory Structure

RepoKit creates an organized project structure:

```
my-project/
├── local/          # Main repository (private branch)
│   ├── docs/       # Documentation
│   ├── tests/      # Test files
│   ├── scripts/    # Utility scripts
│   ├── private/    # Local-only content
│   │   └── claude/ # AI assistance docs
│   └── ...
├── github/         # Main branch worktree
└── dev/           # Development branch worktree
```

## 🧪 Testing

RepoKit includes a comprehensive test framework:

```bash
# Run all tests
python tests/run_tests.py

# Run specific test categories
python tests/run_tests.py --unit        # Fast unit tests
python tests/run_tests.py --integration # CLI integration tests
python tests/run_tests.py --github      # GitHub API tests (live; requires token)

# Check test environment
python tests/run_tests.py --check
```

Every run is isolated from your git config, home directory and tokens; see `tests/README.md` (and `python -m pytest` works too).

## 📚 Documentation

### Getting Started
- **[Documentation Guide](docs/README.md)** - Start here for navigation
- **[Why RepoKit Exists](docs/Why-RepoKit-Exists.md)** - Understand the problem and solution
- **[Adoption Guide](docs/Adoption-Guide.md)** - Step-by-step tutorials for existing projects

### Reference Guides  
- **[Recipes and How-Tos](docs/Recipes-And-Howtos.md)** - Copy-paste commands for common scenarios
- **[Branch Strategies](docs/Branch-Strategies.md)** - Branching workflows explained
- **[Migration Guide](docs/Migration-Guide.md)** - Universal bootstrap scenarios
- **[Auth Guide](docs/Auth-Guide.md)** - Authentication and credentials
- **[Workflow Guide](docs/Workflow-Guide.md)** - Development workflows
- **[Deployment Demo](docs/Deployment-Demo.md)** - Step-by-step deployment examples
- **[Test Framework](tests/README.md)** - Comprehensive testing documentation

> **💡 Pro Tip**: Start with the [Documentation Guide](docs) for easier perusal and recommended reading order.

## 🛠️ Configuration

RepoKit uses hierarchical configuration:

1. **Default values** (built-in)
2. **Global config** (`~/.repokit/config.json`)
3. **Project config** (`./.repokit.json`)
4. **Environment variables** (`REPOKIT_*`)
5. **CLI arguments** (highest priority)

### Example Configuration
```json
{
  "name": "my-project",
  "language": "python",
  "branches": ["main", "develop", "staging"],
  "worktrees": ["main", "develop"],
  "user": {
    "name": "Your Name",
    "email": "your.email@example.com"
  },
  "github": true,
  "private_repo": true
}
```

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines. Please feel free to open issues or submit pull requests.

Like the project?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djdarcy)


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by modern DevOps practices and GitOps workflows
  - https://nvie.com/posts/a-successful-git-branching-model/
  - https://trunkbaseddevelopment.com/
  - https://docs.github.com/en/get-started/quickstart/github-flow
  - https://martinfowler.com/articles/continuousIntegration.html
  - https://www.atlassian.com/continuous-delivery
  - https://www.perforce.com/blog/vcs/best-branching-strategies-high-velocity-development
- Built for developers who value consistency and automation
- Special thanks to the open-source community
