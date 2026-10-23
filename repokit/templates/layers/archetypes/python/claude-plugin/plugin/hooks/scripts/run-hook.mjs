#!/usr/bin/env node
// Launch one of this plugin's Python hooks: node run-hook.mjs <script.py>
//
// Claude Code always has node (it is a node app), but `python3 || python` in
// hooks.json depends on the shell the hook runs under, which differs by
// platform. This launcher finds a Python 3 the platform's way round, runs the
// named script beside it with the event passed through on stdin, and returns
// its exit code. A missing Python or script is reported on stderr and exits 0,
// so a broken hook never blocks the session. Modelled on
// claude-session-logger's run-hook.mjs; the script name is an argument here,
// so one launcher serves every hook.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const NAME = "__RK_PROJECT__";
const script = join(HERE, process.argv[2] || "session_start.py");

function findPython() {
  const candidates = process.platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"];
  for (const cmd of candidates) {
    const r = spawnSync(cmd, ["--version"], { stdio: "pipe", timeout: 5000 });
    const out = `${r.stdout || ""}${r.stderr || ""}`;
    if (r.status === 0 && out.includes("Python 3")) return cmd;
  }
  return null;
}

const python = findPython();
if (!python) {
  process.stderr.write(`[${NAME}] Python 3 not found; install it and put python3 (or python) on PATH.\n`);
  process.exit(0);
}
if (!existsSync(script)) {
  process.stderr.write(`[${NAME}] hook script not found: ${script}\n`);
  process.exit(0);
}
const r = spawnSync(python, [script], { stdio: "inherit", timeout: 60000 });
process.exit(r.status || 0);
