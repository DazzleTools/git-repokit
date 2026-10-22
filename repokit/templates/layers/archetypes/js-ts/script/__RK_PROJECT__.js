#!/usr/bin/env node
// __RK_DESCRIPTION__
//
// A plain script: one file, run with node, no build step and no dependencies.
// The version lives in the VERSION file beside this module (git-repokit-common's
// version tool keeps it, package.json, the CHANGELOG and the tags in step).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

export function readVersion() {
  try {
    return readFileSync(join(HERE, "VERSION"), "utf8").trim() || "0.0.0+unknown";
  } catch {
    return "0.0.0+unknown";
  }
}

export function main(argv = process.argv.slice(2)) {
  if (argv.includes("--version") || argv.includes("-V")) {
    console.log(readVersion());
    return 0;
  }
  if (argv.includes("--help") || argv.includes("-h")) {
    console.log("usage: __RK_PROJECT__ [--version] [--help]\n\n__RK_DESCRIPTION__");
    return 0;
  }
  console.log("Hello from __RK_PROJECT__. Replace this with the script's work.");
  return 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  process.exit(main());
}
