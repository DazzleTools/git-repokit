# POC: four grammars for `repokit create` below the language (2026-10-18)

**Question.** When a project is more than "a language" (a Claude Code plugin, a Vite React site, a C/C++ library with Qt, a Python script that is deliberately not a package), how does the person name it on the command line, and what does each way of naming cost in tokens typed, in ambiguity, in the error on a typo, and in the size of the listing that teaches the names?

**Why now.** The measure beside this folder (`../measure-create-grammars/`) found that no generator in daily use exposes more than one level in its grammar: a short name or a template, with the second axis a compound token (`react-ts`), an orthogonal flag, or booleans. djdarcy's reading of that finding set the requirement this proof tests:

> That's largely because we have customized each project after we created the basic template ourselves by hand. The goal is to not have to use a "basic" temlate (like our git-repokit-template which is python-based) and then customizing that for some other scenario. We want to have appropriate configurations that are easy to compose. We could do the composition as just a comma-separated list? For "--langs react,ts,..." or some equivalent? What do you propose?

and, on the compound-name candidate:

> Or your idea of doing a forward-slash as "js-ts/web-vite..." is a decent concept. It's extensible to any language.

and, reading the first draft of the hybrid:

> So you see the "js-ts/claude-plugin" as the composite that we've already assembled and that's why it's safe to have "ts,react,vite" because it maps to the fully-qualified name?

The earlier requirement, from the same day: "there should be a generic node variation, a normal js-ts version for pure js projects / for scripting, a version for web development work, and all the other variations. In other words we should already be planning for "sub-types" and possibly even even "sub-sub-types"".

## Method

`catalogue.py` is one catalogue every candidate parses against: the shipped manifest's languages and archetypes (python, c-cpp), the roster's five js-ts flavours, the python/script floor, and the layers those would be built from (node, browser, ts, vite, react, svelte, qt twice, …). Each layer has a **facet** (language, runtime, dialect, build, framework, purpose), a rank (the order the engine applies facets in), the layers it **implies**, and whether its facet is **exclusive** in one project. Seventeen **presets** are named lists (`js-ts/claude-plugin` = node + claude-plugin).

`grammars.py` holds four mock parsers over that catalogue; `run_matrix.py` pushes seven requests, a typo, the ambiguous bare name `qt`, and a collision through each and prints the matrix. Nothing is generated; the output is the ordered, qualified layer list the grammar would hand `repokit/layers.py`, or the error.

| | Grammar | Composition | What carries a combination |
|---|---|---|---|
| **A** | `--archetype <lang>/<leaf>` | none | a leaf per shape; a wanted combination (lib + Qt) is a new leaf, `c-cpp/cmake-lib-qt` |
| **B** | `--type <flat-name>`, tags for grouping | none | same leaves as A, no prefix; colliding names are renamed (`qt-cpp`, `qt-py`) |
| **C** | `--kind a,b,c` | raw layers in the user's order | the user lists everything, language included; no implies, no exclusivity, no presets |
| **D** | `--archetype` takes a list; a token is a preset (`lang/name`), a qualified layer (`lang/layer`) or a bare layer | ordered by facet, parents implied, exclusive collisions refused, a list equal to a preset recognised | the hybrid djdarcy's two messages describe |

All four share `--language` as shipped (a list, stacking in order, each language's default preset when nothing else is named) and the same typo suggestion, so the comparison is the grammar alone.

## Results (`python run_matrix.py`, second run)

Tokens count items after `create <name>` (a comma list is one token); characters are the flag text typed.

| Request | A | B | C | D |
|---|---|---|---|---|
| Common case, Python package (the floor) | `--language python` 17 ch | same 17 | `--language python --kind pypi` 29 ch, 4 tok | same as A, 17 |
| Claude Code plugin | `--archetype js-ts/claude-plugin` 31 | `--type claude-plugin` **20** | `--kind js-ts,node,claude-plugin` 31 | `--archetype js-ts/claude-plugin` 31, *preset named* |
| Vite + React + TypeScript site | `--archetype js-ts/web-vite-react` 32 | `--type web-vite-react` **21** | `--kind js-ts,browser,ts,vite,react` 34 | `--archetype ts,react,vite` 25, *preset recognised from the list* |
| Python local script | `--archetype python/script` 25 | `--type script` **13** | `--kind python,python/script` 27 | `--archetype python/script` 25 |
| C/C++ library with Qt | `--archetype c-cpp/cmake-lib-qt` 30, **needs a new leaf** | `--type cmake-lib-qt` 19, **needs a new leaf** | `--kind c-cpp,cmake-lib,c-cpp/qt` 31 | `--archetype cmake-lib,qt` **24**, *assembled, not a verified preset* |
| Python + C/C++ mixed | `--language python,c-cpp` 23 | same | same, *language layers only* | same |
| bare `create demo` | structure only | same | same | same |
| typo `claude-plugn` | suggests three leaves | suggests `claude-plugin` | suggests `claude-plugin` | suggests `claude-plugin, js-ts/claude-plugin` |
| bare `qt` | n/a (`c-cpp/qt` is a leaf) | n/a (`qt-cpp`, a name to know) | `'qt' is ambiguous: python/qt, c-cpp/qt` | `'qt' is ambiguous: python/qt or c-cpp/qt` |
| `pypi` and `setuppy` together | impossible to express | impossible to express | **stacks both silently** | `'pypi' and 'setuppy' are both a build for python; pick one` |
| `repokit list` | 27 lines (17 presets + 10 cross-product leaves) | 27 | 25 (one per layer) | 30 (per language: presets, then facets with their choices) |

Every cell resolved or errored with a named reason; no cell was ambiguous on the inputs the person typed. A, B and D meet the floor on the common case; C does not unless it grows a default archetype, which makes it D without the rules.

## What the run found

1. **My facet model was wrong, and the mock said so before any code did.** The first run put `ts` and `vite` both in an exclusive `build` facet, and the `web-vite-react` preset collided with itself. I had filed TypeScript by the tooling it drops into a tree (a `tsconfig.json`, a compile step, a type-check job) and so set it beside the bundler. djdarcy's correction: "I know that typescript is just a flavor of Javascript, but what does that have to do with "a build system"? No language is a build-system even if it can be used to construct a build system?" The rule that falls out: **a facet is named by the choice the person makes, not by the files the choice produces.** Vite answers "how is this bundled"; TypeScript answers "which dialect am I writing in"; a project needs both answers, so they cannot share an exclusive facet. `dialect` is its own facet (rank between runtime and build), and the same split will recur: a Python-version floor or a C++ standard is a dialect too. This is the finding the DWP inherits: the facet list is design, not catalogue data, and it needs to be right before presets are written.
2. **A and B pay per combination; D pays once.** The lib-with-Qt request has no preset. Under A and B it is a new leaf in the catalogue (and the cross-product the catalogue would need to be complete is ten more leaves here, `msbuild-qt` and `minimal-qt` among them, which nobody wants). Under D it is two tokens and the three rules. The listing under D stays at one block per language however many combinations people type; under A and B it grows with every leaf.
3. **B's flat names are the cheapest to type (13 to 21 characters) and D can have that too.** B wins every single-shape row by the width of the `js-ts/` prefix. Nothing stops D from accepting a bare preset name when it is unique across languages (`claude-plugin` alone resolves to `js-ts/claude-plugin`; `qt` does not, and says so). With that, D ties B on every row and beats it on composition. Refinement for the DWP, not implemented here.
4. **The preset is safe because it was assembled and tested; the list is safe because of the rules.** `ts,react,vite` is not looked up against a preset first. It is sorted, its parents implied (`js-ts`, and `browser` from `vite`), exclusivity checked, then assembled. D then notices the result equals `js-ts/web-vite-react` and says so; `cmake-lib,qt` matches nothing and is marked "assembled, not a verified preset". That note is the honest cost of composition: a list that equals no preset is structurally sound and unverified as a combination until a cross-product test exists.
5. **C is the engine without a grammar.** It stacks `pypi,setuppy` without a word, needs the language spelled out, and has no default, so the common case costs four tokens. Its one virtue, that the user controls the order, is a burden for the common user and no help to the expert, who can write a preset.
6. **Ambiguity is a property of the catalogue, not the grammar.** Only `qt` collides, in every candidate; A and B hide it by renaming the leaf, C and D surface it with both names. Either is fine as long as the error names both.

## What this fixes for the DWP on the family's type system

- The grammar is D: `--language` as shipped for the first level; `--archetype` grows from one token to a list; a token is a preset, a qualified layer or a bare layer; parents implied, facets ordered, exclusive collisions refused, a preset recognised when the list equals one; a bare preset name accepted when unique. The flag's name is the cheapest thing to change and was not measured.
- The facets, with their ranks and exclusivity, are the design decision the layers' manifest must carry before js-ts presets are written: language, runtime, dialect, build, framework, purpose, as a first cut; the DWP decides the list.
- Sub-types and sub-sub-types are facets, not tree depth: node is a runtime, web is a runtime (`browser`) plus a bundler, a Claude plugin is a purpose that implies node. The slash stays two levels deep, `language/name`.
- The verification story has to be written: presets are tested; compositions are assembled with a notice until the cross-product (or the combinations people actually type) gets a test.

Kill condition: "the common case costs more than `create demo --language python`, or any cell is ambiguous". Not met for A, B, D. Met for C on the first clause. The proof survives with D as the candidate to design.

Files: `catalogue.py` (the shared catalogue and the order/imply/exclusive rules), `grammars.py` (the four parsers and their listings), `run_matrix.py` (the matrix; `--list A|B|C|D` prints one grammar's `repokit list`). Run from this folder with Python 3.8+; stdlib only.
