"""Red-green for 0.9.7: revert each badge or README rule, its test must go red.

    python tests/one-offs/thinking/p4-badges-0.9.7/redgreen.py

Each case swaps one string in one file, runs the named test, and restores
the file from memory in a finally block.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
B = "repokit/badges.py"
T = "tests/test_badges.py::"

CASES = [
    ("platform closes the pypi line", B,
     '"installs", "platform"],\n    "github"', '"platform", "installs"],\n    "github"',
     T + "test_the_pypi_template_in_the_house_order_platform_last"),
    ("the version shows once", B,
     '"pypi": ["pypi-version", "release-date"', '"pypi": ["pypi-version", "release-version", "release-date"',
     T + "test_the_version_shows_once"),
    ("comfyui keeps its own order", B,
     '"comfyui": ["runtime", "comfyui-registry", "release-version"',
     '"comfyui": ["runtime", "release-version", "comfyui-registry"',
     T + "test_comfyui_keeps_its_own_order_and_makes_no_platform_claim"),
    ("a hand-picked list is sorted into the order", B,
     "names = sorted(dict.fromkeys(names), key=lambda n: order.index(n) if n in order else len(order))",
     "names = list(dict.fromkeys(names))",
     T + "test_a_hand_picked_list_renders_in_the_house_order"),
    ("CI never starts a row alone", B,
     "if ci == \"off\" or (others and others % ROW == 0):", "if ci == \"off\":",
     T + "test_ci_fills_a_row_but_never_starts_one_alone"),
    ("a badge with no value is left out", B,
     "        if n == \"ci\" and not values.get(\"ci\"):\n            continue\n", "",
     T + "test_no_ci_file_no_floor_no_licence_means_no_badge"),
    ("the licence contrasts its neighbours", B,
     "colours[i] = house if house not in neighbours else next(", "colours[i] = house if True else next(",
     T + "test_the_licence_takes_its_house_colour_unless_a_neighbour_has_it"),
    ("MIT's house colour is yellow", B,
     '"mit": ("MIT", "https://opensource.org/licenses/MIT", "yellow"),',
     '"mit": ("MIT", "https://opensource.org/licenses/MIT", "green"),',
     T + "test_the_licence_takes_its_house_colour_unless_a_neighbour_has_it"),
    ("a person's own templates are read", B,
     "templates = {**TEMPLATES, **(templates or {})}", "templates = dict(TEMPLATES)",
     T + "test_a_persons_own_template_and_badge_type"),
    ("the README has no self-acknowledgement and ends with License",
     "repokit/templates/common/README.md.template",
     "${support_line}## License", "${support_line}## License\n\n$license_line\n\n## Acknowledgements\n\n$author",
     "tests/test_github_owner.py::TestOwner::test_the_readme_ends_the_way_the_house_projects_do"),
    ("or-later licences are named so", "repokit/licenses/__init__.py",
     'return f"{base} or later" if base else None', "return base",
     "tests/test_readme_blocks.py::test_licence_titles_come_from_the_catalogue"),
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
