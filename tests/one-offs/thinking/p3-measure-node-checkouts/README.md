# Measure: the Node checkouts under C:\code (2026-10-21)

Question: before the js-ts language layer and its first presets are written (Phase 3 slice 3), what do the JavaScript/TypeScript projects on this machine actually look like? The roster counted "6 census checkouts with package.json"; this reads every `package.json` at depth three or less (node_modules excluded) and the files beside it. `measure.py` is read-only and writes `results.md` here.

| Fact | Count of 11 |
|---|---|
| `tsconfig.json` present | 6 |
| `"type": "module"` | 5 |
| test runner named | vitest 5, none 6 |
| bundler named | vite 6, none 5 |
| `engines` set | 4 |
| `.nvmrc` | 1 |
| lockfile | package-lock 5, pnpm-lock 2, none 4 |
| `manifest.json` (a plugin or extension) | 1 (the ComfyUI frontend) |
| `.claude-plugin` beside a `package.json` | 0 (claude-bookmarks has no `package.json`) |
| repokit-common vendored | 1 (a ComfyUI node whose version lives in `version.py`) |

Reading, for the layer: ES modules by default; npm (its lockfile outnumbers pnpm's); `engines` rather than `.nvmrc`; TypeScript is common but not universal, so it stays its own layer (the dialect facet); the web stack is Vite plus Vitest in every modern checkout, so `vite` and `react` presets wait for the web slice and Vitest is the runner there; a pure Node package without a bundler is rare here (the reddit-slack checkouts, CommonJS, `engines node >=14`), so `node-package`'s own tests use `node --test`, which needs no dependency, and a Vitest runner is a later layer's choice. No project keeps a plain `VERSION`; all carry the version in `package.json`, which is why the layer makes `VERSION` the source and `package.json` an extra target of the vendored version tool (the route claude-bookmarks already uses for its plugin manifest).
