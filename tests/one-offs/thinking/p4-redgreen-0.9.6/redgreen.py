"""Red-green for 0.9.6: revert each behaviour, the test that pins it must go red.

    python tests/one-offs/thinking/p4-redgreen-0.9.6/redgreen.py

Each case swaps one string in one file (the behaviour, not the API), runs the
named tests, and restores the file from memory in a finally block. Prints one
line per case: RED (the test caught the revert) or GREEN (it did not).
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

CASES = [
    ("the gh login is read before rendering", "repokit/cli.py",
     "            if login:\n                config[\"github_login\"] = login",
     "            if False:\n                config[\"github_login\"] = login",
     "tests/test_github_owner.py::TestOwner::test_github_fills_every_file_with_gh_login"),
    ("the CHANGELOG links use the owner", "repokit/templates/common/CHANGELOG.md.template",
     "https://github.com/$github_org/$project_name/compare", "https://github.com/$github_user/$project_name/compare",
     "tests/test_github_owner.py::TestOwner::test_org_owns_the_urls_and_the_login_owns_codeowners_and_funding"),
    ("CODEOWNERS names the login", "repokit/templates/github/CODEOWNERS.template",
     "*       @$github_user", "*       @$author",
     "tests/test_github_owner.py::TestOwner::test_github_fills_every_file_with_gh_login"),
    ("the pypi licence is the one chosen", "repokit/templates/layers/archetypes/python/pypi/pyproject.toml",
     'license = {text = "__RK_LICENSE__"}', 'license = {text = "GPL-3.0-or-later"}',
     "tests/test_github_owner.py::TestOwner::test_the_manifests_say_the_chosen_licence_and_the_topics"),
    ("the README body is the preset's", "repokit/templates/common/README.md.template",
     "${install_section}${usage_section}## Development", "## Features\n\n- Feature 1\n\n## Development",
     "tests/test_github_owner.py::TestOwner::test_the_manifests_say_the_chosen_licence_and_the_topics"),
    ("the record is written before the first commit", "repokit/repo_manager.py",
     "            self._generate_repokit_config()\n\n            # Create initial commit",
     "            pass\n\n            # Create initial commit",
     "tests/test_github_owner.py::TestOwner::test_the_record_is_committed_with_its_author"),
    ("the record is not a private file", "repokit/defaults.py",
     '    "CLAUDE.md",\n]', '    "CLAUDE.md",\n    ".repokit.json",\n]',
     "tests/test_hook_patterns.py::TestOwnHookOnARealProject::test_a_name_containing_log_is_not_private"),
    ("labels names the referenced labels", "repokit/github_setup.py",
     "for n in (referenced or [])", "for n in ([] or [])",
     "tests/test_readme_blocks.py::test_labels_creates_the_referenced_ones_the_repository_lacks"),
    ("the pypi floor matches requires-python", "repokit/readme_blocks.py",
     '"python/pypi": {"python": "3.10"}', '"python/pypi": {"python": "3.7"}',
     "tests/test_readme_blocks.py::test_pypi_floor_is_the_pyprojects_requires_python"),
    ("keywords come from the topics", "repokit/template_engine.py",
     '"RK_KEYWORDS": ", ".join(json.dumps(str(t)) for t in (context.get("topics") or [])),',
     '"RK_KEYWORDS": "",',
     "tests/test_readme_blocks.py::test_tokens_carry_the_owner_the_licence_and_the_keywords"),
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
            verdict = "RED  " if r.returncode != 0 else "GREEN"
            bad += r.returncode == 0
            print(f"{verdict} {label}")
        finally:
            path.write_bytes(original)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
