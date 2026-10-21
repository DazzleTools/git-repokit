# Measure: how generators ask for a project type (2026-10-18)

Question: before `repokit create` learns a type and a sub-type below the language (js-ts / web / vite-react; python / script; c-cpp / lib / qt), how do the generators in daily use name theirs, and what does a three-level request cost the person typing it?

Method: `capture_help.py` ran each installed tool's own `--help` (and `dotnet new list`) on this machine; the texts are in `help/`. Nothing was generated. Tools not installed here (copier, yeoman, degit) are not measured.

## What each tool does

| Tool | Grammar for the type | Levels | What carries the variant | Discovery | Failure on a wrong name |
|---|---|---|---|---|---|
| `dotnet new` | `dotnet new <short-name> -n X [-f net8.0] [-lang F#]` | 1 positional (type) + flags for variants | a flat catalogue of ~40 short names (`console`, `classlib`, `webapi`, `blazor`, `maui-blazor`); language and framework are orthogonal flags; **tags** on each name (`Web/Web API/API/Service`) give the grouping a human would call sub-types | `dotnet new list`, `dotnet new search`; tags are the only hierarchy | lists templates, suggests `search` |
| `cargo new` | `cargo new <path> [--bin\|--lib]` | 1 boolean | two kinds only; `--bin` default | in `--help` | n/a |
| `flutter create` | `flutter create <dir> -t app\|plugin\|package\|module\|skeleton [--platforms a,b] [--sample id]` | 1 flag (type) + a list flag that only applies to some types | the type flag; `--platforms` is a per-type sub-choice; `--sample` and `--empty` imply the type | `--help` lists the allowed `-t` values | rejects with the allowed list |
| `create-vite` | `create-vite [dir] -t react-ts` | 1 flag, **compound name** | the template name encodes framework and language in one token (`react-ts`, `svelte`); interactive prompts when run in a TTY with no flag | `--help` prints the 18 names in two columns (ts / js) | prompts |
| `create-next-app` | `create-next-app [dir] --ts\|--js [--app] [--empty] ...` | 0 types, many boolean switches | each variation is its own boolean (`--typescript`, `--tailwind`, `--src-dir`, `--empty`); the "type" is the product of the switches; interactive prompts fill what is missing | `--help` | prompts |
| `create-react-router` | `create-react-router dir --template <name\|owner/repo\|url\|path>` | 1 flag, open-ended | a template is any repository path, so the catalogue is GitHub | examples in `--help` | fetch error |
| `cookiecutter` | `cookiecutter <template> [key=value...]` | 0 in the CLI | the template asks questions; the CLI names only which template | none | n/a |
| `gh repo create` | `gh repo create <name> -p owner/template` | 1 flag, a whole repository | a template repository is the type | none (GitHub's UI) | API error |
| `npm init` | `npm init <package-spec>` is `npx create-<spec>` | 0; delegates | the create-package decides everything above | none | npm error |

## What the population says

- **Nobody exposes more than one level in the grammar.** Every tool has one axis the person names (a short name, a template, a kind), and the second axis is either a compound token (`react-ts`), an orthogonal flag that applies to some types (`--framework`, `--platforms`), or a set of booleans (`--ts`, `--empty`). None has a `type/subtype/subsubtype` path in the CLI.
- **The two that have many types keep a flat catalogue and group it with tags**, not nesting (`dotnet new list` with its Tags column; create-vite's two-column listing). Discovery is a `list` subcommand or the `--help` text, never guessing.
- **Compound names are the cheapest to type and the hardest to list**: `react-ts` is one token; eighteen of them fit on a screen, forty do not without tags.
- **Interactive prompting is the fallback everywhere a TTY is present** (create-vite, create-next-app, cookiecutter), and every tool that prompts also accepts the full answer on the command line for scripts.
- **"Implies" is common**: `--sample` implies `--template=app`; `--lib` excludes `--bin`; an archetype implying its language (git-repokit today) is the same move.
- **The common case is one token**: `cargo new x`, `dotnet new console`, `create-vite x -t react-ts`. A three-level request is at most one positional plus one or two flags in every tool measured.

## What this fixes for the proof

The grammar candidates for `repokit create` have to beat or match: one token for the common case; a flat, listable catalogue with grouping rather than a nested path the person has to know; a `list` or `--help` that fits on a screen with tags; prompts in a TTY and full flags for scripts; and "implies" so a sub-type names its parents for the person. The existing `--language` list (stacking in order) and `--archetype language/name` already cover two levels; the open question the proof tests is whether the third level is a compound archetype name (`web-vite-react`), a tag-grouped flat catalogue, or stacked layers behind one `--kind` flag.

Source files: `help/*.txt`, captured 2026-10-18 on plzwork (dotnet SDK with net8/9/10 templates, cargo, flutter, cookiecutter, gh, npm 11).
