#!/usr/bin/env python3
"""Public CLI tests for installer/verify_release.py.

All release files and mutations live in a temporary directory. No target
project is created or touched.
"""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "installer" / "verify_release.py"
TEMPLATE = ROOT / "package" / "template"
VERSION = "0.3.0"
ARCHIVE_NAME = f"iskin-v{VERSION}.zip"
INSTALLER_NAME = "install-iskin.py"
SUMS_NAME = "SHA256SUMS"
ARCHIVE_ROOT = f"iskin-v{VERSION}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def template_payload() -> dict[str, bytes]:
    return {
        path.relative_to(TEMPLATE).as_posix(): path.read_bytes()
        for path in sorted(TEMPLATE.rglob("*"))
        if path.is_file()
    }


def build_release(
    directory: Path,
    *,
    payload: dict[str, bytes] | None = None,
    manifest_payload: dict[str, bytes] | None = None,
    version_file: str = VERSION,
    manifest_bytes: bytes | None = None,
    manifest_updates: dict[str, object] | None = None,
    manifest_remove: tuple[str, ...] = (),
    manifest_files: list[dict[str, object]] | None = None,
    extra_members: list[tuple[str, bytes, int | None]] | None = None,
) -> Path:
    payload = dict(template_payload() if payload is None else payload)
    manifest_payload = payload if manifest_payload is None else manifest_payload
    manifest = {
        "schema_version": 1,
        "release_version": VERSION,
        "root": ARCHIVE_ROOT,
        "template_root": "template",
        "files": manifest_files if manifest_files is not None else [
            {"path": path, "sha256": sha256_bytes(data)}
            for path, data in sorted(manifest_payload.items())
        ],
    }
    manifest.update(manifest_updates or {})
    for key in manifest_remove:
        manifest.pop(key, None)
    if manifest_bytes is None:
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()

    archive = directory / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{ARCHIVE_ROOT}/VERSION", version_file + "\n")
        zf.writestr(f"{ARCHIVE_ROOT}/package-manifest.json", manifest_bytes)
        for path, data in sorted(payload.items()):
            zf.writestr(f"{ARCHIVE_ROOT}/template/{path}", data)
        for name, data, mode in extra_members or []:
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.create_system = 3
                info.external_attr = mode << 16
            zf.writestr(info, data)

    installer = directory / INSTALLER_NAME
    installer.write_text("#!/usr/bin/env python3\n# fixture only\n", encoding="utf-8")
    sums = directory / SUMS_NAME
    sums.write_text(
        f"{sha256_file(archive)}  {ARCHIVE_NAME}\n"
        f"{sha256_file(installer)}  {INSTALLER_NAME}\n",
        encoding="utf-8",
    )
    return archive


class VerifyReleaseCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-verify-")
        self.directory = Path(self.tempdir.name)
        self.archive = build_release(self.directory)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_validator(self, archive: Path | None = None, *, expected: str | None = None, version: str = VERSION) -> subprocess.CompletedProcess[str]:
        archive = self.archive if archive is None else archive
        expected = sha256_file(archive) if expected is None else expected
        report = self.directory / "report.json"
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--archive",
                str(archive),
                "--release-version",
                version,
                "--expected-sha256",
                expected,
                "--report",
                str(report),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def rewrite_sums_for_archive(self, archive: Path) -> None:
        installer = self.directory / INSTALLER_NAME
        (self.directory / SUMS_NAME).write_text(
            f"{sha256_file(archive)}  {ARCHIVE_NAME}\n"
            f"{sha256_file(installer)}  {INSTALLER_NAME}\n",
            encoding="utf-8",
        )

    def rebuild(self, **kwargs: object) -> Path:
        self.archive.unlink()
        archive = build_release(self.directory, **kwargs)
        return archive

    def manifest_entries(self, payload: dict[str, bytes] | None = None) -> list[dict[str, object]]:
        payload = template_payload() if payload is None else payload
        return [
            {"path": path, "sha256": sha256_bytes(data)}
            for path, data in sorted(payload.items())
        ]

    def test_valid_archive_passes_and_writes_report(self) -> None:
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.directory / "report.json").is_file())
        report = json.loads((self.directory / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["exit_code"], 0)

    def test_wrong_expected_sha256_has_release_exit_code(self) -> None:
        result = self.run_validator(expected="0" * 64)
        self.assertEqual(result.returncode, 3)
        self.assertIn("archive_sha256", result.stdout)

    def test_malformed_expected_sha256_has_usage_exit_code(self) -> None:
        result = self.run_validator(expected="not-a-sha256")
        self.assertEqual(result.returncode, 2)
        self.assertIn("expected_sha256", result.stdout)

    def test_wrong_version_is_rejected(self) -> None:
        result = self.run_validator(version="0.3.1")
        self.assertEqual(result.returncode, 4)
        self.assertIn("archive_name", result.stdout)

    def test_wrong_version_file_is_rejected(self) -> None:
        archive = self.rebuild(version_file="9.9.9")
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("VERSION contains", result.stdout)

    def test_missing_file_is_rejected(self) -> None:
        payload = template_payload()
        original_payload = dict(payload)
        payload.pop(next(iter(sorted(payload))))
        archive = self.rebuild(payload=payload, manifest_payload=original_payload)
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("allowlist", result.stdout)

    def test_extra_file_is_rejected(self) -> None:
        archive = self.rebuild(extra_members=[(f"{ARCHIVE_ROOT}/template/extra.txt", b"extra", None)])
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("allowlist", result.stdout)

    def test_budget_specific_file_is_rejected(self) -> None:
        payload = template_payload()
        payload["Budget.txt"] = b"product-specific\n"
        archive = self.rebuild(payload=payload)
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("forbidden_product_file", result.stdout)

    def test_changed_file_hash_is_rejected(self) -> None:
        payload = template_payload()
        original_payload = dict(payload)
        first = sorted(payload)[0]
        payload[first] = b"changed bytes\n"
        archive = self.rebuild(payload=payload, manifest_payload=original_payload)
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("file_sha256", result.stdout)

    def test_damaged_manifest_is_rejected(self) -> None:
        archive = self.rebuild(manifest_bytes=b"{not-json")
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_json", result.stdout)

    def test_missing_manifest_field_is_rejected(self) -> None:
        archive = self.rebuild(manifest_remove=("release_version",))
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_fields", result.stdout)

    def test_unknown_manifest_field_is_rejected(self) -> None:
        archive = self.rebuild(manifest_updates={"unexpected": "value"})
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_unknown_fields", result.stdout)

    def test_manifest_release_version_mismatch_is_rejected(self) -> None:
        archive = self.rebuild(manifest_updates={"release_version": "0.3.1"})
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_release_version", result.stdout)

    def test_manifest_root_mismatch_is_rejected(self) -> None:
        archive = self.rebuild(manifest_updates={"root": "iskin-v0.3.1"})
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_root", result.stdout)

    def test_manifest_template_root_mismatch_is_rejected(self) -> None:
        archive = self.rebuild(manifest_updates={"template_root": "template-v2"})
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_template_root", result.stdout)

    def test_unknown_manifest_entry_field_is_rejected(self) -> None:
        entries = self.manifest_entries()
        entries[0]["unexpected"] = "value"
        archive = self.rebuild(manifest_files=entries)
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_entry", result.stdout)

    def test_unsorted_manifest_files_are_rejected(self) -> None:
        archive = self.rebuild(manifest_files=list(reversed(self.manifest_entries())))
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_order", result.stdout)

    def test_uppercase_manifest_sha256_is_rejected(self) -> None:
        entries = self.manifest_entries()
        entries[0]["sha256"] = "A" * 64
        archive = self.rebuild(manifest_files=entries)
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_sha256", result.stdout)

    def test_service_file_in_manifest_is_rejected(self) -> None:
        payload = template_payload()
        payload["VERSION"] = b"service file\n"
        archive = self.rebuild(payload=payload, manifest_files=self.manifest_entries(payload))
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_path", result.stdout)

    def test_non_integer_schema_version_is_rejected(self) -> None:
        archive = self.rebuild(manifest_updates={"schema_version": True})
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 5)
        self.assertIn("manifest_schema", result.stdout)

    def test_path_traversal_is_rejected(self) -> None:
        archive = self.rebuild(extra_members=[(f"{ARCHIVE_ROOT}/../../escape.txt", b"escape", None)])
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("safe_path", result.stdout)

    def test_absolute_path_is_rejected(self) -> None:
        archive = self.rebuild(extra_members=[("/absolute.txt", b"absolute", None)])
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("safe_path", result.stdout)

    def test_symlink_is_rejected(self) -> None:
        symlink_mode = stat.S_IFLNK | 0o777
        archive = self.rebuild(extra_members=[(f"{ARCHIVE_ROOT}/template/link", b"target", symlink_mode)])
        result = self.run_validator(archive)
        self.assertEqual(result.returncode, 4)
        self.assertIn("symlink", result.stdout)

    def test_duplicate_path_is_rejected(self) -> None:
        payload = template_payload()
        duplicate_name = f"{ARCHIVE_ROOT}/VERSION"
        self.archive.unlink()
        manifest = {
            "schema_version": 1,
            "release_version": VERSION,
            "root": ARCHIVE_ROOT,
            "template_root": "template",
            "files": [
                {"path": path, "sha256": sha256_bytes(data)}
                for path, data in sorted(payload.items())
            ],
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w") as zf:
                zf.writestr(duplicate_name, VERSION + "\n")
                zf.writestr(duplicate_name, VERSION + "\n")
                zf.writestr(f"{ARCHIVE_ROOT}/package-manifest.json", json.dumps(manifest).encode())
                for path, data in sorted(payload.items()):
                    zf.writestr(f"{ARCHIVE_ROOT}/template/{path}", data)
        self.rewrite_sums_for_archive(self.archive)
        result = self.run_validator()
        self.assertEqual(result.returncode, 4)
        self.assertIn("duplicate_paths", result.stdout)


if __name__ == "__main__":
    unittest.main()
