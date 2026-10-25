# $project_name -- the private vault

This folder is its own git repository, ignored by the project and never pushed. It holds the project's thinking: design analyses, postmortems, notes, issue drafts, commit messages, and the map an oracle session keeps.

## Layout

- `claude/` -- dated documents (`YYYY-MM-DD__HH-MM-SS__<type>__<topic>.md`); `claude/notes/`, `claude/issues/`, `claude/commits/` for the smaller kinds
- `claude/_maps/MOC-$project_name.md` -- the map of content: the project's arcs and the documents behind each
- `claude/_oracle/` -- the oracle's index: `manifest.md` (every document, one line each), `concepts.md` (the project's own words), `backlinks.md` (generated)
- `claude/_todo/` -- `OPEN-LOOPS.md` (deferred work, each with its next action) and `ACTIVE-WORK.md` (the working set)

## Conventions

- Link with wikilinks relative to `claude/`: `[[notes/2026-01-01__00-00-00__both_topic]]`, never `../` paths.
- Frontmatter on every document: `type`, `date`, `author`, `tags`.
- A finished document's body is not edited; it is extended with a dated addendum.
- Commit by named path; the vault is local-only.

## Three sessions per project

A project of any size runs three Claude Code sessions, each named `<PROJECT>__<YYYY-MM-DD>__<Role>`:

| Role | Model | First command |
|---|---|---|
| Decisions | the strongest available | `/familiarize`, then the design work |
| Work | Opus | the plan or goal the decisions session wrote |
| Oracle | any | `/obsidian-update`, then `/obsidian-loop` |

`repokit create` laid this skeleton and wrote the oracle's first prompt to `claude/_oracle/bootstrap-prompt.md`; the oracle session builds the map from it.
