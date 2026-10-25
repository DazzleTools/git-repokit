# RepoKit Migration Guide

This guide explains how to bring an existing project into the RepoKit structure and, if you want, deploy it to GitHub.

## Overview

RepoKit's universal migration system handles **any type of project**, from empty directories to Git repositories with existing history. It analyzes your project and recommends a migration approach.

### What RepoKit Can Migrate

- **Empty directories** → New RepoKit projects with the standard structure
- **Source code without Git** → Projects with Git initialized and the RepoKit structure added
- **Existing Git repositories** → Preserves history while adding the RepoKit structure
- **Multi-branch projects** → Keeps existing branches and adds the RepoKit branches around them
- **Any programming language** → `analyze` recognizes many languages; code-type layers (`--language`) exist for python, c-cpp and js-ts, and every other project uses `generic` (run `repokit list` to see the languages, presets and layers)

### Which command, which layout

`adopt` and `migrate` work on a folder you already have. They use the **private-branch layout**: your folder becomes the local checkout on the `private` branch, and the public branches (`main`, `dev`, ...) are checked out as sibling worktree folders (`github/`, `dev/`).

A new project made with `repokit create` defaults to something different: the `main-only` strategy, where the project folder is the repository, on `main`, with `private/` as its own nested git repository and git-repokit-common vendored at `scripts/repokit-common/`. `adopt` does not offer `main-only`. If you want that layout for a project that has no history worth keeping, create a new repository with `repokit create` and copy your files into it. See [Branch-Strategies.md](Branch-Strategies.md) for the difference.

## Quick Start

### 1. Analyze Any Project

Before migration, analyze your project to understand what RepoKit will do:

```bash
# Analyze any directory or project
repokit analyze /path/to/your/project
```

**Example output:**
```
=== PROJECT ANALYSIS: /path/to/my-python-app ===
  Project type: source_no_git
  Detected language: python
  Migration complexity: low
  Recommended strategy: safe
  Recommended branch strategy: simple
  Git repository: No

  Directory structure:
    Existing standard directories: None
    Missing standard directories: convos, docs, logs, private, revisions, scripts, tests
    Special directories: None
    Has template conflicts: No

  File counts:
    python: 2
    markdown: 1
    Total: 3

  Migration steps:
    1. Backup existing project (recommended)
    2. Analyze and resolve any template conflicts
    3. Apply RepoKit directory structure
    4. Initialize or update Git repository
    5. Set up branch strategy and worktrees
    6. Generate appropriate templates
    7. Create remote repository if requested
```

The "Next steps" that `analyze` prints at the end still show the old `--strategy` spelling. The flag is `--migration-strategy`.

### 2. Adopt Your Project

Use the `adopt` command to convert your project in place. Adopt keeps the project's own license file (`LICENSE`, `LICENSE.md`, `COPYING`, ...). With none, it writes the `license` your `~/.repokit/config.json` names, or adopts the project without one and says so. Pass `--license <id>` only to choose one, which replaces the project's own file; `repokit list` shows the license ids.

```bash
# Dry run to see what would happen
repokit adopt /path/to/your/project --dry-run

# Actually adopt the project
repokit adopt /path/to/your/project --license mit

# Adopt and deploy to GitHub in one command
repokit adopt /path/to/your/project --license mit --publish-to github
```

Adopt uses the `standard` branch strategy unless you pass `--branch-strategy` (the choices for adopt are `standard`, `simple`, `gitflow`, `github-flow`, `minimal`). The `Recommended branch strategy` line in the analysis is advice only; it is not applied for you.

A project with no Git repository gets one. A project that already has history keeps it, and the uncommitted-changes prompt asks you to confirm before going on.

## Migration Scenarios

### Scenario 1: Brand New Project

**Situation:** You have an empty directory or just a few files, no Git history.

For a project you are starting now, `repokit create` is the better tool (it makes the default `main-only` layout, with the vault and the hooks):

```bash
repokit create my-new-app --language python --license mit
```

If you have already begun in a folder and want to keep going there, adopt it:

```bash
mkdir my-new-app
cd my-new-app
echo 'print("Hello World")' > main.py

# Analyze first
repokit analyze .

# Adopt with the simple branch strategy
repokit adopt . --license mit --language python --branch-strategy simple
```

**What happens:**
- Lays down the python layers (only because `--language python` was given; the analysis' "Detected language" does not select them)
- Creates the RepoKit directories (docs, tests, scripts, private, ...) and the standard files (LICENSE, CHANGELOG, CONTRIBUTING, `.repokit.json`, CLAUDE.md)
- Initializes Git with the branches `private`, `main` and `dev`
- Checks `main` out in a sibling `github/` folder and `dev` in a sibling `dev/` folder; your folder stays on `private`

Publishing is a separate step; see "GitHub Deployment" below.

### Scenario 2: Existing Code, No Git

**Situation:** You have a working project with source code but no version control.

```bash
# Your existing project structure:
my-python-app/
├── src/
│   ├── __init__.py
│   └── main.py
├── requirements.txt
└── README.md

# Analyze the project
repokit analyze my-python-app

# Adopt with the safe migration strategy (preserves existing files)
repokit adopt my-python-app --license mit --language python --migration-strategy safe
```

**What happens:**
- Uses the "safe" migration strategy (no file overwrites)
- Adds the missing RepoKit directories (docs, tests, private, etc.)
- Keeps your existing files such as README.md and requirements.txt as they are; the python layers add files that are not there yet (for example `pyproject.toml`) and never overwrite your own
- Initializes Git and creates the branch structure
- Add `--publish-to github` to create the GitHub repository and push

### Scenario 3: Existing Git Repository

**Situation:** You have a Git repository with history that you want to enhance with RepoKit.

```bash
# Your existing Git project
my-git-project/
├── .git/           # Existing Git history
├── src/
├── tests/
└── README.md

# Analyze first
repokit analyze my-git-project

# Adopt preserving all Git history
repokit adopt my-git-project --license mit --migration-strategy safe
```

**What happens:**
- Detects the existing Git repository and its branches
- Preserves all Git history and existing branches
- Adds the RepoKit structure around existing files
- Sets up the private-branch worktrees (`github/`, `dev/`) next to your folder
- Optionally publishes to GitHub with the history preserved (`--publish-to github`)

Commit or stash uncommitted work first, and consider `--backup` (see Best Practices).

### Scenario 4: Multi-Branch Project

**Situation:** You have a Git repository with several branches, remotes, and a development workflow.

```bash
# Existing project
my-complex-app/
├── .git/           # Git history
├── branches: main, develop, feature/new-ui, hotfix/security
├── existing remote: origin
└── multiple developers working

# Analyze to understand complexity
repokit analyze my-complex-app

# Adopt with the merge strategy for template integration
repokit adopt my-complex-app --license mit --migration-strategy merge --branch-strategy gitflow
```

**What happens:**
- Preserves existing branches and remotes
- Adds the branches the chosen strategy needs (for `gitflow`: `private`, `main`, `develop`, `release`, `hotfix`)
- Merges RepoKit templates with existing configuration files where it can
- Leaves your remote connections alone

Choose the `--branch-strategy` that matches how the team already works. Adopt does not guess it from the existing branches.

## GitHub Deployment

### The simple path: `create --github`

For a new project, the simplest way to reach GitHub is `repokit create NAME --github`, which uses your `gh` CLI login (no token to manage) and can set up labels, issues, discussions, topics and more with `--github-setup`. `adopt` has no `--github` flag; it uses the token path below.

### The token path: `--publish-to github`

`adopt`, `migrate`, `create` and `publish` take `--publish-to github` (or `gitlab`), which talks to the GitHub REST API with a personal access token.

#### Setting Up GitHub Authentication

RepoKit looks for a token in this order: the `--token-command` output, the `GITHUB_TOKEN` environment variable, then stored credentials. Any one of these works, as does `--token` for a single run.

##### Method 1: Environment Variable
```bash
export GITHUB_TOKEN="your_github_token_here"
repokit adopt my-project --license mit --publish-to github
```

##### Method 2: Store Credentials
```bash
# Store token (saved to ~/.repokit/credentials.json)
repokit store-credentials --publish-to github --token "your_token"

# Now you can deploy without specifying token
repokit adopt my-project --license mit --publish-to github
```

##### Method 3: Token Command
```bash
# Use password manager or secure command
repokit adopt my-project --license mit --publish-to github --token-command "pass show github/token"
```

See [Auth-Guide.md](Auth-Guide.md) for more on tokens and scopes.

### GitHub Deployment Options

```bash
# Private repository
repokit adopt my-project --license mit --publish-to github --private-repo

# Organization repository
repokit adopt my-project --license mit --publish-to github --organization "my-company"

# Public repository with description
repokit adopt my-project --license mit --publish-to github --description "My awesome project"

# Repository named differently from the folder
repokit adopt my-project --license mit --publish-to github --repo-name "my-project-v2"

# All together
repokit adopt my-project \
  --license mit \
  --publish-to github \
  --private-repo \
  --organization "my-company" \
  --migration-strategy safe \
  --branch-strategy standard
```

`--no-push` creates the remote repository without pushing the branches. The private branch is never pushed.

### Full Automation Example

Here is a workflow from an existing folder to GitHub deployment:

```bash
# Create a new Python project
mkdir awesome-python-tool
cd awesome-python-tool

# Add some initial code
echo 'def main():' > main.py
echo '    print("Hello from my awesome tool!")' >> main.py
echo '' >> main.py
echo 'if __name__ == "__main__":' >> main.py
echo '    main()' >> main.py

# Create basic requirements
echo 'requests>=2.28.0' > requirements.txt

# Analyze what RepoKit will do
repokit analyze .

# Adopt and deploy in one command
repokit adopt . \
  --license mit \
  --language python \
  --publish-to github \
  --private-repo \
  --migration-strategy safe \
  --ai claude
```

This single command will:
1. Apply the RepoKit structure safely
2. Initialize Git with the standard branch strategy
3. Lay down the python layers and templates
4. Add Claude AI integration files (`--ai claude` is the default; `--ai none` skips them)
5. Create a private GitHub repository
6. Push the public branches to GitHub (never the private branch)

## Migration Strategies Explained

`--migration-strategy` takes `safe`, `replace` or `merge`. The default is `safe`.

### Safe Strategy
```bash
repokit adopt my-project --license mit --migration-strategy safe
```
- **Never overwrites existing files**
- Copies conflicting files into a `_backup` folder (for example `.github_backup/`)
- Preserves all existing Git history
- **Best for production projects**

### Merge Strategy
```bash
repokit adopt my-project --license mit --migration-strategy merge
```
- Merges RepoKit templates with existing files
- Combines configuration files when possible
- **Best for projects that want the RepoKit files integrated with their own**

### Replace Strategy
```bash
repokit adopt my-project --license mit --migration-strategy replace
```
- Replaces existing template files with RepoKit versions
- Keeps your source code untouched
- **Use when you want fresh RepoKit configuration**

`analyze` recommends one of these three for your project.

## Branch Strategies

Adopt and migrate use the private-branch model: you work on a local-only `private` branch, and finished work moves to the public branches. Choose one with `--branch-strategy`:

### Standard Strategy (default for `adopt` and `migrate`)
- Branches: `private`, `main`, `dev`, `staging`, `test`, `live`
- Worktrees: `main` (in `github/`), `dev`
- **Best for**: Professional projects, CI/CD workflows

### Simple Strategy (recommended for small projects)
- Branches: `private`, `main`, `dev`
- Worktrees: `main`, `dev`
- **Best for**: Personal projects, small teams

### GitFlow Strategy
- Branches: `private`, `main`, `develop`, `release`, `hotfix`
- **Best for**: Large teams, complex release cycles

### GitHub Flow and Minimal
- `github-flow`: `private`, `main`
- `minimal`: `private`, `main`, no worktrees

### Main-only (create only)
`repokit create` also accepts `main-only`, its default: one branch, and the folder is the repository. `adopt` and `migrate` do not take it. See [Branch-Strategies.md](Branch-Strategies.md).

## Command Reference

### Analysis Commands
```bash
# Basic analysis
repokit analyze /path/to/project

# Analysis with more detail
repokit analyze /path/to/project -vv

# Analyze current directory
repokit analyze .
```

### Adoption Commands
```bash
# Basic adoption
repokit adopt /path/to/project --license mit

# Adoption with specific strategies
repokit adopt /path/to/project --license mit --migration-strategy safe --branch-strategy simple

# Dry run (see what would happen)
repokit adopt /path/to/project --license mit --dry-run

# Adopt current directory
repokit adopt . --license mit

# Adopt with a backup copy of the project first
repokit adopt /path/to/project --license mit --backup --backup-location ../project-backup

# Adopt and deploy to GitHub
repokit adopt /path/to/project --license mit --publish-to github

# Everything at once
repokit adopt /path/to/project \
  --license mit \
  --language python \
  --migration-strategy safe \
  --branch-strategy simple \
  --publish-to github \
  --private-repo \
  --organization "my-org" \
  --ai claude
```

`--language` and `--with` choose code-type layers and presets as they do for `create`; see `repokit list` and [Languages-and-Layers.md](Languages-and-Layers.md). The config keys that supply defaults (such as `license`) are in [Configuration.md](Configuration.md).

### Migrate Commands
```bash
# Add the RepoKit directories to a folder (safe by default)
repokit migrate /path/to/project

# Choose a strategy, preview first
repokit migrate /path/to/project --migration-strategy merge --dry-run

# With a backup, then publish
repokit migrate /path/to/project --backup --publish-to github
```

`migrate` has no `--language`, `--license` or `--branch-strategy` flag.

## Troubleshooting

### "No license found in the project and none named"
`adopt` says this when the project has no license file and neither `--license` nor the `license` key in `~/.repokit/config.json` names one. The project is adopted without a LICENSE. Add a license file yourself, or run `adopt` again with `--license mit` (or another id from `repokit list`, or `file=PATH`).

### "already exists" when the worktrees are created
Adopt puts the worktrees beside your project folder, as `github/` and `dev/`. If a folder with one of those names is already next to the project, Git refuses with `fatal: '.../github' already exists`. Move or rename that folder and run the adoption again.

### Uncommitted Changes Warning
If RepoKit detects uncommitted changes:
```
WARNING: Uncommitted changes detected!
Continue with adoption? Changes should be committed first. [y/N]:
```

**Solution:** Commit your changes first. `--migration-strategy safe` never overwrites your files, but committing gives you a restore point. `--backup` makes a copy of the whole folder before anything changes.

### GitHub Authentication Issues
```bash
# Store (or re-store) your GitHub token
repokit store-credentials --publish-to github --token "your_token"

# Or test a token directly
curl -H "Authorization: token your_token" https://api.github.com/user
```

### Template Conflicts
When RepoKit finds existing files that match template names:
- **Safe strategy**: Keeps your file and copies the conflicting ones into a `_backup` folder
- **Merge strategy**: Attempts to merge content
- **Replace strategy**: Replaces with RepoKit templates

### Permission Errors
```bash
# Ensure you have write permissions
ls -la /path/to/project

# For GitHub deployment, ensure token has repo permissions
# Check token scopes at: https://github.com/settings/tokens
```

## Best Practices

### 1. Always Analyze First
```bash
repokit analyze my-project  # Understand what will happen
repokit adopt my-project --license mit --dry-run  # Preview changes
repokit adopt my-project --license mit  # Execute adoption
```

### 2. Use Safe Strategy for Production
```bash
repokit adopt production-app --license mit --migration-strategy safe --publish-to github
```

### 3. Back Up Important Projects
```bash
repokit adopt my-important-project --license mit --backup --backup-location ../my-important-project-backup
```

### 4. Test Deployment on Personal Repos First
```bash
# Test on personal account first
repokit adopt test-project --license mit --publish-to github

# Then deploy to organization
repokit adopt real-project --license mit --publish-to github --organization "company"
```

### 5. Use AI Integration for Enhanced Development
```bash
repokit adopt my-project --license mit --ai claude --publish-to github
```

This adds Claude AI integration with:
- CLAUDE.md configuration file
- Development workflow process documentation
- Context management tools
- Private instruction files

## Migration vs. Adoption

| Feature | `migrate` | `adopt` |
|---------|-------------------|---------------|
| **Analysis** | Directory analysis | Project analysis with Git state |
| **Git Integration** | Adds directories only; you run `git init` and make the branches | Initializes Git or keeps your history, sets up branches and worktrees |
| **Remote publishing** | `--publish-to` | `--publish-to`, with repo name, organization, private repo |
| **Languages and layers** | None | `--language`, `--with` |
| **License** | None | `--license` (or the config's `license`) |
| **Branch Strategy** | Not handled | `--branch-strategy` |

**Recommendation:** Use `adopt` for projects with code or history. `migrate` is the lighter command: it only adds the standard directories and prints the Git steps for you to run.

## What the Universal Bootstrap Does

### Analysis
- **Project Type Detection**: Empty, source code, Git repos, RepoKit projects
- **Language Detection**: Recognizes common languages from file extensions (informational; layers are chosen with `--language`)
- **Git State Analysis**: Branch detection, uncommitted changes, remotes
- **Complexity Assessment**: Low/medium/high migration complexity scoring

### Recommendations
- **Migration Strategy**: Recommends safe, replace or merge
- **Branch Strategy**: Suggests one, which you pass with `--branch-strategy`
- **Step-by-Step Guidance**: The steps for each project type

### Deployment
- **One-Command Deployment**: From adoption to GitHub with `--publish-to github`
- **Multiple Auth Methods**: Environment variables, stored credentials, token commands
- **Organization Support**: Deploy to personal or organization repositories
- **AI Integration**: Claude files by default; `--ai none` to skip

### Preserved Functionality
- Safe/replace/merge strategies
- Template conflict handling
- Language-specific templates, through `--language` and `--with`
- Git repository preservation
- Dry run in both `migrate` and `adopt`
