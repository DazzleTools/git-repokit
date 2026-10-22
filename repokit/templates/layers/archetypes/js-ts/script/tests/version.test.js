// The script answers --version with the VERSION file's content, and --help exits 0.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPT = join(ROOT, "__RK_PROJECT__.js");

function run(...args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], { cwd: ROOT, encoding: "utf8" });
}

test("--version matches the VERSION file", () => {
  const r = run("--version");
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout.trim(), readFileSync(join(ROOT, "VERSION"), "utf8").trim());
});

test("--help exits cleanly and names the script", () => {
  const r = run("--help");
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /__RK_PROJECT__/);
});
