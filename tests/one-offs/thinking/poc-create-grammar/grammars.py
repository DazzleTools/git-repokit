"""Four candidate grammars for `repokit create`, as mock parsers over one
catalogue. Each takes the argv after `repokit create <name>` and returns either
the ordered, qualified layer list it would hand the engine, or an error string.

  A  compound archetype names: --archetype <lang>/<leaf>; one leaf per shape,
     so every combination somebody wants is a leaf (the create-vite move)
  B  flat tag catalogue: --type <name>; names are global and flat, grouped by
     tags for `repokit list --tag web`; combinations are leaves as in A
  C  stacked layers: --kind a,b,c; raw layer names in the user's order; no
     presets, no implies, no exclusivity check (the engine just stacks)
  D  the hybrid djdarcy's two messages describe: --archetype takes a list;
     a token is a preset (lang/name), a qualified layer (lang/layer) or a bare
     layer; the tool implies parents, orders by facet, refuses exclusive
     collisions, and recognises a list that equals a preset

All four share --language (list, as shipped) and the typo suggestion, so the
comparison is the grammar alone.
"""

from __future__ import annotations

import difflib
from typing import Dict, List, Optional, Tuple

import catalogue as C
from catalogue import BY_QUALIFIED, DEFAULT_PRESET, FACETS, LAYERS, PRESETS, by_bare, expand_preset, order_and_imply

Result = Tuple[Optional[List[str]], Optional[str], Dict[str, str]]  # layers, error, notes


def _flag(argv: List[str], name: str) -> List[str]:
    """Collect the values of --name (repeated or comma lists)."""
    out: List[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == name and i + 1 < len(argv):
            out += [p.strip() for p in argv[i + 1].split(",") if p.strip()]
            i += 2
        elif argv[i].startswith(name + "="):
            out += [p.strip() for p in argv[i].split("=", 1)[1].split(",") if p.strip()]
            i += 1
        else:
            i += 1
    return out


def _suggest(bad: str, choices: List[str]) -> str:
    close = difflib.get_close_matches(bad, choices, n=3, cutoff=0.6)
    return f"unknown '{bad}'" + (f"; did you mean {', '.join(close)}?" if close else "")


def _languages_or_default(argv: List[str]) -> Tuple[List[str], Optional[str]]:
    langs = _flag(argv, "--language")
    for l in langs:
        if l not in BY_QUALIFIED or BY_QUALIFIED[l].facet != "language":
            return [], _suggest(l, [l.name for l in LAYERS if l.facet == "language"])
    return langs, None


# ---------------------------------------------------------------- A: compound

def leaves_A() -> Dict[str, List[str]]:
    """A needs a leaf per shape. Presets are leaves, and so is every verified
    combination; the matrix's C/C++ lib with Qt needs 'c-cpp/cmake-lib-qt',
    which no preset provides, so A's catalogue grows a leaf for it. We count the
    catalogue as: presets + one leaf per (exclusive build x additive framework)
    pair per language, which is what 'every combination is a leaf' costs."""
    leaves = dict(PRESETS)
    for lang in ("python", "c-cpp", "js-ts"):
        builds = [l for l in LAYERS if l.language == lang and l.facet == "build"]
        frames = [l for l in LAYERS if l.language == lang and l.facet == "framework"]
        for b in builds:
            for f in frames:
                leaves.setdefault(f"{lang}/{b.name}-{f.name}", [b.name, f.name])
    return leaves


def parse_A(argv: List[str]) -> Result:
    langs, err = _languages_or_default(argv)
    if err:
        return None, err, {}
    arche = _flag(argv, "--archetype")
    leaves = leaves_A()
    if len(arche) > 1:
        return None, "--archetype takes one name (A has no composition)", {}
    if not arche:
        if not langs:
            return [], None, {"note": "generic"}
        return order_and_imply([BY_QUALIFIED[l] for l in langs]) if len(langs) > 1 else expand_preset(DEFAULT_PRESET[langs[0]]), None, {}
    key = arche[0]
    if key not in leaves:
        return None, _suggest(key, list(leaves)), {}
    lang = key.split("/")[0]
    layers = [BY_QUALIFIED[f"{lang}/{n}"] for n in leaves[key]]
    return order_and_imply(layers + [BY_QUALIFIED[l] for l in langs]), None, {}


def list_A() -> List[str]:
    return [f"{k:28} {' + '.join(v)}" for k, v in sorted(leaves_A().items())]


# ---------------------------------------------------------------- B: flat tags

def leaves_B() -> Dict[str, Tuple[str, List[str]]]:
    """Flat global names: the language is a tag, not a prefix, so colliding
    bare names must be renamed (qt -> qt-cpp, qt-py). Same leaf population as A."""
    out: Dict[str, Tuple[str, List[str]]] = {}
    for key, names in leaves_A().items():
        lang, leaf = key.split("/", 1)
        flat = leaf if sum(1 for k in leaves_A() if k.split("/", 1)[1] == leaf) == 1 else f"{leaf}-{ {'python': 'py', 'c-cpp': 'cpp', 'js-ts': 'js'}[lang] }"
        out[flat] = (lang, names)
    return out


def parse_B(argv: List[str]) -> Result:
    langs, err = _languages_or_default(argv)
    if err:
        return None, err, {}
    types = _flag(argv, "--type")
    leaves = leaves_B()
    if len(types) > 1:
        return None, "--type takes one name (B has no composition)", {}
    if not types:
        if not langs:
            return [], None, {"note": "generic"}
        return order_and_imply([BY_QUALIFIED[l] for l in langs]) if len(langs) > 1 else expand_preset(DEFAULT_PRESET[langs[0]]), None, {}
    if types[0] not in leaves:
        return None, _suggest(types[0], list(leaves)), {}
    lang, names = leaves[types[0]]
    return order_and_imply([BY_QUALIFIED[f"{lang}/{n}"] for n in names] + [BY_QUALIFIED[l] for l in langs]), None, {}


def list_B(tag: Optional[str] = None) -> List[str]:
    rows = []
    for flat, (lang, names) in sorted(leaves_B().items()):
        tags = {lang} | {BY_QUALIFIED[f"{lang}/{n}"].facet for n in names}
        if tag and tag not in tags:
            continue
        rows.append(f"{flat:24} [{', '.join(sorted(tags))}]")
    return rows


# ---------------------------------------------------------------- C: stacked

def parse_C(argv: List[str]) -> Result:
    langs, err = _languages_or_default(argv)
    if err:
        return None, err, {}
    kinds = _flag(argv, "--kind")
    if not kinds:
        if not langs:
            return [], None, {"note": "generic"}
        return [BY_QUALIFIED[l].qualified for l in langs], None, {"note": "language layer only; C has no default archetype"}
    out: List[str] = [l for l in langs]
    for k in kinds:
        if "/" in k:
            if k not in BY_QUALIFIED:
                return None, _suggest(k, list(BY_QUALIFIED)), {}
            out.append(k)
            continue
        hits = by_bare(k)
        if not hits:
            return None, _suggest(k, sorted({l.name for l in LAYERS})), {}
        if len(hits) > 1:
            return None, f"'{k}' is ambiguous: {', '.join(h.qualified for h in hits)}", {}
        out.append(hits[0].qualified)
    # C stacks in the user's order; the language must be listed by the user
    has_lang = any(BY_QUALIFIED[q].facet == "language" for q in out)
    notes = {} if has_lang else {"warning": "no language layer listed; the stack has no language"}
    return out, None, notes


def list_C() -> List[str]:
    return [f"{l.qualified:26} {l.facet:9} {l.description}" for l in sorted(LAYERS, key=lambda l: (l.language, l.rank, l.name))]


# ---------------------------------------------------------------- D: hybrid

def parse_D(argv: List[str]) -> Result:
    langs, err = _languages_or_default(argv)
    if err:
        return None, err, {}
    tokens = _flag(argv, "--archetype")
    if not tokens:
        if not langs:
            return [], None, {"note": "generic"}
        return order_and_imply([BY_QUALIFIED[l] for l in langs]) if len(langs) > 1 else expand_preset(DEFAULT_PRESET[langs[0]]), None, {}
    layers: List[C.Layer] = [BY_QUALIFIED[l] for l in langs]
    presets_used: List[str] = []
    for t in tokens:
        if t in PRESETS:
            presets_used.append(t)
            lang = t.split("/")[0]
            layers += [BY_QUALIFIED[f"{lang}/{n}"] for n in PRESETS[t]]
            continue
        if "/" in t:
            if t not in BY_QUALIFIED:
                return None, _suggest(t, sorted(set(PRESETS) | set(BY_QUALIFIED))), {}
            layers.append(BY_QUALIFIED[t])
            continue
        hits = by_bare(t)
        if not hits:
            return None, _suggest(t, sorted({l.name for l in LAYERS} | set(PRESETS))), {}
        if len(hits) > 1:
            # a listed/implied language can settle it
            known_langs = {l.language for l in layers} | {l.name for l in layers if l.facet == "language"}
            narrowed = [h for h in hits if h.language in known_langs]
            if len(narrowed) != 1:
                return None, f"'{t}' is ambiguous: {' or '.join(h.qualified for h in hits)}", {}
            hits = narrowed
        layers.append(hits[0])
    try:
        ordered = order_and_imply(layers)
    except ValueError as e:
        return None, str(e), {}
    notes: Dict[str, str] = {}
    # recognise a preset
    match = [k for k in PRESETS if expand_preset(k) == ordered]
    if match:
        notes["preset"] = match[0] + (" (named)" if match[0] in presets_used else " (recognised from the list)")
    else:
        notes["note"] = "assembled, not a verified preset"
    return ordered, None, notes


def list_D(language: Optional[str] = None) -> List[str]:
    rows = []
    for lang in ("python", "c-cpp", "js-ts"):
        if language and lang != language:
            continue
        rows.append(f"{lang}:")
        for k in sorted(PRESETS):
            if k.startswith(lang + "/"):
                rows.append(f"  {k:26} = {', '.join(PRESETS[k])}")
        for facet in ("runtime", "dialect", "build", "framework", "purpose"):
            names = [l.name for l in LAYERS if l.language == lang and l.facet == facet]
            if names:
                rows.append(f"  {facet:10} {'one of' if FACETS[facet][1] else 'any of'}: {', '.join(names)}")
    return rows


GRAMMARS = {"A": parse_A, "B": parse_B, "C": parse_C, "D": parse_D}
LISTINGS = {"A": list_A, "B": list_B, "C": list_C, "D": list_D}
