#!/usr/bin/env node
// SessionStart hook for __RK_PROJECT__.
//
// Claude Code runs this when a session starts and passes the event as JSON on
// stdin. Anything printed to stdout as JSON with "additionalContext" reaches
// the session; an empty object is a no-op. Replace the body with the plugin's
// work; keep it quick (the hooks.json timeout is 10 seconds).

import { readFileSync } from "node:fs";

let event = {};
try {
  const raw = readFileSync(0, "utf8");
  event = raw.trim() ? JSON.parse(raw) : {};
} catch {
  event = {};
}

const output = {};
if (process.env.__RK_MACRO___DEBUG) {
  output.additionalContext = `__RK_PROJECT__ saw a ${event.hook_event_name ?? "SessionStart"} event (source: ${event.source ?? "unknown"}).`;
}
process.stdout.write(JSON.stringify(output));
