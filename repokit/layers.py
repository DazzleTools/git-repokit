"""Code-type template layers: the second of git-repokit's two template systems.

The structure system (repo_manager._generate_template_files) writes the files
every project gets, from *.template files with $var placeholders. This module
lays the code type on top: a manifest-driven walk over layer folders under
repokit/templates/layers/ -- a language's layer, then an archetype's -- where
a later file replaces an earlier one, a file named <name>.rkappend is appended
to <name> (including a file the structure system already wrote), __RK_NAME__
tokens are replaced in file names and text contents, and workflow files are
copied byte for byte (a token inside one is an error, because GitHub Actions'
own ${{ }} lives there). Both systems render through one TemplateEngine and
one context (template_engine.token_context), so a project has one set of names.

Ported from the proof in git-repokit-common,
tests/one-offs/thinking/poc-templates-c-cpp/assemble.py (8/8 arms on
2026-10-07); design: the Phase 2 v2 analysis of 2026-10-09 in the vault.

The manifest (repokit/templates/layers/manifest.toml):

    [languages.python]
    layers = ["languages/python"]
    default = "python/setuppy"          # the archetype a bare --language gets

    [languages.javascript]
    stub = true                         # named, announced, not built yet
    description = "planned as the js-ts layer"

    [archetypes."python/setuppy"]
    languages = ["python"]              # implied when --archetype names it
    layers = ["archetypes/python/setuppy"]
    description = "setup.py and requirements.txt (git-repokit's output before 0.7)"
"""

import difflib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .template_engine import TemplateEngine, RK_TOKEN

MANIFEST = "manifest.toml"
APPEND = ".rkappend"
WORKFLOWS = ".github/workflows/"
GENERIC = "generic"          # no code-type layers at all
LAYERS_DIR = "layers"        # under the templates directory
ARCHETYPES_DIR = "archetypes"
NOT_A_PRESET = "assembled from layers; not a tested preset"
UNRANKED = 99                # a layer folder with no [layers] entry sorts last, in the order given


class LayerError(Exception):
    """A language or archetype that cannot be assembled: unknown, a stub, or a
    broken layer tree. The message is for the person; create stops before
    `git init` when it is raised."""


@dataclass
class Resolution:
    layers: List[str] = field(default_factory=list)       # layer folders in apply order
    languages: List[str] = field(default_factory=list)
    archetype: Optional[str] = None                       # the preset the request equals, or None
    tokens: List[str] = field(default_factory=list)       # what --with asked for, as given
    names: List[str] = field(default_factory=list)        # qualified layer names in apply order
    notes: List[str] = field(default_factory=list)        # e.g. NOT_A_PRESET


def _load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            raise LayerError(f"{path} needs a TOML parser: Python 3.11+ or the tomli package") from None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise LayerError(f"cannot read {path}: {e}") from None


def layers_root(engine: Optional[TemplateEngine] = None) -> Optional[Path]:
    """The layers folder of the templates directory the engine found, or None."""
    engine = engine or TemplateEngine()
    if not engine.templates_dir:
        return None
    root = Path(engine.templates_dir) / LAYERS_DIR
    return root if (root / MANIFEST).is_file() else None


def load_manifest(root: Path) -> Dict[str, Any]:
    data = _load_toml(root / MANIFEST)
    data.setdefault("languages", {})
    data.setdefault("archetypes", {})
    data.setdefault("layers", {})
    data.setdefault("facets", {})
    return data


def known_languages(manifest: Dict[str, Any]) -> List[str]:
    """Every language the manifest names (stubs included), plus generic."""
    return [GENERIC] + sorted(manifest["languages"])


def known_archetypes(manifest: Dict[str, Any]) -> List[str]:
    """The presets: what --with <lang>/<name> expands to."""
    return sorted(manifest["archetypes"])


def known_layers(manifest: Dict[str, Any]) -> List[str]:
    """Every [layers] entry, qualified (stubs included)."""
    return sorted(manifest["layers"])


def layer_folder(manifest: Dict[str, Any], key: str) -> str:
    """The folder a [layers] entry stands for: archetypes/<lang>/<name>, by convention."""
    return f"{ARCHETYPES_DIR}/{key}"


def facet_rank(manifest: Dict[str, Any], facet: Optional[str]) -> int:
    f = manifest["facets"].get(facet or "", {})
    return f.get("rank", UNRANKED)


def facet_exclusive(manifest: Dict[str, Any], facet: Optional[str]) -> bool:
    return bool(manifest["facets"].get(facet or "", {}).get("exclusive", False))


def parse_languages(value) -> List[str]:
    """A list, or a comma-separated string, or a list of either -> names in
    the order given, without repeats or blanks."""
    items: List[str] = []
    for part in (value if isinstance(value, (list, tuple)) else [value or ""]):
        for name in str(part).split(","):
            name = name.strip()
            if name and name not in items:
                items.append(name)
    return items


def _suggest(token: str, choices: List[str]) -> str:
    close = difflib.get_close_matches(token, choices, n=3, cutoff=0.6)
    return f"; did you mean {', '.join(close)}?" if close else ""


def _check_language(manifest: Dict[str, Any], name: str) -> None:
    entry = manifest["languages"].get(name)
    if entry is None:
        raise LayerError(f"unknown language {name!r}; known: {', '.join(known_languages(manifest))}")
    if entry.get("stub"):
        raise LayerError(f"language {name} is not built yet: {entry.get('description', '')}".rstrip(": "))


def _preset_layers(manifest: Dict[str, Any], key: str) -> List[Tuple[str, Optional[str]]]:
    """A preset's (folder, qualified layer name or None) pairs, after the stub check."""
    preset = manifest["archetypes"][key]
    if preset.get("stub"):
        raise LayerError(f"archetype {key} is not built yet: {preset.get('description', '')}".rstrip(": "))
    out = []
    for folder in preset.get("layers", []):
        name = folder[len(ARCHETYPES_DIR) + 1:] if folder.startswith(ARCHETYPES_DIR + "/") else None
        out.append((folder, name if name in manifest["layers"] else None))
    return out


def _layer(manifest: Dict[str, Any], key: str) -> Tuple[str, str]:
    entry = manifest["layers"][key]
    if entry.get("stub"):
        raise LayerError(f"layer {key} is not built yet: {entry.get('description', '')}".rstrip(": "))
    return layer_folder(manifest, key), key


def resolve(manifest: Dict[str, Any], languages, with_tokens=None, _recognise: bool = True) -> Resolution:
    """The ordered layers for these languages and these --with tokens.

    The eight rules (Phase 3 design, D2): tokens are split on commas and
    lower-cased; a preset (an [archetypes] key) expands to its layers; a bare
    name is looked up across layers and presets, narrowed by the languages
    listed or already implied, and refused with every qualified form when it
    stays ambiguous; every layer implies its language and whatever its entry
    `implies`, transitively; two layers in one exclusive facet of one language
    are refused naming the pair and the facet; layers are ordered by facet
    rank, then by the order given, after the languages' own layers; a list
    that equals a preset's expansion is reported as that preset, any other
    list carries the NOT_A_PRESET note; with no tokens the FIRST language's
    default preset applies (the first language is the project's primary one);
    stubs refuse with their description; an unknown name suggests close ones.
    generic means no layers.
    """
    table = manifest["languages"]
    presets = manifest["archetypes"]
    layer_table = manifest["layers"]
    langs = [name for name in parse_languages(languages) if name != GENERIC]
    tokens: List[str] = []
    for t in parse_languages(with_tokens):
        if t.lower() not in tokens:
            tokens.append(t.lower())
    for name in langs:
        _check_language(manifest, name)
    res = Resolution(languages=langs, tokens=list(tokens))

    chosen: List[Tuple[str, Optional[str]]] = []      # (folder, qualified name or None), in the order given
    presets_used: List[str] = []

    def add_language(name: str) -> None:
        if name not in langs:
            _check_language(manifest, name)
            langs.append(name)

    def add_preset(key: str) -> None:
        presets_used.append(key)
        for lang_name in presets[key].get("languages", []) or [key.split("/")[0]]:
            add_language(lang_name)
        for pair in _preset_layers(manifest, key):
            if pair not in chosen:
                chosen.append(pair)

    def add_layer(key: str) -> None:
        pair = _layer(manifest, key)
        add_language(key.split("/")[0])
        if pair not in chosen:
            chosen.append(pair)

    # Pass 1: presets and qualified names; bare names that are unique anywhere.
    # Pass 2: the bare names left, narrowed by the languages now known.
    deferred: List[str] = []
    for tok in tokens:
        if tok in presets:
            add_preset(tok)
        elif "/" in tok:
            if tok in layer_table:
                add_layer(tok)
            else:
                known = sorted(set(presets) | set(layer_table))
                raise LayerError(f"unknown archetype {tok!r}; known: {', '.join(known) or 'none'}{_suggest(tok, known)}")
        else:
            deferred.append(tok)
    for tok in deferred:
        candidates = _bare_candidates(manifest, tok)
        if not candidates:
            bare = sorted({k.split('/', 1)[1] for k in list(presets) + list(layer_table) if '/' in k})
            raise LayerError(f"unknown name {tok!r}; known: {', '.join(bare) or 'none'}{_suggest(tok, bare + sorted(set(presets) | set(layer_table)))}")
        if len(candidates) > 1:
            narrowed = [c for c in candidates if c.split("/")[0] in langs]
            if len(narrowed) == 1:
                candidates = narrowed
            else:
                raise LayerError(f"{tok!r} is ambiguous: {' or '.join(candidates)}")
        key = candidates[0]
        if key in presets:
            add_preset(key)
        else:
            add_layer(key)

    # Rule 4: imply, transitively (a layer implies its language; its entry may imply more).
    i = 0
    while i < len(chosen):
        folder, name = chosen[i]
        if name:
            lang_name = name.split("/")[0]
            for imp in layer_table[name].get("implies", []):
                target = imp if "/" in imp else f"{lang_name}/{imp}"
                if target in table:              # a language
                    add_language(target)
                elif target in layer_table:
                    pair = _layer(manifest, target)
                    if pair not in chosen:
                        chosen.append(pair)
                else:
                    raise LayerError(f"layer {name} implies {imp!r}, which the manifest does not define")
        i += 1

    # Rule 5: exclusivity, per language and facet.
    seen: Dict[Tuple[str, str], str] = {}
    for folder, name in chosen:
        if not name:
            continue
        facet = layer_table[name].get("facet")
        if facet and facet_exclusive(manifest, facet):
            slot = (name.split("/")[0], facet)
            other = seen.get(slot)
            if other and other != name:
                a, b = other.split("/", 1)[1], name.split("/", 1)[1]
                raise LayerError(f"'{a}' and '{b}' are both a {facet} for {slot[0]}; pick one")
            seen[slot] = name

    # Rule 7 (default) when nothing was asked.
    if not tokens:
        for name in langs[:1]:   # the primary language's default only
            default = table[name].get("default")
            if default:
                entry = presets.get(default)
                if entry is None or entry.get("stub"):
                    raise LayerError(f"language {name} names default archetype {default!r}, which is {'unknown' if entry is None else 'a stub'}")
                add_preset(default)
                res.archetype = default

    # Rule 6: order -- the languages' own layers first (in the order given), then by facet rank, then as given.
    order: List[Tuple[str, Optional[str]]] = []
    for name in langs:
        for folder in table[name].get("layers", []):
            order.append((folder, name))
    ranked = sorted(enumerate(chosen), key=lambda ic: (facet_rank(manifest, layer_table.get(ic[1][1] or "", {}).get("facet")), ic[0]))
    order += [pair for _, pair in ranked]
    for folder, name in order:
        if folder not in res.layers:
            res.layers.append(folder)
            res.names.append(name or folder)
    res.languages = langs

    # Rule 8: recognise a preset -- the WHOLE request must equal the preset's
    # expansion, languages included (`--language python --with minimal` is a
    # two-language composition no preset vouches for, even though `minimal`
    # alone is one).
    if tokens and _recognise:
        for key in presets_used + [k for k in presets if k not in presets_used]:
            if presets[key].get("stub"):
                continue
            try:
                expansion = resolve(manifest, [], [key], _recognise=False).layers
            except LayerError:
                continue
            if expansion == res.layers:
                res.archetype = key
                break
        if res.archetype is None:
            res.notes.append(NOT_A_PRESET)
    return res


def catalogue_lines(manifest: Dict[str, Any], language: Optional[str] = None) -> List[str]:
    """`repokit list [LANG]`: per language, the presets (name = layers; planned
    ones marked), then each facet with its choices and one-of / any-of."""
    table = manifest["languages"]
    if language and language not in table:
        raise LayerError(f"unknown language {language!r}; known: {', '.join(known_languages(manifest))}")
    facets = sorted(manifest["facets"].items(), key=lambda kv: kv[1].get("rank", UNRANKED))
    lines: List[str] = []
    for lang in sorted(table):
        if language and lang != language:
            continue
        entry = table[lang]
        head = f"{lang}:" + (f"  (planned: {entry.get('description', '')})" if entry.get("stub") else "")
        lines.append(head)
        default = entry.get("default")
        for key in sorted(k for k in manifest["archetypes"] if k.startswith(lang + "/")):
            preset = manifest["archetypes"][key]
            if preset.get("stub"):
                lines.append(f"  {key:28} (planned: {preset.get('description', '')})")
            else:
                parts = [f.split("/", 2)[-1] for f in preset.get("layers", [])]
                mark = "  <- default" if key == default else ""
                lines.append(f"  {key:28} = {', '.join(parts)}{mark}")
        for facet, spec in facets:
            if facet == "language":
                continue
            names = []
            for key, l_entry in manifest["layers"].items():
                if key.startswith(lang + "/") and l_entry.get("facet") == facet:
                    names.append(key.split("/", 1)[1] + (" (planned)" if l_entry.get("stub") else ""))
            if names:
                pick = "one of" if spec.get("exclusive") else "any of"
                lines.append(f"  {facet:10} {pick}: {', '.join(sorted(names))}")
    return lines


def _bare_candidates(manifest: Dict[str, Any], tok: str) -> List[str]:
    """Qualified keys whose bare name is tok: one per language, a preset
    preferred over a layer of the same name (the preset is the tested one)."""
    by_lang: Dict[str, str] = {}
    for key in manifest["layers"]:
        lang, name = key.split("/", 1)
        if name == tok:
            by_lang.setdefault(lang, key)
    for key in manifest["archetypes"]:
        lang, name = key.split("/", 1)
        if name == tok:
            by_lang[lang] = key
    return [by_lang[l] for l in sorted(by_lang)]


def _is_text(data: bytes) -> bool:
    return b"\0" not in data[:8192]


def assemble(root: Path, layers: List[str], dest: str, context: Dict[str, Any],
             engine: Optional[TemplateEngine] = None, preserve_existing: bool = False,
             logger=None) -> List[str]:
    """Lay the layers down under ``dest``. Returns the files written or appended,
    as dest-relative POSIX paths. ``context`` is token_context(...)."""
    engine = engine or TemplateEngine()
    files: Dict[str, bytes] = {}        # template-relative path (tokens unresolved) -> content
    appends: Dict[str, bytes] = {}      # appends whose target no layer provides: a file already on disk

    for layer in layers:
        base = root / layer
        if not base.is_dir():
            raise LayerError(f"layer folder missing: {layer} (under {root})")
        for src in sorted(p for p in base.rglob("*") if p.is_file()):
            # Bytecode beside the template sources (a syntax check compiled
            # them) is not part of any layer, and carries the tokens inside.
            if "__pycache__" in src.parts or src.suffix in (".pyc", ".pyo"):
                continue
            rel = src.relative_to(base).as_posix()
            data = src.read_bytes()
            if rel.endswith(APPEND):
                target = rel[: -len(APPEND)]
                if target in files:
                    files[target] = _joined(files[target], data)
                else:
                    appends[target] = _joined(appends.get(target, b""), data) if target in appends else data
            else:
                files[rel] = data   # a later layer's file replaces an earlier one

    def out_path(rel: str) -> str:
        resolved = engine.render_bytes(rel.encode("utf-8"), context, dollar=False).decode("utf-8")
        if ".." in Path(resolved).parts:
            raise LayerError(f"a layer path escapes the project: {rel}")
        return resolved

    written: List[str] = []
    for rel, data in files.items():
        is_workflow = rel.startswith(WORKFLOWS)
        if is_workflow and RK_TOKEN.search(data.decode("latin-1")):
            raise LayerError(f"token in workflow file {rel}: workflow files must stay placeholder-free")
        target = out_path(rel)
        full = os.path.join(dest, target)
        if preserve_existing and os.path.exists(full):
            if logger:
                logger.info(f"Preserving existing file: {target}")
            continue
        if not is_workflow and _is_text(data):
            data = engine.render_bytes(data, context, dollar=False)
        os.makedirs(os.path.dirname(full) or dest, exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        written.append(target)

    for rel, data in appends.items():
        target = out_path(rel)
        full = os.path.join(dest, target)
        if preserve_existing and os.path.exists(full):
            if logger:
                logger.info(f"Preserving existing file, not appending: {target}")
            continue
        data = engine.render_bytes(data, context, dollar=False) if _is_text(data) else data
        os.makedirs(os.path.dirname(full) or dest, exist_ok=True)
        existing = open(full, "rb").read() if os.path.exists(full) else b""
        with open(full, "wb") as f:
            f.write(_joined(existing, data))
        written.append(target)
    return written


def _joined(head: bytes, tail: bytes) -> bytes:
    """head + tail, with a newline between when head has none at its end."""
    if head and not head.endswith((b"\n", b"\r\n")):
        head += b"\n"
    return head + tail
