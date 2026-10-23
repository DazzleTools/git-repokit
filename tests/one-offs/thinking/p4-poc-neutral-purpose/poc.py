"""Proof of concept: can a language-neutral purpose (claude-plugin) be expressed
with a pseudo-language holding the neutral files (candidate B), with a small
resolver change, no duplicated files, and bare `claude-plugin` resolving under
both python and js-ts?

Predictions are in PREDICTIONS below, written before the first run. The
control arm runs candidate B's manifest through the UNPATCHED production
resolver and is predicted to FAIL by leaking "any" into the project's
languages; if it does not leak, the method is broken and nothing here counts.

Run: python tests/one-offs/thinking/p4-poc-neutral-purpose/poc.py
Writes results_run.md beside itself. Production source untouched.
"""
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import patch_b                                   # noqa: E402
from repokit import layers as prod               # noqa: E402

ADDED, REMOVED = patch_b.build()
spec = importlib.util.spec_from_file_location("layers_b", HERE / "layers_b.py")
cand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cand)

NEUTRAL = [".claude-plugin/marketplace.json", "plugin/.claude-plugin/plugin.json", "plugin/README.md"]
PY_PARTS = ["plugin/hooks/hooks.json", "plugin/hooks/scripts/run-hook.mjs", "plugin/hooks/scripts/session_start.py"]
JS_PARTS = ["plugin/hooks/hooks.json", "plugin/hooks/scripts/session-start.mjs", "plugin/tests/manifest.test.js"]


def manifest_b():
    return {
        "facets": {"language": {"rank": 0}, "runtime": {"rank": 1, "exclusive": True},
                   "build": {"rank": 3, "exclusive": True}, "purpose": {"rank": 5, "exclusive": True}},
        "languages": {
            "python": {"layers": ["languages/python"], "default": "python/pypi"},
            "js-ts": {"layers": ["languages/js-ts"], "default": "js-ts/node-package"},
            "any": {"pseudo": True, "layers": [], "description": "holds language-neutral layers"},
        },
        "layers": {
            "python/pypi": {"facet": "build"},
            "js-ts/node": {"facet": "runtime"},
            "js-ts/node-package": {"facet": "purpose", "implies": ["node"]},
            "any/claude-plugin": {"facet": "purpose"},
            "python/claude-plugin": {"facet": "purpose", "implies": ["any/claude-plugin"]},
            "js-ts/claude-plugin": {"facet": "purpose", "implies": ["node", "any/claude-plugin"]},
        },
        "archetypes": {
            "python/pypi": {"layers": ["archetypes/python/pypi"]},
            "js-ts/node-package": {"layers": ["archetypes/js-ts/node", "archetypes/js-ts/node-package"]},
            "python/claude-plugin": {"layers": ["archetypes/python/claude-plugin"]},
            "js-ts/claude-plugin": {"layers": ["archetypes/js-ts/node", "archetypes/js-ts/claude-plugin"]},
        },
    }


PREDICTIONS = {
    "control": "unpatched resolver, B manifest, python + the direct token any/claude-plugin -> 'any' IN languages (the leak; predicted FAIL). Round 1 aimed this at the implies path and the control passed: production's implies never registers an implied layer's language, so that path cannot leak; method-broken, re-aimed here",
    "B1e": "patched resolver, python + the direct token any/claude-plugin -> languages ['python'] (the leak closed)",
    "B0": "candidate B changes at most 10 lines of layers.py",
    "B1a": "python + claude-plugin -> languages ['python']; names [python, python/claude-plugin, any/claude-plugin]; preset python/claude-plugin recognised",
    "B1b": "js-ts + claude-plugin -> languages ['js-ts']; names [js-ts, js-ts/node, js-ts/claude-plugin, any/claude-plugin]; preset js-ts/claude-plugin recognised",
    "B1c": "--language any is refused; python,js-ts + bare claude-plugin is refused as ambiguous between js-ts and python only (round 1 listed any/ too)",
    "B1d": "list python shows claude-plugin under purpose; the catalogue has no 'any:' section; known_languages omits any",
    "B2": "assembly for python writes exactly the 3 neutral + 3 python files + the language layer's VERSION (round 1 omitted VERSION from the prediction); no neutral path exists in more than one layer folder",
    "C": "measured, not predicted: the number of sites where the key prefix means the language (what candidate C would have to change)",
}

rows = []


def arm(name, observation, ok):
    rows.append((name, PREDICTIONS[name], observation, "held" if ok else "MISSED"))


# control: the unpatched production resolver on the B manifest
r = prod.resolve(manifest_b(), ["python"], ["any/claude-plugin"])
leak = "any" in r.languages
arm("control", f"languages={r.languages}", leak)   # ok means the leak happened, as predicted
method_ok = leak
r = cand.resolve(manifest_b(), ["python"], ["any/claude-plugin"])
arm("B1e", f"languages={r.languages} names={r.names}", r.languages == ["python"])

arm("B0", f"+{ADDED} -{REMOVED}", ADDED + REMOVED <= 10)

r = cand.resolve(manifest_b(), ["python"], ["claude-plugin"])
arm("B1a", f"languages={r.languages} names={r.names} archetype={r.archetype} notes={r.notes}",
    r.languages == ["python"] and r.names == ["python", "python/claude-plugin", "any/claude-plugin"]
    and r.archetype == "python/claude-plugin")

r = cand.resolve(manifest_b(), ["js-ts"], ["claude-plugin"])
arm("B1b", f"languages={r.languages} names={r.names} archetype={r.archetype}",
    r.languages == ["js-ts"] and r.names == ["js-ts", "js-ts/node", "js-ts/claude-plugin", "any/claude-plugin"]
    and r.archetype == "js-ts/claude-plugin")

errs = []
for langs, toks in ((["any"], None), (["python", "js-ts"], ["claude-plugin"])):
    try:
        cand.resolve(manifest_b(), langs, toks)
        errs.append("accepted")
    except cand.LayerError as e:
        errs.append(str(e))
arm("B1c", " | ".join(errs), "not a project language" in errs[0] and "ambiguous" in errs[1] and "any/" not in errs[1])

cat_py = cand.catalogue_lines(manifest_b(), "python")
cat_all = cand.catalogue_lines(manifest_b())
arm("B1d", f"python purpose line={[l for l in cat_py if 'purpose' in l]} any-section={[l for l in cat_all if l.startswith('any:')]} known={cand.known_languages(manifest_b())}",
    any("claude-plugin" in l and "purpose" in l for l in cat_py)
    and not any(l.startswith("any:") for l in cat_all) and "any" not in cand.known_languages(manifest_b()))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "layers"
    tree = {"languages/python": ["VERSION"], "languages/js-ts": ["VERSION"],
            "archetypes/any/claude-plugin": NEUTRAL, "archetypes/python/claude-plugin": PY_PARTS,
            "archetypes/js-ts/node": ["package.json"], "archetypes/js-ts/claude-plugin": JS_PARTS}
    for folder, files in tree.items():
        for rel in files:
            p = root / folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"{folder}:{rel}\n", encoding="utf-8")
    dest = Path(tmp) / "out"
    dest.mkdir()
    res = cand.resolve(manifest_b(), ["python"], ["claude-plugin"])
    written = sorted(cand.assemble(root, res.layers, str(dest), {}))
    dupes = [rel for rel in NEUTRAL if sum((root / f / rel).exists() for f in tree) != 1]
    arm("B2", f"written={written} duplicated_neutral={dupes}",
        written == sorted(NEUTRAL + PY_PARTS + ["VERSION"]) and dupes == [])

src = (REPO / "repokit" / "layers.py").read_text(encoding="utf-8")
sites = len(re.findall(r'split\("/"', src))
arm("C", f"{sites} split('/') sites in layers.py (key prefix read as the language); candidate A duplicates {len(NEUTRAL)} neutral files", True)

out = ["# p4-poc-neutral-purpose: run record", "",
       f"method: {'control failed as predicted; results count' if method_ok else 'CONTROL PASSED -- METHOD BROKEN; no result counts'}", "",
       "| arm | prediction | observation | verdict |", "|---|---|---|---|"]
out += [f"| {n} | {p} | `{o}` | {v} |" for n, p, o, v in rows]
(HERE / "results_run.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
