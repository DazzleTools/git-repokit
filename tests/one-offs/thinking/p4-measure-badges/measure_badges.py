"""Which README badges the house actually uses (2026-10-25, djdarcy's request).

    python tests/one-offs/thinking/p4-measure-badges/measure_badges.py [root]

Reads every README.md under root (default C:\\code), read-only. Skips vendored
and generated trees (node_modules, .git, scripts/repokit-common, build, dist,
old_test_runs, site-packages). Projects checked out more than once (local/,
github/ worktrees, forks) are counted once, by the README's first heading.

Each badge -- inline `[![alt](image)](link)` or a reference-style pair -- is
classified into a kind (pypi-version, downloads-pepy, installs-ghtraf, ...)
and normalised (owner, repo, package, gist id become tokens), so the same
badge on different projects counts as one form. Writes results.md beside
itself: kinds by how many projects use them, the commonest form of each kind,
how projects order them, and the sets that occur together.
"""
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\code")
SKIP = {"node_modules", ".git", "repokit-common", "build", "dist", "old_test_runs", "site-packages",
        ".venv", "venv", "__pycache__", ".tox", "vendor", "_vendor", "third_party"}
HOUSE = {"djdarcy", "dazzleml", "dazzletools", "dazzlenodes", "dazzlelib"}
INLINE = re.compile(r"\[!\[([^\]]*)\]\(([^)\s]+)[^)]*\)\]\(([^)\s]+)[^)]*\)")
REFSTYLE = re.compile(r"\[!\[([^\]]*)\]\[([^\]]+)\]\]\[([^\]]+)\]")
REFDEF = re.compile(r"^\[([^\]]+)\]:\s*(\S+)", re.M)

KINDS = [  # (kind, test on the image URL)
    ("pypi-version", r"shields\.io/pypi/v/"),
    ("pypi-pyversions", r"shields\.io/pypi/pyversions/"),
    ("downloads-pepy", r"pepy\.tech"),
    ("downloads-pypistats", r"shields\.io/pypi/d[mwt]?/"),
    ("release-date", r"shields\.io/github/release-date"),
    ("release-version", r"shields\.io/github/v/(release|tag)"),
    ("ci-workflow", r"/actions/workflows/.+badge\.svg|shields\.io/github/actions"),
    ("installs-ghtraf", r"gist\.githubusercontent\.com/.+installs\.json"),
    ("views-ghtraf", r"gist\.githubusercontent\.com/.+views\.json"),
    ("clones-ghtraf", r"gist\.githubusercontent\.com/.+clones\.json"),
    ("downloads-ghtraf", r"gist\.githubusercontent\.com/.+downloads\.json"),
    ("discussions", r"github/discussions|discussions"),
    ("python", r"badge/[Pp]ython"),
    ("node", r"badge/[Nn]ode"),
    ("license", r"badge/[Ll]icen[sc]e|github/license"),
    ("platform", r"badge/[Pp]latform"),
    ("comfyui-registry", r"[Cc]omfy[Uu][Ii]"),
    ("cuda", r"badge/CUDA"),
    ("buymeacoffee", r"buymeacoffee"),
    ("stars", r"github/stars"),
    ("issues", r"github/issues"),
    ("last-commit", r"github/last-commit"),
]


def kind_of(image: str) -> str:
    for kind, pat in KINDS:
        if re.search(pat, image):
            return kind
    return "other:" + re.sub(r"https?://([^/]+).*", r"\1", image)


def normalise(text: str, owner: str, repo: str, dist: str) -> str:
    t = text
    t = re.sub(r"gist\.githubusercontent\.com/[^/]+/[0-9a-f]{20,}", "gist.githubusercontent.com/<user>/<gist>", t)
    for value, token in sorted([(owner, "<owner>"), (repo, "<repo>"), (dist, "<dist>")], key=lambda p: -len(p[0] or "")):
        if value:
            t = re.sub(re.escape(value), token, t, flags=re.I)
    t = re.sub(r"[a-z0-9-]+\.github\.io", "<owner>.github.io", t, flags=re.I)
    return t


def origin(readme: Path):
    """(owner, repo) from the checkout's git remote, else the folder name."""
    for d in [readme.parent, *readme.parents]:
        cfg = d / ".git" / "config"
        if cfg.is_file():
            m = re.search(r"url\s*=\s*\S*github\.com[:/]([^/\s]+)/([^/\s]+?)(\.git)?\s*$", cfg.read_text(errors="replace"), re.M)
            if m:
                return m.group(1), m.group(2)
            break
        if (d / ".git").is_file():
            break
    return "", readme.parent.name


def badges(text: str):
    """[(alt, image, link)] in the order they appear in the README's first 60 lines."""
    head = "\n".join(text.splitlines()[:60])
    defs = dict(REFDEF.findall(text))
    found = []
    for m in re.finditer(f"{INLINE.pattern}|{REFSTYLE.pattern}", head):
        if m.group(1) is not None:
            found.append((m.group(1), m.group(2), m.group(3)))
        else:
            found.append((m.group(4), defs.get(m.group(5), ""), defs.get(m.group(6), "")))
    return found


def main():
    projects = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for fn in filenames:
            if fn.lower() != "readme.md":
                continue
            path = Path(dirpath, fn)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            b = badges(text)
            if not b:
                continue
            owner, repo = origin(path)
            # the house's own projects only: C:\code also holds third-party clones
            if owner.lower() not in HOUSE and "djdarcy" not in text.lower():
                continue
            title = (re.search(r"^#\s+(.+)$", text, re.M) or [None, repo])[1].strip()
            key = (owner.lower(), repo.lower()) if owner else ("", title.lower())
            if key not in projects or len(b) > len(projects[key][2]):
                projects[key] = (path, (owner, repo), b)

    kind_projects = Counter()
    forms = defaultdict(Counter)
    sequences = Counter()
    pairs = Counter()
    style = Counter()
    for (path, (owner, repo), b) in projects.values():
        dist = repo.lower()
        kinds_here = []
        for alt, image, link in b:
            k = kind_of(image)
            kinds_here.append(k)
            line = f"[![{alt}]({image})]({link})"
            forms[k][normalise(line, owner, repo, dist)] += 1
        style["reference" if "][" in "".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[2:4]) else "inline"] += 1
        uniq = list(dict.fromkeys(kinds_here))
        for k in uniq:
            kind_projects[k] += 1
        sequences[" > ".join(uniq)] += 1
        for i, a in enumerate(uniq):
            for c in uniq[i + 1:]:
                pairs[(a, c)] += 1

    out = [f"# Badge audit of {ROOT} ({len(projects)} projects with badges)", "",
           "## Kinds, by how many projects use them", "", "| kind | projects | commonest form (normalised) | its count |", "|---|---|---|---|"]
    for k, n in kind_projects.most_common():
        form, c = forms[k].most_common(1)[0]
        out.append(f"| {k} | {n} | `{form}` | {c} |")
    out += ["", "## Every form of the top kinds", ""]
    for k, _ in kind_projects.most_common(12):
        out.append(f"### {k}")
        for form, c in forms[k].most_common(6):
            out.append(f"- {c} x `{form}`")
        out.append("")
    out += ["## Orders that occur more than once", ""]
    for seq, n in sequences.most_common():
        if n > 1:
            out.append(f"- {n} x {seq}")
    # --- order and sets (djdarcy, 2026-10-25: "research the ORDER and which
    # ones are included as a SET" -- e.g. platform at the END of the line)
    position = defaultdict(lambda: Counter())     # kind -> first / last / middle / only
    rel_pos = defaultdict(list)                   # kind -> position in 0..1
    before = Counter()                            # (a, b) -> a came before b
    sets = Counter()
    by_owner = defaultdict(Counter)               # owner -> kind -> projects
    owners = Counter()
    for (path, (owner, repo), b) in projects.values():
        uniq = [k for k in dict.fromkeys(kind_of(i) for _, i, _ in b)
                if not k.startswith("other:camo")]  # the coffee button is not a badge
        if not uniq:
            continue
        owners[owner.lower() or "?"] += 1
        sets[" + ".join(sorted(uniq))] += 1
        for i, k in enumerate(uniq):
            by_owner[owner.lower() or "?"][k] += 1
            if len(uniq) == 1:
                position[k]["only"] += 1
            elif i == 0:
                position[k]["first"] += 1
            elif i == len(uniq) - 1:
                position[k]["last"] += 1
            else:
                position[k]["middle"] += 1
            rel_pos[k].append(i / (len(uniq) - 1) if len(uniq) > 1 else 0.5)
            for later in uniq[i + 1:]:
                before[(k, later)] += 1
    out += ["", "## Where each kind sits in the line", "",
            "0 is the first badge, 1 the last; `last` counts the projects where it closes the line.", "",
            "| kind | projects | mean position | first | middle | last | only |", "|---|---|---|---|---|---|---|"]
    for k, n in kind_projects.most_common():
        if k.startswith("other:camo") or n < 3:
            continue
        p = position[k]
        mean = sum(rel_pos[k]) / len(rel_pos[k]) if rel_pos[k] else 0
        out.append(f"| {k} | {n} | {mean:.2f} | {p['first']} | {p['middle']} | {p['last']} | {p['only']} |")
    top = [k for k, n in kind_projects.most_common() if n >= 9 and not k.startswith("other:")]
    out += ["", "## Which comes first, pair by pair", "",
            "Cell = projects where the row kind comes before the column kind (of those carrying both).", "",
            "| before \\ after | " + " | ".join(top) + " |", "|---|" + "---|" * len(top)]
    for a in top:
        cells = []
        for c in top:
            if a == c:
                cells.append("--")
            else:
                ab, ba = before[(a, c)], before[(c, a)]
                cells.append(f"{ab}/{ab + ba}" if ab + ba else "")
        out.append(f"| {a} | " + " | ".join(cells) + " |")
    out += ["", "## Sets (ignoring order) that occur more than once", ""]
    for s, n in sets.most_common():
        if n > 1:
            out.append(f"- {n} x {s}")
    out += ["", "## By owner (projects carrying each kind)", ""]
    for o, n in owners.most_common():
        kinds = ", ".join(f"{k} {c}" for k, c in by_owner[o].most_common() if not k.startswith("other:"))
        out.append(f"- **{o}** ({n} projects): {kinds}")

    # --- colours (djdarcy, 2026-10-25: "I think I made the color vary based
    # on adjacent tags not unto itself ... see if you can detect that?")
    def colour_of(kind, image):
        m = re.search(r"[?&](?:color|right_color)=([A-Za-z0-9#]+)", image)
        if m:
            return m.group(1).lower()
        m = re.search(r"shields\.io/badge/[^?]*-([A-Za-z0-9]+)(?:\.svg)?(?:\?|$)", image)
        if m:
            return m.group(1).lower()
        if kind.endswith("-ghtraf"):
            return "blue"            # ghtraf's build_badge default
        return "default"             # a dynamic badge with shields' own colour
    lic_left, lic_right, lic_colour = Counter(), Counter(), Counter()
    lic_by_name = defaultdict(Counter)
    colour_by_kind = defaultdict(Counter)
    triples = Counter()
    for (path, (owner, repo), b) in projects.values():
        seq = [(kind_of(i), colour_of(kind_of(i), i), alt) for alt, i, _ in b if "camo" not in i]
        for k, c, _ in seq:
            colour_by_kind[k][c] += 1
        for idx, (k, c, alt) in enumerate(seq):
            if k != "license":
                continue
            lic_colour[c] += 1
            name = "GPL" if "GPL" in alt.upper() and "AGPL" not in alt.upper() else "AGPL" if "AGPL" in alt.upper() else "MIT" if "MIT" in alt.upper() else "other"
            lic_by_name[name][c] += 1
            left = seq[idx - 1] if idx > 0 else None
            right = seq[idx + 1] if idx + 1 < len(seq) else None
            if left:
                lic_left["same" if left[1] == c else "differs"] += 1
                triples[(left[0], left[1], c, right[0] if right else "-", right[1] if right else "-")] += 1
            if right:
                lic_right["same" if right[1] == c else "differs"] += 1
    out += ["", "## Colours", "", "### Each kind's colours", ""]
    for k, n in kind_projects.most_common(14):
        if k.startswith("other:"):
            continue
        out.append(f"- **{k}**: " + ", ".join(f"{c} {n}" for c, n in colour_by_kind[k].most_common()))
    out += ["", "### The licence badge against its neighbours", "",
            f"- licence colours: {dict(lic_colour.most_common())}",
            f"- by licence: " + "; ".join(f"{n}: {dict(c.most_common())}" for n, c in lic_by_name.items()),
            f"- vs the badge on its left: {dict(lic_left)}",
            f"- vs the badge on its right: {dict(lic_right)}", "",
            "### (left kind, left colour) -> licence colour -> (right kind, right colour), commonest", ""]
    for (lk, lc, c, rk, rc), n in triples.most_common(16):
        out.append(f"- {n} x {lk} [{lc}] -> license [{c}] -> {rk} [{rc}]")

    out += ["", "## The projects", ""]
    for (path, (owner, repo), b) in sorted(projects.values(), key=lambda p: str(p[0])):
        out.append(f"- `{owner}/{repo}` ({len(b)}): " + ", ".join(dict.fromkeys(kind_of(i) for _, i, _ in b)) + f" -- {path}")
    Path(__file__).with_name("results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(projects)} projects; wrote results.md")
    for k, n in kind_projects.most_common(25):
        print(f"{n:4d}  {k}")


if __name__ == "__main__":
    main()
