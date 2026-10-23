# p4-poc-neutral-purpose: run record

method: CONTROL PASSED -- METHOD BROKEN; no result counts

| arm | prediction | observation | verdict |
|---|---|---|---|
| control | unpatched resolver, B manifest, python + claude-plugin -> 'any' IN languages (the leak; predicted FAIL) | `languages=['python']` | MISSED |
| B0 | candidate B changes at most 10 lines of layers.py | `+7 -1` | held |
| B1a | python + claude-plugin -> languages ['python']; names [python, python/claude-plugin, any/claude-plugin]; preset python/claude-plugin recognised | `languages=['python'] names=['python', 'python/claude-plugin', 'any/claude-plugin'] archetype=python/claude-plugin notes=[]` | held |
| B1b | js-ts + claude-plugin -> languages ['js-ts']; names [js-ts, js-ts/node, js-ts/claude-plugin, any/claude-plugin]; preset js-ts/claude-plugin recognised | `languages=['js-ts'] names=['js-ts', 'js-ts/node', 'js-ts/claude-plugin', 'any/claude-plugin'] archetype=js-ts/claude-plugin` | held |
| B1c | --language any is refused; python,js-ts + bare claude-plugin is refused as ambiguous (known limit) | `'any' holds language-neutral layers; it is not a project language | 'claude-plugin' is ambiguous: any/claude-plugin or js-ts/claude-plugin or python/claude-plugin` | held |
| B1d | list python shows claude-plugin under purpose; the catalogue has no 'any:' section; known_languages omits any | `python purpose line=['  purpose    one of: claude-plugin'] any-section=[] known=['generic', 'js-ts', 'python']` | held |
| B2 | assembly for python writes exactly the 3 neutral + 3 python files; no neutral path exists in more than one layer folder | `written=['.claude-plugin/marketplace.json', 'VERSION', 'plugin/.claude-plugin/plugin.json', 'plugin/README.md', 'plugin/hooks/hooks.json', 'plugin/hooks/scripts/run-hook.mjs', 'plugin/hooks/scripts/session_start.py'] duplicated_neutral=[]` | MISSED |
| C | measured, not predicted: the number of sites where the key prefix means the language (what candidate C would have to change) | `11 split('/') sites in layers.py (key prefix read as the language); candidate A duplicates 3 neutral files` | held |
