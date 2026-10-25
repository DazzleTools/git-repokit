"""README badges in the house's shape (0.9.7).

Measured on 2026-10-25 across the 107 house projects under C:\\code
(tests/one-offs/thinking/p4-measure-badges/) and settled with djdarcy; the
design is notes/2026-10-25__00-02-16__both_readme-badge-sets__the-house-badges-and-how-repokit-picks-them.md
in the vault.

- TYPES is the catalogue: each badge's commonest house form, filled per
  project, inline (`[![alt](image)](link)`) as the house writes them.
- TEMPLATES are ordered lists. The general ones follow djdarcy's slots:
  where to get it (PyPI, else the release), when it was released, package
  downloads, runtime, other package locations, license, discussions,
  ghstats, platform last (the commitment that the tools work everywhere).
  ComfyUI keeps its own order: the Registry is where a node comes from.
- CI is a filler: in when it lands on a row that already exists, out when
  it would start a row by itself (ROW badges per row).
- The license's color is its house color (GPL/AGPL green, MIT yellow,
  others orange), switched to the next of green, yellow, orange when it would
  equal a neighbour's color.

A person's own templates (`badge_templates`) and badge types
(`badge_types`, each naming `after` to take its place in the order) come
from the global config; `--badges NAME|a,b,c` or the config's `badges`
picks one.
"""
from typing import Dict, List, Optional, Sequence

ROW = 7  # shields badges per row of a GitHub README (to be checked on a render)

# id -> (alt, image, link, color). {owner} {repo} {dist} {python} {node}
# {license_label} {license_url} {gist_user} {gist} {pages} are filled per
# project; {color} is the badge's resolved color.
TYPES: Dict[str, tuple] = {
    "pypi-version": ("PyPI", "https://img.shields.io/pypi/v/{dist}?color={color}",
                     "https://pypi.org/project/{dist}/", "green"),
    "release-date": ("Release Date", "https://img.shields.io/github/release-date/{owner}/{repo}?color={color}",
                     "https://github.com/{owner}/{repo}/releases", "green"),
    "downloads": ("PyPI Downloads",
                  "https://static.pepy.tech/personalized-badge/{dist}?period=total&units=international_system"
                  "&left_color=black&right_color={color}&left_text=downloads",
                  "https://pypistats.org/packages/{dist}", "green"),
    "release-version": ("GitHub release",
                        "https://img.shields.io/github/v/release/{owner}/{repo}?include_prereleases&label=version",
                        "https://github.com/{owner}/{repo}/releases", "blue"),
    "ci": ("CI", "https://github.com/{owner}/{repo}/actions/workflows/{ci}/badge.svg",
           "https://github.com/{owner}/{repo}/actions/workflows/{ci}", "default"),
    "python": ("Python {python}+", "https://img.shields.io/badge/python-{python}+-{color}.svg",
               "https://www.python.org/downloads/", "blue"),
    "node": ("Node {node}+", "https://img.shields.io/badge/node-{node}+-{color}.svg",
             "https://nodejs.org/en/download", "blue"),
    "comfyui-registry": ("ComfyUI Registry", "https://img.shields.io/badge/ComfyUI-Registry-{color}.svg",
                         "https://registry.comfy.org/publishers/{gist_user}/nodes/{repo_lower}", "green"),
    "license": ("License: {license_label}", "https://img.shields.io/badge/license-{license_badge}-{color}.svg",
                "{license_url}", "contrast"),
    "discussions": ("GitHub Discussions", "https://img.shields.io/github/discussions/{owner}/{repo}",
                    "https://github.com/{owner}/{repo}/discussions", "blue"),
    "installs": ("Installs",
                 "https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/{gist_user}/{gist}/raw/installs.json",
                 "https://{pages}.github.io/{repo}/stats/#installs", "blue"),
    "views": ("Views",
              "https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/{gist_user}/{gist}/raw/views.json",
              "https://{pages}.github.io/{repo}/stats/#views", "blue"),
    "platform": ("Platform", "https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-{color}.svg",
                 "{platform_link}", "lightgrey"),
}

# The default order: djdarcy's slots, CI after the release slots. A badge type
# a person adds names its place with `after`.
ORDER = ["pypi-version", "release-date", "downloads", "release-version", "ci", "python", "node",
         "comfyui-registry", "license", "discussions", "installs", "views", "platform"]

TEMPLATES: Dict[str, List[str]] = {
    "pypi": ["pypi-version", "release-date", "downloads", "ci", "runtime", "license", "discussions",
             "installs", "platform"],
    "github": ["release-version", "ci", "runtime", "license", "discussions", "installs", "platform"],
    # its own order: the Registry is where a node comes from (djdarcy, 2026-10-25)
    "comfyui": ["runtime", "comfyui-registry", "release-version", "license", "installs", "views"],
    "minimal": ["runtime", "license"],
}

# The default template for a preset
PRESET_TEMPLATE = {"python/pypi": "pypi", "python/comfyui": "comfyui"}

# license id -> (badge text, the license's page, house color)
LICENSES = {
    "gpl-3.0": ("GPL v3", "https://www.gnu.org/licenses/gpl-3.0.html", "green"),
    "gpl-3.0-or-later": ("GPL v3", "https://www.gnu.org/licenses/gpl-3.0.html", "green"),
    "agpl-3.0": ("AGPL v3", "https://www.gnu.org/licenses/agpl-3.0.html", "green"),
    "agpl-3.0-or-later": ("AGPL v3", "https://www.gnu.org/licenses/agpl-3.0.html", "green"),
    "lgpl-3.0": ("LGPL v3", "https://www.gnu.org/licenses/lgpl-3.0.html", "green"),
    "lgpl-3.0-or-later": ("LGPL v3", "https://www.gnu.org/licenses/lgpl-3.0.html", "green"),
    "gpl-2.0": ("GPL v2", "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html", "green"),
    "mit": ("MIT", "https://opensource.org/licenses/MIT", "yellow"),
    "apache-2.0": ("Apache 2.0", "https://opensource.org/licenses/Apache-2.0", "orange"),
}
CONTRAST = ["green", "yellow", "orange"]


class BadgeError(ValueError):
    """A template or badge name the catalogue does not know."""


def _shields_text(text: str) -> str:
    """A static shields badge's text: '-' doubled, '_' doubled, spaces escaped."""
    return text.replace("-", "--").replace("_", "__").replace(" ", "%20")


def resolve(request, archetype: Optional[str], templates: Optional[dict] = None,
            types: Optional[dict] = None) -> List[str]:
    """The badge ids for a request: a template name, a list of ids, or None
    (the preset's default template)."""
    templates = {**TEMPLATES, **(templates or {})}
    known = set(TYPES) | set(types or {}) | {"runtime"}
    if request is None or request == "":
        request = PRESET_TEMPLATE.get(archetype or "", "github")
    if isinstance(request, str) and "," not in request:
        if request not in templates:
            if request in known:
                return [request]
            raise BadgeError(f"unknown badge template {request!r}; known: {', '.join(sorted(templates))}")
        names = list(templates[request])
    else:
        names = [n.strip() for n in (request.split(",") if isinstance(request, str) else request) if n.strip()]
        order = ORDER + [t for t in (types or {})]
        names = sorted(dict.fromkeys(names), key=lambda n: order.index(n) if n in order else len(order))
    unknown = [n for n in names if n not in known]
    if unknown:
        raise BadgeError(f"unknown badges {', '.join(unknown)}; known: {', '.join(sorted(known))}")
    return names


def render(names: Sequence[str], values: Dict[str, str], ci: str = "auto",
           types: Optional[dict] = None) -> str:
    """The badge lines, one per line, inline. `values` fills the tokens; a
    badge whose required value is missing (no CI file, no runtime floor) is
    left out. `ci` is auto, on or off."""
    catalogue = dict(TYPES)
    for tid, spec in (types or {}).items():  # a person's own badge lines
        catalogue[tid] = (spec.get("alt", tid), spec["image"], spec.get("link", ""), spec.get("color", "default"))
    picked = []
    for n in names:
        if n == "runtime":
            n = "python" if values.get("python") else "node" if values.get("node") else None
            if not n:
                continue
        if n == "ci" and not values.get("ci"):
            continue
        if n == "license" and not values.get("license_badge"):
            continue
        if n in ("python",) and not values.get("python"):
            continue
        if n in ("node",) and not values.get("node"):
            continue
        picked.append(n)
    if "ci" in picked and ci != "on":
        others = len(picked) - 1
        if ci == "off" or (others and others % ROW == 0):
            picked.remove("ci")
    colors = [catalogue[n][3] for n in picked]
    for i, n in enumerate(picked):
        if colors[i] != "contrast":
            continue
        neighbours = {colors[j] for j in (i - 1, i + 1) if 0 <= j < len(picked)}
        neighbours |= {"blue"} if "default" in neighbours else set()  # shields' default reads blue
        house = values.get("license_color") or "orange"
        colors[i] = house if house not in neighbours else next(
            (c for c in CONTRAST if c not in neighbours), house)
    lines = []
    for n, color in zip(picked, colors):
        alt, image, link, _ = catalogue[n]
        fill = {**values, "color": color}
        lines.append(f"[![{alt.format(**fill)}]({image.format(**fill)})]({link.format(**fill)})")
    return "\n".join(lines)


def license_values(lid: Optional[str], spdx: Optional[str]) -> Dict[str, str]:
    """The license badge's text, link and house color; empty when the project
    has no catalogue license (a file, none, or all rights reserved)."""
    if not lid or not spdx or spdx.startswith("LicenseRef"):
        return {}
    label, url, color = LICENSES.get(lid, (spdx, "LICENSE", "orange"))
    return {"license_label": label, "license_badge": _shields_text(label), "license_url": url,
            "license_color": color}
