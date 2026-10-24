# P4 measure: what launch.json configurations the projects on this machine use

Measured 2026-10-23. Population: `fd -H -t f -g launch.json C:/code --max-depth 5` excluding node_modules, .git and any `templates` folder = 143 files, all parsed (comments and trailing commas stripped; 0 parse failures). Two non-matching names (`vscode_launch_json_complete.json`, `launch.json.default`) were left out. Language is from root markers of the folder holding `.vscode/`.

## Summary

The machine is overwhelmingly Python: 99 files sit in a Python-marked root and 36 more are in unmarked roots (org `.github-repo` profile repos, backups, Django copies) that carry the same Python configs, so about 135 of 143 files are Python. 98 of the 143 files hold only the three configs git-repokit's own template writes ("Python: Current File", "Python: Module", "Python: Current File with Arguments"), i.e. they are unedited copies of the template. The hand-written ones (45 files) converge on one pattern: one configuration per CLI invocation or test run, `request: launch`, `console: integratedTerminal`, `justMyCode: false`, using `module` (for packages) or `program: ${workspaceFolder}/x.py` (for scripts), plus `args`. There is a visible drift from `"type": "python"` to `"type": "debugpy"` in newer projects. Non-Python evidence is thin: one C/C++ repo family (xormove, `cppvsdbg` + MSBuild preLaunchTask), one Node family (zmsync_reddit-slack, `type: node`, no TypeScript anywhere), one Flutter/dart pair, and no `launch.json` anywhere that targets a Claude plugin. The nearest "plugin" analog is the ComfyUI custom-node repos (Python, program = host app's main.py, cwd/env from `${env:COMFYUI_PATH}`, plus an attach config).

## Tally by language

Counts are files, then configuration entries. Many repos appear 2-3 times (`local/` and `github/` copies, backups), so "files" overstates distinct repos; the template-copy count (98) is the biggest inflation.

| Language (root markers) | Files | Configs | Type / request | Most common shapes (key fields) |
|---|---|---|---|---|
| python (pyproject/setup.py/requirements) | 99 | 438 | `python`/launch 90%+, `debugpy`/launch in 9 files (53 configs), `python`/attach 6 | program+console+justMyCode (91), module+console+justMyCode (64), program+args+console (62, the `${command:pickArgs}` one), module+args+console+justMyCode (43 python, 38 debugpy), program+args+cwd+console+justMyCode (36), program+args+cwd+env+... (14) |
| unmarked (org profile repos, Django copies, Flutter) | 36 | 116 | `python`/launch 105, `dart`/launch 11 | identical template trio x35; dart: program `lib/main.dart` + deviceId + flutterMode (+cwd) |
| js-ts (package.json) | 4 | 21 | `node`/launch 18; 3 stray Python template configs | program+args+env+console (18). `outFiles` on some. No `tsconfig`, no `preLaunchTask`, no `runtimeExecutable`, no `npm` launch |
| c-cpp (CMakeLists/sln) | 4 | 9 | `cppvsdbg`/launch 6; 3 stray Python template configs | program+args+cwd+console+preLaunchTask (6), all in the xormove family |

Whole-population field use (files that contain the field at least once): `module` 115, `cwd` 29, `env` 25, `args` most, `console` every Python/node config, `justMyCode` every Python config except the `program+args` pick-args one, `preLaunchTask` only in the 3 xormove C++ files (1 repo family). Two files use non-standard top-level keys (`configurations-sql-tests` in `zmsync_reddit-slack/gdevvit-dev-branch`), so VS Code ignores part of them. Also notable: `${input:...}` variables (needs an `inputs` block) appear in 4 repos for arbitrary args; `${env:COMFYUI_PATH}` in the ComfyUI nodes; `PYTHONDONTWRITEBYTECODE` env in two pytest-heavy repos.

## Representative configurations (verbatim)

Python script, hand-written with env and cwd (`C:/code/ai-toolkit/.vscode/launch.json`):

```json
{"name": "Run current config", "type": "python", "request": "launch", "program": "${workspaceFolder}/run.py", "args": ["${file}"], "env": {"CUDA_LAUNCH_BLOCKING": "1", "DEBUG_TOOLKIT": "1"}, "console": "integratedTerminal", "justMyCode": false}
```

Python package via module, newer `debugpy` type, plus pytest (`C:/code/claude-projects/Claude-Session-Backup/.vscode/launch.json`):

```json
{"name": "csb: status", "type": "debugpy", "request": "launch", "module": "claude_session_backup", "args": ["status"], "console": "integratedTerminal", "justMyCode": false}
{"name": "pytest: current file", "type": "debugpy", "request": "launch", "module": "pytest", "args": ["${file}", "-v"], "justMyCode": true, "console": "integratedTerminal"}
```

Python script with `cwd` (`C:/code/dazzle-checksum/github/.vscode/launch.json`):

```json
{"name": "Dazzlesum: Generate recursive", "type": "python", "request": "launch", "program": "${workspaceFolder}/dazzlesum.py", "args": ["-r"], "console": "integratedTerminal", "cwd": "${workspaceFolder}", "justMyCode": true}
```

Python plugin-ish (host application launches the plugin; `C:/code/ComfyUI-PreviewBridgeExtended/local/.vscode/launch.json`):

```json
{"name": "ComfyUI: Debug This Node", "type": "python", "request": "launch", "program": "${env:COMFYUI_PATH}/main.py", "console": "integratedTerminal", "justMyCode": false, "cwd": "${env:COMFYUI_PATH}", "env": {"COMFY_DEBUG_PREVIEW_BRIDGE_EXT": "true"}, "args": []}
{"name": "ComfyUI: Attach to Running", "type": "python", "request": "attach", "connect": {"host": "localhost", "port": 5678}, "justMyCode": false, "pathMappings": [{"localRoot": "${workspaceFolder}", "remoteRoot": "${env:COMFYUI_PATH}/custom_nodes/ComfyUI-PreviewBridgeExtended"}]}
```

C/C++ MSBuild (`C:/code/xormove/local/.vscode/launch.json`; its `tasks.json` defines label "Build Debug" = `msbuild /property:Configuration=Debug /property:Platform=x64 ${workspaceFolder}/xormove.sln`). The repo also has CMakeLists.txt and CMakePresets.json, but the launch config points at `build/Debug/xormove.exe` and uses the MSBuild task:

```json
{
    "name": "Debug xormove",
    "type": "cppvsdbg",
    "request": "launch",
    "program": "${workspaceFolder}/build/Debug/xormove.exe",
    "args": ["${workspaceFolder}/test-runs/fileA.txt", "${workspaceFolder}/test-runs/fileB.txt", "--verbose", "--progress"],
    "stopAtEntry": false,
    "cwd": "${workspaceFolder}",
    "environment": [],
    "console": "integratedTerminal",
    "preLaunchTask": "Build Debug"
}
```

Node script (`C:/code/zmsync_reddit-slack/RedditSlackTemp/.vscode/launch.json`, args trimmed by me to the first pair only):

```json
{"type": "node", "request": "launch", "name": "Test-config-merge.js: Debug cfg Merging", "program": "${workspaceFolder}/scripts/test-config-merge.js", "args": ["../config.test-sql.json"], "env": {"NODE_ENV": "development"}, "console": "integratedTerminal", "outFiles": ["${workspaceFolder}/**/*.js"]}
```

## The two generators

**`Z:\OmniTools\cmd-to-launchjson\cmd-to-launchjson.py`** (Z: is mounted; 76 lines, read whole). Python-only, tiny. `create_json <command ...>` writes `.vscode/launch.json` with `version "0.0.0.1"` (not a valid 0.2.0) and three configs: one named after `program` (default `${file}`) with `type: "debugpy"`, `request: launch`, `program`, `console: integratedTerminal`, and `args` = the command line minus its first token; then a fixed "Python: Current File" (`justMyCode: true`) and a fixed "Python: Attach" with `pathMappings` localRoot/remoteRoot both `${workspaceFolder}`. `gen_args` prints just `{"args": [...]}`. There is no parsing (`parse_command_line` returns its input), and `cwd`, `env`, `module` and `preLaunchTask` are not mapped at all. The `revisions/` folder next to it was not read.

**Successors in `C:/code/dazzlecmd`**: none found. `rg -il "launch.json|launchjson|launch_json|cmd-to-launch|debugpy"` over the whole tree (excluding node_modules and .git) matched no source, doc or tool file, and `fd` found no tool directory with a launch-ish name. The only launch.json files there (`github/`, `local/`, `fiber-work/`, `github.2026.6.21/`, `github - Copy/`, and `projects/wtf/.../restarted/`) are plain outputs of the same three-config template, with `module` set to `dazzlecmd`. So the generator idea did not graduate beyond the OmniTools script; the template copy is what the machine actually runs on.

## Comparison to today's template

`repokit/templates/common/launch.json.template` is Python-only and ships three configs (`type: "python"`, `launch`; Current File with `program ${file}`; Module with `module $project_name`, both `integratedTerminal` and `justMyCode: true`; Current File with Arguments using `${command:pickArgs}`) plus a "Server/Client" compound that pairs Module and Current File, a pairing nothing else on the machine uses. It matches the dominant Python shapes exactly, which is why 98 files are unedited copies, but it is written for every language (a JS or C++ project gets Python configs, seen in 3 stray cases here), it uses legacy `python` where newer projects have moved to `debugpy`, and it lacks the hand-written patterns people actually add: a pytest config, a `program ${workspaceFolder}/x.py` script config with `cwd`, `justMyCode: false`, and per-CLI-subcommand `args`.

## What a per-preset launch.json should contain

Marked (M) = directly measured on this machine, (I) = inferred, no example here.

- **Python package**: (M) `module: <package>` launch, `console: integratedTerminal`, `justMyCode` (template says true, hand-written configs mostly false); (M) a pytest config (`module: pytest`, `args: ["tests/", "-v"]`) and a "pytest: current file" (`${file}`); (M) current file (`program ${file}`); (M) optional `env` with `PYTHONDONTWRITEBYTECODE=1`; (I) use `debugpy` type, which the newest projects already use; (I) drop the compound.
- **Python script**: (M) `program: ${workspaceFolder}/<script>.py`, `args: []`, `cwd: ${workspaceFolder}`, `console`, `justMyCode` (dazzle-checksum, Prime-Square-Sum); (M) current file, and current file with `${command:pickArgs}`; (M) optional `${input:...}` args entry (needs an `inputs` array, which is easy to forget: (I)).
- **Python Claude plugin**: no measured Claude-plugin launch.json. (M) the nearest analog is the ComfyUI custom-node pattern: host `program` + `cwd` + `env` via `${env:HOST_PATH}`, plus an attach config with `connect` host/port and `pathMappings`. (I) for a Claude plugin, a package-module config for the hook/CLI module plus the pytest pair is the safe base; a launch-the-host entry cannot be derived from measurements.
- **C/C++ CMake app**: (M) `cppvsdbg` launch with `program ${workspaceFolder}/build/Debug/<name>.exe`, `args`, `cwd`, `stopAtEntry: false`, `environment: []`, `console: integratedTerminal`. (I) the `preLaunchTask` must reference a label in a shipped `tasks.json` (xormove ships one), and for CMake that task would run `cmake --build build --config Debug`; no CMake-task example was measured, even though xormove has CMakePresets.json.
- **C/C++ MSBuild**: (M) same `cppvsdbg` config; `preLaunchTask: "Build Debug"` backed by a `tasks.json` shell task `msbuild /property:Configuration=Debug /property:Platform=x64 ${workspaceFolder}/<name>.sln` with `$msCompile` problem matcher; program path under `bin/Debug` (older xormove copies) or `build/Debug`; a "Build Release" sibling exists.
- **C/C++ minimal**: (I) one `cppvsdbg` config with `program`, `cwd`, `console`, no `preLaunchTask`; the measured configs all have a preLaunchTask, so the minimal form is my reduction. `cppdbg` (gdb/lldb) was not seen anywhere; it would be needed off Windows (I).
- **JS/TS npm package in TypeScript**: no TypeScript launch.json exists here. (M) the only JS shape is `type: node`, `request: launch`, `program ${workspaceFolder}/index.js`, `args`, `env.NODE_ENV`, `console`, `outFiles ${workspaceFolder}/**/*.js`. (I) for TS the program would be the compiled output with `preLaunchTask` running `tsc` (npm: build) and `sourceMaps`/`outFiles` pointing at `dist`; `outFiles` is the one measured hook for that.
- **JS/TS script**: (M) the `node` launch above, one config per run mode, `env: {NODE_ENV: "development"}`.
- **JS/TS Claude plugin**: no measured example. (I) same `node` launch of the plugin's entry plus an attach entry; nothing derivable.

Gaps to settle before shipping, since the data cannot: whether to use `debugpy` or `python` (both work in current VS Code; `python` is the older alias), the `justMyCode` default, and whether any non-Python preset should keep Python Current File.
