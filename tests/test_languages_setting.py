"""Every create writes the languages it composed (0.10.0).

git-repokit-common's hooks run one profile per language: from the project's
`languages` setting, else detection from the root markers, else Python. A
create used to leave the line out where detection would find it; a project
whose markers sit in a subfolder (a plugin's plugin/tsconfig.json) then read
as Python, as claude-bookmarks did (measured 2026-10-31,
git-repokit-common's tests/one-offs/thinking/measure-claude-bookmarks-shape/).
Now the create says what the project is, and detection is only the fallback.

Design: 2026-10-30__08-28-15__dev-workflow-process__paradox-mods-and-the-version-pattern-target.md,
Addendum 2.
"""

import unittest

try:
    import tomllib
except ModuleNotFoundError:     # Python 3.10: tomli, a dependency there (pyproject.toml)
    import tomli as tomllib
from pathlib import Path

from repokit import common_kit

from .test_utils import RepoKitTestCase


class TestLanguagesSetting(unittest.TestCase):

    def test_repokit_names_map_to_repokit_commons(self):
        f = common_kit.languages_setting
        self.assertEqual(f(["python"], ["languages/python", "archetypes/python/pypi"]), ["python"])
        self.assertEqual(f(["c-cpp"], ["languages/c-cpp"]), ["c-cpp"])
        self.assertEqual(f(["paradox"], ["languages/paradox", "archetypes/paradox/ck3"]), ["paradox"])

    def test_js_ts_is_typescript_only_with_the_ts_layer(self):
        f = common_kit.languages_setting
        self.assertEqual(f(["js-ts"], ["languages/js-ts", "archetypes/js-ts/node", "archetypes/js-ts/ts"]),
                         ["typescript"])
        self.assertEqual(f(["js-ts"], ["languages/js-ts", "archetypes/js-ts/node", "archetypes/js-ts/claude-plugin"]),
                         ["javascript"])

    def test_the_order_is_kept_and_the_neutral_names_add_nothing(self):
        """The first language is the primary; generic and the `any` pseudo-language
        are not product languages; a name repeated by the mapping appears once."""
        f = common_kit.languages_setting
        self.assertEqual(f(["python", "js-ts"], ["languages/python", "languages/js-ts"]), ["python", "javascript"])
        self.assertEqual(f(["js-ts", "python"], ["languages/js-ts", "languages/python"]), ["javascript", "python"])
        self.assertEqual(f(["generic"], []), [])
        self.assertEqual(f(["any", "python", "python"], ["archetypes/any/claude-plugin"]), ["python"])


def _settings(path):
    with open(path, "rb") as f:
        return tomllib.load(f)["tool"]["repokit-common"]


class TestCreatedLanguages(RepoKitTestCase):

    def test_a_plugin_whose_markers_sit_in_plugin_declares_javascript(self):
        """js-ts/claude-plugin keeps its manifest and tests in plugin/; the create
        writes languages = ["javascript"] rather than leave the hooks to find it."""
        self.assert_repokit_success(["create", "my-plugin", "--with", "js-ts/claude-plugin", "--no-push"])
        s = _settings(Path(self.test_dir, "my-plugin", ".repokit-common.toml"))
        self.assertEqual(s["languages"], ["javascript"])

    def test_a_two_language_project_declares_both_primary_first(self):
        """--language python,js-ts: the settings live in pyproject.toml (python's
        package) and name both, python first."""
        self.assert_repokit_success(["create", "duo", "--language", "python,js-ts", "--no-push"])
        s = _settings(Path(self.test_dir, "duo", "pyproject.toml"))
        self.assertEqual(s["languages"], ["python", "javascript"])

    def test_a_layers_own_languages_line_is_not_overwritten(self):
        """paradox's settings name their language themselves; the create's merge
        adds nothing and the file holds the line once."""
        self.assert_repokit_success(["create", "a-mod", "--language", "paradox", "--no-push"])
        text = Path(self.test_dir, "a-mod", ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertEqual(text.count("\nlanguages = "), 1, text)
