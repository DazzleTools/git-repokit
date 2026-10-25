"""The lowest Python git-repokit runs on (2026-10-25; djdarcy: "if we can use
older version of python that's great, but if not then we'll use what we know
works and that becomes the new floor").

    python tests/one-offs/thinking/p4-measure-python-floor/measure.py PY [PY ...]

For each interpreter PY (a path):
  1. syntax: compile every repokit/*.py in memory (nothing written);
  2. install: a fresh venv in a temp folder, `pip install <this repo>` plus
     tomli where the interpreter has no tomllib (as the planned
     `tomli; python_version < "3.11"` dependency would);
  3. run: `repokit --version`, a python create and a js-ts create, unsigned,
     stdin closed, in a temp folder;
  4. the unit tests against this source (pytest in the venv,
     PYTHONDONTWRITEBYTECODE so no bytecode lands in the repo).
Prints one line per step per interpreter and a summary table.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENV = dict(os.environ, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false",
           GIT_CONFIG_KEY_1="tag.gpgsign", GIT_CONFIG_VALUE_1="false", PYTHONDONTWRITEBYTECODE="1",
           REPOKIT_COMMON_SOURCE=str(REPO.parent / "git-repokit-common"))


def run(cmd, cwd=None, env=ENV, timeout=600):
    r = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


SYNTAX = r'''
import sys, pathlib
bad = []
for p in pathlib.Path(sys.argv[1], "repokit").rglob("*.py"):
    if "_vendor" in p.parts and "tests" in p.parts:
        continue
    try:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    except SyntaxError as e:
        bad.append(f"{p.relative_to(sys.argv[1])}:{e.lineno}: {e.msg}")
print("\n".join(bad) if bad else "ok")
'''


def measure(py: str):
    row = {"python": py}
    rc, out = run([py, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    row["version"] = out.splitlines()[-1] if rc == 0 else "?"
    rc, out = run([py, "-c", SYNTAX, str(REPO)])
    row["syntax"] = "ok" if out == "ok" else "FAIL"
    print(f"[{row['version']}] syntax: {out[:600]}")
    with tempfile.TemporaryDirectory(prefix="rkpy") as tmp:
        venv = Path(tmp, "v")
        rc, out = run([py, "-m", "venv", str(venv)])
        vpy = str(venv / ("Scripts" if os.name == "nt" else "bin") / "python")
        if rc != 0:
            row["install"] = "venv FAIL"
            print(f"[{row['version']}] venv: {out[-300:]}")
            return row
        run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        need_tomli = run([vpy, "-c", "import tomllib"])[0] != 0
        extra = ["tomli>=1.1"] if need_tomli else []
        # pytest and python-dotenv: the suite's own needs (tests/test_utils.py imports dotenv)
        rc, out = run([vpy, "-m", "pip", "install", "-q", str(REPO), "pytest", "python-dotenv", *extra],
                      timeout=900)
        row["install"] = "ok" if rc == 0 else "FAIL"
        print(f"[{row['version']}] install (tomli {'added' if need_tomli else 'not needed'}): "
              f"{'ok' if rc == 0 else out[-800:]}")
        if rc != 0:
            return row
        scripts = venv / ("Scripts" if os.name == "nt" else "bin")
        rk = str(scripts / ("repokit.exe" if os.name == "nt" else "repokit"))
        rc, out = run([rk, "--version"])
        row["version_cmd"] = out.splitlines()[-1] if rc == 0 else "FAIL"
        work = Path(tmp, "w")
        work.mkdir()
        home = Path(tmp, "home")
        home.mkdir()
        (home / ".gitconfig").write_text("[user]\n\tname = Floor Test\n\temail = floor@example.invalid\n", encoding="utf-8")
        env = dict(ENV, HOME=str(home), USERPROFILE=str(home))
        for lang in ("python", "js-ts"):
            rc, out = run([rk, "create", f"f-{lang}", "--language", lang, "--license", "mit", "--no-push"],
                          cwd=work, env=env)
            ok = rc == 0 and (work / f"f-{lang}" / "README.md").is_file()
            row[f"create_{lang}"] = "ok" if ok else "FAIL"
            print(f"[{row['version']}] create {lang}: {'ok' if ok else out[-800:]}")
        rc, out = run([vpy, "-m", "pytest", "-q", "-m", "unit", "-p", "no:cacheprovider", "-x"],
                      cwd=REPO, env=dict(env, PYTHONPATH=""), timeout=900)
        last = out.splitlines()[-1] if out else ""
        row["unit_tests"] = last
        print(f"[{row['version']}] unit tests: {last if rc == 0 else out[-1500:]}")
    return row


def main():
    rows = [measure(py) for py in sys.argv[1:]]
    keys = ["version", "syntax", "install", "version_cmd", "create_python", "create_js-ts", "unit_tests"]
    print("\n| " + " | ".join(keys) + " |\n|" + "---|" * len(keys))
    for r in rows:
        print("| " + " | ".join(str(r.get(k, "")) for k in keys) + " |")


if __name__ == "__main__":
    main()
