# Triaged survivors (guarded authority: stale when the file hash changes)

## repokit/layers.py @ 9727e01a8262

- `by_lang[lang] = key` -> `by_lang.setdefault(lang, key)` (in `_bare_candidates`): **equivalent**. A preset and the layer of the same name expand to the same folders, so preferring one over the other changes which key heads the recognition loop and nothing in the result. 2026-10-20, mode 1.
- `return f.get("rank", UNRANKED)` -> `return f.get("rank", 0)` (in `facet_rank`): **don't-care**. Observable only in a manifest that mixes `[layers]` entries with folders that have none; the shipped manifest has an entry for every folder and the 0.7.3-style mock has none, so both sort by the given order either way. 2026-10-20, mode 1.

## repokit/repo_manager.py @ 67fe877dcd0f

- `if not self.config.get("github", True):` -> `if not self.config.get("github", False):` (in `_setup_github_integration`): **equivalent**. The default is never read: `config.py:75` puts `"github": True` in every configuration before the manager sees it. 2026-10-26, mode 1.
- `if files_to_remove_from_index and not dry_run:` -> `if files_to_remove_from_index:` (in `_cleanup_sensitive_files`): **equivalent**. The only caller (`_create_clean_public_branch`) never passes `dry_run=True`, so the flag is always false. 2026-10-26, mode 1.
- `self.run_git(["rm", "--cached", file_to_remove], ...)` -> `self.run_git(["rm", file_to_remove], ...)` (in `_cleanup_sensitive_files`): **equivalent**, observed. The file is tracked on the private branch, so the `checkout private` that ends the public-branch loop writes it back; T7 (tracked `config/.env`) stays green under the mutant. 2026-10-26, mode 1.
