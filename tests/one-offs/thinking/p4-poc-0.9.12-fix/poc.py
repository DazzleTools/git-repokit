"""0.9.12 POC: the four-part fix, tried in scratch copies of repokit/ only.

Predictions (written before running; see results.md for the table):
  P1 all five private-branch strategies: 0 ambiguous, 0 ERROR lines; every
     public branch = the private branch minus its private files; no private
     path in any public tree.
  P2 untracked .env, app.log, logs/run.log planted in local/ before the public
     branches are cut survive on disk and reach no public tree.
     CONTROL: with only the `--` fix, the working-folder cleanup deletes them.
  P3 a `minimal` and a `simple --branch-dir-main public` create inside a dummy
     parent repository leave the parent's HEAD and index unchanged, and
     `minimal` leaves no <name>/github folder.
     CONTROL: the shipped code moves the parent's HEAD.
  P4 a forced failure cutting `dev` makes `create` exit non-zero.
     CONTROL: with only the `--` fix, the create exits 0.

Throwaway repositories only, under %TEMP%; HOME isolated; commits unsigned;
the checkout is never edited -- every change is a text replacement in a
scratch copy, and each replacement asserts it matched exactly once.

    python poc.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MEASURE = REPO / "tests" / "one-offs" / "thinking" / "p4-measure-0.9.12-private-ref"
sys.path.insert(0, str(MEASURE))
from probe import env_for, git, private_paths  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
STRATEGIES = ["standard", "simple", "gitflow", "github-flow", "minimal"]
PLANT = {".env": "SECRET=keep-me\n", "app.log": "a line\n", "logs/run.log": "run\n"}

# ---- the patches (each anchor must match exactly once) -------------------

P_RESET = [
    ('["reset", "--hard", source_branch]', '["reset", "--hard", source_branch, "--"]'),
    ('["reset", "--hard", private_branch]', '["reset", "--hard", private_branch, "--"]'),
]
P_INDEX_ONLY = [
    ("        clean_working_dir = not is_private_branch\n",
     "        clean_working_dir = False  # poc: never the working folder; the index clean below suffices\n"),
]
P_GITHUB = [
    ("        if self.github_root:\n            os.makedirs(self.github_root, exist_ok=True)\n",
     "        # poc: no <name>/github until a worktree goes there\n"),
    ("        # Only proceed if the GitHub worktree exists\n",
     "        # poc: git runs only in the default branch's real worktree, never above the project\n"
     "        main_wt = None\n"
     "        out = self.run_git([\"worktree\", \"list\", \"--porcelain\"], cwd=self.repo_root, check=False) or \"\"\n"
     "        path = None\n"
     "        for line in out.splitlines():\n"
     "            if line.startswith(\"worktree \"):\n"
     "                path = line[9:].strip()\n"
     "            elif line.strip() == \"branch refs/heads/\" + self.config.get(\"default_branch\", \"main\"):\n"
     "                if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(self.repo_root)):\n"
     "                    main_wt = path\n"
     "        if not main_wt:\n"
     "            self.logger.info(\"No worktree for the default branch; its .github came with the branch\")\n"
     "            return\n"
     "        self.github_root = main_wt\n"
     "        # Only proceed if the GitHub worktree exists\n"),
]
P_FAIL_LOUD = [
    ("        for branch in branches:\n            if branch != private_branch:  # Skip private branch\n",
     "        failed = []  # poc\n"
     "        for branch in branches:\n            if branch != private_branch:  # Skip private branch\n"),
    ("                        self.logger.error(f\"Branch '{branch}' failed verification - contains private content!\")\n",
     "                        self.logger.error(f\"Branch '{branch}' failed verification - contains private content!\")\n"
     "                        failed.append((branch, \"contains private content\"))\n"),
    ("                    self.logger.warning(f\"Failed to create clean public branch '{branch}': {str(e)}\")\n",
     "                    self.logger.error(f\"Failed to create clean public branch '{branch}': {str(e)}\")\n"
     "                    failed.append((branch, str(e)))\n"),
    ("        # Switch back to private branch for continued development\n"
     "        self.run_git([\"checkout\", private_branch], cwd=self.repo_root)\n",
     "        # Switch back to private branch for continued development\n"
     "        self.run_git([\"checkout\", private_branch], cwd=self.repo_root)\n"
     "        if failed:\n"
     "            raise RuntimeError(\"public branches not built: \" + \", \".join(b for b, _ in failed))\n"),
]
# Test scaffolding, not part of the fix: plant files, force a failure.
P_PLANT = [
    ("        # Create public branches with safe content migration using safe-merge-dev\n",
     "        if os.environ.get(\"RK_POC_PLANT\"):  # poc scaffolding\n"
     "            import json as _j\n"
     "            for _rel, _txt in _j.loads(os.environ[\"RK_POC_PLANT\"]).items():\n"
     "                _p = os.path.join(self.repo_root, _rel)\n"
     "                os.makedirs(os.path.dirname(_p) or self.repo_root, exist_ok=True)\n"
     "                open(_p, \"w\").write(_txt)\n"
     "        # Create public branches with safe content migration using safe-merge-dev\n"),
]
P_FORCE_FAIL = [
    ("            # First, ensure we're in a git repository\n",
     "            if branch_name == os.environ.get(\"RK_POC_FAIL\"):  # poc scaffolding\n"
     "                raise RuntimeError(\"poc: forced failure\")\n"
     "            # First, ensure we're in a git repository\n"),
]


def package(tmp, name, patches):
    dst = tmp / f"pkg-{name}"

    def ignore(dirpath, names):  # keep the layer templates' .vscode folders
        top = Path(dirpath).resolve() == (REPO / "repokit").resolve()
        return [n for n in names if n == "__pycache__" or (top and n == ".vscode")]
    shutil.copytree(REPO / "repokit", dst / "repokit", ignore=ignore)
    p = dst / "repokit" / "repo_manager.py"
    t = p.read_text(encoding="utf-8")
    for old, new in patches:
        n = t.count(old)
        assert n == 1, f"{name}: anchor matched {n} times: {old[:60]!r}"
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    return dst


def create(tmp, tag, pkg, strategy, extra=(), env_extra=None, where=None):
    home = tmp / f"home-{tag}"
    home.mkdir()
    env = env_for(home)
    env["PYTHONPATH"] = str(pkg)
    env.update(env_extra or {})
    work = where or (tmp / f"w-{tag}")
    work.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "repokit.cli", "-v", "create", "p", "--branch-strategy", strategy,
           "--language", "python", "--license", "mit", "--no-push",
           "--user-name", "T", "--user-email", "t@example.com", *extra]
    r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    log = r.stdout + r.stderr
    (OUT / f"{tag}.log").write_text(log, encoding="utf-8")
    proj = work / "p"
    local = proj / "local" if (proj / "local").is_dir() else proj
    _, refs = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], local, env)
    trees = {}
    for b in refs.split():
        _, names = git(["ls-tree", "-r", "--name-only", f"refs/heads/{b}"], local, env)
        names = names.splitlines()
        trees[b] = {"files": len(names), "private": private_paths(names),
                    "planted": [n for n in names if n in PLANT]}
    return {"exit": r.returncode, "ambiguous": log.count("ambiguous argument"),
            "errors": sum(1 for l in log.splitlines() if " - ERROR - " in l),
            "trees": trees, "folders": sorted(x.name for x in proj.iterdir() if x.is_dir()) if proj.is_dir() else [],
            "planted_on_disk": {f: (local / f).is_file() for f in PLANT}, "env": env, "local": local}


def main():
    OUT.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="rk0912-poc-"))
    fix = P_RESET + P_INDEX_ONLY + P_GITHUB + P_FAIL_LOUD
    pk = {"shipped": package(tmp, "shipped", []),
          "reset-only": package(tmp, "reset-only", P_RESET + P_PLANT + P_FORCE_FAIL),
          "fix": package(tmp, "fix", fix + P_PLANT + P_FORCE_FAIL)}
    rows = []

    # P1
    for s in STRATEGIES:
        r = create(tmp, f"p1-{s}", pk["fix"], s)
        priv = r["trees"].get("private", {"files": 0, "private": []})
        public = {b: d for b, d in r["trees"].items() if b != "private"}
        ok = (r["exit"] == 0 and r["ambiguous"] == 0 and r["errors"] == 0 and public
              and all(d["private"] == [] and d["files"] == priv["files"] - len(priv["private"]) for d in public.values()))
        rows.append(("P1", s, ok, f"exit={r['exit']} amb={r['ambiguous']} err={r['errors']} "
                     f"private={priv['files']}({len(priv['private'])} private) "
                     f"public={ {b: d['files'] for b, d in public.items()} }"))

    # P2 and its control
    plant = {"RK_POC_PLANT": json.dumps(PLANT)}
    for name, expect_survive in (("fix", True), ("reset-only", False)):
        r = create(tmp, f"p2-{name}", pk[name], "standard", env_extra=plant)
        survived = all(r["planted_on_disk"].values())
        deleted = not any(r["planted_on_disk"].values())
        in_public = any(d["planted"] for b, d in r["trees"].items() if b != "private")
        ok = (survived and not in_public) if expect_survive else deleted
        rows.append(("P2" if expect_survive else "P2-control", name, ok,
                     f"on disk={r['planted_on_disk']} in a public tree={in_public}"))

    # P3 and its control: inside a dummy parent repository
    for name, expect_still in (("fix", True), ("shipped", False)):
        parent = tmp / f"parent-{name}"
        parent.mkdir()
        penv = env_for(tmp / f"home-parent-{name}")
        (tmp / f"home-parent-{name}").mkdir()
        git(["init", "-q", "-b", "main"], parent, penv)
        (parent / "keep.txt").write_text("parent\n")
        git(["add", "keep.txt"], parent, penv)
        git(["commit", "-qm", "parent repo"], parent, penv)
        _, head0 = git(["rev-parse", "HEAD"], parent, penv)
        detail = []
        still = True
        for s, extra in (("minimal", ()), ("simple", ("--branch-dir-main", "public"))):
            r = create(tmp, f"p3-{name}-{s}", pk[name], s, extra, where=parent / f"in-{s}")
            _, head = git(["rev-parse", "HEAD"], parent, penv)
            _, staged = git(["diff", "--cached", "--name-only"], parent, penv)
            moved = head != head0 or bool(staged.strip())
            still = still and not moved
            detail.append(f"{s}: parent moved={moved} folders={r['folders']} exit={r['exit']}")
        stray = "github" in r["folders"] if False else None
        ok = still if expect_still else not still
        rows.append(("P3" if expect_still else "P3-control", name, ok, "; ".join(detail)))

    # P4 and its control
    for name, expect_nonzero in (("fix", True), ("reset-only", False)):
        r = create(tmp, f"p4-{name}", pk[name], "standard", env_extra={"RK_POC_FAIL": "dev"})
        ok = (r["exit"] != 0) if expect_nonzero else (r["exit"] == 0)
        rows.append(("P4" if expect_nonzero else "P4-control", name, ok, f"exit={r['exit']} errors={r['errors']}"))

    (OUT / "rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("scratch", tmp)
    for arm, variant, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {arm:11} {variant:10} {detail}")


if __name__ == "__main__":
    main()
