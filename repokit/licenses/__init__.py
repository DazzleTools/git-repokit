"""The license catalogue: the SPDX set GitHub and GitLab offer at repository
creation, as text files beside this module, plus a file form for anything else.

The texts come from github/choosealicense.com at one pinned commit; LICENSES.md
beside them records the commit and each file's fingerprint as received and as
shipped (the placeholders became __RK_YEAR__ and __RK_HOLDER__, nothing else).
A license is a PARAMETER of `repokit create`, not a template file: the value
comes from --license, else the global config (`license`, or `license_private`
for a private repository), and with none of those the create is refused and the
catalogue named -- there is no silent default (djdarcy, 2026-10-22: "perhaps
just making it a requirement that the person provides it is best").

The "or-later" variants are not files: the license text is identical and only
the project's notice says "or later", so they render from the base text with a
notice line. Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-
with-the-old-route.md (U1, U2); the survey behind the catalogue's size:
tests/one-offs/thinking/p4-measure-licenses/results.md.
"""
import datetime
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DIR = Path(__file__).resolve().parent
RECORD = DIR / "LICENSES.md"
HOLDER = "__RK_HOLDER__"
YEAR = "__RK_YEAR__"

# id -> (base id, SPDX id, the notice line's wording)
VARIANTS: Dict[str, Tuple[str, str, str]] = {
    "gpl-3.0-or-later": ("gpl-3.0", "GPL-3.0-or-later", "GNU General Public License, version 3 or (at your option) any later version"),
    "lgpl-3.0-or-later": ("lgpl-3.0", "LGPL-3.0-or-later", "GNU Lesser General Public License, version 3 or (at your option) any later version"),
    "agpl-3.0-or-later": ("agpl-3.0", "AGPL-3.0-or-later", "GNU Affero General Public License, version 3 or (at your option) any later version"),
}


class LicenseError(ValueError):
    """A license the person named cannot be used; the message says what would."""


# The names a project's own license file goes by (adopt keeps it, 0.9.11),
# in the order a project with several is read: the plain name first.
OWN_LICENSE_STEMS = ("LICENSE", "LICENCE", "COPYING")
OWN_LICENSE_SUFFIXES = ("", ".md", ".txt", ".rst")


def find_existing(root: str) -> Optional[str]:
    """The name of the project's own license file in `root` (LICENSE,
    LICENCE or COPYING, bare or .md/.txt/.rst, any case), or None."""
    try:
        names = sorted(p.name for p in Path(root).iterdir() if p.is_file())
    except OSError:
        return None
    for stem in OWN_LICENSE_STEMS:
        for suffix in OWN_LICENSE_SUFFIXES:
            for name in names:
                if name.upper() == (stem + suffix).upper():
                    return name
    return None


def known() -> List[str]:
    """Every id the catalogue renders: the files, then the notice variants."""
    files = sorted(p.stem for p in DIR.glob("*.txt"))
    return files + sorted(VARIANTS)


def normalise(spec: str) -> str:
    """`GPL-3.0`, `gpl-3.0`, `MIT` -> the catalogue's lower-case id."""
    return spec.strip().lower()


def is_known(spec: str) -> bool:
    return normalise(spec) in known()


def body(lid: str) -> str:
    """The shipped text of one catalogue file, tokens unresolved."""
    path = DIR / f"{lid}.txt"
    if not path.is_file():
        raise LicenseError(f"unknown license {lid!r}; the catalogue has: {', '.join(known())}; or --license file=<path>")
    return path.read_text(encoding="utf-8")


PROJECT = "__RK_PROJECT__"
EMAIL = "__RK_EMAIL__"


def render(spec: str, holder: str, year: Optional[int] = None,
           project: Optional[str] = None, email: Optional[str] = None) -> str:
    """The LICENSE text for this id, holder and year (default: this year).
    A text authored here may also name the project and a contact email
    (proprietary-evaluation, 0.9.11); without them it says "This software"
    and points to the copyright holder."""
    lid = normalise(spec)
    year = year or datetime.date.today().year
    if lid in VARIANTS:
        base, spdx, wording = VARIANTS[lid]
        notice = (f"Copyright (c) {year} {holder}\n\n"
                  f"This program is free software: you may redistribute it and/or modify it under the terms of the "
                  f"{wording} (SPDX-License-Identifier: {spdx}). The license text follows.\n\n")
        return notice + body(base)
    return (body(lid).replace(HOLDER, holder).replace(YEAR, str(year))
            .replace(PROJECT, project or "This software")
            .replace(EMAIL, email or "(contact the copyright holder)"))


def record() -> Dict[str, Tuple[str, str]]:
    """LICENSES.md's table: id -> (sha256 as received, sha256 as shipped)."""
    out: Dict[str, Tuple[str, str]] = {}
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*([a-z0-9.\-]+)\s*\|[^|]*\|[^|]*\|\s*([0-9a-f]{64}|-)\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m:
            out[m.group(1)] = (m.group(2), m.group(3))
    return out


def spdx(lid: str) -> Optional[str]:
    """The SPDX identifier for a catalogue id (`gpl-3.0` -> `GPL-3.0`), from the
    variants or LICENSES.md's SPDX column; None for an id the catalogue lacks."""
    lid = normalise(lid)
    if lid in VARIANTS:
        return VARIANTS[lid][1]
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 2 and cells[0] == lid:
            return cells[1]
    return None


def title(lid: str) -> Optional[str]:
    """The license's full name for prose (`gpl-3.0` -> `GNU General Public
    License v3.0`): the variants' base title plus "or later", else
    LICENSES.md's title column; None for an id the catalogue lacks."""
    lid = normalise(lid)
    if lid in VARIANTS:
        base = title(VARIANTS[lid][0])
        return f"{base} or later" if base else None
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 2 and cells[0] == lid:
            return cells[2].replace(" (authored here)", "")
    return None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(spec: Optional[str], config_license: Optional[str], private: bool,
            config_private: Optional[str]) -> Tuple[str, Optional[str]]:
    """What LICENSE to write: ("catalogue", id), ("file", path) or ("none", None).

    Order: --license; else the config's `license_private` for a private
    repository or `license` otherwise; else refuse. `none` means no file."""
    chosen = spec or (config_private if private and config_private else config_license)
    if not chosen:
        raise LicenseError("no license named: pass --license <id>, --license file=<path> or --license none, "
                           "or set `license` (and `license_private`) in ~/.repokit/config.json; "
                           f"the catalogue has: {', '.join(known())}")
    chosen = chosen.strip()
    if chosen.lower() == "none":
        return ("none", None)
    if chosen.lower().startswith("file="):
        path = chosen[5:].strip()
        if not Path(path).is_file():
            raise LicenseError(f"license file not found: {path}")
        return ("file", path)
    lid = normalise(chosen)
    if lid not in known():
        raise LicenseError(f"unknown license {chosen!r}; the catalogue has: {', '.join(known())}; or --license file=<path>")
    return ("catalogue", lid)
