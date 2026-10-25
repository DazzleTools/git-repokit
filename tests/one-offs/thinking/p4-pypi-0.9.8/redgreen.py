"""Red-green for 0.9.8: revert each packaging rule, its test must go red.

    python tests/one-offs/thinking/p4-pypi-0.9.8/redgreen.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
P = "tests/test_packaging.py::"

CASES = [
    ("the distribution is git-repokit", "pyproject.toml", 'name = "git-repokit"', 'name = "repokit"',
     P + "test_the_distribution_is_named_for_its_trusted_publisher"),
    ("the floor is 3.10", "pyproject.toml", 'requires-python = ">=3.10"', 'requires-python = ">=3.7"',
     P + "test_the_python_floor_is_the_measured_one_and_tomli_covers_it"),
    ("tomli covers 3.10", "pyproject.toml", "\"tomli>=1.1; python_version < '3.11'\",", "",
     P + "test_the_python_floor_is_the_measured_one_and_tomli_covers_it"),
    ("the licence is an SPDX string", "pyproject.toml", 'license = "MIT"', 'license = {text = "MIT"}',
     P + "test_the_licence_is_declared_the_pep_639_way"),
    ("setuptools 77 for PEP 639", "pyproject.toml", 'requires = ["setuptools>=77", "wheel"]',
     'requires = ["setuptools>=61", "wheel"]', P + "test_the_licence_is_declared_the_pep_639_way"),
    ("setup.py is a shim", "setup.py", "setup()\n", 'setup(name="repokit")\n', P + "test_setup_py_is_only_a_shim"),
    ("publish runs on a published release", ".github/workflows/publish.yml", "types: [published]",
     "types: [created]", P + "test_publish_runs_on_a_release_through_the_pypi_environment"),
    ("publish runs the leak check", ".github/workflows/publish.yml",
     "run: python scripts/check_dist_no_leak.py dist/", "run: echo skipped",
     P + "test_publish_runs_on_a_release_through_the_pypi_environment"),
    ("the leak check refuses private/", "scripts/check_dist_no_leak.py",
     'FORBIDDEN_DIRS = {"private", "convos"', 'FORBIDDEN_DIRS = {"convos"',
     P + "test_the_leak_check_refuses_vault_and_local_only_paths"),
    ("the preset writes the SPDX field", "repokit/template_engine.py",
     "\"RK_LICENSE_FIELD\": (f'license = \"{context[\"license_spdx\"]}\"' if context.get(\"license_spdx\") else \"\"),",
     "\"RK_LICENSE_FIELD\": \"\",",
     "tests/test_readme_blocks.py::test_tokens_carry_the_owner_the_licence_and_the_keywords"),
    ("a file licence makes no SPDX claim", "repokit/template_engine.py",
     "if context.get(\"license_spdx\") else \"\"),", "if True else \"\"),",
     "tests/test_readme_blocks.py::test_a_file_licence_ships_its_file_without_an_spdx_claim"),
]


def main():
    bad = 0
    for label, rel, old, new, test in CASES:
        path = REPO / rel
        original = path.read_bytes()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            print(f"SKIP  {label}: anchor found {text.count(old)} times in {rel}")
            bad += 1
            continue
        try:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test],
                               cwd=REPO, capture_output=True, text=True)
            bad += r.returncode == 0
            print(f"{'RED  ' if r.returncode else 'GREEN'} {label}")
        finally:
            path.write_bytes(original)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
