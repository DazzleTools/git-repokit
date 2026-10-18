"""Red-green audit of slice G4's tests (2026-10-09): the C/C++ builds through
repokit create. Each arm breaks ONE layer file or manifest entry, runs the test
that should notice (a real build), restores the file byte for byte (SHA-256
checked), and archives the output beside this script. Needs the VS toolchain,
as the tests do."""
import datetime
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
T = "tests/test_layers_c_cpp.py"
L = "repokit/templates/layers"

M = [
    ("M1 cmake-app main.cpp broken", f"{L}/archetypes/c-cpp/cmake-app/src/main.cpp",
     "int main(", "int main(int broken_arg_list_missing_type,", f"{T} -k cmake_app", ["cmake_app"]),
    ("M2 minimal source broken", f"{L}/archetypes/c-cpp/minimal/src/__RK_SNAKE__.c",
     "int main(", "int main(int broken_arg_list_missing_type,", f"{T} -k minimal", ["minimal"]),
    ("M3 msbuild main.cpp broken", f"{L}/archetypes/c-cpp/msbuild/src/main.cpp",
     "int main(", "int main(int broken_arg_list_missing_type,", f"{T} -k msbuild", ["msbuild"]),
    ("M4 cmake-lib no longer a stub", f"{L}/manifest.toml",
     '[archetypes."c-cpp/cmake-lib"]\nstub = true', '[archetypes."c-cpp/cmake-lib"]\nlayers = ["archetypes/c-cpp/cmake-lib"]\nlanguages = ["c-cpp"]',
     f"{T} -k stubs", ["stubs"]),
    ("M5 the header's MINOR changed in the layer", f"{L}/languages/c-cpp/include/__RK_SNAKE__/version.h",
     "_VERSION_STRING \"0.1.0\"", "_VERSION_STRING \"0.1.9\"", f"{T} -k 'bytes or cmake_app'", ["cmake_app"]),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    log = Path(__file__).with_name(f"run-{stamp}.txt")
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out, rows = [f"redgreen G4 -- {stamp}"], []
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
        for fl in failed:
            print(f"{'':46} red: {fl}")
    print("tree:", "unchanged" if before == after else "CHANGED", "| log:", log)


if __name__ == "__main__":
    main()
