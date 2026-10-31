# Working on __RK_PROJECT__

This repository holds a Paradox game mod. The mod itself is `mod/`: the folder the game loads, and the folder a Workshop upload ships. Everything else stays above it, so it never reaches the game or the Workshop.

## Load the working copy in the game

The game finds a local mod through a small pointer file in its Documents folder, `Documents\Paradox Interactive\<Game>\mod\__RK_PROJECT__.mod`. For Crusader Kings III, `<Game>` is `Crusader Kings III`. Write it once, with any editor:

```
name="__RK_PROJECT__"
path="C:/path/to/__RK_PROJECT__/mod"
supported_version="1.20.*"
```

`path` names this repository's `mod/` folder, with forward slashes. Then enable the mod in the game's launcher. git-repokit never writes this file, and never touches the launcher's own files: they belong to the game.

## Version

The version lives in `VERSION`, and `mod/descriptor.mod`'s `version="..."` line follows it:

```
python scripts/repokit-common/sync-versions.py --bump patch
```

Only that line changes. `supported_version`, the encoding and the line endings stay as they were.

## Checks

- **On push:** the game's [Tiger](https://github.com/amtep/tiger) linter (`ck3-tiger`, `vic3-tiger`, `imperator-tiger`) runs on the mod when it is on PATH. The push shows Tiger's summary line, and the full report goes to `.git/repokit-<linter>.txt`. Findings never block. Set `paradox-game` in `.repokit-common.toml` to choose the linter.
- **On commit:** a localization `.yml` saved without a UTF-8 BOM is refused. The game would skip it without an error, and its keys would show raw in the game.

## Encoding

Keep localization files as **UTF-8 with BOM**, and script files as the game expects. `.gitattributes` stops git from converting anything under `mod/`.
