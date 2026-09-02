#!/usr/bin/env python3
"""Temporary-directory tests for the standalone ИскИн installer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

TEST_DIR = Path(__file__).resolve().parent
ROOT = TEST_DIR.parent
CANONICAL = TEST_DIR / "install-iskin.py"

sys.path.insert(0, str(TEST_DIR))
from test_verify_release import (  # noqa: E402
    ARCHIVE_NAME,
    INSTALLER_NAME,
    SUMS_NAME,
    VERSION,
    build_release,
    sha256_file,
    template_payload,
)


def load_canonical() -> ModuleType:
    spec = importlib.util.spec_from_file_location("iskin_test_installer", CANONICAL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical installer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tree_snapshot(path: Path) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    if not path.exists() and not path.is_symlink():
        return result
    for current, dirs, files in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(dirs)
        files[:] = sorted(files)
        for name in dirs + files:
            child = current_path / name
            relative = child.relative_to(path).as_posix()
            if child.is_symlink():
                result[relative] = ("symlink", os.readlink(child))
            elif child.is_dir():
                result[relative] = ("dir", "")
            else:
                result[relative] = ("file", hashlib.sha256(child.read_bytes()).hexdigest())
    return result


class InstallIskinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-install-")
        self.root = Path(self.tempdir.name)
        self.release_dir = self.root / "release"
        self.release_dir.mkdir()
        self.archive = build_release(self.release_dir)
        self.module = load_canonical()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def expected_sha256(self) -> str:
        return sha256_file(self.archive)

    def run_cli(self, script: Path, target: Path, *, init_git: bool = False) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(script),
            "--archive",
            str(self.archive),
            "--release-version",
            VERSION,
            "--expected-sha256",
            self.expected_sha256(),
            "--target-path",
            str(target),
        ]
        if init_git:
            command.append("--init-git")
        return subprocess.run(command, cwd=self.root, text=True, capture_output=True, check=False)

    def assert_installed(self, target: Path) -> None:
        self.assertTrue(target.is_dir())
        payload = template_payload()
        for relative, data in payload.items():
            installed = target / relative
            self.assertTrue(installed.is_file(), relative)
            self.assertEqual(installed.read_bytes(), data, relative)
        self.assertEqual((target / ".iskin" / "version").read_text(encoding="utf-8").strip(), VERSION)
        manifest_path = target / ".iskin" / "installation-manifest.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["release_version"], VERSION)
        self.assertEqual(manifest["archive_sha256"], self.expected_sha256())
        expected_paths = sorted(list(payload) + [".iskin/version"])
        self.assertEqual([item["path"] for item in manifest["files"]], expected_paths)
        for item in manifest["files"]:
            self.assertEqual(item["sha256"], hashlib.sha256((target / item["path"]).read_bytes()).hexdigest())

    def test_install_to_nonexistent_target(self) -> None:
        target = self.root / "new-project"
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed(target)

    def test_install_to_empty_target(self) -> None:
        target = self.root / "empty-project"
        target.mkdir()
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed(target)

    def test_existing_git_directory_is_preserved(self) -> None:
        target = self.root / "git-directory-project"
        git_dir = target / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        before = tree_snapshot(git_dir)
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_snapshot(git_dir), before)
        self.assert_installed(target)

    def test_existing_git_worktree_file_is_preserved(self) -> None:
        target = self.root / "git-file-project"
        target.mkdir()
        git_file = target / ".git"
        git_file.write_text("gitdir: /tmp/external-worktree\n", encoding="utf-8")
        before = git_file.read_bytes()
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(git_file.read_bytes(), before)
        self.assert_installed(target)

    def test_nonempty_target_is_rejected_without_changes(self) -> None:
        target = self.root / "nonempty-project"
        target.mkdir()
        marker = target / "existing.txt"
        marker.write_text("keep\n", encoding="utf-8")
        before = tree_snapshot(target)
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 6)
        self.assertEqual(tree_snapshot(target), before)

    def test_target_symlink_is_rejected(self) -> None:
        real_target = self.root / "real-target"
        real_target.mkdir()
        target = self.root / "target-link"
        target.symlink_to(real_target, target_is_directory=True)
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 6)
        self.assertTrue(target.is_symlink())
        self.assertEqual(tree_snapshot(real_target), {})

    def test_git_symlink_is_rejected(self) -> None:
        target = self.root / "git-link-project"
        target.mkdir()
        real_git = self.root / "real-git"
        real_git.mkdir()
        (target / ".git").symlink_to(real_git, target_is_directory=True)
        before = tree_snapshot(target)
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 6)
        self.assertEqual(tree_snapshot(target), before)

    def test_validation_failure_does_not_change_target(self) -> None:
        target = self.root / "validation-failure-project"
        target.mkdir()
        before = tree_snapshot(target)
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0)
        installed_before = tree_snapshot(target)

        broken = subprocess.run(
            [
                sys.executable,
                str(CANONICAL),
                "--archive",
                str(self.archive),
                "--release-version",
                VERSION,
                "--expected-sha256",
                "0" * 64,
                "--target-path",
                str(target),
            ],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(broken.returncode, 3)
        self.assertEqual(tree_snapshot(target), installed_before)
        self.assertNotEqual(before, installed_before)

    def test_injected_mid_install_failure_rolls_back_and_has_no_manifest(self) -> None:
        target = self.root / "rollback-project"
        target.mkdir()
        code, report = self.module.install_release(
            self.archive,
            VERSION,
            self.expected_sha256(),
            target,
            fail_after_files=1,
        )
        self.assertEqual(code, 7)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(tree_snapshot(target), {})
        self.assertFalse((target / ".iskin" / "installation-manifest.json").exists())

    def test_manifest_is_created_last(self) -> None:
        target = self.root / "event-project"
        target.mkdir()
        events: list[str] = []
        code, _ = self.module.install_release(
            self.archive,
            VERSION,
            self.expected_sha256(),
            target,
            event_hook=events.append,
        )
        self.assertEqual(code, 0)
        self.assertTrue(events)
        self.assertEqual(events[-1], "installation_manifest_created")
        self.assert_installed(target)

    def test_installation_hashes_and_version_are_correct(self) -> None:
        target = self.root / "metadata-project"
        result = self.run_cli(CANONICAL, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed(target)

    def test_repeat_installation_is_rejected_without_changes(self) -> None:
        target = self.root / "repeat-project"
        first = self.run_cli(CANONICAL, target)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = tree_snapshot(target)
        second = self.run_cli(CANONICAL, target)
        self.assertEqual(second.returncode, 6)
        self.assertEqual(tree_snapshot(target), before)

    def test_no_overwrite_when_destination_appears_mid_install(self) -> None:
        target = self.root / "race-project"
        target.mkdir()
        injected = target / "AGENTS.md"

        def inject_after_first_transfer(event: str) -> None:
            if event == "template_file_transferred" and not injected.exists():
                injected.write_text("external\n", encoding="utf-8")

        code, _ = self.module.install_release(
            self.archive,
            VERSION,
            self.expected_sha256(),
            target,
            event_hook=inject_after_first_transfer,
        )
        self.assertEqual(code, 7)
        self.assertEqual(injected.read_text(encoding="utf-8"), "external\n")
        self.assertFalse((target / ".iskin" / "installation-manifest.json").exists())
        remaining = {path: value for path, value in tree_snapshot(target).items() if path != "AGENTS.md"}
        self.assertEqual(remaining, {})

    def test_init_git_requires_explicit_flag(self) -> None:
        without_flag = self.root / "without-git-init"
        result = self.run_cli(CANONICAL, without_flag)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((without_flag / ".git").exists())

        with_flag = self.root / "with-git-init"
        result = self.run_cli(CANONICAL, with_flag, init_git=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((with_flag / ".git").is_dir())
        self.assert_installed(with_flag)
        self.assertEqual(subprocess.run(["git", "remote"], cwd=with_flag, text=True, capture_output=True).stdout, "")
        self.assertNotEqual(subprocess.run(["git", "show-ref"], cwd=with_flag, text=True, capture_output=True).returncode, 0)

    def test_init_git_on_empty_target_requires_explicit_flag(self) -> None:
        target = self.root / "empty-with-git-init"
        target.mkdir()
        result = self.run_cli(CANONICAL, target, init_git=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / ".git").is_dir())
        self.assert_installed(target)

    def test_standalone_copy_runs_without_repository_modules(self) -> None:
        standalone_dir = self.root / "standalone-release"
        standalone_dir.mkdir()
        archive = build_release(standalone_dir)
        standalone = standalone_dir / INSTALLER_NAME
        shutil.copy2(CANONICAL, standalone)
        installer_digest = sha256_file(standalone)
        (standalone_dir / SUMS_NAME).write_text(
            f"{sha256_file(archive)}  {ARCHIVE_NAME}\n"
            f"{installer_digest}  {INSTALLER_NAME}\n",
            encoding="utf-8",
        )
        self.archive = archive
        target = self.root / "standalone-target"
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        result = subprocess.run(
            [
                sys.executable,
                str(standalone),
                "--archive",
                str(archive),
                "--release-version",
                VERSION,
                "--expected-sha256",
                sha256_file(archive),
                "--target-path",
                str(target),
            ],
            cwd=standalone_dir,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed(target)


if __name__ == "__main__":
    unittest.main()
