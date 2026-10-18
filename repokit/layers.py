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

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .template_engine import TemplateEngine, RK_TOKEN

MANIFEST = "manifest.toml"
APPEND = ".rkappend"
WORKFLOWS = ".github/workflows/"
GENERIC = "generic"          # no code-type layers at all
LAYERS_DIR = "layers"        # under the templates directory


class LayerError(Exception):
    """A language or archetype that cannot be assembled: unknown, a stub, or a
    broken layer tree. The message is for the person; create stops before
    `git init` when it is raised."""


@dataclass
class Resolution:
    layers: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    archetype: Optional[str] = None


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
    return data


def known_languages(manifest: Dict[str, Any]) -> List[str]:
    """Every language the manifest names (stubs included), plus generic."""
    return [GENERIC] + sorted(manifest["languages"])


def known_archetypes(manifest: Dict[str, Any]) -> List[str]:
    return sorted(manifest["archetypes"])


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


def resolve(manifest: Dict[str, Any], languages, archetype: Optional[str] = None) -> Resolution:
    """The ordered layers for these languages and this archetype.

    Each language's layers in the order given, then the archetype's; an
    archetype implies its languages; without one, the FIRST language's default
    archetype (when it names one) is used -- the first language is the
    project's primary one, and two archetypes would both claim the project's
    settings file and build files. generic means no layers. Unknown names and
    stubs raise LayerError naming what is known.
    """
    langs = [name for name in parse_languages(languages) if name != GENERIC]
    table = manifest["languages"]
    arches = manifest["archetypes"]

    arch_entry = None
    if archetype:
        arch_entry = arches.get(archetype)
        if arch_entry is None:
            raise LayerError(f"unknown archetype {archetype!r}; known: {', '.join(known_archetypes(manifest)) or 'none'}")
        if arch_entry.get("stub"):
            raise LayerError(f"archetype {archetype} is not built yet: {arch_entry.get('description', '')}".rstrip(": "))
        for name in arch_entry.get("languages", []):
            if name not in langs:
                langs.append(name)

    for name in langs:
        entry = table.get(name)
        if entry is None:
            raise LayerError(f"unknown language {name!r}; known: {', '.join(known_languages(manifest))}")
        if entry.get("stub"):
            raise LayerError(f"language {name} is not built yet: {entry.get('description', '')}".rstrip(": "))

    res = Resolution(languages=langs, archetype=archetype)
    order: List[str] = []
    for name in langs:
        order += table[name].get("layers", [])
    if arch_entry is None:
        for name in langs[:1]:   # the primary language's default only
            default = table[name].get("default")
            if default:
                entry = arches.get(default)
                if entry is None or entry.get("stub"):
                    raise LayerError(f"language {name} names default archetype {default!r}, which is {'unknown' if entry is None else 'a stub'}")
                order += entry.get("layers", [])
                res.archetype = default
    else:
        order += arch_entry.get("layers", [])
    for layer in order:
        if layer not in res.layers:
            res.layers.append(layer)
    return res


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
