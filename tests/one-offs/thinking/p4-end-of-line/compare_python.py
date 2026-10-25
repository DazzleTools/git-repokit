"""The 0.9.x end-of-line check, part 2: a python create with the house config, row by row.

    python tests/one-offs/thinking/p4-end-of-line/compare_python.py <scratch-dir> [throwaway]

Creates `golden-tool` (--language python, no --github) in <scratch-dir> with
the parity map's house config in a temp HOME, unsigned, stdin from /dev/null,
repokit-common vendored from the sibling checkout. Then checks the map's
section 2a and 2c rows against the tree, runs the created project's own
tests, and (when a throwaway name is given) reads section 2b's rows back from
GitHub, read-only: labels, issues, pins, topics, discussions, environments.
Prints PASS / GAP / NOTE per row and writes results-python.txt beside itself.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENV = dict(os.environ, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false",
           GIT_CONFIG_KEY_1="tag.gpgsign", GIT_CONFIG_VALUE_1="false", PYTHONPATH=str(REPO),
           REPOKIT_COMMON_SOURCE=str(REPO.parent / "git-repokit-common"))
HOUSE = {"license": "gpl-3.0", "license_private": "all-rights-reserved",
         "extras": ["funding", "dependabot", "stale", "pr-template", "release-template"],
         "github_setup": ["labels", "issues", "discussions", "topics"], "vault_init": "prompt-file"}
rows = []


def run(cmd, cwd, env=ENV):
    r = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def row(ok, what, detail=""):
    rows.append(f"{'PASS' if ok is True else ('NOTE' if ok is None else 'GAP ')}  {what}" + (f" -- {detail}" if detail else ""))


def check_tree(t):
    tracked = set(run(["git", "ls-files"], t)[1].splitlines())
    lic = (t / "LICENSE").read_text(encoding="utf-8", errors="replace") if (t / "LICENSE").exists() else ""
    row("GNU GENERAL PUBLIC LICENSE" in lic and "LICENSE" in tracked, "2a LICENSE from the house licence (gpl-3.0), tracked")
    for f in (".github/FUNDING.yml", ".github/dependabot.yml", ".github/stale.yml",
              ".github/pull_request_template.md", ".github/release-template.md"):
        row(f in tracked, f"2a extra {f} tracked")
    for f in ("ROADMAP.md", "docs/platform-support.md", ".vscode/settings.json", "tests/output/.gitkeep"):
        row(None if f not in tracked else True, f"2a {f}", "" if f in tracked else "not in the house list of five; on with `all` or by name")
    launch = t / ".vscode" / "launch.json"
    row(launch.exists() and "debugpy" in launch.read_text(encoding="utf-8"), "2a .vscode/launch.json (debugpy)")
    pp = (t / "pyproject.toml").read_text(encoding="utf-8")
    row("End-of-line golden" in pp, "2a pyproject description from --description")
    row("Demo Maker" in pp, "2a pyproject authors from the git identity")
    for f in ("golden_tool/__init__.py", "golden_tool/cli.py", "tests/test_version.py", ".github/workflows/release.yml"):
        row(f in tracked, f"2a {f} tracked")
    row(any(f.startswith("scripts/repokit-common/") for f in tracked), "2a repokit-common vendored")
    hooks = [h for h in ("pre-commit", "post-commit", "pre-push") if (t / ".git" / "hooks" / h).exists()]
    row(len(hooks) == 3, "2a hooks installed", ", ".join(hooks))
    row(".repokit.json" in tracked, "the record .repokit.json tracked",
        "written after the last commit, so it is left untracked" if ".repokit.json" not in tracked else "")
    if (t / ".repokit.json").exists():
        rec = json.loads((t / ".repokit.json").read_text(encoding="utf-8"))
        row(bool(rec.get("author", {}).get("name")), "the record's author", repr(rec.get("author")))
        row(rec.get("license") == "gpl-3.0" and len(rec.get("extras", [])) == 5, "the record's licence and extras",
            f"{rec.get('license')}, {rec.get('extras')}")
    status = run(["git", "status", "--short"], t)[1].strip()
    row(None, "working tree after create", status.replace("\n", "; ") or "clean")
    # 2c, the vault
    p = t / "private"
    row((p / ".git").exists(), "2c private/ is its own repository")
    for f in ("CLAUDE.md", "claude/_maps/MOC-project.md", "claude/_oracle/manifest.md",
              "claude/_todo/OPEN-LOOPS.md", "claude/_todo/ACTIVE-WORK.md"):
        hit = list(p.glob(f.replace("MOC-project", "MOC-*")))
        row(bool(hit), f"2c vault {f}")
    prompts = list(p.rglob("*oracle*prompt*")) + list(p.rglob("*bootstrap*"))
    row(bool(prompts), "2c the oracle's first prompt written", ", ".join(x.name for x in prompts[:3]))
    row(None, "2c backlinks", "the stub ships; not run at create (map row: partly)")
    # the project's own tests and its first-commit hook
    rc, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], t)
    row(rc == 0, "the created project's own pytest", out.strip().splitlines()[-1] if out.strip() else "")
    rc, out = run(["sh", ".git/hooks/pre-commit"], t)
    row(rc == 0, "the pre-commit hook on the created tree", f"exit {rc}")
    # the first release (map row 109)
    drafts = list(p.rglob("release*v0.1.0*")) + list(p.rglob("*release-notes*"))
    row(None if not drafts else True, "2b the first release",
        "no notes draft written; /github-release stays the person's (Q261022-06)" if not drafts else drafts[0].name)


def check_github(name):
    gh = lambda *a: run(["gh", *a], REPO, env=os.environ)
    rc, out = gh("label", "list", "--repo", name, "--limit", "50", "--json", "name", "--jq", ".[].name")
    want = {"pinned", "evergreen", "roadmap", "scratchpad", "architecture", "epic", "ideas", "CurrentTask", "NextTask"}
    have = set(out.split())
    row(want <= have, "2b the nine labels", f"missing {sorted(want - have)}" if want - have else "")
    rc, out = gh("issue", "list", "--repo", name, "--state", "all", "--json", "number,title", "--jq", ".[] | \"\\(.number) \\(.title)\"")
    row("1 " in out and "2 " in out, "2b issues #1 and #2", out.strip().replace("\n", "; "))
    owner, repo = name.split("/")
    q = ('query{repository(owner:"%s",name:"%s"){pinnedIssues(first:5){nodes{issue{number}}} '
         'hasDiscussionsEnabled repositoryTopics(first:10){nodes{topic{name}}}}}' % (owner, repo))
    rc, out = gh("api", "graphql", "-f", f"query={q}")
    try:
        r = json.loads(out)["data"]["repository"]
        pins = sorted(n["issue"]["number"] for n in r["pinnedIssues"]["nodes"])
        row(pins == [1, 2], "2b both issues pinned", str(pins))
        row(r["hasDiscussionsEnabled"], "2b discussions enabled")
        topics = [n["topic"]["name"] for n in r["repositoryTopics"]["nodes"]]
        row(None if not topics else True, "2b topics", ", ".join(topics) or "none (the live run passed no --topics)")
    except (ValueError, KeyError, TypeError) as e:
        row(False, "2b the GraphQL read", f"{e.__class__.__name__}: {out[:200]}")
    rc, out = gh("api", f"repos/{name}/environments", "--jq", ".environments[].name")
    row("pypi" in out.split(), "2b the pypi environment", out.strip() or "none")


def main():
    scratch = Path(sys.argv[1]).resolve() / "golden"
    scratch.mkdir(parents=True, exist_ok=True)
    home = scratch / "home"
    (home / ".repokit").mkdir(parents=True, exist_ok=True)
    (home / ".gitconfig").write_text("[user]\n\tname = Demo Maker\n\temail = demo@example.invalid\n", encoding="utf-8")
    (home / ".repokit" / "config.json").write_text(json.dumps(HOUSE, indent=2), encoding="utf-8")
    ENV.update(HOME=str(home), USERPROFILE=str(home))
    rc, out = run([sys.executable, "-m", "repokit", "create", "golden-tool", "--language", "python",
                   "--no-push", "--description", "End-of-line golden"], scratch)
    (scratch / "golden-tool.create.log").write_text(out, encoding="utf-8")
    if rc != 0:
        sys.exit(f"create failed ({rc}); see {scratch / 'golden-tool.create.log'}")
    check_tree(scratch / "golden-tool")
    if len(sys.argv) > 2:
        check_github(sys.argv[2])
    text = "\n".join(rows) + "\n"
    Path(__file__).with_name("results-python.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
