"""Red-green audit of slice G3's tests (2026-10-09): the pypi archetype and the
default flip. Same shape as g2-redgreen: one behaviour reverted per arm, the
targeted tests run, the file restored byte for byte (SHA-256 checked), full
output archived beside this script."""
import datetime
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CLI = "tests/test_layers_cli.py"

M = [
    ("M1 default flipped back to setuppy", "repokit/templates/layers/manifest.toml",
     'default = "python/pypi"', 'default = "python/setuppy"',
     f"{CLI} -k 'bare_python'", ["bare_python"]),
    ("M2 the language key no longer follows the archetype", "repokit/repo_manager.py",
     '        self.config["language"] = resolution.languages[0] if resolution.languages else layers.GENERIC',
     '        pass',
     f"{CLI} -k 'setuppy_keeps'", ["setuppy_keeps"]),
    ("M3 the version module loses its app name", "repokit/templates/layers/archetypes/python/pypi/__RK_SNAKE__/_version.py",
     '__app_name__ = "__RK_PROJECT__"', '__app_name__ = "project"',
     f"{CLI} -k 'bare_python'", ["bare_python"]),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    log = Path(__file__).with_name(f"run-{stamp}.txt")
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out, rows = [f"redgreen G3 -- {stamp}"], []
    for name, rel, old, new, selector, expect_red in M:
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
        print(f"{name:52} {summary:40} {verdict}")
        for fl in failed:
            print(f"{'':52} red: {fl}")
    print("tree:", "unchanged" if before == after else "CHANGED", "| log:", log)


if __name__ == "__main__":
    main()
