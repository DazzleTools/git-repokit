"""The C/C++ layer through `repokit create`: the three archetypes build with the
local Visual Studio toolchain, the stubs announce themselves, the resource file
and header reach the project byte for byte, and git-repokit-common's version
tool reads the generated header.

Design: the Phase 2 v2 analysis of 2026-10-09 (units U4.1-U4.5) in the
project's private notes; the layer files are the C/C++ template proof's
(git-repokit-common, tests/one-offs/thinking/poc-templates-c-cpp, 8/8 on
2026-10-07), copied unchanged in the previous slice.

The build tests need Visual Studio 2022's bundled CMake, vcpkg and MSBuild
(C:\\Program Files\\Microsoft Visual Studio\\2022\\Community, or VS_ROOT);
without them they skip and say so. They are integration tests (a minute or
two); nothing reaches the network (the vcpkg manifest has no dependencies).
"""

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from .test_utils import RepoKitTestCase

REPO = Path(__file__).resolve().parents[1]
LAYERS = REPO / "repokit" / "templates" / "layers"
TOKEN = re.compile(rb"__RK_[A-Z_]+?__")


def _vs_root():
    candidates = [os.environ.get("VS_ROOT")] if os.environ.get("VS_ROOT") else []
    candidates += [r"C:\Program Files\Microsoft Visual Studio\2022\Community",
                   r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
                   r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise"]
    for c in candidates:
        if c and Path(c, "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe").exists():
            return Path(c)
    return None


VS = _vs_root()
CMAKE = VS / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe" if VS else None
CTEST = VS / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/ctest.exe" if VS else None
MSBUILD = VS / "MSBuild/Current/Bin/MSBuild.exe" if VS else None
VCVARS = VS / "VC/Auxiliary/Build/vcvars64.bat" if VS else None
VCPKG = VS / "VC/vcpkg" if VS else None

needs_toolchain = unittest.skipUnless(
    VS is not None and all(p.exists() for p in (CMAKE, CTEST, MSBUILD, VCVARS, VCPKG / "vcpkg.exe")),
    "Visual Studio 2022 with CMake, vcpkg and MSBuild not found (set VS_ROOT)")


def _run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def _tokens_left(root):
    return [p.relative_to(root).as_posix() for p in Path(root).rglob("*")
            if p.is_file() and ".git" not in p.parts and "repokit-common" not in p.parts
            and (TOKEN.search(p.name.encode()) or TOKEN.search(p.read_bytes()))]


class TestCCppLayer(RepoKitTestCase):

    def _create(self, name, *extra):
        self.assert_repokit_success(["create", name, *extra, "--no-push"])
        return Path(self.test_dir, name)

    def test_cmake_lib_and_qt_stubs_announce_themselves(self):
        """U4 stubs: naming an unbuilt archetype stops before anything is created."""
        for arch in ("c-cpp/cmake-lib", "c-cpp/qt"):
            rc, out, err = self.run_repokit(["create", "demo", "--archetype", arch, "--no-push"])
            self.assertNotEqual(rc, 0, arch)
            self.assertIn(f"archetype {arch} is not built yet", out + err)
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, "demo")), arch)

    def test_resource_file_and_header_are_the_layers_bytes_with_tokens_resolved(self):
        """U4.4: app.rc and version.h in the project equal the layer's files with
        the tokens replaced and not one other byte changed (the proof's A5 claim,
        through the real engine)."""
        repo = self._create("my-tool", "--language", "c-cpp")
        subs = {b"__RK_SNAKE__": b"my_tool", b"__RK_MACRO__": b"MY_TOOL", b"__RK_PROJECT__": b"my-tool",
                b"__RK_DESCRIPTION__": b""}
        for rel in ("src/app.rc", "include/__RK_SNAKE__/version.h"):
            src = (LAYERS / "languages/c-cpp" / rel).read_bytes()
            expected = src
            for k, v in subs.items():
                expected = expected.replace(k, v)
            got = (repo / rel.replace("__RK_SNAKE__", "my_tool")).read_bytes()
            # the description token takes the project's description; strip it from the comparison
            self.assertEqual(got.replace(b"A new project repository", b""), expected, rel)
        self.assertEqual(_tokens_left(repo), [])
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["languages"], meta["archetype"]), (["c-cpp"], "c-cpp/cmake-app"))

    @needs_toolchain
    def test_cmake_app_configures_builds_and_passes_ctest(self):
        """U4.2: the default C/C++ project configures with the vcpkg toolchain,
        builds, passes its CTest, and the binary reports the header's version."""
        repo = self._create("my-tool", "--language", "c-cpp")
        # The project-wide phase is shown by --version like Python's
        # get_display_version(): set it in the generated header before building.
        header = repo / "include" / "my_tool" / "version.h"
        header.write_bytes(header.read_bytes().replace(b'_PROJECT_PHASE ""', b'_PROJECT_PHASE "alpha"'))
        env = dict(os.environ, VCPKG_ROOT=str(VCPKG))
        r = _run([str(CMAKE), "--preset", "windows-release"], repo, env)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("my-tool version 0.1.0", r.stdout)
        r = _run([str(CMAKE), "--build", "--preset", "windows-release"], repo, env)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        r = _run([str(CTEST), "--preset", "windows-release"], repo, env)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        exe = repo / "build" / "Release" / "my-tool.exe"
        self.assertTrue(exe.exists())
        r = _run([str(exe), "--version"], repo)
        self.assertEqual(r.returncode, 0)
        self.assertIn("my-tool ALPHA 0.1.0 (0.1.0_main_", r.stdout)   # project phase, version, the build stamp

    @needs_toolchain
    def test_msbuild_archetype_builds(self):
        """U4.3: the Visual Studio solution builds and the binary runs."""
        repo = self._create("my-tool", "--archetype", "c-cpp/msbuild")
        r = _run([str(MSBUILD), str(repo / "my-tool.sln"), "-nologo", "-v:minimal",
                  "-p:Configuration=Release", "-p:Platform=x64"], repo)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        exe = repo / "x64" / "Release" / "my-tool.exe"
        self.assertTrue(exe.exists(), r.stdout[-2000:])
        r = _run([str(exe), "--version"], repo)
        self.assertEqual(r.returncode, 0)
        self.assertIn("0.1.0", r.stdout)

    @needs_toolchain
    def test_minimal_archetype_builds_with_cl(self):
        """U4.3: build.bat compiles the one source file with rc and cl under vcvars64."""
        repo = self._create("my-tool", "--archetype", "c-cpp/minimal")
        wrapper = repo.parent / "run_min.cmd"
        # .\ because NoDefaultCurrentDirectoryInExePath may be set; CRLF for cmd
        wrapper.write_bytes(f'@call "{VCVARS}" >nul\r\n@cd /d "{repo}"\r\n@call .\\build.bat\r\n'.encode())
        r = _run(["cmd.exe", "/c", str(wrapper)], repo)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        exe = repo / "build" / "my-tool.exe"
        self.assertTrue(exe.exists(), r.stdout[-2000:])
        r = _run([str(exe), "--version"], repo)
        self.assertEqual(r.returncode, 0)
        self.assertIn("0.1.0", r.stdout)

    def test_sync_versions_check_reads_the_generated_header(self):
        """U4.5: git-repokit-common's version tool, vendored into the project,
        reads include/<pkg>/version.h and finds it in sync. Needs the vendored
        copy at 0.4.0 or later (the header source kind); an older copy skips."""
        repo = self._create("my-tool", "--language", "c-cpp")
        tool = repo / "scripts" / "repokit-common" / "sync-versions.py"
        if not tool.exists():
            self.skipTest("git-repokit-common not vendored (REPOKIT_COMMON_SOURCE=off)")
        if "c-header" not in tool.read_text(encoding="utf-8", errors="replace"):
            self.skipTest("the vendored git-repokit-common predates 0.4.0 (no C-header version source yet)")
        settings = (repo / ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertIn('version-source = "include/my_tool/version.h"', settings)
        r = _run([shutil.which("python") or "python", str(tool), "--check"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
