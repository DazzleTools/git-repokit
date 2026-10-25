# Platform Support

git-repokit is pure Python (3.10 or newer) and is built to work the same way on Windows, Linux and macOS. It drives `git` (and `gh` for `--github`), so most of what differs between platforms is what those tools and the shell provide.

## What runs where

| Part | Windows | Linux | macOS |
|---|---|---|---|
| `repokit` CLI | Tested | Tested (CI) | Expected |
| `create`, the layers and presets | Tested | Tested (CI, unit tests) | Expected |
| The vault (`private/` as its own repository) | Tested | Tested (CI, unit tests) | Expected |
| The vault linked into worktrees (`--private-mode nested` with a multi-branch strategy) | Tested (directory junction) | Expected (symlink) | Expected (symlink) |
| The private-branch model (`safe-merge`, guardrail hooks) | Tested | Expected | Expected |
| `--github` and `--github-setup` | Tested | Expected | Expected |
| The vendored git-repokit-common and its hooks | Tested | Tested (CI, unit tests) | Expected |

**Tested** means run on the development machine (Windows 11) with the full suite, or in CI. **Expected** means the code has no platform-specific path there, or a standard one, but nobody runs it routinely: please [file an issue](https://github.com/DazzleTools/git-repokit/issues) if it does not work.

## Created projects

| Preset | Windows | Linux | macOS | Notes |
|---|---|---|---|---|
| `python/*` | Yes | Yes | Yes | The created CI runs on Linux and Windows |
| `js-ts/*` | Yes | Yes | Yes | Needs Node.js |
| `c-cpp/cmake-app` | Yes | Yes | Yes | Built and tested with Visual Studio 2022's tools here; the created CI builds on all three |
| `c-cpp/msbuild` | Yes | No | No | A Visual Studio solution |
| `c-cpp/minimal` | Yes (`build.bat`) | Yes (`Makefile`) | Yes (`Makefile`) | |

`.vscode/launch.json` for C/C++ uses `cppvsdbg` on Windows and `cppdbg` elsewhere.

## Links between worktrees and the vault

On Windows, a worktree's `private` is a **directory junction** to the vault: it needs no administrator rights and no Developer Mode. repokit creates it directly, and falls back to PowerShell's `New-Item -ItemType Junction` if Python cannot. Elsewhere it is a **symlink**.

## Requirements by platform

- **git** with `git subtree` (used to vendor git-repokit-common). Git for Windows and the Debian and Ubuntu `git` packages include it; some distributions ship it as a separate package (Fedora's `git-subtree`, for example). `--no-common` skips it.
- **A POSIX shell for the hooks.** The vendored hooks are `sh` scripts. Git runs them with its own shell on Windows (Git for Windows ships one), and with the system shell elsewhere.
- **`gh`, the GitHub CLI,** for `--github` only.
- **Line endings:** every project gets a `.gitattributes`, so files keep their line endings whatever `core.autocrlf` says. git-repokit's own license texts are checked out byte for byte, because the tests fingerprint them.

## CI testing

`.github/workflows/main.yml` runs the unit tests on Python 3.10, 3.11, 3.12 and 3.13, on `ubuntu-latest` and `windows-latest`, and builds the package. The full suite, including the integration tests that create real repositories, runs on Windows before each release (`python -m pytest -q`, about ten minutes).

## Known limitations

- **macOS** is expected to work but is not in CI.
- **The vault links on Linux and macOS** (symlinks) are not exercised by the CI's unit tests.
- **`--private-mode nested` with a multi-branch strategy** builds its public branches incorrectly today; see [#16](https://github.com/DazzleTools/git-repokit/issues/16).
