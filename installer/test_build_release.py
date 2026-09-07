#!/usr/bin/env python3
"""Temporary-directory integration tests for build_release.py."""

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
import zipfile
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "installer" / "build_release.py"
CANONICAL_INSTALLER = ROOT / "installer" / "install-iskin.py"
TEMPLATE_ROOT = ROOT / "package" / "template"
VERSION = "0.3.0"
ARCHIVE_NAME = "iskin-v0.3.0.zip"
INSTALLER_NAME = "install-iskin.py"
SUMS_NAME = "SHA256SUMS"


def load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("iskin_release_builder_tests", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_release.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files() -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(TEMPLATE_ROOT.rglob("*")):
        if path.is_file():
            result[path.relative_to(TEMPLATE_ROOT).as_posix()] = path.read_bytes()
    return result


class BuildReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-build-tests-")
        self.root = Path(self.tempdir.name)
        self.template = source_files()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_builder(self, output: Path, version: str = VERSION) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILD_SCRIPT), "--release-version", version, "--output-dir", str(output)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def build_successfully(self, output: Path) -> None:
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_release_shape(self, output: Path) -> None:
        self.assertEqual({path.name for path in output.iterdir()}, {ARCHIVE_NAME, INSTALLER_NAME, SUMS_NAME})
        self.assertEqual((output / INSTALLER_NAME).read_bytes(), CANONICAL_INSTALLER.read_bytes())
        with zipfile.ZipFile(output / ARCHIVE_NAME) as archive:
            self.assertEqual(archive.comment, b"")
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertTrue(all(not name.endswith("/") for name in names))
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.extra, b"")
                self.assertEqual(info.comment, b"")
                self.assertEqual(info.create_system, 3)
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)
            self.assertEqual(names[0], "iskin-v0.3.0/VERSION")
            self.assertEqual(names[1], "iskin-v0.3.0/package-manifest.json")
            self.assertEqual((archive.read(names[0])), b"0.3.0\n")
            manifest_bytes = archive.read(names[1])
            self.assertNotIn(b"\r", manifest_bytes)
            self.assertTrue(manifest_bytes.endswith(b"\n"))
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            self.assertEqual(set(manifest), {"schema_version", "release_version", "root", "template_root", "files"})
            self.assertEqual(
                list(manifest),
                ["schema_version", "release_version", "root", "template_root", "files"],
            )
            manifest_paths = {item["path"] for item in manifest["files"]}
            self.assertIn(".iskin/policy_gate.py", manifest_paths)
            self.assertNotIn(".iskin/policy_state.json", manifest_paths)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["release_version"], VERSION)
            self.assertEqual(manifest["root"], "iskin-v0.3.0")
            self.assertEqual(manifest["template_root"], "template")
            entries = manifest["files"]
            self.assertEqual([entry["path"] for entry in entries], sorted(self.template))
            self.assertEqual(set(entry["path"] for entry in entries), set(self.template))
            for entry in entries:
                self.assertEqual(entry["sha256"], sha256(self.template[entry["path"]]))
            expected_template_names = {f"iskin-v0.3.0/template/{path}" for path in self.template}
            self.assertEqual(set(names[2:]), expected_template_names)

        archive_sha256 = sha256((output / ARCHIVE_NAME).read_bytes())
        installer_sha256 = sha256((output / INSTALLER_NAME).read_bytes())
        expected_sums = (
            f"{installer_sha256}  {INSTALLER_NAME}\n"
            f"{archive_sha256}  {ARCHIVE_NAME}\n"
        ).encode("ascii")
        self.assertEqual((output / SUMS_NAME).read_bytes(), expected_sums)

    def test_builds_current_template_into_exactly_three_files(self) -> None:
        output = self.root / "release"
        self.build_successfully(output)
        self.assert_release_shape(output)

    def test_existing_empty_output_is_supported(self) -> None:
        output = self.root / "release"
        output.mkdir()
        self.build_successfully(output)
        self.assert_release_shape(output)

    def test_validator_and_real_installer_accept_generated_release(self) -> None:
        output = self.root / "release"
        self.build_successfully(output)
        archive = output / ARCHIVE_NAME
        archive_sha256 = sha256(archive.read_bytes())
        validated = subprocess.run(
            [
                sys.executable,
                str(ROOT / "installer" / "verify_release.py"),
                "--archive",
                str(archive),
                "--release-version",
                VERSION,
                "--expected-sha256",
                archive_sha256,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        target = self.root / "project"
        installed = subprocess.run(
            [
                sys.executable,
                str(CANONICAL_INSTALLER),
                "--archive",
                str(archive),
                "--release-version",
                VERSION,
                "--expected-sha256",
                archive_sha256,
                "--target-path",
                str(target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        for relative, expected in self.template.items():
            self.assertEqual((target / relative).read_bytes(), expected)
        self.assertEqual((target / ".iskin" / "version").read_bytes(), b"0.3.0\n")
        installation_manifest = json.loads(
            (target / ".iskin" / "installation-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(installation_manifest["schema_version"], 1)
        self.assertEqual(installation_manifest["release_version"], VERSION)
        self.assertEqual(installation_manifest["archive_sha256"], archive_sha256)

    def test_independent_builds_are_byte_identical(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        self.build_successfully(first)
        self.build_successfully(second)
        for name in (ARCHIVE_NAME, INSTALLER_NAME, SUMS_NAME):
            first_bytes = (first / name).read_bytes()
            second_bytes = (second / name).read_bytes()
            self.assertEqual(first_bytes, second_bytes, name)
            self.assertEqual(sha256(first_bytes), sha256(second_bytes), name)

    def test_invalid_version_refuses_without_output(self) -> None:
        output = self.root / "release"
        result = self.run_builder(output, "0.3")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_nonempty_output_refuses_without_overwrite(self) -> None:
        output = self.root / "release"
        output.mkdir()
        sentinel = output / "sentinel"
        sentinel.write_bytes(b"keep")
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertEqual([path.name for path in output.iterdir()], ["sentinel"])

    def test_output_symlink_refuses_without_following(self) -> None:
        real_output = self.root / "real-output"
        real_output.mkdir()
        output = self.root / "release-link"
        output.symlink_to(real_output, target_is_directory=True)
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertTrue(output.is_symlink())
        self.assertEqual(list(real_output.iterdir()), [])

    def test_injected_failure_leaves_no_partial_result(self) -> None:
        builder = load_builder()
        output = self.root / "release"

        def fail_after_probe(event: str) -> None:
            if event == "probe_complete":
                raise RuntimeError("injected generator failure")

        code, report = builder.build_release(VERSION, output, event_hook=fail_after_probe)
        self.assertEqual(code, 7, report)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_no_permanent_release_files_are_created_by_tests(self) -> None:
        for name in (ARCHIVE_NAME, INSTALLER_NAME, SUMS_NAME):
            self.assertFalse((ROOT / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
