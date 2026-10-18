"""Build one 0.7.x version's tree from the final working tree (2026-10-09).

Phase 2 of the repokit revival was built as four slices in one working tree
and never committed on the way. djdarcy wants every version to be its own
commit, and every intermediate commit to be a valid tree (creates projects,
passes its own tests); the shared code lands in v0.7.0 at its final form and
the messages say so. This script copies the final tree's Phase 2 files from
SRC (the main checkout) into DST (a detached worktree) and applies the
version's transforms, so each state is reproducible and reviewable.

Usage: python build_version.py 0.7.N  [--src C:/code/git-repokit] [--dst C:/code/git-repokit__common-pull]

It stages the result in DST (`git add -A` there; DST holds nothing but what
this script copies, and the private/ junction is ignored). It never commits.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROOF = Path("C:/code/git-repokit-common/tests/one-offs/thinking/poc-templates-c-cpp/templates")
LAYERS = "repokit/templates/layers"
CMAKE_WF = f"{LAYERS}/archetypes/c-cpp/cmake-app/.github/workflows"

# Paths that exist in the final tree but belong to a later version.
REMOVE_BEFORE = {
    1: [f"{LAYERS}/archetypes/python/pypi", "tests/one-offs/thinking/g3-redgreen",
        "tests/checklists/v0.7.1__Feature__python-pypi-archetype-default.md"],
    2: ["tests/test_layers_c_cpp.py", "tests/one-offs/thinking/g4-redgreen",
        "tests/checklists/v0.7.2__Feature__c-cpp-archetypes-build.md"],
    3: [f"{LAYERS}/languages/python/.github", f"{CMAKE_WF}/ci-c-cpp.yml",
        "tests/one-offs/thinking/g5-redgreen", "tests/one-offs/thinking/split-0.7.x",
        "tests/checklists/v0.7.3__Feature__ci-per-language-gitattributes-changelog.md"],
}
# The C/C++ files the parity addendum changed (0.7.3): the proof holds the earlier form.
PRE_PARITY = {
    f"{LAYERS}/languages/c-cpp/include/__RK_SNAKE__/version.h": "languages/c-cpp/include/__RK_SNAKE__/version.h",
    f"{LAYERS}/archetypes/c-cpp/cmake-app/src/main.cpp": "archetypes/c-cpp/cmake-app/src/main.cpp",
    f"{LAYERS}/archetypes/c-cpp/msbuild/src/main.cpp": "archetypes/c-cpp/msbuild/src/main.cpp",
    f"{LAYERS}/archetypes/c-cpp/minimal/src/__RK_SNAKE__.c": "archetypes/c-cpp/minimal/src/__RK_SNAKE__.c",
}
SETUPPY_ROW = ("| `python` | `python/setuppy` (`setup.py` + `requirements.txt`: today's Python output) "
               "| `python/pypi`, `python/comfyui`, `python/django`, `python/qt` announced |\n")


def sh(args, cwd, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        sys.exit(f"{' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


def changed_paths(src: Path):
    """Every Phase 2 path in SRC: modified/deleted tracked files and untracked files, minus editor settings."""
    out = sh(["git", "status", "--porcelain", "--untracked-files=all"], src)
    paths = []
    for line in out.splitlines():
        code, path = line[:2], line[3:].strip().strip('"')
        if "/.vscode/" in f"/{path}" or path.startswith(".vscode/"):
            continue
        paths.append((code, path))
    return paths


def cut_function(text: str, name: str) -> str:
    """Remove a method `    def name(` up to the next member at the same indent (or EOF)."""
    m = re.search(rf"^(    (?:@[^\n]*\n    )*def {re.escape(name)}\(.*?)(?=^    (?:@|def )|^class |\Z)",
                  text, re.S | re.M)
    if not m:
        sys.exit(f"function {name} not found")
    return text[:m.start()] + text[m.end():]


def cut_changelog(text: str, keep_upto_minor: int) -> str:
    """Drop every ## [0.7.x] section with x > keep_upto_minor."""
    sections = re.split(r"(?m)^(?=## \[)", text)
    kept = []
    for s in sections:
        m = re.match(r"## \[0\.7\.(\d+)\]", s)
        if m and int(m.group(1)) > keep_upto_minor:
            continue
        kept.append(s)
    return "".join(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--src", default="C:/code/git-repokit")
    ap.add_argument("--dst", default="C:/code/git-repokit__common-pull")
    a = ap.parse_args()
    n = int(a.version.split(".")[2])
    assert a.version.startswith("0.7.") and 0 <= n <= 3
    src, dst = Path(a.src), Path(a.dst)
    if not (dst / ".git").exists():
        sys.exit(f"{dst} is not a worktree")
    if sh(["git", "status", "--porcelain"], dst).strip():
        sys.exit("DST is dirty; commit or clean it first")

    # 1. copy the final tree's Phase 2 paths; mirror the deletions
    for code, rel in changed_paths(src):
        s, d = src / rel, dst / rel
        if code.strip().startswith("D") or not s.exists():
            if d.exists():
                d.unlink()
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    # 2. remove what belongs to a later version
    for upto, rels in REMOVE_BEFORE.items():
        if n < upto:
            for rel in rels:
                p = dst / rel
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()

    # 3. version strings
    for rel in ("pyproject.toml", "repokit/__version__.py"):
        p = dst / rel
        p.write_bytes(p.read_bytes().replace(b"0.7.3", a.version.encode()))

    # 4. CHANGELOG: this version's sections only
    p = dst / "CHANGELOG.md"
    p.write_bytes(cut_changelog(p.read_bytes().decode("utf-8"), n).encode("utf-8"))

    # 5. README
    p = dst / "README.md"
    t = p.read_bytes().decode("utf-8")
    if n < 3:
        t = re.sub(r"(?ms)^CI comes from the layers too:.*?\n\n", "", t, count=1)
    if n < 1:
        t = re.sub(r"(?m)^\| `python` \| `python/pypi`.*\n", SETUPPY_ROW, t, count=1)
    p.write_bytes(t.encode("utf-8"))

    # 6. the manifest: setuppy is python's default until 0.7.1 builds pypi
    if n < 1:
        p = dst / LAYERS / "manifest.toml"
        t = p.read_bytes().decode("utf-8")
        t = t.replace('default = "python/pypi"', 'default = "python/setuppy"')
        t = re.sub(r'(?ms)^\[archetypes\."python/pypi"\]\n.*?\n\n',
                   '[archetypes."python/pypi"]\nstub = true\n'
                   'description = "pyproject.toml with a dynamic version, the package, tests and the '
                   'publish-on-release workflow: the shape of git-repokit-template\'s projects (built in 0.7.1)"\n\n',
                   t, count=1)
        p.write_bytes(t.encode("utf-8"))

    # 7. pre-parity C/C++ files and the un-renamed cmake-app workflow before 0.7.3
    if n < 3:
        for rel, proof_rel in PRE_PARITY.items():
            shutil.copy2(PROOF / proof_rel, dst / rel)
        shutil.copy2(PROOF / "archetypes/c-cpp/cmake-app/.github/workflows/ci.yml", dst / CMAKE_WF / "ci.yml")
    else:
        # 0.7.3 renames it to ci-c-cpp.yml; the earlier build left ci.yml in DST
        (dst / CMAKE_WF / "ci.yml").unlink(missing_ok=True)

    # 8. tests
    p = dst / "tests/test_layers_cli.py"
    t = p.read_bytes().decode("utf-8")
    if n < 3:
        t = cut_function(t, "test_ci_attributes_and_changelog_follow_the_language")
        t = t.replace("ci-c-cpp.yml", "ci.yml")
    if n < 1:
        t = cut_function(t, "test_a_bare_python_is_the_pypi_archetype_that_installs_and_tests")
        t = t.replace('"python/pypi"', '"python/setuppy"')
        t = t.replace('(repo2 / "pyproject.toml").is_file()', '(repo2 / "setup.py").is_file()')
        t = t.replace("Reversed, python is primary: pypi's\n        pyproject, no CMake.",
                      "Reversed, python is primary: setuppy's\n        setup.py, no CMake.")
    p.write_bytes(t.encode("utf-8"))
    if n < 1:
        (dst / "tests/test_cli_integration.py").write_bytes(
            subprocess.run(["git", "show", "HEAD:tests/test_cli_integration.py"], cwd=src,
                           capture_output=True, check=True).stdout)
    if n == 2:
        p = dst / "tests/test_layers_c_cpp.py"
        t = p.read_bytes().decode("utf-8")
        t = re.sub(r"(?m)^        # The project-wide phase is shown by --version like Python's\n"
                   r"        # get_display_version\(\): set it in the generated header before building\.\n"
                   r"        header = repo / \"include\" / \"my_tool\" / \"version\.h\"\n"
                   r"        header\.write_bytes\(.*\n", "", t, count=1)
        t = t.replace('"my-tool ALPHA 0.1.0 (0.1.0_main_", r.stdout)   # project phase, version, the build stamp',
                      '"my-tool 0.1.0 (0.1.0_main_", r.stdout)   # version and the build stamp')
        p.write_bytes(t.encode("utf-8"))

    # 9. stage
    sh(["git", "add", "-A"], dst)
    print(sh(["git", "status", "--short"], dst))
    print(f"built {a.version} in {dst}")


if __name__ == "__main__":
    main()
