"""0.9.7: README badges in the house's shape (repokit/badges.py).

The rules come from an audit of the house's 107 projects and djdarcy's
answers (2026-10-25): the templates' members and order, Platform closing
the line, the release shown once, CI as a filler, and the licence's colour
contrasting its neighbours.
"""
import re

import pytest

from repokit import badges

VALUES = {
    "owner": "Org", "repo": "tool", "repo_lower": "tool", "dist": "tool", "python": "3.10", "node": "",
    "ci": "ci-python.yml", "gist_user": "me", "gist": "abc", "pages": "org",
    "platform_link": "docs/platform-support.md",
    **badges.license_values("gpl-3.0", "GPL-3.0"),
}


def ids(rendered):
    """The badge alts in order, as a compact list."""
    return [re.match(r"\[!\[([^\]]*)\]", line).group(1) for line in rendered.splitlines()]


def test_the_pypi_template_in_the_house_order_platform_last():
    out = badges.render(badges.resolve("pypi", None), VALUES)
    assert ids(out) == ["PyPI", "Release Date", "PyPI Downloads", "CI", "Python 3.10+", "License: GPL v3",
                        "GitHub Discussions", "Installs", "Platform"]


def test_the_preset_picks_the_template():
    assert badges.resolve(None, "python/pypi")[0] == "pypi-version"
    assert badges.resolve(None, "js-ts/node-package")[0] == "release-version"


def test_the_version_shows_once():
    for name in badges.TEMPLATES:
        names = badges.resolve(name, None)
        assert not ({"pypi-version", "release-version"} <= set(names)), name


def test_comfyui_keeps_its_own_order_and_makes_no_platform_claim():
    names = badges.resolve("comfyui", None)
    assert names[:3] == ["runtime", "comfyui-registry", "release-version"]
    assert "platform" not in names


def test_a_hand_picked_list_renders_in_the_house_order():
    out = badges.render(badges.resolve("platform,license,python", None), VALUES)
    assert ids(out) == ["Python 3.10+", "License: GPL v3", "Platform"]


def test_ci_fills_a_row_but_never_starts_one_alone():
    seven = badges.render(["release-version", "ci", "runtime", "license", "discussions", "installs", "platform"], VALUES)
    assert "CI" in ids(seven)  # six others: CI completes the row
    names = ["pypi-version", "release-date", "downloads", "ci", "runtime", "license", "discussions",
             "platform"]  # seven others fill row one: CI would start row two alone
    others = [n for n in names if n != "ci"]
    assert len(others) == badges.ROW
    assert "CI" not in ids(badges.render(names, VALUES))
    assert "CI" in ids(badges.render(names, VALUES, ci="on"))
    assert "CI" not in ids(badges.render(["ci", "runtime"], VALUES, ci="off"))


def test_no_ci_file_no_floor_no_licence_means_no_badge():
    bare = {**VALUES, "ci": "", "python": "", "license_badge": ""}
    assert ids(badges.render(["ci", "runtime", "license", "platform"], bare)) == ["Platform"]


def test_the_licence_takes_its_house_colour_unless_a_neighbour_has_it():
    mit = {**VALUES, **badges.license_values("mit", "MIT")}
    assert "license-MIT-yellow" in badges.render(["runtime", "license"], mit)
    assert "license-GPL%20v3-green" in badges.render(["runtime", "license"], VALUES)
    # a green neighbour on each side pushes GPL off green
    out = badges.render(["release-date", "license", "downloads"], VALUES)
    assert "license-GPL%20v3-yellow" in out


def test_unknown_names_are_refused_naming_the_catalogue():
    with pytest.raises(badges.BadgeError, match="known:"):
        badges.resolve("nonesuch", None)
    with pytest.raises(badges.BadgeError, match="unknown badges"):
        badges.resolve("python,nonesuch", None)


def test_a_persons_own_template_and_badge_type():
    mine = {"house": ["python", "my-docs", "license", "platform"]}
    types = {"my-docs": {"alt": "Docs", "image": "https://img.shields.io/badge/docs-site-blue",
                         "link": "https://example.invalid/{repo}"}}
    out = badges.render(badges.resolve("house", None, mine, types), VALUES, types=types)
    assert ids(out) == ["Python 3.10+", "Docs", "License: GPL v3", "Platform"]
    assert "https://example.invalid/tool" in out
