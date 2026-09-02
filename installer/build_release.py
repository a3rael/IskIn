#!/usr/bin/env python3
"""Build a deterministic local ИскИн v0.3 release комплект.

This is a repository-side generator. The generated installer is copied byte
for byte from installer/install-iskin.py; no installer implementation is
embedded here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "package" / "template"
CANONICAL_INSTALLER = ROOT / "installer" / "install-iskin.py"
ARCHIVE_PREFIX = "iskin-v"
INSTALLER_NAME = "install-iskin.py"
SUMS_NAME = "SHA256SUMS"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o644

EventHook = Callable[[str], None]


class BuildFailure(Exception):
    def __init__(self, name: str, detail: str, code: int = 7) -> None:
        super().__init__(detail)
        self.name = name
        self.detail = detail
        self.code = code


def _load_canonical_installer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("iskin_canonical_installer_for_build", CANONICAL_INSTALLER)
    if spec is None or spec.loader is None:
        raise BuildFailure("canonical_installer", f"cannot load {CANONICAL_INSTALLER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _normalise_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_output_path(output: Path, canonical: ModuleType) -> str:
    if output.is_symlink():
        raise BuildFailure("output_symlink", "output directory must not be a symlink", 6)
    try:
        canonical._check_no_symlink_ancestors(output)
    except Exception as exc:
        raise BuildFailure("output_symlink", str(exc), 6) from exc

    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        raise BuildFailure("output_parent", "output parent must be an existing non-symlink directory", 6)
    if output.exists():
        if not output.is_dir():
            raise BuildFailure("output_type", "output path exists but is not a directory", 6)
        try:
            entries = list(output.iterdir())
        except OSError as exc:
            raise BuildFailure("output_read", f"cannot inspect output directory: {exc}", 6) from exc
        if entries:
            raise BuildFailure("output_not_empty", "output directory must be empty", 6)
        return "empty"
    return "new"


def _collect_template(template_root: Path) -> dict[str, bytes]:
    if template_root.is_symlink() or not template_root.is_dir():
        raise BuildFailure("template_root", "package/template must be a real directory")

    files: dict[str, bytes] = {}

    def on_walk_error(error: OSError) -> None:
        raise BuildFailure("template_read", f"cannot walk package/template: {error}") from error

    for current_name, directory_names, file_names in os.walk(
        template_root, topdown=True, followlinks=False, onerror=on_walk_error
    ):
        current = Path(current_name)
        directory_names.sort()
        file_names.sort()
        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise BuildFailure("template_entry", f"template directory is not ordinary: {path}")
        for name in file_names:
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise BuildFailure("template_entry", f"template file is not ordinary: {path}")
            relative = path.relative_to(template_root).as_posix()
            try:
                files[relative] = path.read_bytes()
            except OSError as exc:
                raise BuildFailure("template_read", f"cannot read {path}: {exc}") from exc

    if not files:
        raise BuildFailure("template_empty", "package/template contains no files")
    return files


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n").encode("utf-8")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.external_attr = (stat.S_IFREG | FILE_MODE) << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    info.flag_bits = 0
    return info


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            archive.comment = b""
            for name in sorted(members):
                archive.writestr(_zip_info(name), members[name])
        path.chmod(FILE_MODE)
    except (OSError, zipfile.LargeZipFile, ValueError) as exc:
        raise BuildFailure("zip_write", f"cannot write deterministic ZIP: {exc}") from exc


def _write_file(path: Path, data: bytes) -> None:
    try:
        path.write_bytes(data)
        path.chmod(FILE_MODE)
    except OSError as exc:
        raise BuildFailure("file_write", f"cannot write {path.name}: {exc}") from exc


def _build_stage(stage: Path, release_version: str, template_files: dict[str, bytes], canonical: ModuleType) -> tuple[Path, str, str]:
    archive_name = f"{ARCHIVE_PREFIX}{release_version}.zip"
    archive_path = stage / archive_name
    installer_path = stage / INSTALLER_NAME
    sums_path = stage / SUMS_NAME
    if CANONICAL_INSTALLER.is_symlink() or not CANONICAL_INSTALLER.is_file():
        raise BuildFailure("canonical_installer", "canonical installer must be an ordinary file")
    installer_bytes = CANONICAL_INSTALLER.read_bytes()
    manifest = canonical.build_package_manifest(release_version, template_files)
    root = f"{ARCHIVE_PREFIX}{release_version}"
    members: dict[str, bytes] = {
        f"{root}/VERSION": f"{release_version}\n".encode("utf-8"),
        f"{root}/package-manifest.json": _json_bytes(manifest),
    }
    members.update({f"{root}/template/{path}": data for path, data in template_files.items()})
    _write_zip(archive_path, members)
    _write_file(installer_path, installer_bytes)
    archive_sha256 = _sha256_file(archive_path)
    installer_sha256 = _sha256_bytes(installer_bytes)
    sums = (
        f"{installer_sha256}  {INSTALLER_NAME}\n"
        f"{archive_sha256}  {archive_name}\n"
    ).encode("ascii")
    _write_file(sums_path, sums)
    if {entry.name for entry in stage.iterdir()} != {archive_name, INSTALLER_NAME, SUMS_NAME}:
        raise BuildFailure("stage_contents", "release staging directory must contain exactly three files")
    return archive_path, archive_sha256, installer_sha256


def _verify_probe(
    target: Path,
    package: Any,
    release_version: str,
    archive_sha256: str,
    canonical: ModuleType,
) -> None:
    canonical.validate_installation_manifest(target, package)
    version_path = target / ".iskin" / "version"
    if version_path.read_bytes() != f"{release_version}\n".encode("utf-8"):
        raise BuildFailure("probe_version", ".iskin/version does not contain the exact release version")
    for relative, expected in package.template_files.items():
        installed = target / Path(relative)
        if installed.is_symlink() or not installed.is_file() or installed.read_bytes() != expected:
            raise BuildFailure("probe_template", f"temporary installation differs from package/template: {relative}")
    manifest_path = target / ".iskin" / "installation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["archive_sha256"] != archive_sha256 or manifest["release_version"] != release_version:
        raise BuildFailure("probe_manifest", "temporary installation metadata does not match release")


def _probe_install(archive: Path, release_version: str, archive_sha256: str, canonical: ModuleType) -> None:
    with tempfile.TemporaryDirectory(prefix=".iskin-release-probe-") as directory:
        target = Path(directory) / "project"
        code, report = canonical.install_release(archive, release_version, archive_sha256, target, init_git=False)
        if code != canonical.EXIT_OK:
            raise BuildFailure("probe_install", f"temporary installation failed: {report}")
        package = canonical.validate_release(archive, release_version, archive_sha256)
        _verify_probe(target, package, release_version, archive_sha256, canonical)


def _publish_existing(stage: Path, output: Path, names: Iterable[str], created: list[Path]) -> None:
    for name in sorted(names):
        source = stage / name
        destination = output / name
        if destination.exists() or destination.is_symlink():
            raise BuildFailure("no_overwrite", f"refusing to overwrite output file: {name}", 7)
        try:
            os.link(source, destination, follow_symlinks=False)
            created.append(destination)
            source.unlink()
        except OSError as exc:
            raise BuildFailure("publish", f"cannot publish {name}: {exc}", 7) from exc


def _cleanup_created(paths: Iterable[Path]) -> None:
    for path in reversed(list(paths)):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
        except OSError:
            pass


def _verify_published(output: Path, release_version: str, canonical: ModuleType) -> tuple[str, str]:
    archive_name = f"{ARCHIVE_PREFIX}{release_version}.zip"
    expected = {archive_name, INSTALLER_NAME, SUMS_NAME}
    try:
        actual = {entry.name for entry in output.iterdir()}
    except OSError as exc:
        raise BuildFailure("output_read", f"cannot read published output: {exc}") from exc
    if actual != expected:
        raise BuildFailure("output_contents", f"published output mismatch: expected={sorted(expected)}, actual={sorted(actual)}")
    for name in expected:
        path = output / name
        if path.is_symlink() or not path.is_file():
            raise BuildFailure("output_entry", f"published release entry is not an ordinary file: {name}")
    archive = output / archive_name
    archive_sha256 = _sha256_file(archive)
    canonical.validate_release(archive, release_version, archive_sha256)
    installer_sha256 = _sha256_file(output / INSTALLER_NAME)
    if (output / INSTALLER_NAME).read_bytes() != CANONICAL_INSTALLER.read_bytes():
        raise BuildFailure("installer_copy", "published installer differs from canonical installer")
    return archive_sha256, installer_sha256


def build_release(
    release_version: str,
    output_dir: Path,
    *,
    event_hook: EventHook | None = None,
) -> tuple[int, dict[str, Any]]:
    canonical = _load_canonical_installer()
    checks: list[dict[str, str]] = []
    output = _normalise_path(output_dir)
    stage: Path | None = None
    published_new = False
    completed = False
    created_output: list[Path] = []
    try:
        canonical.validate_release_version(release_version)
        output_state = _check_output_path(output, canonical)
        checks.append({"name": "arguments_and_output", "status": "PASS", "detail": output_state})
        template_files = _collect_template(TEMPLATE_ROOT)
        checks.append({"name": "template_source", "status": "PASS", "detail": f"{len(template_files)} files"})
        stage = Path(tempfile.mkdtemp(prefix=".iskin-release-stage-", dir=output.parent))
        archive, archive_sha256, installer_sha256 = _build_stage(stage, release_version, template_files, canonical)
        checks.append({"name": "deterministic_stage", "status": "PASS", "detail": "three files, ZIP_STORED, fixed metadata"})
        if event_hook:
            event_hook("archive_built")

        package = canonical.validate_release(archive, release_version, archive_sha256)
        if package.template_files != template_files:
            raise BuildFailure("validator_source", "validated archive payload differs from package/template")
        checks.append({"name": "read_only_validator", "status": "PASS", "detail": "release package fully validated"})
        if event_hook:
            event_hook("release_validated")

        _probe_install(archive, release_version, archive_sha256, canonical)
        checks.append({"name": "temporary_install_probe", "status": "PASS", "detail": "metadata and template bytes match"})
        if event_hook:
            event_hook("probe_complete")

        if output_state == "new":
            if output.exists() or output.is_symlink():
                raise BuildFailure("output_race", "output path appeared before atomic publish", 6)
            os.rename(stage, output)
            stage = None
            published_new = True
        else:
            if {entry.name for entry in output.iterdir()}:
                raise BuildFailure("output_race", "output directory became non-empty before publish", 6)
            _publish_existing(stage, output, (archive.name, INSTALLER_NAME, SUMS_NAME), created_output)
        checks.append({"name": "publish", "status": "PASS", "detail": "exactly three release files published"})

        final_archive_sha256, final_installer_sha256 = _verify_published(output, release_version, canonical)
        checks.append({"name": "final_readback", "status": "PASS", "detail": "validator and installer copy match"})
        completed = True
        return canonical.EXIT_OK, {
            "status": "PASS",
            "release_version": release_version,
            "output_dir": str(output),
            "archive_sha256": final_archive_sha256,
            "installer_sha256": final_installer_sha256,
            "files": sorted((entry.name for entry in output.iterdir())),
            "checks": checks,
        }
    except canonical.VerificationFailure as exc:
        checks.append({"name": exc.name, "status": "FAIL", "detail": exc.detail})
        return exc.code, {"status": "FAIL", "exit_code": exc.code, "checks": checks}
    except canonical.InstallationFailure as exc:
        checks.append({"name": exc.name, "status": "FAIL", "detail": exc.detail})
        return canonical.EXIT_INSTALL, {"status": "FAIL", "exit_code": canonical.EXIT_INSTALL, "checks": checks}
    except BuildFailure as exc:
        checks.append({"name": exc.name, "status": "FAIL", "detail": exc.detail})
        return exc.code, {"status": "FAIL", "exit_code": exc.code, "checks": checks}
    except OSError as exc:
        checks.append({"name": "filesystem", "status": "FAIL", "detail": str(exc)})
        return canonical.EXIT_INSTALL, {"status": "FAIL", "exit_code": canonical.EXIT_INSTALL, "checks": checks}
    except Exception as exc:
        checks.append({"name": "build", "status": "FAIL", "detail": str(exc)})
        return canonical.EXIT_INSTALL, {"status": "FAIL", "exit_code": canonical.EXIT_INSTALL, "checks": checks}
    finally:
        if not completed and published_new and output.exists():
            shutil.rmtree(output, ignore_errors=True)
        elif not completed and created_output:
            _cleanup_created(created_output)
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def build_cli(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic local ИскИн v0.3 release комплект")
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    code, report = build_release(args.release_version, args.output_dir)
    for check in report.get("checks", []):
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    if code == 0:
        print(f"PASS: built {report['release_version']} ({len(report['files'])} files)")
    else:
        print(f"FAIL: release build refused (exit_code={code})")
    return code


if __name__ == "__main__":
    raise SystemExit(build_cli())
