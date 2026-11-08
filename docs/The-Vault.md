# The vault

Every project repokit creates has a `private/` folder: the **vault**. It is its own git repository, ignored by the project and never pushed, so notes, design documents, postmortems, issue drafts and commit messages can be versioned without any risk of reaching a public branch.

## How it is made

Under the default `main-only` strategy (`--private-mode nested`), and the same way under the private-branch strategies' default, `--private-mode nested-branch`:

- The project's `.gitignore` excludes `/private/`, and `private/` gets its own `git init` and first commit.
- The vault has its own `.gitignore` (editor files, Python caches, temp files, agent working state).
- No hook has to guard the project, because git never sees the vault's files from the project's side.

## The three private modes

| `--private-mode` | `private/` | The private branch | `convos/`, `revisions/`, `logs/` | Default for |
|---|---|---|---|---|
| `nested` | its own repository | none (or present but carrying nothing private) | inside the vault | `main-only` |
| `nested-branch` | its own repository, linked into every worktree | yes | at the root, **tracked on the private branch** | a `create` with a private-branch strategy |
| `branch` | tracked on the private branch | yes | at the root, tracked on the private branch | `adopt`; otherwise asked for by name (warned) |

**`nested-branch`** is for a project that wants its conversations and old revisions in git history without giving up the portable vault. Move an old file to `revisions/` and it is still tracked; run `git add .` on the private branch and `convos/` comes with it. `logs/` is tracked as a folder with its own `.gitignore` (`*.log`), so run output stays out and a chosen log can be committed with `git add -f`. The folders are committed on the private branch *after* the public branches are cut from it, so no public branch's history holds them.

**`branch`** tracks `private/` itself on the private branch as well. Only the hooks and `safe-merge` then keep it off the public branches, which is why it is opt-in and warned.

**How the promoted folders stay off public branches and remotes.** On the private branch the `.gitignore` does not name them. On the public branches it does, and the pre-commit hook refuses them there, `repokit safe-merge` leaves them out of a merge, and git-repokit-common's pre-push hook (0.4.4 and later) refuses any push whose new commits add them. A private branch pushed by mistake, a fast-forward merge (which makes no commit, so pre-commit never runs), or a commit made with `--no-verify` is therefore stopped at the push. On a remote that is itself private, `REPOKIT_ALLOW_PRIVATE_PUSH=1 git push ...` allows one push.

**Where each sits, by exposure** (who can read it, from `untracked` to `public`): the vault and the promoted folders are `local`. They never leave the machine. The public branches are `shared` or `public`. `.repokit.json` records the mode's ranks as `private_exposure`.

**With `minimal`** (one checkout that switches branches): checking out `main` takes the promoted folders off the disk until you switch back to `private`. That is git hiding files the public branch does not track. The vault stays, because it is its own repository.

**`nested-branch` and `branch` need a private branch.** With `main-only`, `create` refuses and names the fixes: a private-branch strategy, or `--private-mode nested`.

If you work in a `git worktree` of the project, link the worktree's `private/` back to the main checkout's (a junction on Windows, a symlink elsewhere). Otherwise each worktree gets an empty vault of its own. git-repokit makes the link for the worktrees it creates.

## What it starts with

```
private/
  CLAUDE.md                     the vault's conventions, for a Claude Code session working here
  claude/
    _maps/MOC-<project>.md      the map of content: the project's arcs and the documents behind each
    _oracle/manifest.md         every document, one line each
    _oracle/concepts.md         the project's own vocabulary
    _oracle/backlinks.md        generated from the wikilinks
    _oracle/bootstrap-prompt.md the oracle session's first prompt
    _todo/OPEN-LOOPS.md         deferred work, each with its next action
    _todo/ACTIVE-WORK.md        the working set
    commits/                    commit message drafts
    issues/                     issue drafts (the --github-setup issue bodies land here)
  docs/
  notes/
```

Existing files are never overwritten, so running a create over an existing vault keeps what is there.

### The conventions

`private/CLAUDE.md` sets them out; in short:

- Dated documents in `claude/`, named `YYYY-MM-DD__HH-MM-SS__<type>__<topic>.md`.
- Wikilinks relative to `claude/` (`[[notes/2026-01-01__00-00-00__topic]]`), never `../` paths.
- Frontmatter on every document: `type`, `date`, `author`, `tags`.
- A finished document is not edited; it is extended with a dated addendum.
- Commits by named path, and the vault is never pushed.

## The oracle's first prompt

repokit writes nothing a model would write. It lays the skeleton, and writes `claude/_oracle/bootstrap-prompt.md`: the instructions for an **oracle** session to read the project and fill in the map, the manifest and the concepts. Nothing is sent anywhere.

Set `"vault_init": "none"` in `~/.repokit/config.json` to skip the prompt file.

## Sessions that use the vault

The vault is laid out for three Claude Code sessions per project, each named `<PROJECT>__<YYYY-MM-DD>__<role>`:

| Role | What it does | Starts with |
|---|---|---|
| Director (decisions) | Designs, plans, decides; writes the design documents | `/familiarize` |
| Worker | Does the implementation the director's plan describes | the plan or goal the director wrote |
| Oracle | Keeps the vault's map and index current, and answers questions from it | the bootstrap prompt, then `/obsidian-update` and `/obsidian-loop` |

Smaller projects run one session that both decides and works, plus the oracle. The commands named here are Claude Code skills from the author's own setup, not part of repokit; the vault works with any tools that read Markdown.

## After the create

These steps are still done by hand:

- **The oracle's permissions.** An oracle session launched from `private/` needs a `private/.claude/settings.local.json` that lets it read the project and write the vault. A session may not write its own permissions, so you install that file yourself.
- **The first map.** Start the oracle session in `private/` and give it the bootstrap prompt. Running `/obsidian-init` over the skeleton adds the rest of the house layout (a hold list, open questions, a notes tree by area).
