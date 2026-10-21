"""The one catalogue every candidate grammar in this proof parses against.

It is a sketch of what the layers' manifest would hold once js-ts exists, drawn
from the shipped manifest (python, c-cpp and their archetypes), the roster's
five js-ts flavours (claude-plugin, node-package, obsidian-plugin,
browser-extension, comfyui-frontend) and the python/script floor. Nothing here
is a layer on disk; the proof measures how a request NAMES these, not what
they contain.

Each layer has a FACET (its category), a RANK (the order the engine applies
facets in), the LANGUAGE it belongs to, the layers it IMPLIES, and whether its
facet is EXCLUSIVE within one project (two build systems collide; two
frameworks may stack).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# facet -> (rank, exclusive)
# First run of the matrix (2026-10-18 07:3x) had ts and vite both as "build"
# and the web-vite-react preset collided with itself: TypeScript is a dialect
# of the language, not a build system, so it is its own facet.
FACETS: Dict[str, Tuple[int, bool]] = {
    "language":  (0, False),   # python,c-cpp stacks: --language python,c-cpp today
    "runtime":   (1, True),
    "dialect":   (2, True),    # ts; (later: py3.12-only, c++20)
    "build":     (3, True),    # packaging or bundler or build system
    "framework": (4, False),
    "purpose":   (5, True),
}


@dataclass(frozen=True)
class Layer:
    name: str
    facet: str
    language: str            # "" for a language itself
    implies: Tuple[str, ...] = ()
    description: str = ""

    @property
    def qualified(self) -> str:
        return self.name if not self.language else f"{self.language}/{self.name}"

    @property
    def rank(self) -> int:
        return FACETS[self.facet][0]


def _L(name, facet, language, implies=(), description=""):
    return Layer(name, facet, language, tuple(implies), description)


LAYERS: List[Layer] = [
    # languages (the first level, as shipped)
    _L("python", "language", "", (), "Python"),
    _L("c-cpp", "language", "", (), "C and C++"),
    _L("js-ts", "language", "", (), "JavaScript and TypeScript together"),
    # python
    _L("pypi", "build", "python", ("python",), "pyproject.toml, dynamic version, publish-on-release"),
    _L("setuppy", "build", "python", ("python",), "setup.py and requirements.txt"),
    _L("script", "purpose", "python", ("python",), "a local tool: one module, no packaging (the simple-projects floor)"),
    _L("django", "framework", "python", ("python",), "a Django project"),
    _L("qt", "framework", "python", ("python",), "PySide6 or PyQt app"),
    _L("comfyui", "purpose", "python", ("python",), "a ComfyUI custom-node package"),
    # c-cpp
    _L("cmake-app", "build", "c-cpp", ("c-cpp",), "CMake + presets + vcpkg + CTest (xormove's shape)"),
    _L("cmake-lib", "build", "c-cpp", ("c-cpp",), "library with install/export targets"),
    _L("msbuild", "build", "c-cpp", ("c-cpp",), "Visual Studio solution, Windows only"),
    _L("minimal", "build", "c-cpp", ("c-cpp",), "one source file, Makefile + build.bat"),
    _L("qt", "framework", "c-cpp", ("c-cpp",), "Qt 6: find_package(Qt6), windeployqt"),
    # js-ts
    _L("node", "runtime", "js-ts", ("js-ts",), "runs under Node: package.json engines, .nvmrc"),
    _L("browser", "runtime", "js-ts", ("js-ts",), "runs in a browser: index.html, bundler expected"),
    _L("ts", "dialect", "js-ts", ("js-ts",), "TypeScript: tsconfig, type-check in CI"),
    _L("vite", "build", "js-ts", ("js-ts", "browser"), "Vite bundler and dev server"),
    _L("react", "framework", "js-ts", ("js-ts",), "React"),
    _L("svelte", "framework", "js-ts", ("js-ts",), "Svelte"),
    _L("claude-plugin", "purpose", "js-ts", ("js-ts", "node"), "a Claude Code plugin: .claude-plugin/plugin.json, hooks, skills"),
    _L("node-package", "purpose", "js-ts", ("js-ts", "node"), "an npm package: exports map, publish-on-release"),
    _L("obsidian-plugin", "purpose", "js-ts", ("js-ts", "browser"), "an Obsidian plugin: manifest.json, esbuild"),
    _L("browser-extension", "purpose", "js-ts", ("js-ts", "browser"), "a WebExtension: manifest v3"),
    _L("comfyui-frontend", "purpose", "js-ts", ("js-ts", "browser"), "a ComfyUI frontend extension"),
]

BY_QUALIFIED: Dict[str, Layer] = {l.qualified: l for l in LAYERS}


def by_bare(name: str) -> List[Layer]:
    """Every layer with this bare name (qt has two)."""
    return [l for l in LAYERS if l.name == name]


# Presets: a named, verified list. The key is language/name, as --archetype
# spells it today. Values are bare layer names within that language.
PRESETS: Dict[str, List[str]] = {
    "python/pypi": ["pypi"],
    "python/setuppy": ["setuppy"],
    "python/script": ["script"],
    "python/comfyui": ["pypi", "comfyui"],
    "python/django": ["pypi", "django"],
    "python/qt": ["pypi", "qt"],
    "c-cpp/cmake-app": ["cmake-app"],
    "c-cpp/cmake-lib": ["cmake-lib"],
    "c-cpp/msbuild": ["msbuild"],
    "c-cpp/minimal": ["minimal"],
    "c-cpp/qt": ["cmake-app", "qt"],
    "js-ts/node-package": ["node", "ts", "node-package"],
    "js-ts/claude-plugin": ["node", "claude-plugin"],
    "js-ts/web-vite-react": ["browser", "ts", "vite", "react"],
    "js-ts/obsidian-plugin": ["browser", "ts", "obsidian-plugin"],
    "js-ts/browser-extension": ["browser", "ts", "browser-extension"],
    "js-ts/comfyui-frontend": ["browser", "ts", "vite", "comfyui-frontend"],
}

DEFAULT_PRESET = {"python": "python/pypi", "c-cpp": "c-cpp/cmake-app", "js-ts": "js-ts/node-package"}


def expand_preset(key: str) -> List[str]:
    """A preset's full ordered layer list, qualified, language first, implied
    layers included."""
    language = key.split("/")[0]
    layers = [BY_QUALIFIED[f"{language}/{n}"] for n in PRESETS[key]]
    return order_and_imply(layers)


def order_and_imply(layers: List[Layer]) -> List[str]:
    """Add every implied layer, sort by facet rank then by the order given,
    return qualified names. Raises ValueError on an exclusive collision."""
    seen: List[Layer] = []

    def add(l: Layer):
        for imp in l.implies:
            add(BY_QUALIFIED[imp] if "/" in imp else BY_QUALIFIED[f"{l.language}/{imp}"] if f"{l.language}/{imp}" in BY_QUALIFIED else BY_QUALIFIED[imp])
        if l not in seen:
            seen.append(l)

    for l in layers:
        add(l)
    # exclusivity per (facet, language)
    for i, a in enumerate(seen):
        for b in seen[i + 1:]:
            if a.facet == b.facet and FACETS[a.facet][1] and a.language == b.language:
                raise ValueError(f"'{a.name}' and '{b.name}' are both a {a.facet} for {a.language}; pick one")
    ordered = sorted(seen, key=lambda l: (l.rank, seen.index(l)))
    return [l.qualified for l in ordered]
