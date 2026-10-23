"""Candidate B as a patch: a pseudo-language ("any") holds language-neutral
layers that per-language layers imply. Builds layers_b.py from the production
repokit/layers.py by exact string replacement, so the whole change is visible
here and its size is measured, and production is never touched.

The first edit only makes the copy importable standalone; it is not part of
the candidate and is excluded from the count.
"""
import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SRC = REPO / "repokit" / "layers.py"
OUT = HERE / "layers_b.py"

IMPORT_EDIT = ("from .template_engine import TemplateEngine, RK_TOKEN",
               "from repokit.template_engine import TemplateEngine, RK_TOKEN")

EDITS = [
    # known_languages hides a pseudo-language (so --language's choices never show it)
    ('    return [GENERIC] + sorted(manifest["languages"])',
     '    return [GENERIC] + sorted(k for k, v in manifest["languages"].items() if not v.get("pseudo"))'),
    # a pseudo-language named explicitly is refused
    ('    for name in langs:\n        _check_language(manifest, name)\n    res = Resolution(',
     '    for name in langs:\n        _check_language(manifest, name)\n'
     '        if table[name].get("pseudo"):\n'
     '            raise LayerError(f"{name!r} holds language-neutral layers; it is not a project language")\n'
     '    res = Resolution('),
    # a pseudo-language implied by a layer is never a project language
    ('            _check_language(manifest, name)\n            langs.append(name)',
     '            _check_language(manifest, name)\n'
     '            if table[name].get("pseudo"):\n'
     '                return\n'
     '            langs.append(name)'),
    # a bare name never resolves to the pseudo-language's layer, and the
    # ambiguity message never lists it (round 2: round 1 showed it listed)
    ('        lang, name = key.split("/", 1)\n        if name == tok:\n            by_lang.setdefault(lang, key)',
     '        lang, name = key.split("/", 1)\n'
     '        if name == tok and not manifest["languages"].get(lang, {}).get("pseudo"):\n'
     '            by_lang.setdefault(lang, key)'),
    # the catalogue (repokit list) hides it
    ('        entry = table[lang]\n        head =',
     '        entry = table[lang]\n        if entry.get("pseudo"):\n            continue\n        head ='),
]


def build():
    """Write layers_b.py; return (added, removed) lines of the candidate's change."""
    original = SRC.read_text(encoding="utf-8")
    text = original
    for old, new in [IMPORT_EDIT] + EDITS:
        assert text.count(old) == 1, f"anchor not unique or missing: {old[:60]!r}"
        text = text.replace(old, new)
    OUT.write_text(text, encoding="utf-8")
    # count the candidate alone: diff production against the text with only the import edit
    base = original.replace(*IMPORT_EDIT)
    changed = [l for l in difflib.unified_diff(base.splitlines(), text.splitlines(), lineterm="", n=0)
               if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return sum(l.startswith("+") for l in changed), sum(l.startswith("-") for l in changed)


if __name__ == "__main__":
    print("candidate B: +%d -%d lines" % build())
