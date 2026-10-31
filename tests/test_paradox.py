"""The paradox language family (0.10.0): Paradox game mods through `repokit create`.

Design: 2026-10-30__08-28-15__dev-workflow-process__paradox-mods-and-the-version-pattern-target.md
(units 5 and 6, Addendum 2: the facets are the existing ones -- engine =
dialect, descriptor = build, game = purpose). The measures behind the shape
are in tests/one-offs/thinking/p5-measure-paradox-and-pattern-target/: an
upload ships its whole folder (so the mod is mod/, M2), and the descriptor's
version pattern rewrites real descriptors byte-exactly (M3). The hooks'
paradox profile and the pattern target are git-repokit-common 0.4.3's.

Nothing here runs a game or Tiger: those are the checklist's, by hand.
"""

import json
import subprocess
import sys
from pathlib import Path

from .test_utils import RepoKitTestCase

BOM = b"\xef\xbb\xbf"
MOD_TEXT_SUFFIXES = (".mod", ".yml", ".txt", ".gui", ".gfx")


def _tokens_left(root):
    import re
    token = re.compile(rb"__RK_[A-Z_]+?__")
    hits = []
    for p in Path(root).rglob("*"):
        if ".git" in p.parts or "repokit-common" in p.parts or not p.is_file():
            continue
        if token.search(p.name.encode()) or token.search(p.read_bytes()):
            hits.append(p.relative_to(root).as_posix())
    return hits


def _mod_files(d):
    return sorted(p.relative_to(d / "mod").as_posix() for p in (d / "mod").rglob("*") if p.is_file())


def _settings(d):
    """The created project's [tool.repokit-common] table, parsed: the file's
    comments repeat its keys' text, so a substring check proves nothing."""
    import tomllib
    with open(d / ".repokit-common.toml", "rb") as f:
        return tomllib.load(f)["tool"]["repokit-common"]


def _vendored(d, name):
    tool = d / "scripts" / "repokit-common" / name
    return tool if tool.exists() else None


class TestParadoxFamily(RepoKitTestCase):

    def test_the_default_is_a_ck3_mod_in_mod(self):
        """--language paradox: a Crusader Kings III mod. mod/ holds only the mod
        (descriptor, thumbnail, English localization) -- an upload ships that
        folder whole -- and the repository's own files stay above it."""
        self.assert_repokit_success(["create", "cheat-menu", "--language", "paradox", "--no-push"])
        d = Path(self.test_dir, "cheat-menu")
        self.assertEqual(_mod_files(d), ["descriptor.mod", "localization/english/cheat_menu_l_english.yml",
                                         "thumbnail.png"])
        for rel in ("VERSION", ".repokit-common.toml", "docs/modding.md", ".gitattributes"):
            self.assertTrue((d / rel).is_file(), rel)
        self.assertEqual((d / "mod" / "descriptor.mod").read_bytes(),
                         b'version="0.1.0"\ntags={\n\t"Utilities"\n}\nname="cheat-menu"\nsupported_version="1.20.*"\n')
        self.assertEqual((d / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0")
        meta = json.loads((d / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["archetype"], "paradox/ck3")
        self.assertEqual(meta["layers"], ["paradox", "paradox/jomini", "paradox/descriptor-mod", "paradox/ck3"])
        self.assertEqual(_tokens_left(d), [])
        png = (d / "mod" / "thumbnail.png").read_bytes()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"), "the thumbnail's bytes survived")

    def test_the_mod_files_keep_their_bom_and_lf(self):
        """The game reads mod files as they are: the localization .yml starts
        with a UTF-8 BOM (a file without one is skipped silently), every mod
        text file is LF, and .gitattributes keeps git from converting them."""
        self.assert_repokit_success(["create", "cheat-menu", "--language", "paradox", "--no-push"])
        d = Path(self.test_dir, "cheat-menu")
        loc = (d / "mod" / "localization" / "english" / "cheat_menu_l_english.yml").read_bytes()
        self.assertTrue(loc.startswith(BOM), "localization needs its BOM")
        self.assertIn(b'cheat_menu_name:0 "cheat-menu"', loc)
        for p in (d / "mod").rglob("*"):
            if p.suffix in MOD_TEXT_SUFFIXES:
                self.assertNotIn(b"\r", p.read_bytes(), p.name)
        self.assertFalse((d / "mod" / "descriptor.mod").read_bytes().startswith(BOM))
        attrs = (d / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("mod/**/*.yml -text", attrs)
        self.assertIn("mod/**/*.mod -text", attrs)
        r = subprocess.run(["git", "check-attr", "text", "--", "mod/descriptor.mod",
                            "mod/localization/english/cheat_menu_l_english.yml"],
                           cwd=d, capture_output=True, text=True)
        self.assertEqual(r.stdout.count("text: unset"), 2, r.stdout)

    def test_the_settings_declare_paradox_ck3_and_keep_the_descriptor_in_step(self):
        """.repokit-common.toml: languages = ["paradox"], paradox-game = "ck3"
        (ck3-tiger on push), VERSION as the source and the descriptor's version
        line as a pattern target. Through the vendored copy: the languages and
        game read back, --check passes, and a bump moves exactly the
        descriptor's version line."""
        self.assert_repokit_success(["create", "cheat-menu", "--language", "paradox", "--no-push"])
        d = Path(self.test_dir, "cheat-menu")
        s = _settings(d)
        self.assertEqual((s["languages"], s["paradox-game"], s["version-source"]), (["paradox"], "ck3", "VERSION"))
        self.assertEqual(s["extra-targets"], [{"path": "mod/descriptor.mod",
                                               "pattern": '^version="([^"]*)"\\r?$', "format": "base"}])
        config, sync = _vendored(d, "repokit_config.py"), _vendored(d, "sync-versions.py")
        if not (config and sync):
            self.skipTest("no vendored repokit-common in this create (no sibling checkout)")
        get = lambda key: subprocess.run([sys.executable, str(config), "--get", key], cwd=d,
                                         capture_output=True, text=True).stdout.strip()
        self.assertEqual((get("languages"), get("paradox-game")), ("paradox", "ck3"))
        r = subprocess.run([sys.executable, str(sync), "--check"], cwd=d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        before = (d / "mod" / "descriptor.mod").read_bytes()
        r = subprocess.run([sys.executable, str(sync), "--bump", "patch"], cwd=d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((d / "VERSION").read_text(encoding="utf-8").strip(), "0.1.1")
        self.assertEqual((d / "mod" / "descriptor.mod").read_bytes(),
                         before.replace(b'version="0.1.0"', b'version="0.1.1"'))

    def test_the_generic_engine_presets(self):
        """paradox/jomini and paradox/clausewitz: a generic descriptor
        (supported_version "*", with a comment saying to set it), the
        localization folder spelled as the engine spells it, and no game: the
        settings name none (paradox-game commented)."""
        for preset, folder in (("paradox/jomini", "localization"), ("paradox/clausewitz", "localisation")):
            name = preset.split("/")[1] + "-mod"
            self.assert_repokit_success(["create", name, "--with", preset, "--no-push"])
            d = Path(self.test_dir, name)
            snake = name.replace("-", "_")
            self.assertEqual(_mod_files(d), ["descriptor.mod", f"{folder}/english/{snake}_l_english.yml",
                                             "thumbnail.png"], preset)
            desc = (d / "mod" / "descriptor.mod").read_text(encoding="utf-8")
            self.assertIn('supported_version="*"', desc)
            self.assertIn("# Set supported_version", desc)
            self.assertTrue((d / "mod" / folder / "english" / f"{snake}_l_english.yml").read_bytes().startswith(BOM))
            s = _settings(d)
            self.assertEqual(s["languages"], ["paradox"], preset)
            self.assertNotIn("paradox-game", s, preset)            # no game: a commented hint only
            self.assertIn('# paradox-game = "ck3"', (d / ".repokit-common.toml").read_text(encoding="utf-8"))
            self.assertEqual(s["extra-targets"][0]["path"], "mod/descriptor.mod", preset)
            self.assertEqual(_tokens_left(d), [], preset)

    def test_repokit_list_paradox_shows_presets_facets_and_planned_games(self):
        """`repokit list paradox`: the three built presets (ck3 the default),
        the planned games, and the three facets with their answers."""
        code, out, err = self.run_repokit(["list", "paradox"])
        self.assertEqual(code, 0, err)
        self.assertIn("paradox/ck3                  = jomini, descriptor-mod, ck3  <- default", out)
        self.assertIn("paradox/jomini               = jomini, descriptor-mod", out)
        self.assertIn("paradox/clausewitz           = clausewitz, descriptor-mod", out)
        self.assertIn("paradox/stellaris            (planned", out)
        self.assertIn("dialect    one of: clausewitz, jomini", out)
        self.assertIn("build      one of: descriptor-mod, metadata-json (planned)", out)
        self.assertIn("purpose    one of: ck3,", out)

    def test_a_game_with_the_other_engine_is_refused(self):
        """paradox/ck3 implies the jomini engine, so --with clausewitz,ck3 is no
        mod at all: the create stops naming the two engines, before anything is
        written (the compositions test skips this combination on that basis)."""
        code, out, err = self.run_repokit(["create", "m", "--with", "paradox/clausewitz,paradox/ck3", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertIn("'clausewitz' and 'jomini' are both a dialect for paradox; pick one", out + err)
        self.assertFalse(Path(self.test_dir, "m").exists())

    def test_a_planned_game_is_refused_by_name(self):
        """A planned game is named but not built: the create stops and says so."""
        code, out, err = self.run_repokit(["create", "m", "--with", "paradox/stellaris", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertIn("paradox/stellaris is not built yet", out + err)
        self.assertFalse(Path(self.test_dir, "m").exists())
