#!/usr/bin/env python3
"""Read-only validator for the ИскИн v0.3 release format.

The validator inspects a ZIP and its two sibling release files. It never
extracts the archive and has no target-project or installation operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_RELEASE = 3
EXIT_ARCHIVE = 4
EXIT_MANIFEST = 5

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256_INPUT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SHA256_MANIFEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ARCHIVE_RE = re.compile(r"^iskin-v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\.zip$")
_FORBIDDEN_PATH_RE = re.compile(
    r"budget|p0-0[1-5]|(?:^|[-_.])g[1-5](?:$|[-_.])|swift|xcode|xctest|xcuitest|budgetapp|₽|руб",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


class VerificationFailure(Exception):
    def __init__(self, code: int, name: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.name = name
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_regular(path: Path, label: str) -> None:
    if path.is_symlink():
        raise VerificationFailure(EXIT_RELEASE, f"{label}_symlink", f"{label} is a symlink")
    if not path.is_file():
        raise VerificationFailure(EXIT_RELEASE, f"{label}_file", f"{label} is missing or not a regular file")


def _validate_safe_member_name(name: str) -> None:
    if not name or "\x00" in name:
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe ZIP member path: {name!r}")
    if "\\" in name or name.startswith("/") or name.startswith("//"):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe ZIP member path: {name!r}")
    if re.match(r"^[A-Za-z]:", name):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe ZIP member path: {name!r}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts[:-1]):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe ZIP member path: {name!r}")
    if parts[-1] in {".", ".."}:
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe ZIP member path: {name!r}")


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _parse_sha256sums(path: Path, archive_name: str, installer_name: str) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationFailure(EXIT_RELEASE, "sha256sums_read", f"cannot read SHA256SUMS: {exc}") from exc

    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
        if not match:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_format", f"invalid SHA256SUMS line {line_number}")
        digest, name = match.groups()
        if name in entries:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_duplicate", f"duplicate SHA256SUMS path: {name}")
        if name not in {archive_name, installer_name} or "/" in name or "\\" in name:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_path", f"unexpected SHA256SUMS path: {name}")
        entries[name] = digest.lower()

    expected_names = {archive_name, installer_name}
    if set(entries) != expected_names:
        missing = sorted(expected_names - set(entries))
        extra = sorted(set(entries) - expected_names)
        raise VerificationFailure(
            EXIT_RELEASE,
            "sha256sums_entries",
            f"SHA256SUMS must contain exactly archive and installer; missing={missing}, extra={extra}",
        )
    return entries


def _load_manifest(raw: bytes, expected_version: str, expected_root: str) -> dict[str, Any]:
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_json", f"invalid package-manifest.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise VerificationFailure(EXIT_MANIFEST, "manifest_object", "package-manifest.json must be an object")

    required = {"schema_version", "release_version", "root", "template_root", "files"}
    keys = set(manifest)
    missing = sorted(required - keys)
    if missing:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_fields", f"manifest is missing fields: {missing}")
    unknown = sorted(keys - required)
    if unknown:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_unknown_fields", f"manifest has unknown fields: {unknown}")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_schema", "schema_version must be integer 1")
    release_version = manifest["release_version"]
    if not isinstance(release_version, str) or not _VERSION_RE.fullmatch(release_version):
        raise VerificationFailure(EXIT_MANIFEST, "manifest_release_version", "release_version must be MAJOR.MINOR.PATCH")
    if release_version != expected_version:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_release_version", "manifest release_version does not match release")
    root = manifest["root"]
    if not isinstance(root, str) or root != f"iskin-v{release_version}" or root != expected_root:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_root", "manifest root must be iskin-v<release_version>")
    if manifest["template_root"] != "template":
        raise VerificationFailure(EXIT_MANIFEST, "manifest_template_root", "manifest template_root must be 'template'")
    if not isinstance(manifest["files"], list) or not manifest["files"]:
        raise VerificationFailure(EXIT_MANIFEST, "manifest_files", "manifest files must be a non-empty array")

    seen: set[str] = set()
    paths: list[str] = []
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise VerificationFailure(EXIT_MANIFEST, "manifest_entry", "each manifest file entry must contain path and sha256 only")
        path = item["path"]
        digest = item["sha256"]
        if (
            not isinstance(path, str)
            or not path
            or path.endswith("/")
            or path in {"VERSION", "package-manifest.json"}
            or path.startswith("template/")
        ):
            raise VerificationFailure(EXIT_MANIFEST, "manifest_path", f"manifest path is not relative to template: {path!r}")
        _validate_safe_member_name(path)
        if not isinstance(digest, str) or not _SHA256_MANIFEST_RE.fullmatch(digest):
            raise VerificationFailure(EXIT_MANIFEST, "manifest_sha256", f"invalid SHA-256 for manifest path: {path!r}")
        if path in seen:
            raise VerificationFailure(EXIT_MANIFEST, "manifest_duplicate", f"duplicate manifest path: {path}")
        if _FORBIDDEN_PATH_RE.search(path):
            raise VerificationFailure(EXIT_ARCHIVE, "forbidden_product_file", f"forbidden product-specific path: {path}")
        seen.add(path)
        paths.append(path)
    if paths != sorted(paths):
        raise VerificationFailure(EXIT_MANIFEST, "manifest_order", "manifest files must be sorted lexicographically by path")
    return manifest


def _verify_archive(archive: Path, expected_version: str, checks: list[Check]) -> None:
    archive_name = archive.name
    match = _ARCHIVE_RE.fullmatch(archive_name)
    if not match or match.group("version") != expected_version:
        raise VerificationFailure(EXIT_ARCHIVE, "archive_name", f"archive must be iskin-v{expected_version}.zip")
    checks.append(Check("archive_name", "PASS", archive_name))

    root = f"iskin-v{expected_version}"
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                duplicates = sorted({name for name in names if names.count(name) > 1})
                raise VerificationFailure(EXIT_ARCHIVE, "duplicate_paths", f"duplicate ZIP paths: {duplicates}")

            regular_infos: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                _validate_safe_member_name(info.filename)
                if _is_zip_symlink(info):
                    raise VerificationFailure(EXIT_ARCHIVE, "symlink", f"ZIP member is a symlink: {info.filename}")
                if info.filename == f"{root}/" or info.filename == f"{root}/template/":
                    if not info.is_dir():
                        raise VerificationFailure(EXIT_ARCHIVE, "directory_type", f"expected directory: {info.filename}")
                    continue
                if info.is_dir():
                    raise VerificationFailure(EXIT_ARCHIVE, "unexpected_directory", f"unexpected ZIP directory: {info.filename}")
                if not info.filename.startswith(f"{root}/"):
                    raise VerificationFailure(EXIT_ARCHIVE, "archive_root", f"member outside archive root: {info.filename}")
                if _FORBIDDEN_PATH_RE.search(info.filename):
                    raise VerificationFailure(EXIT_ARCHIVE, "forbidden_product_file", f"forbidden product-specific path: {info.filename}")
                regular_infos[info.filename] = info

            if not regular_infos:
                raise VerificationFailure(EXIT_ARCHIVE, "archive_files", "archive contains no regular files")
            checks.append(Check("safe_paths_and_types", "PASS", f"{len(infos)} ZIP members; no traversal or symlinks"))

            version_path = f"{root}/VERSION"
            manifest_path = f"{root}/package-manifest.json"
            if version_path not in regular_infos or manifest_path not in regular_infos:
                raise VerificationFailure(EXIT_ARCHIVE, "control_files", "archive must contain VERSION and package-manifest.json")
            try:
                version = zf.read(regular_infos[version_path]).decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise VerificationFailure(EXIT_ARCHIVE, "version_encoding", f"VERSION is not valid UTF-8: {exc}") from exc
            if version != expected_version:
                raise VerificationFailure(EXIT_ARCHIVE, "version", f"VERSION contains {version!r}, expected {expected_version!r}")
            checks.append(Check("version", "PASS", version))

            manifest = _load_manifest(zf.read(regular_infos[manifest_path]), expected_version, root)
            manifest_paths = {item["path"] for item in manifest["files"]}
            expected_members = {version_path, manifest_path} | {f"{root}/template/{path}" for path in manifest_paths}
            actual_members = set(regular_infos)
            if actual_members != expected_members:
                missing = sorted(expected_members - actual_members)
                extra = sorted(actual_members - expected_members)
                raise VerificationFailure(EXIT_ARCHIVE, "allowlist", f"manifest/archive mismatch; missing={missing}, extra={extra}")
            checks.append(Check("full_allowlist", "PASS", f"{len(manifest_paths)} template files"))

            for item in manifest["files"]:
                member_name = f"{root}/template/{item['path']}"
                observed = _sha256_bytes(zf.read(regular_infos[member_name]))
                if observed.lower() != item["sha256"].lower():
                    raise VerificationFailure(EXIT_MANIFEST, "file_sha256", f"SHA-256 mismatch for {item['path']}")
            checks.append(Check("template_sha256", "PASS", f"verified {len(manifest_paths)} template file hashes"))
            checks.append(Check("manifest", "PASS", "package-manifest.json is valid and complete"))
    except zipfile.BadZipFile as exc:
        raise VerificationFailure(EXIT_ARCHIVE, "zip_format", f"invalid ZIP archive: {exc}") from exc


def verify_release(archive: Path, expected_version: str, expected_sha256: str) -> tuple[int, dict[str, Any]]:
    """Verify a release without extracting or installing it.

    Returns ``(exit_code, report)``. The returned report is JSON-serializable.
    """

    checks: list[Check] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "FAIL",
        "exit_code": EXIT_USAGE,
        "archive": archive.name,
        "version": expected_version,
        "checks": [],
    }

    try:
        if not _VERSION_RE.fullmatch(expected_version):
            raise VerificationFailure(EXIT_USAGE, "release_version", "release version must be MAJOR.MINOR.PATCH")
        if not _SHA256_INPUT_RE.fullmatch(expected_sha256):
            raise VerificationFailure(EXIT_USAGE, "expected_sha256", "expected SHA-256 must be 64 hexadecimal characters")
        _require_regular(archive, "archive")
        checks.append(Check("archive_file", "PASS", "regular local file"))

        installer = archive.parent / "install-iskin.py"
        sums = archive.parent / "SHA256SUMS"
        _require_regular(installer, "install-iskin.py")
        _require_regular(sums, "SHA256SUMS")
        checks.append(Check("release_companions", "PASS", "install-iskin.py and SHA256SUMS are present"))

        observed_archive_sha256 = _sha256_file(archive)
        if observed_archive_sha256 != expected_sha256.lower():
            raise VerificationFailure(EXIT_RELEASE, "archive_sha256", "archive SHA-256 differs from expected_sha256")
        checks.append(Check("expected_sha256", "PASS", observed_archive_sha256))

        sums_entries = _parse_sha256sums(sums, archive.name, installer.name)
        if sums_entries[archive.name] != observed_archive_sha256:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_archive", "SHA256SUMS archive digest does not match archive")
        installer_sha256 = _sha256_file(installer)
        if sums_entries[installer.name] != installer_sha256:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_installer", "SHA256SUMS installer digest does not match installer")
        checks.append(Check("sha256sums", "PASS", "archive and installer digests match"))

        _verify_archive(archive, expected_version, checks)
        report.update({"status": "PASS", "exit_code": EXIT_OK})
    except VerificationFailure as exc:
        checks.append(Check(exc.name, "FAIL", exc.detail))
        report.update({"status": "FAIL", "exit_code": exc.code})
    except OSError as exc:
        checks.append(Check("filesystem", "FAIL", str(exc)))
        report.update({"status": "FAIL", "exit_code": EXIT_RELEASE})

    report["checks"] = [check.__dict__ for check in checks]
    return int(report["exit_code"]), report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only ИскИн v0.3 release validator")
    parser.add_argument("--archive", required=True, type=Path, help="path to iskin-v<version>.zip")
    parser.add_argument("--release-version", required=True, help="expected release version, e.g. 0.3.0")
    parser.add_argument("--expected-sha256", required=True, help="expected SHA-256 of the archive")
    parser.add_argument("--report", type=Path, help="optional JSON report path; parent must already exist")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    code, report = verify_release(args.archive, args.release_version, args.expected_sha256)
    if args.report:
        try:
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"FAIL report: {exc}", file=sys.stderr)
            return EXIT_RELEASE
    print(f"{report['status']} exit_code={code} archive={args.archive.name} version={args.release_version}")
    for check in report["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
