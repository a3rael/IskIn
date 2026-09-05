#!/usr/bin/env python3
"""Standalone ИскИн v0.3 release validator and local installer.

This file deliberately uses only the Python standard library. It is the
canonical source that a future release generator may publish unchanged as
``install-iskin.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_RELEASE = 3
EXIT_ARCHIVE = 4
EXIT_MANIFEST = 5
EXIT_TARGET = 6
EXIT_INSTALL = 7

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ARCHIVE_RE = re.compile(r"^iskin-v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\.zip$")
_FORBIDDEN_PATH_RE = re.compile(
    r"budget|p0-0[1-5]|(?:^|[-_.])g[1-5](?:$|[-_.])|swift|xcode|xctest|xcuitest|budgetapp|₽|руб",
    re.IGNORECASE,
)

EventHook = Callable[[str], None]


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class ReleasePackage:
    archive: Path
    release_version: str
    root: str
    template_root: str
    archive_sha256: str
    template_files: dict[str, bytes]


class VerificationFailure(Exception):
    def __init__(self, code: int, name: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.name = name
        self.detail = detail


class InstallationFailure(Exception):
    def __init__(self, name: str, detail: str) -> None:
        super().__init__(detail)
        self.name = name
        self.detail = detail


class TargetFailure(InstallationFailure):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _require_regular(path: Path, label: str) -> None:
    if path.is_symlink():
        raise VerificationFailure(EXIT_RELEASE, f"{label}_symlink", f"{label} is a symlink")
    if not path.is_file():
        raise VerificationFailure(EXIT_RELEASE, f"{label}_file", f"{label} is missing or not a regular file")


def _validate_safe_path(name: str, *, allow_directory: bool = False) -> None:
    if not name or "\x00" in name:
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe path: {name!r}")
    if "\\" in name or name.startswith("/") or name.startswith("//"):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe path: {name!r}")
    if re.match(r"^[A-Za-z]:", name):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe path: {name!r}")
    parts = name.split("/")
    if not allow_directory and name.endswith("/"):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"directory is not a file path: {name!r}")
    if any(part in {"", ".", ".."} for part in parts[:-1]):
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe path: {name!r}")
    if parts[-1] in {".", ".."}:
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"unsafe path: {name!r}")
    if not allow_directory and not parts[-1]:
        raise VerificationFailure(EXIT_ARCHIVE, "safe_path", f"empty file name: {name!r}")


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


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
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_format", f"invalid SHA256SUMS line {line_number}")
        digest, name = match.groups()
        if name in entries:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_duplicate", f"duplicate SHA256SUMS path: {name}")
        if name not in {archive_name, installer_name} or "/" in name or "\\" in name:
            raise VerificationFailure(EXIT_RELEASE, "sha256sums_path", f"unexpected SHA256SUMS path: {name}")
        entries[name] = digest

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
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
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
        try:
            _validate_safe_path(path)
        except VerificationFailure as exc:
            raise VerificationFailure(EXIT_MANIFEST, "manifest_path", exc.detail) from exc
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
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


def validate_release_version(release_version: str) -> None:
    if not isinstance(release_version, str) or not _VERSION_RE.fullmatch(release_version):
        raise VerificationFailure(EXIT_USAGE, "release_version", "release version must be MAJOR.MINOR.PATCH")


def build_package_manifest(release_version: str, template_files: dict[str, bytes]) -> dict[str, Any]:
    """Build the exact schema-v1 package manifest from known file bytes."""
    validate_release_version(release_version)
    if not isinstance(template_files, dict) or not template_files:
        raise VerificationFailure(EXIT_MANIFEST, "template_files", "template_files must be a non-empty mapping")

    entries: list[dict[str, str]] = []
    for path in sorted(template_files):
        if not isinstance(path, str) or path in {"VERSION", "package-manifest.json"} or path.startswith("template/"):
            raise VerificationFailure(EXIT_MANIFEST, "manifest_path", f"invalid template path: {path!r}")
        try:
            _validate_safe_path(path)
        except VerificationFailure as exc:
            raise VerificationFailure(EXIT_MANIFEST, "manifest_path", exc.detail) from exc
        if _FORBIDDEN_PATH_RE.search(path):
            raise VerificationFailure(EXIT_ARCHIVE, "forbidden_product_file", f"forbidden product-specific path: {path}")
        data = template_files[path]
        if not isinstance(data, bytes):
            raise VerificationFailure(EXIT_MANIFEST, "template_bytes", f"template file is not bytes: {path}")
        entries.append({"path": path, "sha256": _sha256_bytes(data)})

    return {
        "schema_version": 1,
        "release_version": release_version,
        "root": f"iskin-v{release_version}",
        "template_root": "template",
        "files": entries,
    }


def _validate_release(archive: Path, expected_version: str, expected_sha256: str, checks: list[Check]) -> ReleasePackage:
    validate_release_version(expected_version)
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise VerificationFailure(EXIT_USAGE, "expected_sha256", "expected SHA-256 must be 64 lowercase hexadecimal characters")

    archive = _normalise_path(archive)
    _require_regular(archive, "archive")
    checks.append(Check("archive_file", "PASS", "regular local file"))
    match = _ARCHIVE_RE.fullmatch(archive.name)
    if not match or match.group("version") != expected_version:
        raise VerificationFailure(EXIT_ARCHIVE, "archive_name", f"archive must be iskin-v{expected_version}.zip")
    checks.append(Check("archive_name", "PASS", archive.name))

    installer = archive.parent / "install-iskin.py"
    sums = archive.parent / "SHA256SUMS"
    _require_regular(installer, "install-iskin.py")
    _require_regular(sums, "SHA256SUMS")
    checks.append(Check("release_companions", "PASS", "install-iskin.py and SHA256SUMS are present"))

    observed_archive_sha256 = _sha256_file(archive)
    if observed_archive_sha256 != expected_sha256:
        raise VerificationFailure(EXIT_RELEASE, "archive_sha256", "archive SHA-256 differs from expected_sha256")
    checks.append(Check("expected_sha256", "PASS", observed_archive_sha256))

    sums_entries = _parse_sha256sums(sums, archive.name, installer.name)
    if sums_entries[archive.name] != observed_archive_sha256:
        raise VerificationFailure(EXIT_RELEASE, "sha256sums_archive", "SHA256SUMS archive digest does not match archive")
    installer_sha256 = _sha256_file(installer)
    if sums_entries[installer.name] != installer_sha256:
        raise VerificationFailure(EXIT_RELEASE, "sha256sums_installer", "SHA256SUMS installer digest does not match installer")
    checks.append(Check("sha256sums", "PASS", "archive and installer digests match"))

    root = f"iskin-v{expected_version}"
    try:
        zf = zipfile.ZipFile(archive, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise VerificationFailure(EXIT_ARCHIVE, "zip_format", f"invalid ZIP archive: {exc}") from exc
    with zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise VerificationFailure(EXIT_ARCHIVE, "duplicate_paths", f"duplicate ZIP paths: {duplicates}")

        regular_infos: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            try:
                _validate_safe_path(info.filename, allow_directory=info.is_dir())
            except VerificationFailure as exc:
                raise VerificationFailure(EXIT_ARCHIVE, "safe_path", exc.detail) from exc
            if _is_zip_symlink(info):
                raise VerificationFailure(EXIT_ARCHIVE, "symlink", f"ZIP member is a symlink: {info.filename}")
            if info.filename in {f"{root}/", f"{root}/template/"}:
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
        manifest_paths = [item["path"] for item in manifest["files"]]
        expected_members = {version_path, manifest_path} | {f"{root}/template/{path}" for path in manifest_paths}
        actual_members = set(regular_infos)
        if actual_members != expected_members:
            missing = sorted(expected_members - actual_members)
            extra = sorted(actual_members - expected_members)
            raise VerificationFailure(EXIT_ARCHIVE, "allowlist", f"manifest/archive mismatch; missing={missing}, extra={extra}")
        checks.append(Check("full_allowlist", "PASS", f"{len(manifest_paths)} template files"))

        template_files: dict[str, bytes] = {}
        for item in manifest["files"]:
            member_name = f"{root}/template/{item['path']}"
            data = zf.read(regular_infos[member_name])
            observed = _sha256_bytes(data)
            if observed != item["sha256"]:
                raise VerificationFailure(EXIT_MANIFEST, "file_sha256", f"SHA-256 mismatch for {item['path']}")
            template_files[item["path"]] = data
        checks.append(Check("template_sha256", "PASS", f"verified {len(template_files)} template file hashes"))
        checks.append(Check("manifest", "PASS", "package-manifest.json schema v1 is valid and complete"))

    return ReleasePackage(
        archive=archive,
        release_version=expected_version,
        root=root,
        template_root="template",
        archive_sha256=observed_archive_sha256,
        template_files=template_files,
    )


def validate_release(archive: Path, expected_version: str, expected_sha256: str) -> ReleasePackage:
    """Validate a release and return its in-memory, unextracted payload."""
    return _validate_release(archive, expected_version, expected_sha256, [])


def verify_release(archive: Path, expected_version: str, expected_sha256: str) -> tuple[int, dict[str, Any]]:
    checks: list[Check] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "FAIL",
        "exit_code": EXIT_USAGE,
        "archive": Path(archive).name,
        "release_version": expected_version,
        "checks": [],
    }
    try:
        _validate_release(archive, expected_version, expected_sha256, checks)
        report.update({"status": "PASS", "exit_code": EXIT_OK})
    except VerificationFailure as exc:
        checks.append(Check(exc.name, "FAIL", exc.detail))
        report.update({"status": "FAIL", "exit_code": exc.code})
    except zipfile.BadZipFile as exc:
        checks.append(Check("zip_format", "FAIL", f"invalid ZIP archive: {exc}"))
        report.update({"status": "FAIL", "exit_code": EXIT_ARCHIVE})
    except OSError as exc:
        checks.append(Check("filesystem", "FAIL", str(exc)))
        report.update({"status": "FAIL", "exit_code": EXIT_RELEASE})
    report["checks"] = [check.__dict__ for check in checks]
    return int(report["exit_code"]), report


def _check_no_symlink_ancestors(path: Path) -> None:
    def is_allowed_macos_alias(candidate: Path) -> bool:
        if candidate not in {Path("/var"), Path("/tmp")} or not candidate.is_symlink():
            return False
        try:
            return Path(os.path.realpath(candidate)).parent == Path("/private")
        except OSError:
            return False

    current = path
    while True:
        if current.is_symlink():
            if not is_allowed_macos_alias(current):
                raise TargetFailure("target_symlink", f"path component is a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise TargetFailure("target_parent", f"path component is not a directory: {current}")
        if current.parent == current:
            return
        current = current.parent


def _snapshot_path(path: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if path.is_symlink():
        snapshot["."] = "symlink:" + os.readlink(path)
        return snapshot
    if path.is_file():
        snapshot["."] = "file:" + _sha256_file(path)
        return snapshot
    if not path.is_dir():
        snapshot["."] = f"mode:{path.stat().st_mode}"
        return snapshot
    for current, dirs, files in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(dirs)
        files[:] = sorted(files)
        for name in dirs + files:
            child = current_path / name
            relative = child.relative_to(path).as_posix()
            if child.is_symlink():
                snapshot[relative] = "symlink:" + os.readlink(child)
            elif child.is_dir():
                snapshot[relative] = "dir"
            elif child.is_file():
                snapshot[relative] = "file:" + _sha256_file(child)
            else:
                snapshot[relative] = f"mode:{child.stat().st_mode}"
    return snapshot


def _inspect_target(target: Path) -> tuple[str, dict[str, str] | None]:
    _check_no_symlink_ancestors(target)
    if target.is_symlink():
        raise TargetFailure("target_symlink", "target_path is a symlink")
    if not target.exists():
        if not target.parent.exists() or not target.parent.is_dir():
            raise TargetFailure("target_parent", "target parent must already exist as a directory")
        return "new", None
    if not target.is_dir():
        raise TargetFailure("target_type", "target_path must be a directory")

    entries = sorted(target.iterdir(), key=lambda item: item.name)
    if not entries:
        return "empty", None
    if len(entries) == 1 and entries[0].name == ".git":
        git_path = entries[0]
        if git_path.is_symlink() or not (git_path.is_dir() or git_path.is_file()):
            raise TargetFailure("git_symlink", ".git must be a regular directory or Git worktree file")
        return "git-only", _snapshot_path(git_path)
    if any(entry.name == ".git" and entry.is_symlink() for entry in entries):
        raise TargetFailure("git_symlink", ".git is a symlink")
    raise TargetFailure("target_not_empty", "target must be nonexistent, empty, or contain only .git")


def _mkdir_no_symlink(path: Path, created_dirs: list[Path]) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise InstallationFailure("write_path", f"cannot use existing path: {path}")
        return
    parent = path.parent
    _mkdir_no_symlink(parent, created_dirs)
    try:
        path.mkdir()
    except FileExistsError:
        if path.is_symlink() or not path.is_dir():
            raise InstallationFailure("write_path", f"cannot use existing path: {path}")
        return
    created_dirs.append(path)


def _write_exclusive(path: Path, data: bytes, created_files: list[Path] | None = None) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o644)
    except OSError as exc:
        raise InstallationFailure("write_file", f"cannot create {path}: {exc}") from exc
    if created_files is not None:
        created_files.append(path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    except OSError as exc:
        raise InstallationFailure("write_file", f"cannot write {path}: {exc}") from exc


def _prepare_template(stage: Path, package: ReleasePackage) -> None:
    for relative, data in sorted(package.template_files.items()):
        destination = stage / Path(relative)
        _mkdir_no_symlink(destination.parent, [])
        _write_exclusive(destination, data)


def _verify_template_tree(stage: Path, package: ReleasePackage) -> None:
    expected_files = {Path(relative) for relative in package.template_files}
    actual_files: set[Path] = set()
    for current, dirs, files in os.walk(stage, topdown=True, followlinks=False):
        current_path = Path(current)
        for directory in list(dirs):
            child = current_path / directory
            if child.is_symlink():
                raise InstallationFailure("staging_symlink", f"staging directory is a symlink: {child}")
        for filename in files:
            child = current_path / filename
            if child.is_symlink():
                raise InstallationFailure("staging_symlink", f"staging file is a symlink: {child}")
            relative = child.relative_to(stage)
            actual_files.add(relative)
            if relative not in expected_files:
                raise InstallationFailure("staging_extra", f"unexpected staging file: {relative}")
            if _sha256_file(child) != _sha256_bytes(package.template_files[relative.as_posix()]):
                raise InstallationFailure("staging_sha256", f"staging SHA-256 mismatch: {relative}")
    if actual_files != expected_files:
        missing = sorted(str(path) for path in expected_files - actual_files)
        extra = sorted(str(path) for path in actual_files - expected_files)
        raise InstallationFailure("staging_allowlist", f"staging mismatch; missing={missing}, extra={extra}")


def _write_version(
    base: Path,
    package: ReleasePackage,
    event_hook: EventHook | None,
    created_files: list[Path] | None = None,
) -> Path:
    metadata = base / ".iskin"
    dirs: list[Path] = []
    _mkdir_no_symlink(metadata, dirs)
    version_path = metadata / "version"
    _write_exclusive(
        version_path,
        (package.release_version + "\n").encode("utf-8"),
        created_files,
    )
    if event_hook:
        event_hook("version_created")
    return version_path


def _expected_installation_files(package: ReleasePackage) -> dict[str, bytes]:
    return {
        **package.template_files,
        ".iskin/version": (package.release_version + "\n").encode("utf-8"),
    }


def _installation_entries(package: ReleasePackage) -> list[dict[str, str]]:
    expected_files = _expected_installation_files(package)
    return [
        {"path": relative, "sha256": _sha256_bytes(expected_files[relative])}
        for relative in sorted(expected_files)
    ]


def _write_installation_manifest(
    base: Path,
    package: ReleasePackage,
    event_hook: EventHook | None,
    created_files: list[Path] | None = None,
) -> Path:
    manifest_path = base / ".iskin" / "installation-manifest.json"
    entries = _installation_entries(package)
    payload = {
        "schema_version": 1,
        "release_version": package.release_version,
        "archive_sha256": package.archive_sha256,
        "files": entries,
    }
    _write_exclusive(
        manifest_path,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        created_files,
    )
    if event_hook:
        event_hook("installation_manifest_created")
    return manifest_path


def _transfer_new_files(
    target: Path,
    stage: Path,
    package: ReleasePackage,
    created_files: list[Path],
    created_dirs: list[Path],
    event_hook: EventHook | None,
    fail_after_files: int | None,
) -> None:
    transfer_paths = sorted(list(package.template_files) + [".iskin/version"])
    transferred = 0
    for relative in transfer_paths:
        source = stage / Path(relative)
        destination = target / Path(relative)
        if destination.exists() or destination.is_symlink():
            raise InstallationFailure("no_overwrite", f"refusing to overwrite existing path: {relative}")
        _mkdir_no_symlink(destination.parent, created_dirs)
        try:
            os.link(source, destination, follow_symlinks=False)
            created_files.append(destination)
            source.unlink()
        except OSError as exc:
            raise InstallationFailure("transfer", f"cannot transfer {relative}: {exc}") from exc
        transferred += 1
        if event_hook:
            event_hook("template_file_transferred")
        if fail_after_files is not None and transferred >= fail_after_files:
            raise InstallationFailure("injected_failure", "artificial mid-installation failure")


def _run_git_init(target: Path, created_roots: list[Path]) -> None:
    git_path = target / ".git"
    if git_path.exists() or git_path.is_symlink():
        raise InstallationFailure("git_race", ".git appeared before --init-git")

    def remove_partial_git() -> list[str]:
        issues: list[str] = []
        try:
            if git_path.is_symlink() or git_path.is_file():
                git_path.unlink()
            elif git_path.is_dir():
                shutil.rmtree(git_path)
            elif git_path.exists():
                issues.append(f"cannot remove partial .git: unexpected path type: {git_path}")
        except OSError as exc:
            issues.append(f"cannot remove partial .git {git_path}: {exc}")
        if git_path.exists() or git_path.is_symlink():
            issues.append(f"remaining_paths={git_path}")
        return issues

    def raise_git_init_failure(detail: str, cause: BaseException | None = None) -> None:
        cleanup_issues = remove_partial_git()
        if cleanup_issues:
            detail += "; rollback incomplete: " + "; ".join(cleanup_issues)
        failure = InstallationFailure("git_init", detail)
        if cause is not None:
            raise failure from cause
        raise failure

    try:
        result = subprocess.run(
            ["git", "init", "--quiet", str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise_git_init_failure(f"cannot execute git init: {exc}", exc)
    if result.returncode != 0:
        raise_git_init_failure("git init failed")
    if git_path.is_symlink() or not git_path.is_dir():
        raise_git_init_failure("git init did not create a regular .git directory")
    created_roots.append(git_path)


def _validate_installation_manifest(base: Path, package: ReleasePackage) -> None:
    manifest_path = base / ".iskin" / "installation-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise InstallationFailure("installation_manifest", "installation manifest is missing or symlinked")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InstallationFailure("installation_manifest", f"invalid installation manifest: {exc}") from exc
    required = {"schema_version", "release_version", "archive_sha256", "files"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise InstallationFailure("installation_manifest", "installation manifest has an invalid field set")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise InstallationFailure("installation_manifest", "installation manifest schema_version must be integer 1")
    if manifest["release_version"] != package.release_version or manifest["archive_sha256"] != package.archive_sha256:
        raise InstallationFailure("installation_manifest", "installation manifest identity mismatch")
    entries = manifest["files"]
    if not isinstance(entries, list) or not entries:
        raise InstallationFailure("installation_manifest", "installation manifest files must be a non-empty array")
    paths: list[str] = []
    observed: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise InstallationFailure("installation_manifest", "installation manifest entries must contain path and sha256 only")
        relative = item["path"]
        digest = item["sha256"]
        if not isinstance(relative, str) or not relative or relative in observed:
            raise InstallationFailure("installation_manifest", f"invalid or duplicate installed path: {relative!r}")
        try:
            _validate_safe_path(relative)
        except VerificationFailure as exc:
            raise InstallationFailure("installation_manifest", exc.detail) from exc
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise InstallationFailure("installation_manifest", f"invalid installed SHA-256: {relative!r}")
        paths.append(relative)
        observed[relative] = digest
    if paths != sorted(paths):
        raise InstallationFailure("installation_manifest", "installation manifest files are not sorted")

    expected_paths = set(package.template_files) | {".iskin/version"}
    if set(observed) != expected_paths:
        missing = sorted(expected_paths - set(observed))
        extra = sorted(set(observed) - expected_paths)
        raise InstallationFailure("installation_manifest", f"installed file list mismatch; missing={missing}, extra={extra}")
    expected_files = _expected_installation_files(package)
    expected_entries = {
        item["path"]: item["sha256"] for item in _installation_entries(package)
    }
    for relative, expected_digest in expected_entries.items():
        if observed[relative] != expected_digest:
            raise InstallationFailure("installation_manifest", f"installation SHA-256 differs from release: {relative}")
        path = base / Path(relative)
        if path.is_symlink() or not path.is_file():
            raise InstallationFailure("installation_manifest", f"installed file is missing or symlinked: {relative}")
        try:
            actual_bytes = path.read_bytes()
        except OSError as exc:
            raise InstallationFailure("installation_manifest", f"cannot read installed file: {relative}: {exc}") from exc
        if actual_bytes != expected_files[relative]:
            raise InstallationFailure("installation_manifest", f"installed SHA-256 mismatch: {relative}")

    version_path = base / ".iskin" / "version"
    if version_path.read_bytes() != expected_files[".iskin/version"]:
        raise InstallationFailure("version", ".iskin/version does not match release bytes")


def validate_installation_manifest(base: Path, package: ReleasePackage) -> None:
    """Read back installation metadata without exposing private rules to callers."""
    _validate_installation_manifest(base, package)


def _cleanup_created(
    created_files: list[Path],
    created_dirs: list[Path],
    created_roots: list[Path],
) -> list[str]:
    issues: list[str] = []
    for path in reversed(created_files):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                issues.append(f"cannot remove created path {path}: unexpected path type")
        except OSError as exc:
            issues.append(f"cannot remove created file {path}: {exc}")
    for path in reversed(created_roots):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                issues.append(f"cannot remove created root {path}: unexpected path type")
        except OSError as exc:
            issues.append(f"cannot remove created root {path}: {exc}")
    for path in sorted(created_dirs, key=lambda item: len(item.parts), reverse=True):
        try:
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            elif path.exists():
                issues.append(f"cannot remove created directory {path}: unexpected path type")
        except OSError as exc:
            issues.append(f"cannot remove created directory {path}: {exc}")
    remaining = sorted(
        {
            str(path)
            for path in [*created_files, *created_roots, *created_dirs]
            if path.exists() or path.is_symlink()
        }
    )
    if remaining:
        issues.append("remaining_paths=" + ", ".join(remaining))
    return issues


def _remove_stage(stage: Path | None) -> None:
    if stage is not None and stage.exists() and not stage.is_symlink():
        shutil.rmtree(stage)


def _cleanup_published_target(target: Path) -> list[str]:
    issues: list[str] = []
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            issues.append(f"cannot remove published target {target}: unexpected path type")
    except OSError as exc:
        issues.append(f"cannot remove published target {target}: {exc}")
    if target.exists() or target.is_symlink():
        issues.append(f"remaining_paths={target}")
    return issues


def _install_package(
    package: ReleasePackage,
    target: Path,
    *,
    init_git: bool,
    event_hook: EventHook | None,
    fail_after_files: int | None,
) -> dict[str, Any]:
    mode, original_git_snapshot = _inspect_target(target)
    parent = target.parent
    stage = Path(tempfile.mkdtemp(prefix=".iskin-stage-", dir=parent))
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    created_roots: list[Path] = []
    published_new_target = False
    try:
        _prepare_template(stage, package)
        _verify_template_tree(stage, package)

        if mode == "new":
            if init_git:
                _run_git_init(stage, created_roots=[])
            _write_version(stage, package, event_hook)
            _write_installation_manifest(stage, package, event_hook)
            _validate_installation_manifest(stage, package)
            if target.exists() or target.is_symlink():
                raise TargetFailure("target_race", "target appeared before atomic publish")
            try:
                os.rename(stage, target)
            except OSError as exc:
                raise InstallationFailure("publish", f"cannot atomically publish target: {exc}") from exc
            stage = None  # type: ignore[assignment]
            published_new_target = True
            _validate_installation_manifest(target, package)
            return {
                "status": "PASS",
                "exit_code": EXIT_OK,
                "release_version": package.release_version,
                "archive_sha256": package.archive_sha256,
                "target_mode": "new",
                "git_initialized": init_git,
            }

        _write_version(stage, package, event_hook)
        _transfer_new_files(target, stage, package, created_files, created_dirs, event_hook, fail_after_files)
        if init_git and mode == "empty":
            _run_git_init(target, created_roots)
        _write_installation_manifest(target, package, event_hook, created_files)
        _validate_installation_manifest(target, package)
        if original_git_snapshot is not None and _snapshot_path(target / ".git") != original_git_snapshot:
            raise InstallationFailure("git_modified", "existing .git changed during installation")
        return {
            "status": "PASS",
            "exit_code": EXIT_OK,
            "release_version": package.release_version,
            "archive_sha256": package.archive_sha256,
            "target_mode": mode,
            "git_initialized": bool(init_git and mode == "empty"),
        }
    except Exception as exc:
        rollback_issues: list[str]
        if published_new_target:
            rollback_issues = _cleanup_published_target(target)
        else:
            rollback_issues = _cleanup_created(created_files, created_dirs, created_roots)
        if rollback_issues:
            detail = "; ".join(rollback_issues)
            raise InstallationFailure(
                "rollback_incomplete",
                f"installation failed: {exc}; rollback incomplete: {detail}",
            ) from exc
        raise
    finally:
        _remove_stage(stage)


def install_release(
    archive: Path,
    expected_version: str,
    expected_sha256: str,
    target_path: Path,
    *,
    init_git: bool = False,
    event_hook: EventHook | None = None,
    fail_after_files: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Validate and install a release, rolling back ordinary failures."""
    checks: list[Check] = []
    target = _normalise_path(target_path)
    report: dict[str, Any] = {
        "status": "FAIL",
        "exit_code": EXIT_USAGE,
        "target_mode": None,
        "release_version": expected_version,
        "checks": [],
    }
    try:
        package = _validate_release(archive, expected_version, expected_sha256, checks)
        result = _install_package(
            package,
            target,
            init_git=init_git,
            event_hook=event_hook,
            fail_after_files=fail_after_files,
        )
        report.update(result)
    except VerificationFailure as exc:
        checks.append(Check(exc.name, "FAIL", exc.detail))
        report.update({"status": "FAIL", "exit_code": exc.code})
    except zipfile.BadZipFile as exc:
        checks.append(Check("zip_format", "FAIL", f"invalid ZIP archive: {exc}"))
        report.update({"status": "FAIL", "exit_code": EXIT_ARCHIVE})
    except TargetFailure as exc:
        checks.append(Check(exc.name, "FAIL", exc.detail))
        report.update({"status": "FAIL", "exit_code": EXIT_TARGET})
    except InstallationFailure as exc:
        checks.append(Check(exc.name, "FAIL", exc.detail))
        report.update({"status": "FAIL", "exit_code": EXIT_INSTALL})
    except OSError as exc:
        checks.append(Check("filesystem", "FAIL", str(exc)))
        report.update({"status": "FAIL", "exit_code": EXIT_INSTALL})
    report["checks"] = [check.__dict__ for check in checks]
    return int(report["exit_code"]), report


def _build_verify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only ИскИн v0.3 release validator")
    parser.add_argument("--archive", required=True, type=Path, help="path to iskin-v<version>.zip")
    parser.add_argument("--release-version", required=True, help="expected release version, e.g. 0.3.0")
    parser.add_argument("--expected-sha256", required=True, help="lowercase SHA-256 of the archive")
    parser.add_argument("--report", type=Path, help="optional JSON report path; parent must already exist")
    return parser


def run_verify_cli(argv: Iterable[str] | None = None) -> int:
    args = _build_verify_parser().parse_args(argv)
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


def _build_install_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install ИскИн v0.3 into a new or empty local project directory")
    parser.add_argument("--archive", required=True, type=Path, help="path to iskin-v<version>.zip")
    parser.add_argument("--release-version", required=True, help="expected release version, e.g. 0.3.0")
    parser.add_argument("--expected-sha256", required=True, help="lowercase SHA-256 of the archive")
    parser.add_argument("--target-path", required=True, type=Path, help="new, empty, or .git-only target directory")
    parser.add_argument("--init-git", action="store_true", help="explicitly run git init; no commit, remote, branch ref, tag, or push")
    return parser


def run_install_cli(argv: Iterable[str] | None = None) -> int:
    args = _build_install_parser().parse_args(argv)
    code, report = install_release(
        args.archive,
        args.release_version,
        args.expected_sha256,
        args.target_path,
        init_git=args.init_git,
    )
    print(f"{report['status']} exit_code={code} version={args.release_version} target={args.target_path}")
    for check in report["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    if code == EXIT_OK:
        print("[PASS] installation_manifest: created last and verified")
        target = _normalise_path(args.target_path)
        print("[NEXT] Run manually; the installer does not execute this command:")
        print(f"cd {shlex.quote(str(target))}")
        print("hermes skills trust")
        print("[INFO] `hermes skills trust` changes Hermes trusted runtime state.")
    return code


if __name__ == "__main__":
    raise SystemExit(run_install_cli())
