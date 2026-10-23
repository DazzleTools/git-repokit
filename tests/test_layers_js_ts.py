"""The js-ts language layer and its first presets (Phase 3 slice 3, v0.8.2):
node-package (the default) and script, through `repokit create`.

Design: 2026-10-19__22-11-27__dev-workflow-process__family-type-system-facets-and-grammar.md
(Unit 6, D5, Addendum 2). The measure behind the shape:
tests/one-offs/thinking/p3-measure-node-checkouts/. Node-dependent checks run
when `node` is on PATH and skip with a reason otherwise; nothing here installs
packages from the network (a TypeScript compile needs `npm install`, which the
checklist covers by hand).
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from .test_utils import RepoKitTestCase

NODE = shutil.which("node")


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


class TestJsTsLayer(RepoKitTestCase):

    def test_the_default_is_an_npm_package_in_typescript(self):
        """--language js-ts: the language layer (VERSION, settings, CI, ignores,
        editorconfig), node (package.json kept by the version tool), ts
        (tsconfig), node-package (exports, src, tests, publish-on-release)."""
        self.assert_repokit_success(["create", "my-lib", "--language", "js-ts", "--no-push"])
        d = Path(self.test_dir, "my-lib")
        for rel in ("package.json", "tsconfig.json", "VERSION", ".editorconfig", ".repokit-common.toml",
                    "src/index.ts", "tests/index.test.ts",
                    ".github/workflows/ci-js-ts.yml", ".github/workflows/release.yml"):
            self.assertTrue((d / rel).is_file(), rel)
        pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
        self.assertEqual((pkg["name"], pkg["version"], pkg["type"]), ("my-lib", "0.1.0", "module"))
        self.assertIn("exports", pkg)
        self.assertNotIn("private", pkg)                      # the package layer's package.json won
        self.assertIn("typescript", pkg["devDependencies"])
        self.assertEqual((d / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0")
        settings = (d / ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertIn('version-source = "VERSION"', settings)
        self.assertIn('path = "package.json"', settings)       # node's .rkappend landed
        self.assertIn("private-patterns", settings)
        self.assertNotIn("languages =", settings)              # detected by the hooks from the root
        ignore = (d / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("node_modules/", ignore)
        self.assertIn("dist/", ignore)
        self.assertIn("ci-js-ts.yml/badge.svg", (d / "README.md").read_text(encoding="utf-8"))
        meta = json.loads((d / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["archetype"], "js-ts/node-package")
        self.assertEqual(meta["layers"], ["js-ts", "js-ts/node", "js-ts/ts", "js-ts/node-package"])
        self.assertEqual(_tokens_left(d), [])
        tool = d / "scripts" / "repokit-common" / "sync-versions.py"
        if tool.exists():
            r = subprocess.run([sys.executable, str(tool), "--check"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_script_floor_runs_with_node(self):
        """--with js-ts/script (or bare: script resolves to python's unless js-ts is
        listed, so the qualified form here): one .js reading VERSION, node's
        package.json, no tsconfig; `node my-tool.js --version` prints 0.1.0 and
        `node --test tests/` passes, when node is on PATH."""
        self.assert_repokit_success(["create", "my-tool", "--with", "js-ts/script", "--no-push"])
        d = Path(self.test_dir, "my-tool")
        self.assertTrue((d / "my-tool.js").is_file() and (d / "tests" / "version.test.js").is_file())
        self.assertFalse((d / "tsconfig.json").exists())
        self.assertFalse((d / ".github" / "workflows" / "release.yml").exists())
        pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(pkg.get("private"))
        meta = json.loads((d / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["archetype"], meta["layers"]), ("js-ts/script", ["js-ts", "js-ts/node", "js-ts/script"]))
        self.assertEqual(_tokens_left(d), [])
        if not NODE:
            self.skipTest("node is not on PATH; the run and the node:test tests are skipped")
        r = subprocess.run([NODE, "my-tool.js", "--version"], cwd=d, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0.1.0"), r.stderr)
        r = subprocess.run([NODE, "--test"], cwd=d, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_js_ts_script_is_a_build_choice_and_the_bare_name_is_ambiguous(self):
        """Addendum 2: script is exclusive with the other build choices in js-ts
        too; and `script` alone now names two languages' layers."""
        rc, out, err = self.run_repokit(["create", "x", "--with", "script", "--no-push"])
        self.assertNotEqual(rc, 0)
        self.assertIn("'script' is ambiguous: js-ts/script or python/script", out + err)
        self.assert_repokit_success(["create", "y", "--language", "js-ts", "--with", "script", "--no-push"])
        meta = json.loads(Path(self.test_dir, "y", ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["archetype"], "js-ts/script")

    def test_the_claude_plugin_is_nested_with_two_manifests(self):
        """Phase 3 slice 4 (AC-7 end to end): --with claude-plugin (bare, unique)
        makes the nested shape djdarcy keeps: the plugin in plugin/ with its own
        manifest, a SessionStart hook, node:test tests and the marketplace README;
        the marketplace manifest and the GitHub README at the root; VERSION kept
        in step with package.json and plugin.json; human tags."""
        self.assert_repokit_success(["create", "my-plugin", "--with", "claude-plugin", "--no-push"])
        d = Path(self.test_dir, "my-plugin")
        for rel in (".claude-plugin/marketplace.json", "plugin/.claude-plugin/plugin.json", "plugin/hooks/hooks.json",
                    "plugin/hooks/scripts/session-start.mjs", "plugin/tests/manifest.test.js", "plugin/README.md",
                    "README.md", "VERSION", "package.json", ".repokit-common.toml", ".github/workflows/ci-js-ts.yml"):
            self.assertTrue((d / rel).is_file(), rel)
        self.assertFalse((d / "tsconfig.json").exists())            # ts is not in the preset
        self.assertFalse((d / ".github" / "workflows" / "release.yml").exists())
        plugin = json.loads((d / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((d / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual((plugin["name"], plugin["version"]), ("my-plugin", "0.1.0"))
        self.assertEqual(market["plugins"][0]["source"], "./plugin")
        settings = (d / ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertIn('tag-format = "human"', settings)
        self.assertEqual(settings.count("[[tool.repokit-common.extra-targets]]"), 2, settings)
        self.assertIn('path = "plugin/.claude-plugin/plugin.json"', settings)
        meta = json.loads((d / ".repokit.json").read_text(encoding="utf-8"))
        # 0.9.1: the manifests and the marketplace README come from the shared any/claude-plugin layer
        self.assertEqual((meta["archetype"], meta["layers"]),
                         ("js-ts/claude-plugin", ["js-ts", "js-ts/node", "js-ts/claude-plugin", "any/claude-plugin"]))
        self.assertEqual(_tokens_left(d), [])
        tool = d / "scripts" / "repokit-common" / "sync-versions.py"
        if tool.exists():
            r = subprocess.run([sys.executable, str(tool), "--check"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        if NODE:
            r = subprocess.run([NODE, "--test"], cwd=d, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_planned_flavours_refuse_with_their_description(self):
        for preset in ("js-ts/web-vite-react", "js-ts/obsidian-plugin", "js-ts/browser-extension"):
            rc, out, err = self.run_repokit(["create", "x", "--with", preset, "--no-push"])
            self.assertNotEqual(rc, 0, preset)
            self.assertIn(f"archetype {preset} is not built yet", out + err)
