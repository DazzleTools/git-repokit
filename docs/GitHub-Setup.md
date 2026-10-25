# GitHub setup

`repokit create ... --github` creates the repository on GitHub, sets it up, and pushes. It uses the [GitHub CLI](https://cli.github.com/)'s login, so no token is stored anywhere.

```bash
gh auth login        # once

repokit create my-tool --language python --license mit \
  --description "What my-tool does" \
  --github --github-setup all --topics cli,python
```

## The repository

- **Owner:** your `gh` login, or `--org MyOrg` (also `github.organization` in the config). With `--org`, the URLs in the project's files use the organization, while CODEOWNERS and FUNDING keep your login.
- **Visibility:** private, unless `--public`.
- **What is pushed:** the public branches only. Under the default `main-only` strategy that is `main`; a private branch never leaves your machine, and the vault in `private/` is a separate repository with no remote.
- **The wrong account:** if `~/.repokit/config.json` names `github.username` and `gh` is logged into a different account, the create stops before making anything on GitHub. Switch with `gh auth switch`.
- **The owner in the files:** repokit reads the `gh` login before writing any file, so the README, `pyproject.toml`, CODEOWNERS and FUNDING carry the real owner.
- `--no-push` with `--github` creates nothing on GitHub.

If something on GitHub fails, the local project is left as it is, and the create says what went wrong.

## `--github-setup`: the steps

Name the steps, or `all`, on the command line or as `github_setup` in the config. Every step is safe to run twice: it creates only what is missing.

| Step | What it does |
|---|---|
| `labels` | Creates nine labels: `pinned`, `evergreen`, `roadmap`, `scratchpad`, `architecture`, `epic`, `ideas`, `CurrentTask`, `NextTask`. It also creates any label the project's own files use (the issue templates' `bug`, `enhancement`, `documentation`; Dependabot's `dependencies`, `github-actions`, `pip`), because a repository made by `gh` starts with none |
| `issues` | Opens **Roadmap** as #1 and **Quick Notes -- Bugs, Features, Ideas** as #2. Their bodies are also saved in `private/claude/issues/` |
| `pin` | Pins #1 and #2 |
| `discussions` | Turns on Discussions |
| `topics` | Adds the topics from `--topics` (or `topics` in the config) |
| `pypi-environment` | Creates the `pypi` environment the publish workflow uses. Only for the `python/pypi` preset |
| `traffic` | Prints the commands that set up [ghtraf](https://github.com/djdarcy/github-traffic-tracker) traffic stats. It runs nothing, because ghtraf needs a secret only you can set |

### The order matters

Labels, issues and pins go in **before the first push**. The first push lets Dependabot open pull requests, and a pull request would take number 1. Discussions, topics and the `pypi` environment come after the push.

The `issues` step refuses to run on a repository that already has issues, because Roadmap and Quick Notes would not get #1 and #2. It says so, and creates nothing.

## What is still done by hand

GitHub has no API for some settings, and some steps need you. The create prints the first three:

- **The first CI run:** watch it with `gh run list -R OWNER/NAME --limit 5`.
- **Sponsorships** (with the `funding` extra): Settings > General > Features > Sponsorships.
- **Pages,** if the project serves `docs/`: Settings > Pages > main, `/docs`.
- **The PyPI trusted publisher** (the `python/pypi` preset): before the first release, add a pending publisher on PyPI with your project name, the repository's owner and name, workflow `release.yml`, and environment `pypi`. The workflow then publishes each time a GitHub Release is published, with no token.
- **The Roadmap:** issue #1 starts as an outline; fill it in as the plan forms.
- **Tag signing,** if you sign tags: that is your git configuration, not repokit's.

## The older REST path

`--publish-to github` (or `gitlab`) creates the repository through the REST API with a token instead of `gh`. It is public unless `--private-repo`, and it does not run the `--github-setup` steps. Tokens are covered in the [Auth guide](Auth-Guide.md). For GitHub, `--github` is the simpler path.

## An existing repository

`repokit publish <path> --publish-to github` publishes a repository that already exists locally. The setup steps are part of `create --github` only.
