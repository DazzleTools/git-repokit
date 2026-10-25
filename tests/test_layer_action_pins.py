"""The GitHub Actions the layer tree pins (0.9.6).

A created project's CI once pinned checkout@v4 while its own release.yml
pinned checkout@v7, so Dependabot opened three pull requests within two
minutes of the first push (the live golden, 2026-10-24). These tests keep
every workflow in the layer tree on one major per action, and no older than
git-repokit-template's when that checkout is beside this one.
"""
import re
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAYERS = REPO / "repokit" / "templates" / "layers"
TEMPLATE = REPO.parent / "git-repokit-template"
USES = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([A-Za-z0-9_./-]+)")


def pins(root: Path):
    """{action: {ref: [files]}} for every workflow under root."""
    found = defaultdict(lambda: defaultdict(list))
    for path in sorted(root.rglob("*.yml")):
        if ".github" not in path.parts or "workflows" not in path.parts:
            continue
        for action, ref in USES.findall(path.read_text(encoding="utf-8")):
            found[action][ref].append(str(path.relative_to(root)))
    return found


def major(ref: str):
    m = re.match(r"v(\d+)", ref)
    return int(m.group(1)) if m else None


def test_the_layer_tree_has_workflows_to_check():
    assert pins(LAYERS), "no workflow files found under the layer tree"


def test_each_action_is_pinned_to_one_major_across_the_layer_tree():
    split = {}
    for action, refs in pins(LAYERS).items():
        majors = {major(r) for r in refs}
        if len(majors) > 1:
            split[action] = dict(refs)
    assert not split, f"actions pinned to more than one major: {split}"


@pytest.mark.skipif(not TEMPLATE.is_dir(), reason="git-repokit-template is not checked out beside git-repokit")
def test_no_pin_is_older_than_git_repokit_templates():
    ours, theirs = pins(LAYERS), pins(TEMPLATE)
    older = {}
    for action, refs in ours.items():
        their_majors = [m for m in (major(r) for r in theirs.get(action, {})) if m is not None]
        if not their_majors:  # not in the template, or a branch ref such as release/v1
            continue
        their_major = max(their_majors)
        for ref, files in refs.items():
            m = major(ref)
            if m is not None and m < their_major:
                older[f"{action}@{ref}"] = (f"template has v{their_major}", files)
    assert not older, f"pins older than git-repokit-template's: {older}"
