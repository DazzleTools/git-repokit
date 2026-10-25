# Configuration

Everything `repokit create` decides can be set once in a config file instead of on every command line. This page lists where settings come from, and every key with the flag that matches it.

## Where settings come from

Each source overrides the one before it:

1. **Built-in defaults**
2. **The global config:** `~/.repokit/config.json` (on Windows, `%USERPROFILE%\.repokit\config.json`). This is where your house style goes.
3. **The project config:** `.repokit.json` in the folder you run `repokit` from. `--config FILE` (before the command: `repokit --config my.json create ...`) reads FILE in its place.
4. **Environment variables:** `REPOKIT_*` (see below).
5. **Command-line flags**

Objects merge key by key, so a project config can change `github.organization` without repeating `github.username`. Lists are replaced, not merged.

Two things to know:

- A created project commits its own `.repokit.json`, which records how it was made. If you run `repokit create` from inside a project folder, that file is read as the project config. Run creates from the folder that should hold the new project.
- `repokit --save-config FILE create ...` writes the final merged configuration to FILE, which is a quick way to see what a create would use.

## A house config

The keys most people set, as one file:

```json
{
  "license": "gpl-3.0-or-later",
  "license_private": "all-rights-reserved",
  "extras": ["all"],
  "github_setup": ["labels", "issues", "pin", "discussions", "topics"],
  "github": {"username": "your-login", "organization": "your-org"},
  "user": {"name": "Your Name", "email": "you@example.com"}
}
```

With it, `repokit create my-tool --language python --github --description "..."` makes a full project. Leave `organization` out to create repositories under your own account.

## The keys

### What the project is

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `language` | `--language` | `generic` | The language, or a list of them in the order their layers apply: `python`, `c-cpp`, `js-ts`, `generic` |
| `with` | `--with` | the language's default preset | Presets and layers below the language, such as `python/claude-plugin` or `c-cpp/qt`. See [Languages and layers](Languages-and-Layers.md) |
| `description` | `--description` | `A new project repository` | One sentence; it goes into the README, `pyproject.toml` or `package.json`, and the GitHub repository |
| `topics` | `--topics` | none | GitHub topics; they also become `keywords` in `pyproject.toml`. Applied by the `topics` setup step |

### The license

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `license` | `--license` | none (required) | A catalogue id (`mit`, `apache-2.0`, `gpl-3.0`, `gpl-3.0-or-later`, `bsd-3-clause`, `0bsd`, `unlicense`, `all-rights-reserved`, `proprietary-evaluation`, ...), `file=<path>`, or `none` |
| `license_private` | none | none | The license for a create with `--private-repo`, if it should differ from `license` |

A create with no license from either the flag or the config stops before writing anything and lists the catalogue. `repokit list` ends with the catalogue too. `adopt` never stops for this: it keeps the project's own license file, or writes the config's, or adopts without one.

The holder (`user.name`, else your git identity) and the year go into every license that names them. `proprietary-evaluation` also names the project and gives `user.email` (else your git email) as the address for permission requests.

### Optional files

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `extras` | `--extras`, `--no-extras` | none | Optional files, by name, or `all` |

The extras:

| Name | Writes |
|---|---|
| `funding` | `.github/FUNDING.yml` (your GitHub login) |
| `dependabot` | `.github/dependabot.yml` |
| `stale` | `.github/stale.yml` |
| `pr-template` | `.github/pull_request_template.md` |
| `release-template` | `.github/release-template.md` |
| `roadmap` | `ROADMAP.md` |
| `platform-support` | `docs/platform-support.md` |
| `vscode-settings` | `.vscode/settings.json` |
| `placeholders` | `docs/.gitkeep`, `tests/one-offs/README.md`, `tests/output/.gitkeep` |

`--no-extras` writes none, whatever the config says.

### README badges

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `badges` | `--badges` | the preset's template | A template name (`pypi`, `github`, `comfyui`, `minimal`, or one of yours), or a list of badge names |
| `badge_templates` | none | none | Your own templates: `{"name": ["badge", "badge", ...]}` |
| `badge_types` | none | none | Your own badges: `{"id": {"alt": "...", "image": "...", "link": "...", "color": "..."}}` |
| `badges_ci` | none | `auto` | The CI badge: `auto` (only where it fills a row of badges), `on`, or `off` |
| `traffic_gist_id` | none | none | The gist that holds ghtraf's install and view counts, for the `installs` and `views` badges |

The badge names are `pypi-version`, `release-date`, `downloads`, `release-version`, `ci`, `python`, `node`, `comfyui-registry`, `license`, `discussions`, `installs`, `views` and `platform`. `runtime` in a template means `python` or `node`, whichever the preset has. The `python/pypi` preset uses the `pypi` template; every other preset uses `github`.

Badges always come out in one order, with Platform last. A template keeps the order it lists; a list given to `--badges` is sorted into the house order, and badges of your own go after the built-in ones. A badge whose value the project does not have (no CI workflow, no runtime minimum, no catalogue license) is left out. The license badge takes the license's usual color (GPL green, MIT yellow, others orange) unless that would match a neighbour, in which case it takes the next one.

### GitHub

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `github.username` | none | the `gh` login | Your GitHub login. With `--github`, repokit reads the login from `gh` and refuses if it differs from this one, so a create never lands in the wrong account |
| `github.organization`, `organization` | `--org`, `--organization` | none | Create the repository under this organization; its URLs use the organization, while CODEOWNERS and FUNDING keep your login |
| `github_setup` | `--github-setup` | none | What to set up on the new repository: `labels`, `issues`, `pin`, `discussions`, `topics`, `pypi-environment`, `traffic`, or `all` |
| `private_repo` | `--private-repo` | false | For `--publish-to`: make the repository private (with `--github` it is private unless `--public`) |

The setup steps are described in [GitHub setup](GitHub-Setup.md). Without `--github`, and without a `github.username`, the files say `YOUR_GITHUB_USERNAME` where the owner goes, and the create warns once.

### Identity

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `user.name` | `--user-name` | your git identity | The name in the new repository's commits, the license holder, and the project's author |
| `user.email` | `--user-email` | your git identity | The email in the new repository's commits |

Leave both unset to use the identity git already has (`git config user.name` and `user.email`).

### Branches, tooling and the vault

| Key | Flag | Default | Meaning |
|---|---|---|---|
| `branch_strategy` | `--branch-strategy` | `main-only` | `main-only`, or a private-branch strategy: `standard`, `simple`, `gitflow`, `github-flow`, `minimal`. See [Branch strategies](Branch-Strategies.md) |
| `private_mode` | `--private-mode` | `nested` for main-only, `branch` otherwise | `nested`: `private/` is its own git repository. `branch`: private work lives on the private branch only |
| `with_common` | `--with-common`, `--no-common` | on for main-only | Vendor git-repokit-common at `scripts/repokit-common/` and install its hooks |
| `vault_init` | none | `prompt-file` | `prompt-file` writes the oracle's first prompt into the vault; `none` writes nothing. See [The vault](The-Vault.md) |
| `branches`, `worktrees`, `private_branch`, `default_branch` | `--branches`, `--worktrees`, `--private-branch`, `--default-branch` | the strategy's | Override a strategy's branches |
| `branch_config.branch_directories` | `--branch-dir-main`, `--branch-dir-dev` | `main` in `github/`, `dev` in `dev/` | Folder names for the worktrees of the private-branch strategies |
| `branch_strategies` | none | the built-in ones | Add or redefine strategies |

### Folders and private content

| Key | Flag | Meaning |
|---|---|---|
| `directory_profile` | `--dir-profile` | `minimal`, `standard` or `complete` |
| `directory_groups` | `--dir-groups` | `development`, `documentation`, `operations`, `privacy` |
| `directories` | `--directories` | Extra folders to create |
| `private_dirs` | `--private-dirs` | Folders kept out of public branches |
| `private_set` | `--private-set` | `standard` or `enhanced` |
| `sensitive_files`, `sensitive_patterns` | `--sensitive-files`, `--sensitive-patterns` | Files and glob patterns kept out of public branches |

## Environment variables

Any key can be set as `REPOKIT_<KEY>`, uppercased. An underscore in the variable means one level of nesting: `REPOKIT_USER_NAME` sets `user.name`, and `REPOKIT_GITHUB_ORGANIZATION` sets `github.organization`. That also means a key that itself contains an underscore, such as `license_private` or `github_setup`, cannot be set this way; put it in a config file. `REPOKIT_BRANCHES`, `REPOKIT_WORKTREES`, `REPOKIT_DIRECTORIES` and `REPOKIT_PRIVATE_DIRS` take comma-separated lists.

Tokens for `--publish-to` have their own variables (`GITHUB_TOKEN`, `GITLAB_TOKEN`); see the [Auth guide](Auth-Guide.md). `--github` uses the `gh` login and needs no token.
