"""Template parity, the 0.9.0 milestone (U4): a project `repokit create` makes
has every file git-repokit-template's route made, apart from a DECLARED list of
differences; and the pieces that gave parity (LICENSE, the extras) land for
every language, not only Python.

The template route is replayed locally from the sibling checkout
C:/code/git-repokit-template (read-only), the way its setup-from-template.yml
workflow would on a first push; graduated from
tests/one-offs/thinking/split-0.7.x/mirror_template.py (2026-10-09, measured
2026-10-22 17:00). Skipped when the checkout is absent.

Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md (Addendum 2).
"""
import json
import os
import re
from pathlib import Path
from unittest import mock

import pytest

from .test_utils import RepoKitTestCase

TEMPLATE = Path("C:/code/git-repokit-template")
SKIP_DIRS = {".git", "private"}
SKIP_FILES = {".github/workflows/setup-from-template.yml", "pyproject.toml.comfyui"}
NOT_COMPARED = ("scripts/repokit-common/", ".git/", "private/")

# What the template route has and the tool does not, on purpose, with the reason.
ONLY_TEMPLATE = {
    ".github/workflows/ci.yml": "the tool's CI is the language layer's ci-python.yml",
}
# What the tool writes and the template never had, on purpose (0.7.x additions and the vault's marker files).
ONLY_TOOL = {
    ".gitattributes": "line-ending normalisation (0.7.3)",
    "CHANGELOG.md": "first version's heading for the version sync (0.7.3)",
    "CLAUDE.md": "the AI integration's instructions",
    ".github/workflows/ci-python.yml": "the language layer's CI",
    ".vscode/launch.json": "the structure's debug configuration",
    "demo/cli.py": "the pypi preset ships a CLI module the template's workflow never created",
    "ROADMAP.md": "the old route wrote it by hand in /create-project Phase 6; an extra here",
    "docs/platform-support.md": "the old route wrote it by hand in /create-project Phase 6; an extra here",
}

# Shared files whose content is allowed to differ (wording from the tool's own
# templates, tokens filled differently, the vault's ignore lines). Anything
# else that differs is drift, and fails.
DECLARED_CONTENT = {
    ".github/CODEOWNERS": "the tool writes the git identity, the template the GitHub handle",
    ".github/workflows/release.yml": "line endings only on a Windows checkout (both LF after git normalises)",
    ".gitignore": "the vault's ignore lines and the tool's comment block",
    ".repokit.json": "the tool's record: version, layers, licence, extras, created_at",
    "CONTRIBUTING.md": "the tool's own text (Code of Conduct) vs the template's Development Setup",
    "README.md": "the tool's badges and sections",
    "demo/__init__.py": "wording",
    "demo/__main__.py": "wording",
    "demo/_version.py": "the tool adds four lines of sync instructions",
    "pyproject.toml": "description, keywords and author placeholders",
    "tests/conftest.py": "wording",
    "tests/test_version.py": "wording",
}
# The extras copied from the template with the OS: identical after line-ending normalisation, or the copy drifted.
COPIED_EXTRAS = [".github/FUNDING.yml", ".github/dependabot.yml", ".github/stale.yml",
                 ".github/pull_request_template.md", ".github/release-template.md", ".vscode/settings.json",
                 "tests/one-offs/README.md"]

EXTRAS_FILES = [".github/FUNDING.yml", ".github/dependabot.yml", ".github/stale.yml",
                ".github/pull_request_template.md", ".github/release-template.md", "ROADMAP.md",
                "docs/platform-support.md", ".vscode/settings.json", "tests/one-offs/README.md",
                "tests/output/.gitkeep", "docs/.gitkeep"]


def _heredocs(workflow_text):
    out = {}
    pattern = re.compile(r'cat > "\$PACKAGE_NAME/(?P<name>[^"]+)" << \'?PYEOF\'?\n(?P<body>.*?)\n\s*PYEOF', re.S)
    for m in pattern.finditer(workflow_text):
        body = "\n".join(line[10:] if line.startswith(" " * 10) else line for line in m.group("body").split("\n"))
        out[m.group("name")] = body + "\n"
    return out


def mirror_template(dst: Path, name="demo", org="DazzleTools", user="djdarcy"):
    """Replay setup-from-template.yml on the local template checkout into dst/name."""
    values = {"PROJECT_NAME": name, "PACKAGE_NAME": name.replace("-", "_"), "GITHUB_ORG": org,
              "GITHUB_USER": user, "AUTHOR_EMAIL": f"{user}@users.noreply.github.com",
              "CLI_COMMAND": name.replace("_", "-"), "DESCRIPTION": "A new project created from git-repokit-template"}

    def fill(text):
        for key, val in values.items():
            text = text.replace(f"${key}", val)
        return text

    root = dst / name
    workflow = (TEMPLATE / ".github/workflows/setup-from-template.yml").read_text(encoding="utf-8")
    for path in sorted(TEMPLATE.rglob("*")):
        rel = path.relative_to(TEMPLATE)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        rel_posix = rel.as_posix()
        if rel_posix in SKIP_FILES:
            continue
        if rel_posix == "pyproject.toml.pypi":
            rel_posix = "pyproject.toml"
        target = root / rel_posix
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            target.write_bytes(data)
            continue
        if rel_posix == "README.md":
            lines, out, skipping = text.split("\n"), [], False
            for line in lines:
                if not skipping and line == "---":
                    skipping = True
                    continue
                if skipping:
                    if line == "```":
                        skipping = False
                    continue
                out.append(line)
            text = "\n".join(out)
        target.write_text(fill(text), encoding="utf-8", newline="\n")
    pkg = root / values["PACKAGE_NAME"]
    pkg.mkdir(exist_ok=True)
    for fname, body in _heredocs(workflow).items():
        body = body.replace("${PACKAGE_NAME}", values["PACKAGE_NAME"]).replace("$PROJECT_NAME", values["PROJECT_NAME"])
        (pkg / fname).write_text(body, encoding="utf-8", newline="\n")
    return root


def _files(root: Path):
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and not any(p.relative_to(root).as_posix().startswith(x) for x in NOT_COMPARED)}


@pytest.mark.integration
class TestTemplateParity(RepoKitTestCase):

    def setUp(self):
        super().setUp()
        if not (TEMPLATE / ".github/workflows/setup-from-template.yml").is_file():
            self.skipTest(f"template checkout not present at {TEMPLATE}")

    def test_python_matches_the_template_route_apart_from_the_declared_differences(self):
        mirrored = mirror_template(Path(self.test_dir, "mirror"))
        # the house style through the global config, the way a person has it: the
        # licence, every extra, the GitHub handle the template route derived from the owner
        home = Path(self.test_dir, "home")
        (home / ".repokit").mkdir(parents=True)
        (home / ".repokit" / "config.json").write_text(json.dumps(
            {"license": "gpl-3.0", "extras": ["all"],
             "github": {"username": "djdarcy", "organization": "DazzleTools"}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            os.environ.pop("REPOKIT_LICENSE", None)
            self.assert_repokit_success(["create", "demo", "--language", "python", "--user-name", "djdarcy",
                                         "--description", "A new project created from git-repokit-template", "--no-push"])
        created = Path(self.test_dir, "demo")
        a, b = _files(mirrored), _files(created)
        self.assertEqual(sorted(a - b), sorted(ONLY_TEMPLATE), "files only the template route has (declare or build)")
        self.assertEqual(sorted(b - a), sorted(ONLY_TOOL), "files only the tool writes (declare or drop)")

        def lf(path):
            return path.read_bytes().replace(b"\r\n", b"\n")

        # the template ships GPL-3.0; the same text is the parity
        self.assertEqual(lf(created / "LICENSE"), lf(mirrored / "LICENSE"))
        for rel in COPIED_EXTRAS:
            self.assertEqual(lf(created / rel), lf(mirrored / rel), f"{rel}: the OS copy drifted from the template")
        differ = sorted(rel for rel in a & b if lf(mirrored / rel) != lf(created / rel))
        self.assertEqual(sorted(set(differ) - set(DECLARED_CONTENT)), [], "content drift in shared files: declare or fix")
        print("shared files whose content differs, all declared:", differ)

    def test_licence_and_extras_land_for_every_language(self):
        for lang in ("c-cpp", "js-ts"):
            self.assert_repokit_success(["create", f"p-{lang}", "--language", lang, "--license", "gpl-3.0",
                                         "--extras", "all", "--no-push"])
            root = Path(self.test_dir, f"p-{lang}")
            self.assertIn("GNU GENERAL PUBLIC LICENSE", (root / "LICENSE").read_text(encoding="utf-8"), lang)
            for rel in EXTRAS_FILES:
                self.assertTrue((root / rel).exists(), f"{lang}: {rel}")
