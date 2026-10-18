"""Measure: does setuptools package-data "templates/**/*" ship dotfiles in a wheel?

Builds the same throwaway package three ways and lists each wheel.
Known-answer case: a plain file (templates/plain.txt) must ship under every variant.
Decision: whether the Phase 2 layer tree (which holds .gitignore.rkappend, .repokit-common.toml,
.github/workflows/ci.yml) needs a packaging change (G2 unit U2.3).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

FILES = [  # the shapes the layer tree will hold
    "templates/plain.txt",                           # known-answer: always ships
    "templates/.repokit-common.toml",                # dotfile at depth 1
    "templates/layers/python/.gitignore.rkappend",   # dotfile at depth 3
    "templates/layers/c/.github/workflows/ci.yml",   # plain file under a dot DIRECTORY
    "templates/layers/c/.github/dependabot.yml",
]

VARIANTS = {
    "A current: package-data templates/**/*": dict(
        pkgdata='"probe" = ["templates/**/*"]', manifest=None, include=None),
    "B explicit dot globs": dict(
        pkgdata='"probe" = ["templates/**/*", "templates/**/.*", "templates/**/.*/**/*", "templates/**/.*/*"]',
        manifest=None, include=None),
    "C MANIFEST.in graft + include-package-data": dict(
        pkgdata=None, manifest="graft src/probe/templates\n", include="include-package-data = true"),
}


def build(variant, spec, root):
    d = root / variant[:1]
    (d / "src/probe").mkdir(parents=True)
    (d / "src/probe/__init__.py").write_text("")
    for f in FILES:
        p = d / "src/probe" / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    tool = ""
    if spec["pkgdata"]:
        tool += f"[tool.setuptools.package-data]\n{spec['pkgdata']}\n"
    if spec["include"]:
        tool = f"[tool.setuptools]\n{spec['include']}\n" + tool
    (d / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools>=62.3", "wheel"]\nbuild-backend = "setuptools.build_meta"\n'
        '[project]\nname = "probe"\nversion = "0.0.1"\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n' + tool)
    if spec["manifest"]:
        (d / "MANIFEST.in").write_text(spec["manifest"])
    out = d / "dist"
    r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(d)],
                       capture_output=True, text=True)
    if r.returncode:
        return None, r.stderr[-800:]
    whl = next(out.glob("*.whl"))
    names = {n.split("probe/", 1)[1] for n in zipfile.ZipFile(whl).namelist() if n.startswith("probe/templates/")}
    return names, ""


def main():
    import setuptools
    print("setuptools", setuptools.__version__, "python", sys.version.split()[0])
    root = Path(tempfile.mkdtemp(prefix="pkgdata-"))
    try:
        for variant, spec in VARIANTS.items():
            names, err = build(variant, spec, root)
            if names is None:
                print(f"{variant}: BUILD FAILED {err}")
                continue
            shipped = [f for f in FILES if f in names]
            missing = [f for f in FILES if f not in names]
            known = "templates/plain.txt" in names
            print(f"{variant}: shipped {len(shipped)}/{len(FILES)}; known-answer plain.txt={'ok' if known else 'MISSING'}; missing={missing}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
