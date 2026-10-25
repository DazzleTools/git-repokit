"""The live golden: capture a project made by the old route and one made by repokit, then diff.

    python golden.py capture <project-dir> <owner/repo> <out.json>
    python golden.py diff <golden.json> <twin.json> <report.md>

`capture` reads one project into a normalized record:
  - every tracked file at HEAD, its text normalized (line endings, the project
    and package names, the owner, dates, years, the git identity), hashed;
    scripts/repokit-common/ is summarised (file count and VERSION), not listed;
  - what sits on disk untracked (top two levels), the installed hooks, the
    branches, remotes and commit subjects;
  - the vault: private/'s own tracked files, normalized the same way;
  - GitHub, read back: visibility, description, default branch, features,
    topics, labels, issues with their bodies, pins, environments, workflow runs.
Read-only throughout: git plumbing reads and gh GETs (one GraphQL query).

`diff` compares two records and writes a markdown report: files only in one,
files in both that differ (with a short unified diff), and every GitHub field
that differs.
"""
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

VENDORED = "scripts/repokit-common/"


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def normalizer(name, owner, identity):
    pkg = name.replace("-", "_")
    title = name.replace("-", " ").title()
    pairs = [(f"{owner}/{name}", "__OWNER__/__NAME__"), (name, "__NAME__"), (pkg, "__PKG__"),
             (title, "__TITLE__")]
    for value, token in identity:
        if value:
            pairs.append((value, token))
    pairs.append((owner, "__OWNER__"))
    pairs.sort(key=lambda p: -len(p[0]))

    def norm(text):
        text = text.replace("\r\n", "\n")
        for value, token in pairs:
            text = text.replace(value, token)
        text = re.sub(r"\b20\d\d-\d\d-\d\d([T ][0-9:.]+Z?)?\b", "__DATE__", text)
        text = re.sub(r"\b20\d\d\b", "__YEAR__", text)
        return text
    return norm


def read_text(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def files_of(root, norm, prefix_skip=()):
    out, vendored = {}, {"files": 0}
    for rel in sh(["git", "ls-files"], root).splitlines():
        if rel.startswith(VENDORED):
            vendored["files"] += 1
            if rel == VENDORED + "VERSION":
                vendored["VERSION"] = (root / rel).read_text(encoding="utf-8").strip()
            continue
        if any(rel.startswith(p) for p in prefix_skip):
            continue
        text = read_text(root / rel)
        key = norm(rel)  # the package folder carries the project's name
        if text is None:
            out[key] = {"binary": hashlib.sha256((root / rel).read_bytes()).hexdigest()[:16]}
        else:
            t = norm(text)
            out[key] = {"sha": hashlib.sha256(t.encode()).hexdigest()[:16], "text": t[:200000]}
    return out, vendored


def capture(project, repo, out_path):
    root = Path(project).resolve()
    owner, name = repo.split("/")
    identity = [(sh(["git", "config", "user.name"], root).strip(), "__AUTHOR__"),
                (sh(["git", "config", "user.email"], root).strip(), "__EMAIL__")]
    norm = normalizer(name, owner, identity)
    rec = {"project": str(root), "repo": repo}
    rec["files"], rec["vendored"] = files_of(root, norm)
    status = sh(["git", "status", "--short", "--ignored", "--untracked-files=normal"], root).splitlines()
    rec["untracked"] = sorted(norm(l) for l in status if l[:2] in ("??", "!!"))
    hooks = root / ".git" / "hooks"
    rec["hooks"] = sorted(p.name for p in hooks.iterdir() if not p.name.endswith(".sample")) if hooks.is_dir() else []
    rec["branches"] = sorted(sh(["git", "branch", "-a", "--format=%(refname:short)"], root).split())
    rec["remotes"] = sorted(norm(l) for l in sh(["git", "remote", "-v"], root).splitlines() if "(fetch)" in l)
    rec["commits"] = [norm(l) for l in sh(["git", "log", "--format=%s"], root).splitlines()]
    vault = root / "private"
    if (vault / ".git").exists():
        rec["vault_files"], _ = files_of(vault, norm)
        rec["vault_commits"] = [norm(l) for l in sh(["git", "log", "--format=%s"], vault).splitlines()]
        vs = sh(["git", "status", "--short"], vault).splitlines()
        rec["vault_untracked"] = sorted(norm(l) for l in vs)
    rec["github"] = github(owner, name, norm)
    Path(out_path).write_text(json.dumps(rec, indent=1, sort_keys=True), encoding="utf-8")
    print(f"captured {len(rec['files'])} files, {len(rec.get('vault_files', {}))} vault files -> {out_path}")


def gh_json(*args):
    out = sh(["gh", *args])
    try:
        return json.loads(out) if out.strip() else None
    except ValueError:
        return {"_raw": out[:500]}


def github(owner, name, norm):
    g = {}
    v = gh_json("repo", "view", f"{owner}/{name}", "--json",
                "visibility,description,defaultBranchRef,hasDiscussionsEnabled,hasIssuesEnabled,hasWikiEnabled,"
                "hasProjectsEnabled,homepageUrl,repositoryTopics,isTemplate,licenseInfo,deleteBranchOnMerge")
    if isinstance(v, dict):
        v["defaultBranchRef"] = (v.get("defaultBranchRef") or {}).get("name")
        v["repositoryTopics"] = sorted(t["name"] for t in (v.get("repositoryTopics") or []))
        v["licenseInfo"] = (v.get("licenseInfo") or {}).get("key")
        if v.get("description"):
            v["description"] = norm(v["description"])
    g["repo"] = v
    labels = gh_json("label", "list", "--repo", f"{owner}/{name}", "--limit", "100", "--json", "name,color,description")
    g["labels"] = sorted(labels or [], key=lambda l: l["name"]) if isinstance(labels, list) else labels
    issues = gh_json("issue", "list", "--repo", f"{owner}/{name}", "--state", "all", "--limit", "50",
                     "--json", "number,title,labels,state,body")
    g["issues"] = [{"number": i["number"], "title": norm(i["title"]), "state": i["state"],
                    "labels": sorted(l["name"] for l in i["labels"]), "body": norm(i["body"] or "")}
                   for i in sorted(issues or [], key=lambda i: i["number"])] if isinstance(issues, list) else issues
    prs = gh_json("pr", "list", "--repo", f"{owner}/{name}", "--state", "all", "--json", "number,title,author")
    g["prs"] = [{"number": p["number"], "title": norm(p["title"]), "author": p["author"]["login"]}
                for p in (prs or [])] if isinstance(prs, list) else prs
    q = ('query{repository(owner:"%s",name:"%s"){pinnedIssues(first:5){nodes{issue{number title}}}}}' % (owner, name))
    pins = gh_json("api", "graphql", "-f", f"query={q}")
    try:
        g["pinned"] = sorted(n["issue"]["number"] for n in pins["data"]["repository"]["pinnedIssues"]["nodes"])
    except (TypeError, KeyError):
        g["pinned"] = pins
    env = gh_json("api", f"repos/{owner}/{name}/environments")
    g["environments"] = sorted(e["name"] for e in (env or {}).get("environments", [])) if isinstance(env, dict) else env
    runs = gh_json("run", "list", "--repo", f"{owner}/{name}", "--limit", "20", "--json", "workflowName,conclusion,event,displayTitle")
    g["runs"] = sorted(f"{r['workflowName']} [{r['event']}] -> {r['conclusion']}" for r in runs) if isinstance(runs, list) else runs
    prot = sh(["gh", "api", f"repos/{owner}/{name}/branches/main/protection"])
    g["protection"] = "none" if "Not Found" in prot or "not protected" in prot.lower() else norm(prot[:300])
    return g


def section(title, a_only, b_only, lines):
    lines.append(f"## {title}\n")
    if a_only:
        lines.append("Only in the golden (old route):\n")
        lines += [f"- `{x}`" for x in a_only]
        lines.append("")
    if b_only:
        lines.append("Only in the twin (repokit):\n")
        lines += [f"- `{x}`" for x in b_only]
        lines.append("")


def diff_files(fa, fb, title, lines):
    a, b = set(fa), set(fb)
    section(title, sorted(a - b), sorted(b - a), lines)
    same = [f for f in sorted(a & b) if fa[f].get("sha", fa[f].get("binary")) == fb[f].get("sha", fb[f].get("binary"))]
    differ = [f for f in sorted(a & b) if f not in same]
    lines.append(f"In both: {len(a & b)}; identical after normalization: {len(same)}; differing: {len(differ)}.\n")
    if same:
        lines.append("Identical: " + ", ".join(f"`{f}`" for f in same) + "\n")
    for f in differ:
        ta, tb = fa[f].get("text"), fb[f].get("text")
        lines.append(f"### `{f}`\n")
        if ta is None or tb is None:
            lines.append("(binary; hashes differ)\n")
            continue
        d = list(difflib.unified_diff(ta.splitlines(), tb.splitlines(), "golden", "twin", lineterm="", n=1))
        lines.append(f"{sum(1 for l in d if l.startswith('-') and not l.startswith('---'))} lines only in the golden, "
                     f"{sum(1 for l in d if l.startswith('+') and not l.startswith('+++'))} only in the twin.\n")
        lines.append("```diff")
        lines += d[:80] + (["... (truncated)"] if len(d) > 80 else [])
        lines.append("```\n")


def diff(a_path, b_path, out_path):
    A = json.loads(Path(a_path).read_text(encoding="utf-8"))
    B = json.loads(Path(b_path).read_text(encoding="utf-8"))
    lines = [f"# Golden vs twin\n", f"Golden: `{A['repo']}`. Twin: `{B['repo']}`.\n"]
    diff_files(A["files"], B["files"], "Tracked files", lines)
    diff_files(A.get("vault_files", {}), B.get("vault_files", {}), "Vault (private/) tracked files", lines)
    lines.append("## The rest of the record\n")
    for key in ("vendored", "untracked", "hooks", "branches", "remotes", "commits", "vault_commits", "vault_untracked"):
        va, vb = A.get(key), B.get(key)
        mark = "same" if va == vb else "DIFFERS"
        lines.append(f"- **{key}** ({mark})")
        if va != vb:
            lines.append(f"  - golden: `{json.dumps(va)}`")
            lines.append(f"  - twin: `{json.dumps(vb)}`")
    lines.append("\n## GitHub, read back\n")
    for key in sorted(set(A["github"]) | set(B["github"])):
        va, vb = A["github"].get(key), B["github"].get(key)
        if key == "issues" and isinstance(va, list) and isinstance(vb, list):
            lines.append(f"- **issues**: golden {[(i['number'], i['title'], i['labels']) for i in va]}; "
                         f"twin {[(i['number'], i['title'], i['labels']) for i in vb]}")
            for ia, ib in zip(va, vb):
                if ia["body"] != ib["body"]:
                    d = list(difflib.unified_diff(ia["body"].splitlines(), ib["body"].splitlines(), "golden", "twin", lineterm="", n=0))
                    lines.append(f"  - #{ia['number']} body differs ({len(d)} diff lines); first lines:")
                    lines.append("    ```diff")
                    lines += ["    " + l for l in d[:20]]
                    lines.append("    ```")
            continue
        if key == "labels" and isinstance(va, list) and isinstance(vb, list):
            na, nb = {l["name"]: l for l in va}, {l["name"]: l for l in vb}
            lines.append(f"- **labels**: only in the golden {sorted(set(na) - set(nb))}; only in the twin "
                         f"{sorted(set(nb) - set(na))}; same name, different colour or description "
                         f"{sorted(n for n in set(na) & set(nb) if na[n] != nb[n])}")
            continue
        mark = "same" if va == vb else "DIFFERS"
        lines.append(f"- **{key}** ({mark})")
        if va != vb:
            lines.append(f"  - golden: `{json.dumps(va)}`")
            lines.append(f"  - twin: `{json.dumps(vb)}`")
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["capture"]:
        capture(*sys.argv[2:5])
    elif sys.argv[1:2] == ["diff"]:
        diff(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
