# Git Workflow Guide for RepoKit

This guide explains the multi-branch workflow RepoKit can set up and provides practical examples of common workflows.

## Which Workflow Do You Have?

A bare `repokit create my-project` makes a **main-only** repository: one branch, `main`, in the project folder itself, with `private/` kept as its own separate git repository that never reaches `main`. There is nothing to promote: you work on `main` (or on short-lived feature branches you create yourself), commit, and push. The rest of this guide describes the **private-branch model**, which you get with `--branch-strategy standard` (or `simple`, `gitflow`, `github-flow`, `minimal`) on `create` or `adopt`. `adopt` uses `standard` unless you say otherwise. See [Branch-Strategies.md](./Branch-Strategies.md) for the strategies side by side.

## Branching Strategy Overview

With `--branch-strategy standard`, RepoKit sets up a structured branching model with the following branches, arranged in order of stability:

```
private → feature-XYZ → dev → main → test → staging → live
```

Each branch has a specific purpose:

| Branch | Purpose | Push to Remote? |
|--------|---------|----------------|
| `private` | Personal development, experimentation, and initial work | No - local only |
| `feature-*` | Individual feature development | Yes - for collaboration |
| `dev` | Integration branch where features come together | Yes |
| `main` | Stable code that passes CI/CD | Yes - default branch |
| `test` | For QA testing | Yes |
| `staging` | Pre-release validation | Yes |
| `live` | Production-ready code | Yes |

The repository sits in `my-project/local/` (on `private`); `main` is checked out in `my-project/github/` and `dev` in `my-project/dev/`. A branch can be checked out in only one worktree at a time, so to work on `main` or `dev`, go to its folder instead of running `git checkout` from another one. The examples below show plain git commands; run them in the folder where the branch you start from is checked out (for `private`, that is `local/`).

## Common Workflows

### 1. Starting a New Feature

```bash
# From your private branch, create a new feature branch
git checkout private
git checkout -b feature-new-login-system

# Make changes and commit
git add .
git commit -m "Implement new login system"

# Push feature branch to remote
git push -u origin feature-new-login-system
```

### 2. Submitting a Feature for Integration

```bash
# Update your feature branch with latest dev changes
git checkout dev
git pull origin dev
git checkout feature-new-login-system
git merge dev

# Resolve any conflicts
# Then push updated feature to remote
git push origin feature-new-login-system

# Create a pull request from feature-new-login-system to dev
# (Done through GitHub/GitLab UI)

# After PR is approved and merged, update local dev
git checkout dev
git pull origin dev

# Clean up feature branch (optional)
git branch -d feature-new-login-system
git push origin --delete feature-new-login-system
```

### 3. Promoting Changes Through Environments

```bash
# Moving from dev to main
git checkout main
git pull origin main
git merge dev
git push origin main

# Moving from main to test
git checkout test
git pull origin test
git merge main
git push origin test

# Moving from test to staging
git checkout staging
git pull origin staging
git merge test
git push origin staging

# Moving from staging to live
git checkout live
git pull origin live
git merge staging
git push origin live
```

### 4. Creating a Hotfix

```bash
# Create hotfix branch from live
git checkout live
git pull origin live
git checkout -b hotfix-critical-security-issue

# Make hotfix changes
git add .
git commit -m "Fix critical security issue"

# Push hotfix to remote
git push -u origin hotfix-critical-security-issue

# Create PR to merge hotfix into live
# After PR is approved and merged:
git checkout live
git pull origin live

# Also apply hotfix to other branches
git checkout staging
git pull origin staging
git merge hotfix-critical-security-issue
git push origin staging

# Continue this process for test, main, and dev branches
# to ensure hotfix propagates through all environments
```

### 5. Working with Private Branch

The `private` branch is for your personal development and should never be pushed to remote repositories. Use it to experiment, store private notes, or work on changes before they're ready to be shared. RepoKit installs hooks (git-repokit-common's, or its own guard) that refuse private files on public branches, and `repokit create --github` and `repokit publish` never push `private`.

To move finished work from `private` to a public branch, preview first and then merge with private content left behind:

```bash
# From the public branch's folder (for example my-project/dev/)
repokit safe-merge private --preview
repokit safe-merge private --no-ff --no-commit
```

`repokit safe-merge-dev feature/x --preview` does the same for development branches, squashing prototype and experiment branches so their working history stays out of the public log. To keep the history of a hand-picked set of files instead, copy them across as shown below.

```bash
# Switch to private branch (it is checked out in my-project/local/)
git checkout private

# Make experimental changes
# ...

# Once you're ready to share, create a feature branch
git checkout -b feature-my-new-idea

# Copy specific files to your feature branch (without private content)
git checkout private -- src/components/Button.js src/utils/helpers.js

# Commit and push feature branch
git add .
git commit -m "Add new button component and helpers"
git push -u origin feature-my-new-idea
```

### 6. Using Worktrees

The private-branch strategies set up Git worktrees (`local/`, `dev/` and `github/` for `standard`) to allow you to work on multiple branches simultaneously without switching branches. Which branches get a folder depends on the strategy; `--worktrees` and `--branch-dir-main` / `--branch-dir-dev` change it. A main-only repository has no worktrees unless you create them with `git worktree add`; then link its `private/` folder to the main one so the notes stay in one place.

```bash
# From the private worktree (my-project/local/), go to the dev worktree
cd ../dev/

# This directory is already on the dev branch
# Make changes here
git pull
# Edit files...
git add .
git commit -m "Update documentation"
git push

# Go back to your private worktree
cd ../local/
```

## Best Practices

1. **Keep branches synchronized**: Regularly pull changes from upstream branches to minimize merge conflicts.

2. **Feature branches should be short-lived**: Complete features quickly and merge them to avoid long-running branches that diverge significantly.

3. **Never push the private branch**: Keep sensitive or experimental content local only.

4. **Test before promoting**: Ensure code works in each environment before promoting to the next one.

5. **Communicate during complex merges**: Let your team know when you're merging significant changes that might affect others.

6. **Use meaningful commit messages**: Explain what changes were made and why.

7. **Consider using tags**: For important releases, add Git tags to mark significant versions.

## Alternative Workflows

RepoKit's default is main-only, and the `standard` strategy described above is a multi-environment model; your team might prefer other approaches:

- **Trunk-Based Development**: Focus on the main branch with very short-lived feature branches. This is what main-only gives you.
- **GitHub Flow**: Feature branches that merge directly to main, which is always deployable (`--branch-strategy github-flow`).
- **GitFlow**: `develop`, `release` and `hotfix` branches (`--branch-strategy gitflow`).
- **GitLab Flow**: Similar to GitHub Flow but with explicit environment branches.

The RepoKit structure can adapt to these workflows by adjusting which branches you actively use.

## Need Help?

For any Git-related questions or issues with your RepoKit setup, please:

1. Check the official [Git documentation](https://git-scm.com/doc)
2. Visit [RepoKit's GitHub repository](https://github.com/DazzleTools/git-repokit)
3. Open an issue if you encounter bugs or have feature requests
