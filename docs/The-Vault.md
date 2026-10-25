# The vault

Every project repokit creates has a `private/` folder: the **vault**. It is its own git repository, ignored by the project and never pushed, so notes, design documents, postmortems, issue drafts and commit messages can be versioned without any risk of reaching a public branch.

## How it is made

Under the default `main-only` strategy (`--private-mode nested`):

- The project's `.gitignore` excludes `/private/`, and `private/` gets its own `git init` and first commit.
- The vault has its own `.gitignore` (editor files, Python caches, temp files, agent working state).
- No hook has to guard the project, because git never sees the vault's files from the project's side.

With `--private-mode branch` (the default for the private-branch strategies), private work lives on the local-only `private` branch instead, and git-repokit's hooks refuse private files on the public branches. See [Branch strategies](Branch-Strategies.md).

If you work in a `git worktree` of the project, link the worktree's `private/` back to the main checkout's (a junction on Windows, a symlink elsewhere). Otherwise each worktree gets an empty vault of its own.

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
