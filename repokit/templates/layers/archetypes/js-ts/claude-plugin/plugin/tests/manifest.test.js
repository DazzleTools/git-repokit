// The plugin's manifests parse, agree with VERSION, and the hook script answers.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN = join(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = join(PLUGIN, "..");

test("plugin.json names the plugin and carries VERSION", () => {
  const manifest = JSON.parse(readFileSync(join(PLUGIN, ".claude-plugin", "plugin.json"), "utf8"));
  assert.equal(manifest.name, "__RK_PROJECT__");
  assert.equal(manifest.version, readFileSync(join(ROOT, "VERSION"), "utf8").trim());
});

test("marketplace.json lists this plugin from ./plugin", () => {
  const marketplace = JSON.parse(readFileSync(join(ROOT, ".claude-plugin", "marketplace.json"), "utf8"));
  assert.ok(marketplace.plugins.some((p) => p.source === "./plugin" && p.name === "__RK_PROJECT__"));
});

test("hooks.json parses and the SessionStart script returns JSON", () => {
  const hooks = JSON.parse(readFileSync(join(PLUGIN, "hooks", "hooks.json"), "utf8"));
  assert.ok(hooks.hooks.SessionStart);
  const r = spawnSync(process.execPath, [join(PLUGIN, "hooks", "scripts", "session-start.mjs")],
    { input: JSON.stringify({ hook_event_name: "SessionStart", source: "startup" }), encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  assert.doesNotThrow(() => JSON.parse(r.stdout));
});
