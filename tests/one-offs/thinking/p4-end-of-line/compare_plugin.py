"""The 0.9.x end-of-line check, part 1: a created Claude Code plugin vs claude-bookmarks.

    python tests/one-offs/thinking/p4-end-of-line/compare_plugin.py <scratch-dir>

Creates `demo-plugin` (js-ts, --with claude-plugin) and `py-plugin` (python,
--with claude-plugin) with the tool in <scratch-dir>, unsigned, stdin from
/dev/null, a temp HOME, repokit-common vendored from the sibling checkout.
Then compares each created tree's tracked files with claude-bookmarks'
(read-only: `git ls-files` and file reads only), and the manifests key by key.
The trees are left in <scratch-dir> for reading by hand.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BOOKMARKS = Path(r"C:\code\claude-projects\claude-bookmarks")
ENV = dict(os.environ, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false",
           GIT_CONFIG_KEY_1="tag.gpgsign", GIT_CONFIG_VALUE_1="false", PYTHONPATH=str(REPO),
           REPOKIT_COMMON_SOURCE=str(REPO.parent / "git-repokit-common"))

# Paths whose content is the project's own work, not scaffold: compared by
# presence of the folder only.
OWN_WORK = ("plugin/hooks/core/", "plugin/hooks/engine/", "plugin/hooks/views/", "plugin/images/",
            "tests/mutation/", "tests/core/", "tests/one-offs/", "tests/checklists/", "tests/probes/",
            "scripts/repokit-common/", "docs/")


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True).stdout


def create(scratch, name, language):
    cmd = [sys.executable, "-m", "repokit", "create", name, "--language", language,
           "--with", "claude-plugin", "--license", "mit", "--no-push",
           "--description", "A demo plugin made by the end-of-line check"]
    r = subprocess.run(cmd, cwd=scratch, env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    (scratch / f"{name}.create.log").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"create {name} failed ({r.returncode}); see {name}.create.log")
    # the main worktree is the folder whose git ls-files lists plugin/
    for d in sorted({p.parent for p in (scratch / name).rglob(".git")}):
        if "plugin/.claude-plugin/plugin.json" in git(["ls-files"], d) or (d / "plugin").is_dir():
            return d
    return scratch / name


def scaffold(files):
    out, own = set(), set()
    for f in files:
        hit = next((p for p in OWN_WORK if f.startswith(p)), None)
        if hit:
            own.add(hit)
        elif f.endswith((".ts", ".tsx", ".ps1")) and f.startswith("plugin/hooks/"):
            own.add("plugin/hooks/*.ts(x)/.ps1 sources")
        else:
            out.add(f)
    return out, own


def keys(path):
    try:
        return sorted(json.loads(path.read_text(encoding="utf-8")).keys())
    except (OSError, ValueError) as e:
        return [f"<unreadable: {e.__class__.__name__}>"]


def report(name, tree, bm_files, lines):
    files = [f for f in git(["ls-files"], tree).splitlines() if f]
    mine, mine_own = scaffold(files)
    theirs, theirs_own = scaffold(bm_files)
    lines += [f"## {name} ({len(files)} tracked files) vs claude-bookmarks ({len(bm_files)})", "",
              f"In both ({len(mine & theirs)}):", *[f"    {f}" for f in sorted(mine & theirs)], "",
              f"Only in the created project ({len(mine - theirs)}):", *[f"    {f}" for f in sorted(mine - theirs)], "",
              f"Only in claude-bookmarks, scaffold level ({len(theirs - mine)}):",
              *[f"    {f}" for f in sorted(theirs - mine)], "",
              "Own-work folders in claude-bookmarks (presence only): " + ", ".join(sorted(theirs_own)),
              "Own-work folders in the created project: " + (", ".join(sorted(mine_own)) or "none"), ""]
    for rel in ("plugin/.claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "plugin/hooks/hooks.json",
                "package.json", "plugin/package.json", ".repokit.json"):
        a, b = tree / rel, BOOKMARKS / rel
        if a.exists() or b.exists():
            ka = keys(a) if a.exists() else ["<absent>"]
            kb = keys(b) if b.exists() else ["<absent>"]
            lines += [f"Keys of {rel}:", f"    created:   {ka}", f"    bookmarks: {kb}",
                      f"    only created: {sorted(set(ka) - set(kb))}", f"    only bookmarks: {sorted(set(kb) - set(ka))}", ""]
    for rel in (".repokit-common.toml", "plugin/.claude-plugin/plugin.json", "plugin/hooks/hooks.json"):
        if (tree / rel).exists():
            lines += [f"--- created {rel} ---", (tree / rel).read_text(encoding="utf-8").rstrip(), ""]
        if (BOOKMARKS / rel).exists():
            lines += [f"--- bookmarks {rel} ---", (BOOKMARKS / rel).read_text(encoding="utf-8").rstrip(), ""]


def main():
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    home = scratch / "home"
    home.mkdir(exist_ok=True)
    (home / ".gitconfig").write_text("[user]\n\tname = Demo Maker\n\temail = demo@example.invalid\n", encoding="utf-8")
    ENV.update(HOME=str(home), USERPROFILE=str(home))
    house = "--house" in sys.argv
    if house:
        # The parity map's house config (~/.repokit/config.json), with every
        # extra: claude-bookmarks carries ROADMAP, .vscode/settings.json and
        # tests/output/.gitkeep beyond the map's five.
        (home / ".repokit").mkdir(exist_ok=True)
        (home / ".repokit" / "config.json").write_text(json.dumps(
            {"license": "mit", "extras": ["all"], "vault_init": "prompt-file"}, indent=2), encoding="utf-8")
        scratch = scratch / "house"
        scratch.mkdir(exist_ok=True)
    bm_files = [f for f in git(["ls-files"], BOOKMARKS).splitlines() if f]
    lines = ["# End-of-line check, part 1: created plugins vs claude-bookmarks", ""]
    for name, language in (("demo-plugin", "js-ts"), ("py-plugin", "python")):
        tree = create(scratch, name, language)
        lines.append(f"(created {name} at {tree})")
        report(name, tree, bm_files, lines)
    out = Path(__file__).with_name("results-plugin-house.txt" if house else "results-plugin.txt")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
