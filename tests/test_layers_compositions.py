"""Every valid composition of the shipped layers dry-assembles (AC-9).

Presets are the tested surface; a composition the person types is assembled
by the rules and never built as a whole. This is the cheap check that keeps
compositions honest: per non-stub language, every combination of one choice
(or none) per exclusive facet times every subset of the additive facets, over
the built layers only, laid down with layers.assemble() into a temp dir -- no
git, no build. A combination fails when two layers write the same path
without an `.rkappend` and without the later layer declaring the path under
`overrides` in its [layers] entry, when a __RK_ token survives in a name or a
text file, or when an `implies` names a layer the manifest does not define.

Design: 2026-10-19__22-11-27__dev-workflow-process__family-type-system-facets-and-grammar.md (D4).
"""

import itertools
from pathlib import Path

import pytest

from repokit import layers
from repokit.template_engine import RK_TOKEN, TemplateEngine, token_context

ENGINE = TemplateEngine(verbose=0)
CTX = token_context({"project_name": "combo-tool", "description": "a composition",
                     "author": "Dustin", "author_email": "d@example.com",
                     "github": {"username": "acme"}}, archetype=None)


def _manifest():
    root = layers.layers_root(ENGINE)
    assert root is not None
    return root, layers.load_manifest(root)


def _built_layers_by_facet(m, lang):
    out = {}
    for key, entry in m["layers"].items():
        if key.startswith(lang + "/") and not entry.get("stub"):
            out.setdefault(entry["facet"], []).append(key)
    return out


def _implied(m, lang, key, seen=None):
    """Every layer `key` implies, transitively (bare names are in its language)."""
    seen = set() if seen is None else seen
    for name in m["layers"].get(key, {}).get("implies", []):
        q = name if "/" in name else f"{lang}/{name}"
        if q not in seen:
            seen.add(q)
            _implied(m, lang, q, seen)
    return seen


def _contradicts_an_implies(m, lang, chosen):
    """True when a chosen layer implies a different choice in an exclusive facet
    than the one chosen there -- paradox/ck3 implies jomini, so clausewitz + ck3
    is no composition at all (the resolver refuses it; test_paradox pins that)."""
    picked = {m["layers"][k]["facet"]: k for k in chosen
              if m["facets"].get(m["layers"][k].get("facet", ""), {}).get("exclusive")}
    for k in chosen:
        for q in _implied(m, lang, k):
            facet = m["layers"].get(q, {}).get("facet")
            if facet in picked and picked[facet] != q:
                return True
    return False


def combinations(m, lang):
    """Every valid token list for one language: one-or-none per exclusive facet,
    any subset of each additive facet, without the ones a layer's `implies`
    contradicts (a purpose that implies a different engine than the one chosen)."""
    by_facet = _built_layers_by_facet(m, lang)
    axes = []
    for facet, spec in sorted(m["facets"].items(), key=lambda kv: kv[1]["rank"]):
        if facet == "language" or facet not in by_facet:
            continue
        if spec["exclusive"]:
            axes.append([None] + by_facet[facet])
        else:
            names = by_facet[facet]
            axes.append([tuple(c) for r in range(len(names) + 1) for c in itertools.combinations(names, r)])
    for choice in itertools.product(*axes):
        tokens = []
        for c in choice:
            if c is None:
                continue
            tokens += list(c) if isinstance(c, tuple) else [c]
        if _contradicts_an_implies(m, lang, tokens):
            continue
        yield tokens


def _files_of(root, folder):
    base = root / folder
    return {p.relative_to(base).as_posix(): p for p in base.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}


def _check_one(root, m, lang, tokens, dest):
    r = layers.resolve(m, lang, tokens)
    owners = {}                      # rel path -> (folder, qualified name)
    problems = []
    for folder, name in zip(r.layers, r.names):
        entry = m["layers"].get(name, {})
        declared = set(entry.get("overrides", []))
        for rel in _files_of(root, folder):
            if rel.endswith(layers.APPEND):
                continue
            if rel in owners and owners[rel][0] != folder and rel not in declared:
                problems.append(f"{name} writes {rel}, already written by {owners[rel][1]}, with no .rkappend and no overrides entry")
            owners[rel] = (folder, name)
    layers.assemble(root, r.layers, str(dest), CTX, engine=ENGINE)
    for p in dest.rglob("*"):
        if RK_TOKEN.search(p.name):
            problems.append(f"token left in a path: {p.relative_to(dest).as_posix()}")
        elif p.is_file() and b"\0" not in p.read_bytes()[:8192] and not p.relative_to(dest).as_posix().startswith(".github/workflows/"):
            if RK_TOKEN.search(p.read_bytes().decode("latin-1")):
                problems.append(f"token left in {p.relative_to(dest).as_posix()}")
    return r, problems


def _languages():
    _, m = _manifest()
    # A pseudo-language (`any`) is never a project language; its layers are
    # reached through the languages that imply them.
    return [lang for lang, e in m["languages"].items() if not e.get("stub") and not e.get("pseudo")]


@pytest.mark.parametrize("lang", _languages())
def test_every_composition_of_the_shipped_layers_assembles_cleanly(lang, tmp_path):
    root, m = _manifest()
    tried = 0
    failures = []
    for tokens in combinations(m, lang):
        dest = tmp_path / f"{lang}-{tried}"
        dest.mkdir()
        try:
            _, problems = _check_one(root, m, lang, tokens, dest)
        except layers.LayerError as e:
            problems = [str(e)]
        if problems:
            failures.append((tokens, problems))
        tried += 1
    print(f"\n{lang}: {tried} combinations tried")
    assert tried >= 1
    assert not failures, "\n".join(f"{t}: {p}" for t, ps in failures for p in ps)


def test_every_implies_names_a_defined_layer():
    _, m = _manifest()
    for key, entry in m["layers"].items():
        lang = key.split("/")[0]
        for imp in entry.get("implies", []):
            target = imp if "/" in imp else f"{lang}/{imp}"
            assert target in m["layers"] or target in m["languages"], f"{key} implies {imp}"
