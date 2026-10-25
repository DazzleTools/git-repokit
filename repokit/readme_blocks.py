"""The README's and CONTRIBUTING's per-preset sections (0.9.6).

Until 0.9.6 every README said "# Installation instructions here" and
"Feature 1", and CONTRIBUTING was generic text; git-repokit-template's own
README and CONTRIBUTING carried the real commands for a Python package. This
module holds those commands for every built preset, taken from the preset's
own files (its CI workflow, package.json, CMake presets), so a new project's
README says how to install, run, build and test it from the first commit.

`sections(...)` returns the markdown blocks the templates place; an empty
block means the preset has nothing to say there and the heading is left out.
`floors()` is what the badges read; tests/test_readme_blocks.py checks each
floor against the layer file it comes from.
"""
from typing import Dict, List, Optional

# preset -> the minimum runtime its own files declare (badge, prerequisites)
FLOORS: Dict[str, Dict[str, str]] = {
    "python/pypi": {"python": "3.10"},          # pyproject.toml requires-python
    "python/setuppy": {"python": "3.6"},        # setup.py python_requires
    "python/script": {"python": "3.9"},         # the oldest Python its CI runs
    "python/claude-plugin": {"python": "3.10"},  # the oldest Python its CI runs
    "js-ts/node-package": {"node": "20"},       # package.json engines
    "js-ts/script": {"node": "20"},
    "js-ts/claude-plugin": {"node": "20"},
}


def floors(archetype: Optional[str]) -> Dict[str, str]:
    return dict(FLOORS.get(archetype or "", {}))


def _code(*lines: str) -> str:
    return "```bash\n" + "\n".join(lines) + "\n```"


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body}\n\n" if body else ""


def sections(archetype: Optional[str], language: str, name: str, owner: str,
             vendored_common: bool) -> Dict[str, str]:
    """The README's install/usage sections and the development text both
    files use, for one project. Keys: install_section, usage_section,
    prerequisites, setup_block, test_block."""
    snake = name.replace("-", "_")
    clone = [f"git clone https://github.com/{owner}/{name}.git", f"cd {name}"]
    hooks = ["bash scripts/repokit-common/install-hooks.sh"] if vendored_common else []
    a = archetype or ""
    fl = floors(a)
    prereq: List[str] = []
    install = usage = test = ""
    setup = clone

    if a in ("python/pypi", "python/setuppy"):
        prereq = [f"Python {fl['python']}+", "Git"]
        if a == "python/pypi":
            install = _code(f"pip install {name}") + "\n\nFrom source:\n\n" + _code(*clone, 'pip install -e ".[dev]"')
            usage = _code(f"{name} --help", f"python -m {snake} --version")
            setup = clone + ["python -m venv .venv",
                             "source .venv/bin/activate        # Windows: .venv\\Scripts\\activate",
                             'pip install -e ".[dev]"'] + hooks
        else:
            install = _code(*clone, "pip install -e .")
            setup = clone + ["python -m venv .venv",
                             "source .venv/bin/activate        # Windows: .venv\\Scripts\\activate",
                             "pip install -e .", "pip install -r requirements.txt"] + hooks
        test = _code("python -m pytest tests/ -v")
    elif a == "python/script":
        prereq = [f"Python {fl['python']}+", "Git"]
        usage = _code(f"python {name}.py --version")
        setup = clone + hooks
        test = _code("python -m pytest tests/ -v")
    elif a in ("python/claude-plugin", "js-ts/claude-plugin"):
        prereq = ["Claude Code", "Git"] + ([f"Python {fl['python']}+"] if "python" in fl else [f"Node.js {fl['node']}+"])
        install = ("In Claude Code:\n\n"
                   + _code(f"/plugin marketplace add {owner}/{name}", f"/plugin install {name}@{name}"))
        setup = clone + hooks + ["# then, in Claude Code: /plugin marketplace add ./"]
        test = _code("python -m pytest plugin/tests -q") if a.startswith("python") else _code("npm test")
    elif a == "js-ts/node-package":
        prereq = [f"Node.js {fl['node']}+", "Git"]
        install = _code(f"npm install {name}")
        setup = clone + ["npm install", "npm run build"] + hooks
        test = _code("npm test")
    elif a == "js-ts/script":
        prereq = [f"Node.js {fl['node']}+", "Git"]
        usage = _code(f"node {name}.js --version")
        setup = clone + hooks
        test = _code("npm test")
    elif a == "c-cpp/cmake-app":
        prereq = ["CMake", "A C++ compiler (MSVC, GCC or Clang)", "vcpkg (`VCPKG_ROOT` set)", "Git"]
        setup = clone + hooks + [
            "cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake",
            "cmake --build build --config Release"]
        test = _code("ctest --test-dir build -C Release --output-on-failure")
    elif a == "c-cpp/minimal":
        prereq = ["A C compiler (GCC/Clang with make, or MSVC)", "Git"]
        setup = clone + hooks + ["make                # or, on Windows from a Developer Command Prompt: build.bat"]
        usage = _code(f"build/{name} --version")
    elif a == "c-cpp/msbuild":
        prereq = ["Visual Studio 2022 Build Tools (MSBuild, the C++ workload)", "Git"]
        setup = clone + hooks + [f"msbuild {name}.sln -p:Configuration=Debug -p:Platform=x64"]
    else:
        setup = clone + hooks

    return {
        "install_section": _section("Installation", install),
        "usage_section": _section("Usage", usage),
        "prerequisites": "\n".join(f"- {p}" for p in prereq) if prereq else "- Git",
        "setup_block": _code(*setup),
        "test_block": test or "This project has no test suite yet.",
    }
