"""Red-green audit for 0.10.3 (private modes and promotion).

Each mutant reverts one behaviour in a source file (never its interface),
runs the named tests, and expects each named test to FAIL; the file is then
restored from the bytes read first, and a copy is kept in BACKUP before any
edit (a hard kill is recoverable: copy them back). Safety (Critical Rule 1b):
the tests create projects under tmp_path with GIT_CEILING_DIRECTORIES and
push only to a bare remote under tmp_path; no mutant here can reach outside.

    python redgreen.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BACKUP = Path(__file__).resolve().parent / "backup"
PM = "tests/test_private_modes.py"
PK = "tests/test_packaging.py"
RM = "repokit/repo_manager.py"
DF = "repokit/defaults.py"
PY = "pyproject.toml"

MUTANTS = [
    ("R1 old default (branch)", RM,
     'return ("branch" if config.get("is_adoption") else "nested-branch"), None',
     'return "branch", None',
     [f"{PM}::test_the_default_mode_follows_the_strategy_and_the_command",
      f"{PM}::test_nested_branch_is_recorded_and_keeps_private_its_own_repository"]),
    ("R2 no refusal", RM,
     '    if asked in ("nested-branch", "branch") and not private_branch:\n',
     '    if False:\n',
     [f"{PM}::test_a_branch_mode_without_a_private_branch_is_refused_with_the_fixes",
      f"{PM}::test_the_repo_manager_refuses_it_too",
      f"{PM}::test_create_refuses_a_branch_mode_on_main_only_and_writes_nothing"]),
    ("R3 ignore lines kept", RM,
     "            drop = {form for name in self.promoted",
     "            drop = set() or {form for name in []",
     [f"{PM}::test_the_private_branch_gitignore_drops_the_promoted_lines",
      f"{PM}::test_a_plain_add_on_private_commits_conversations_and_revisions_but_not_run_logs"]),
    ("R4 local excludes keep revisions/", RM,
     "                if p.split(\"/\", 1)[0] not in self.promoted or not p or p.startswith(\"#\")",
     "                if True",
     [f"{PM}::test_a_plain_add_on_private_commits_conversations_and_revisions_but_not_run_logs"]),
    ("R5 no promotion commit", RM,
     "        self._promote_record_folders()\n", "\n",
     [f"{PM}::test_the_record_folders_are_tracked_on_private_and_on_no_public_branch"]),
    ("R6 nested-branch loses the vault", DF,
     'VAULT_MODES = ("nested", "nested-branch")', 'VAULT_MODES = ("nested",)',
     [f"{PM}::test_nested_branch_is_recorded_and_keeps_private_its_own_repository"]),
    ("R7 logs/ ignores nothing", RM,
     "commit a chosen log with `git add -f`.\\n*.log\\n\")",
     "commit a chosen log with `git add -f`.\\n\")",
     [f"{PM}::test_a_plain_add_on_private_commits_conversations_and_revisions_but_not_run_logs"]),
    ("R8 no branch-mode warning", RM,
     '            if self.private_mode == "branch" and not self.config.get("is_adoption", False):\n                self.logger.warning(',
     '            if False:\n                self.logger.warning(',
     [f"{PM}::test_branch_mode_is_warned_recorded_and_tracks_private_on_the_private_branch_only"]),
    ("R9 exposure without promoted", DF,
     '    if mode != "nested":\n        ranks.update(',
     '    if False:\n        ranks.update(',
     [f"{PM}::test_each_mode_records_where_private_work_sits_on_the_continuum",
      f"{PM}::test_nested_branch_is_recorded_and_keeps_private_its_own_repository"]),
    ("R10 ranks reordered", DF,
     '"shared": 1, "public": 2}', '"shared": 2, "public": 1}',
     [f"{PM}::test_the_exposure_continuum_has_the_agreed_ranks"]),
    ("R11 branch mode keeps private/ ignored", RM,
     '            if mode == "branch":\n                self.promoted.append("private")',
     '            if False:\n                self.promoted.append("private")',
     [f"{PM}::test_branch_mode_is_warned_recorded_and_tracks_private_on_the_private_branch_only"]),
    ("R12 dependencies dropped", PY, '  "dazzle-loglib>=0.3.3",\n', "",
     [f"{PK}::test_the_dazzlelib_stack_is_a_declared_dependency"]),
]


def run_tests(ids):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ids],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    failed = set()
    for line in r.stdout.splitlines():
        if line.startswith(("FAILED ", "ERROR ")):
            failed.add(line.split(" ", 1)[1].split(" - ")[0].strip())
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return r.returncode, failed, last


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    BACKUP.mkdir(exist_ok=True)
    names = sorted({m[1] for m in MUTANTS})
    originals = {}
    for n in names:
        originals[n] = (ROOT / n).read_bytes()
        (BACKUP / n.replace("/", "__")).write_bytes(originals[n])
    results = []
    try:
        for label, fname, old, new, ids in MUTANTS:
            raw = originals[fname]
            eol = b"\r\n" if b"\r\n" in raw else b"\n"
            o, nw = old.encode().replace(b"\n", eol), new.encode().replace(b"\n", eol)
            if raw.count(o) != 1:
                results.append((label, "ANCHOR", f"found {raw.count(o)} times"))
                continue
            (ROOT / fname).write_bytes(raw.replace(o, nw))
            try:
                rc, failed, last = run_tests(ids)
            finally:
                (ROOT / fname).write_bytes(raw)
            # a parametrized test fails as "<id>[<params>]"; any failed case counts
            stayed = [i.split("::")[1] for i in ids
                      if not any(f == i or f.startswith(i + "[") for f in failed)]
            results.append((label, "RED" if not stayed else "PARTIAL" if len(stayed) < len(ids) else "SURVIVED",
                            last if not stayed else f"stayed green: {stayed}"))
        rc, failed, last = run_tests(sorted({i for m in MUTANTS for i in m[4]}))
        results.append(("restored", "GREEN" if rc == 0 else "NOT GREEN", last))
    finally:
        for n in names:
            (ROOT / n).write_bytes(originals[n])
    for row in results:
        print(" | ".join(row))
    for n in names:
        assert (ROOT / n).read_bytes() == (BACKUP / n.replace("/", "__")).read_bytes(), f"{n} not restored"
    print("sources restored byte-identical to backup")


if __name__ == "__main__":
    main()
