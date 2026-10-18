"""Red-green audit of slice G5's test (2026-10-09): CI from the layers, the
badge, .gitattributes, CHANGELOG. One behaviour reverted per arm, the test run,
the file restored byte for byte (SHA-256 checked), output archived here."""
import datetime
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
T = "tests/test_layers_cli.py -k ci_attributes"
L = "repokit/templates"

M = [
    ("M1 badge never names the workflow", "repokit/repo_manager.py",
     "        workflow = self._ci_workflow()\n        if workflow:", "        workflow = None\n        if workflow:", T, ["ci_attributes"]),
    ("M2 vendored attribute dropped", f"{L}/common/gitattributes.template",
     "scripts/repokit-common/** linguist-vendored", "# (no vendored line)", T, ["ci_attributes"]),
    ("M3 changelog heading wrong", f"{L}/common/CHANGELOG.md.template",
     "## [0.1.0] - $date", "## [0.0.0] - $date", T, ["ci_attributes"]),
    ("M4 python CI no longer runs pytest", f"{L}/layers/languages/python/.github/workflows/ci-python.yml",
     "        python -m pytest tests/ -v", "        python -c 'print(1)'", T, ["ci_attributes"]),
    ("M5 README context loses the badges again", "repokit/repo_manager.py",
     '                "badges": self._generate_badges(language),\n',
     '                "badges": "",\n',
     T, ["ci_attributes"]),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    log = Path(__file__).with_name(f"run-{stamp}.txt")
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out, rows = [f"redgreen G5 -- {stamp}"], []
    only = sys.argv[1:]
    for name, rel, old, new, selector, expect_red in M:
        if only and not any(name.startswith(o + " ") for o in only):
            continue
        f = ROOT / rel
        orig, digest = f.read_bytes(), sha(f)
        nl = "\r\n" if b"\r\n" in orig else "\n"
        text = orig.decode("utf-8").replace("\r\n", "\n")
        assert text.count(old) == 1, f"{name}: anchor not unique/found ({text.count(old)})"
        f.write_bytes(text.replace(old, new).replace("\n", nl).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *shlex.split(selector)],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            f.write_bytes(orig)
        assert sha(f) == digest, f"{name}: restore failed"
        failed = [l.split("::")[-1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        summary = next((l for l in r.stdout.splitlines()[::-1] if "passed" in l or "failed" in l), r.stdout[-200:])
        ok = all(any(e in fl for fl in failed) for e in expect_red)
        rows.append((name, summary.strip("= "), "RED as expected" if ok else "NOT RED -> check", failed))
        out += [f"=== {name} ({rel}) :: {selector}", r.stdout, r.stderr, ""]
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out.append("porcelain unchanged" if before == after else "PORCELAIN CHANGED")
    log.write_text("\n".join(out), encoding="utf-8")
    for name, summary, verdict, failed in rows:
        print(f"{name:46} {summary:42} {verdict}")
    print("tree:", "unchanged" if before == after else "CHANGED", "| log:", log)


if __name__ == "__main__":
    main()
