# Triaged survivors (guarded authority: stale when the file hash changes)

## repokit/layers.py @ 9727e01a8262

- `by_lang[lang] = key` -> `by_lang.setdefault(lang, key)` (in `_bare_candidates`): **equivalent**. A preset and the layer of the same name expand to the same folders, so preferring one over the other changes which key heads the recognition loop and nothing in the result. 2026-10-20, mode 1.
- `return f.get("rank", UNRANKED)` -> `return f.get("rank", 0)` (in `facet_rank`): **don't-care**. Observable only in a manifest that mixes `[layers]` entries with folders that have none; the shipped manifest has an entry for every folder and the 0.7.3-style mock has none, so both sort by the given order either way. 2026-10-20, mode 1.
