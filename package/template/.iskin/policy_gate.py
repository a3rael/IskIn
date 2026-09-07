#!/usr/bin/env python3
"""Read-only, deterministic lifecycle policy gate for an IskIn project.

The executable is installation-managed and immutable.  Project lifecycle
state is represented by append-only JSON approval events under
``product-memory/approval-events/``; no mutable state file is part of the
installed core.  The gate never writes the worktree, index, telemetry, or an
external system.  Conversational display and human authorship remain evidence
boundaries that this program cannot cryptographically prove.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EVENT_SCHEMA_VERSION = 1
EVENT_DIR = "product-memory/approval-events"
DECISIONS_PATH = "product-memory/decisions.md"
REGISTRY_PATH = "product-memory/approval-packages.md"
GATE_PATH = ".iskin/policy_gate.py"
BOOTSTRAP_MANIFEST_PATH = ".iskin/bootstrap-manifest.json"
INSTALLATION_MANIFEST_PATH = ".iskin/installation-manifest.json"
LEGACY_STATE_PATH = ".iskin/policy_state.json"
CHECKPOINT_PREFIX = "iskin: pre-approval checkpoint:"
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
PACKAGE_ID_RE = EVENT_ID_RE
CHECKPOINT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
EVENT_REFERENCE_RE = re.compile(r"^\s*approval_event_id:\s*([^\s]+)\s*$", re.MULTILINE)
EVENT_PATH_REFERENCE_RE = re.compile(r"^\s*approval_event_path:\s*([^\s]+)\s*$", re.MULTILINE)
PACKAGE_REFERENCE_RE = re.compile(r"product-memory/approval-packages/([A-Za-z0-9][A-Za-z0-9._-]{1,127})\.md")

STATUS_DISCOVERY = "DISCOVERY_ALLOWED"
STATUS_AWAITING = "AWAITING_APPROVAL"
STATUS_IMPLEMENTATION = "IMPLEMENTATION_ALLOWED"
STATUS_BLOCKED = "PROCESS_BLOCKED"

ACTIONS = (
    "discover",
    "prepare_approval",
    "pre_approval_checkpoint",
    "human_approval",
    "bootstrap_checkpoint",
    "approval_checkpoint",
    "change_product",
    "prove_result",
    "checkpoint",
    "read_only_recovery",
    "product_tests",
    "telemetry_write",
)
CRITICAL_ACTIONS = (
    "bootstrap_checkpoint",
    "approval_checkpoint",
    "change_product",
    "prove_result",
    "checkpoint",
    "product_tests",
    "telemetry_write",
)
UNVERIFIABLE_REASONS = {
    "GIT_CONTEXT_UNAVAILABLE",
    "GIT_CHECK_FAILED",
    "REQUIRED_STATE_MISSING",
    "REQUIRED_STATE_UNREADABLE",
    "MACHINE_STATE_INVALID",
    "MACHINE_STATE_UNSUPPORTED",
    "UNSUPPORTED_PROJECT_STATE",
    "READ_ONLY_CHECK_FAILED",
}
DEFAULT_PRODUCT_CODE_PATTERNS = (
    "src/**",
    "app/**",
    "lib/**",
    "bin/**",
    "*.py",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.kt",
    "*.java",
    "*.go",
    "*.rs",
    "*.c",
    "*.cc",
    "*.cpp",
)
DEFAULT_PRODUCT_EVIDENCE_PATTERNS = (
    "evidence/**",
    "reports/**",
    "proof-record.json",
    "**/proof-record.json",
)


class GateError(Exception):
    """A deterministic read-only evaluation failure."""

    def __init__(self, *reason_codes: str) -> None:
        super().__init__(", ".join(reason_codes))
        self.reason_codes = tuple(dict.fromkeys(reason_codes))


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass(frozen=True)
class Package:
    package_id: str
    package_path: str
    package_paths: tuple[str, ...]


@dataclass(frozen=True)
class BootstrapBaseline:
    release_version: str
    self_path: str
    files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ApprovalEvent:
    event_id: str
    path: str
    package_id: str
    package_paths: tuple[str, ...]
    checkpoint_sha: str
    approval_question: str
    human_response: str
    actor: str
    package_displayed: bool
    implementation_authorized: bool


@dataclass(frozen=True)
class Evaluation:
    status: str
    reason_codes: tuple[str, ...]
    package_id: str | None
    checkpoint_sha: str | None
    approval_state: str
    lifecycle: str | None
    allowed_actions: tuple[str, ...]
    human_evidence_boundary: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != len(set(value)):
        raise GateError("MACHINE_STATE_INVALID")
    if any(not _safe_relative_path(item) for item in value):
        raise GateError("MACHINE_STATE_INVALID")
    return tuple(value)


def _run_git(repo: Path, *args: str) -> GitResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
        )
    except (OSError, UnicodeError) as exc:
        raise GateError("GIT_CHECK_FAILED") from exc
    return GitResult(completed.stdout, completed.stderr, completed.returncode)


def _run_git_bytes(repo: Path, *args: str) -> tuple[bytes, bytes, int]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise GateError("GIT_CHECK_FAILED") from exc
    return completed.stdout, completed.stderr, completed.returncode


def _git_stdout(repo: Path, *args: str) -> str:
    result = _run_git(repo, *args)
    if result.returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return result.stdout


def _git_paths(repo: Path, *args: str) -> tuple[str, ...]:
    stdout, _, returncode = _run_git_bytes(repo, *args, "-z")
    if returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    try:
        return tuple(item.decode("utf-8") for item in stdout.split(b"\0") if item)
    except UnicodeDecodeError as exc:
        raise GateError("GIT_CHECK_FAILED") from exc


def _resolve_repo(candidate: Path) -> Path:
    result = _run_git(candidate, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise GateError("GIT_CONTEXT_UNAVAILABLE")
    root = Path(result.stdout.strip()).resolve()
    if not root.is_dir():
        raise GateError("GIT_CONTEXT_UNAVAILABLE")
    return root


def _read_regular(repo: Path, relative: str) -> bytes:
    path = repo / relative
    if path.is_symlink() or not path.is_file():
        raise GateError("REQUIRED_STATE_MISSING")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise GateError("REQUIRED_STATE_UNREADABLE") from exc


def _read_text(repo: Path, relative: str) -> str:
    try:
        return _read_regular(repo, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError("REQUIRED_STATE_UNREADABLE") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_bootstrap_manifest(repo: Path) -> BootstrapBaseline:
    try:
        value = json.loads(
            _read_regular(repo, BOOTSTRAP_MANIFEST_PATH).decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GateError("BOOTSTRAP_BASELINE_INVALID") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "release_version", "self_path", "files"}:
        raise GateError("BOOTSTRAP_BASELINE_INVALID")
    if value["schema_version"] != 1 or not isinstance(value["release_version"], str) or not VERSION_RE.fullmatch(value["release_version"]):
        raise GateError("BOOTSTRAP_BASELINE_INVALID")
    if value["self_path"] != BOOTSTRAP_MANIFEST_PATH or not isinstance(value["files"], list) or not value["files"]:
        raise GateError("BOOTSTRAP_BASELINE_INVALID")

    entries: list[tuple[str, str]] = []
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise GateError("BOOTSTRAP_BASELINE_INVALID")
        path = item["path"]
        digest = item["sha256"]
        if (
            not _safe_relative_path(path)
            or path == BOOTSTRAP_MANIFEST_PATH
            or path == INSTALLATION_MANIFEST_PATH
            or path.startswith(".git/")
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise GateError("BOOTSTRAP_BASELINE_INVALID")
        entries.append((path, digest))
    if len({path for path, _ in entries}) != len(entries) or [path for path, _ in entries] != sorted(path for path, _ in entries):
        raise GateError("BOOTSTRAP_BASELINE_INVALID")
    if ".iskin/policy_gate.py" not in {path for path, _ in entries}:
        raise GateError("BOOTSTRAP_BASELINE_INVALID")
    return BootstrapBaseline(value["release_version"], value["self_path"], tuple(entries))


def _load_installation_manifest(repo: Path, baseline: BootstrapBaseline) -> dict[str, str]:
    try:
        value = json.loads(
            _read_regular(repo, INSTALLATION_MANIFEST_PATH).decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID") from exc
    required = {"schema_version", "release_version", "archive_sha256", "files"}
    if not isinstance(value, dict) or set(value) != required:
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")
    if value["schema_version"] != 1 or value["release_version"] != baseline.release_version:
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")
    if not isinstance(value["archive_sha256"], str) or not SHA256_RE.fullmatch(value["archive_sha256"]):
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")
    if not isinstance(value["files"], list) or not value["files"]:
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")

    observed: dict[str, str] = {}
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")
        path = item["path"]
        digest = item["sha256"]
        if not _safe_relative_path(path) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) or path in observed:
            raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")
        observed[path] = digest
    if list(observed) != sorted(observed):
        raise GateError("BOOTSTRAP_INSTALLATION_METADATA_INVALID")

    immutable = {
        path
        for path, _ in baseline.files
        if not path.startswith(("product-memory/", "telemetry/"))
    }
    immutable.update({baseline.self_path, ".iskin/version"})
    if set(observed) != immutable:
        raise GateError("BOOTSTRAP_INSTALLATION_SCOPE_INVALID")
    for path, expected in observed.items():
        file_path = repo / path
        if file_path.is_symlink() or not file_path.is_file():
            raise GateError("BOOTSTRAP_BASELINE_MISSING")
        try:
            actual = _sha256_bytes(file_path.read_bytes())
        except OSError as exc:
            raise GateError("BOOTSTRAP_BASELINE_UNREADABLE") from exc
        if actual != expected:
            raise GateError("BOOTSTRAP_BASELINE_HASH_MISMATCH")
    version_path = repo / ".iskin/version"
    if version_path.read_bytes() != f"{baseline.release_version}\n".encode("utf-8"):
        raise GateError("BOOTSTRAP_BASELINE_HASH_MISMATCH")
    return observed


def _workspace_inventory(repo: Path) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    try:
        for current_name, directory_names, file_names in os.walk(repo, topdown=True, followlinks=False):
            current = Path(current_name)
            if current == repo and ".git" in directory_names:
                directory_names.remove(".git")
            for name in sorted(directory_names):
                path = current / name
                relative = path.relative_to(repo).as_posix()
                if path.is_symlink() or not path.is_dir():
                    raise GateError("BOOTSTRAP_UNSAFE_PATH")
                directories.add(relative)
            for name in sorted(file_names):
                path = current / name
                relative = path.relative_to(repo).as_posix()
                if path.is_symlink() or not path.is_file():
                    raise GateError("BOOTSTRAP_UNSAFE_PATH")
                files.add(relative)
    except OSError as exc:
        raise GateError("BOOTSTRAP_BASELINE_UNREADABLE") from exc
    return files, directories


def _validate_bootstrap_baseline(repo: Path) -> BootstrapBaseline:
    baseline = _load_bootstrap_manifest(repo)
    _load_installation_manifest(repo, baseline)
    expected_files = {path for path, _ in baseline.files}
    expected_files.update({baseline.self_path, ".iskin/version", INSTALLATION_MANIFEST_PATH})
    actual_files, actual_directories = _workspace_inventory(repo)
    missing = expected_files - actual_files
    unexpected = actual_files - expected_files
    if missing:
        raise GateError("BOOTSTRAP_BASELINE_MISSING")
    if unexpected:
        raise GateError("BOOTSTRAP_UNEXPECTED_FILE")

    expected_directories: set[str] = set()
    for path in expected_files:
        parent = Path(path).parent
        while str(parent) not in {"", "."}:
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    if actual_directories != expected_directories:
        raise GateError("BOOTSTRAP_UNEXPECTED_PATH")

    expected_hashes = dict(baseline.files)
    for path, expected in expected_hashes.items():
        file_path = repo / path
        if not file_path.is_file():
            raise GateError("BOOTSTRAP_BASELINE_MISSING")
        if _sha256_bytes(file_path.read_bytes()) != expected:
            raise GateError("BOOTSTRAP_BASELINE_HASH_MISMATCH")
    return baseline


def _head_exists(repo: Path) -> bool:
    result = _run_git(repo, "rev-parse", "--verify", "HEAD")
    if result.returncode == 0:
        return True
    if result.returncode == 128:
        return False
    raise GateError("GIT_CHECK_FAILED")


def _bootstrap_scope(repo: Path, baseline: BootstrapBaseline) -> tuple[bool, tuple[str, ...]]:
    expected = {path for path, _ in baseline.files}
    expected.update({baseline.self_path, ".iskin/version", INSTALLATION_MANIFEST_PATH})
    staged = set(_staged_paths(repo))
    unstaged = set(_unstaged_paths(repo))
    reasons: list[str] = []
    if not staged:
        reasons.append("BOOTSTRAP_SCOPE_NOT_STAGED")
    elif staged != expected:
        reasons.append("BOOTSTRAP_SCOPE_MISMATCH")
    if unstaged:
        reasons.append("BOOTSTRAP_UNSTAGED_REMAINDER")
    diff_check = _run_git(repo, "diff", "--cached", "--check")
    if diff_check.returncode != 0:
        reasons.append("BOOTSTRAP_DIFF_CHECK_FAILED")
    return not reasons, tuple(dict.fromkeys(reasons))


def _head_has(repo: Path, relative: str) -> bool:
    result = _run_git(repo, "cat-file", "-e", f"HEAD:{relative}")
    if result.returncode == 0:
        return True
    if result.returncode == 128:
        return False
    raise GateError("GIT_CHECK_FAILED")


def _head_bytes(repo: Path, relative: str) -> bytes:
    stdout, _, returncode = _run_git_bytes(repo, "show", f"HEAD:{relative}")
    if returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return stdout


def _commit_bytes(repo: Path, commit: str, relative: str) -> bytes:
    stdout, _, returncode = _run_git_bytes(repo, "show", f"{commit}:{relative}")
    if returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return stdout


def _commits(repo: Path, rev: str) -> list[str]:
    return [line for line in _git_stdout(repo, "rev-list", "--reverse", rev).splitlines() if line]


def _changed_paths(repo: Path, commit: str) -> tuple[str, ...]:
    return tuple(sorted(_git_paths(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit)))


def _added_paths(repo: Path, commit: str) -> tuple[str, ...]:
    return tuple(sorted(_git_paths(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=A", "-r", commit)))


def _commit_subject(repo: Path, commit: str) -> str:
    return _git_stdout(repo, "show", "-s", "--format=%s", commit).strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _run_git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise GateError("GIT_CHECK_FAILED")


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _is_product_path(path: str) -> bool:
    if path.startswith(".iskin/") or path.startswith(f"{EVENT_DIR}/"):
        return False
    return _matches(path, DEFAULT_PRODUCT_CODE_PATTERNS)


def _is_evidence_path(path: str) -> bool:
    return _matches(path, DEFAULT_PRODUCT_EVIDENCE_PATTERNS)


def _product_or_evidence(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(path for path in paths if _is_product_path(path) or _is_evidence_path(path)))


def _unstaged_paths(repo: Path) -> tuple[str, ...]:
    tracked = _git_paths(repo, "diff", "--name-only")
    untracked = _git_paths(repo, "ls-files", "--others", "--exclude-standard")
    return tuple(sorted(set(tracked) | set(untracked)))


def _staged_paths(repo: Path) -> tuple[str, ...]:
    return tuple(sorted(set(_git_paths(repo, "diff", "--cached", "--name-only", "--no-renames"))))


def _staged_added_paths(repo: Path) -> tuple[str, ...]:
    return tuple(sorted(set(_git_paths(repo, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=A"))))


def _staged_deleted_paths(repo: Path) -> tuple[str, ...]:
    return tuple(sorted(set(_git_paths(repo, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=D"))))


def _package_paths(package_id: str) -> tuple[str, ...]:
    return (
        REGISTRY_PATH,
        f"product-memory/approval-packages/{package_id}.md",
        "product-memory/intent.md",
        "product-memory/outcomes.md",
        "product-memory/uncertainties.md",
    )


def _load_packages(repo: Path) -> tuple[Package, ...]:
    registry = _read_text(repo, REGISTRY_PATH)
    package_ids = list(dict.fromkeys(PACKAGE_REFERENCE_RE.findall(registry)))
    packages: list[Package] = []
    for package_id in package_ids:
        if not PACKAGE_ID_RE.fullmatch(package_id):
            raise GateError("MACHINE_STATE_INVALID")
        package_path = f"product-memory/approval-packages/{package_id}.md"
        package_text = _read_text(repo, package_path)
        required_markers = (
            f"package_id: {package_id}",
            "### intent",
            "### граница MVP",
            "### outcomes",
            "### обязательные gates",
            "### существенные uncertainties",
        )
        if any(marker not in package_text for marker in required_markers):
            raise GateError("PACKAGE_INCOMPLETE")
        packages.append(Package(package_id, package_path, _package_paths(package_id)))
    return tuple(packages)


def _checkpoint_for_package(repo: Path, package: Package) -> str | None:
    if not _head_has(repo, package.package_path):
        return None
    added = _git_stdout(repo, "log", "--reverse", "--format=%H", "--diff-filter=A", "--", package.package_path).splitlines()
    if len(added) != 1:
        raise GateError("CHECKPOINT_NOT_UNIQUE")
    checkpoint = added[0].strip()
    if not checkpoint or not _commit_subject(repo, checkpoint).startswith(f"{CHECKPOINT_PREFIX} {package.package_id}"):
        raise GateError("CHECKPOINT_MARKER_MISSING")
    head = _git_stdout(repo, "rev-parse", "HEAD").strip()
    if not _is_ancestor(repo, checkpoint, head):
        raise GateError("CHECKPOINT_NOT_ANCESTOR")
    changed = set(_changed_paths(repo, checkpoint))
    if not set(package.package_paths).issubset(changed):
        raise GateError("CHECKPOINT_SCOPE_INCOMPLETE")
    return checkpoint


def _package_drift(repo: Path, package_paths: Iterable[str], checkpoint: str) -> bool:
    package_paths = tuple(package_paths)
    for commit in _commits(repo, "HEAD"):
        if commit == checkpoint or _is_ancestor(repo, commit, checkpoint):
            continue
        if set(_changed_paths(repo, commit)) & set(package_paths):
            return True
    for path in package_paths:
        if _commit_bytes(repo, checkpoint, path) != _read_regular(repo, path):
            return True
    return False


def _preapproval_product_changes(repo: Path, boundary: str) -> tuple[str, ...]:
    findings: set[str] = set()
    for commit in _commits(repo, boundary):
        findings.update(_product_or_evidence(_changed_paths(repo, commit)))
    return tuple(sorted(findings))


def _parse_event(path: str, raw: bytes) -> ApprovalEvent:
    expected_fields = {
        "schema_version",
        "event_type",
        "event_id",
        "package_id",
        "package_paths",
        "checkpoint_sha",
        "package_displayed_in_previous_agent_turn",
        "approval_question",
        "human_response",
        "actor",
        "implementation_authorized",
        "human_decision_path",
    }
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GateError("MACHINE_STATE_INVALID") from exc
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise GateError("MACHINE_STATE_INVALID")
    event_id = value["event_id"]
    package_id = value["package_id"]
    if not isinstance(event_id, str) or not EVENT_ID_RE.fullmatch(event_id) or path != f"{EVENT_DIR}/{event_id}.json":
        raise GateError("MACHINE_STATE_INVALID")
    if not isinstance(package_id, str) or not PACKAGE_ID_RE.fullmatch(package_id):
        raise GateError("MACHINE_STATE_INVALID")
    if value["schema_version"] != EVENT_SCHEMA_VERSION or value["event_type"] != "approval":
        raise GateError("UNSUPPORTED_PROJECT_STATE")
    if not isinstance(value["checkpoint_sha"], str) or not CHECKPOINT_SHA_RE.fullmatch(value["checkpoint_sha"]):
        raise GateError("MACHINE_STATE_INVALID")
    package_paths = _string_list(value["package_paths"])
    if not set(_package_paths(package_id)).issubset(package_paths):
        raise GateError("MACHINE_STATE_INVALID")
    if value["human_decision_path"] != DECISIONS_PATH:
        raise GateError("MACHINE_STATE_INVALID")
    for field in ("approval_question", "human_response", "actor"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise GateError("MACHINE_STATE_INVALID")
    if value["package_displayed_in_previous_agent_turn"] is not True or value["implementation_authorized"] is not True:
        raise GateError("MACHINE_STATE_INVALID")
    return ApprovalEvent(
        event_id,
        path,
        package_id,
        package_paths,
        value["checkpoint_sha"],
        value["approval_question"],
        value["human_response"],
        value["actor"],
        value["package_displayed_in_previous_agent_turn"],
        value["implementation_authorized"],
    )


def _load_events(repo: Path) -> tuple[tuple[ApprovalEvent, bytes], ...]:
    directory = repo / EVENT_DIR
    if not directory.exists():
        return ()
    if directory.is_symlink() or not directory.is_dir():
        raise GateError("MACHINE_STATE_INVALID")
    result: list[tuple[ApprovalEvent, bytes]] = []
    for path in sorted(directory.iterdir()):
        relative = path.relative_to(repo).as_posix()
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise GateError("MACHINE_STATE_INVALID")
        raw = path.read_bytes()
        result.append((_parse_event(relative, raw), raw))
    return tuple(result)


def _event_add_commit(repo: Path, event: ApprovalEvent) -> str | None:
    commits = _git_stdout(repo, "log", "--reverse", "--format=%H", "--diff-filter=A", "--", event.path).splitlines()
    if len(commits) > 1:
        raise GateError("APPROVAL_EVENT_MUTATED")
    return commits[0].strip() if commits else None


def _decision_reference_values(repo: Path) -> tuple[dict[str, str], ...]:
    text = _read_text(repo, DECISIONS_PATH)
    ids = list(EVENT_REFERENCE_RE.finditer(text))
    references: list[dict[str, str]] = []
    for index, match in enumerate(ids):
        start = match.start()
        end = ids[index + 1].start() if index + 1 < len(ids) else len(text)
        block = text[start:end]
        values = {"event_id": match.group(1)}
        for name, pattern in (
            ("event_path", EVENT_PATH_REFERENCE_RE),
            ("package_id", re.compile(r"^\s*package_id:\s*([^\s]+)\s*$", re.MULTILINE)),
            ("checkpoint_sha", re.compile(r"^\s*checkpoint_sha:\s*([^\s]+)\s*$", re.MULTILINE)),
        ):
            found = pattern.search(block)
            if found:
                values[name] = found.group(1)
        references.append(values)
    return tuple(references)


def _decision_reference_for(repo: Path, event: ApprovalEvent) -> bool:
    references = _decision_reference_values(repo)
    for reference in references:
        if reference.get("event_id") != event.event_id:
            continue
        if reference.get("event_path") != event.path:
            continue
        if reference.get("package_id") != event.package_id:
            continue
        if reference.get("checkpoint_sha") != event.checkpoint_sha:
            continue
        return True
    return False


def _check_decision_alignment(repo: Path, events: Iterable[ApprovalEvent]) -> None:
    references = _decision_reference_values(repo)
    event_by_id = {event.event_id: event for event in events}
    for reference in references:
        event = event_by_id.get(reference.get("event_id", ""))
        if event is None:
            raise GateError("ORPHANED_HUMAN_DECISION")
        if not _decision_reference_for(repo, event):
            raise GateError("HUMAN_DECISION_REFERENCE_MISMATCH")
    for event in event_by_id.values():
        if not _decision_reference_for(repo, event):
            raise GateError("HUMAN_DECISION_REFERENCE_MISSING")


def _event_scope(repo: Path, event: ApprovalEvent, checkpoint: str) -> tuple[bool, tuple[str, ...]]:
    # The read-only pre-commit check is equivalent to: git diff --cached --check.
    reasons: list[str] = []
    staged = set(_staged_paths(repo))
    added = set(_staged_added_paths(repo))
    deleted = set(_staged_deleted_paths(repo))
    allowed = {event.path, DECISIONS_PATH}
    if staged != allowed:
        reasons.append("APPROVAL_SCOPE_EXTRANEOUS")
    if event.path not in added or DECISIONS_PATH in deleted:
        reasons.append("APPROVAL_EVENT_NOT_APPEND_ONLY")
    unstaged = set(_unstaged_paths(repo))
    if unstaged:
        reasons.append("APPROVAL_SCOPE_UNSTAGED_CHANGES")
    if _product_or_evidence(staged | unstaged):
        reasons.append("APPROVAL_SCOPE_PRODUCT_OR_EVIDENCE")
    check = _run_git(repo, "diff", "--cached", "--check")
    if check.returncode != 0:
        reasons.append("STAGED_DIFF_CHECK_FAILED")
    if _package_drift(repo, event.package_paths, checkpoint):
        reasons.append("PACKAGE_CHANGED_AFTER_CHECKPOINT")
    if not _decision_reference_for(repo, event):
        reasons.append("HUMAN_DECISION_REFERENCE_MISSING")
    return not reasons, tuple(dict.fromkeys(reasons))


def _approval_commit(repo: Path, event: ApprovalEvent, checkpoint: str) -> str | None:
    commit = _event_add_commit(repo, event)
    if commit is None:
        return None
    if not _is_ancestor(repo, checkpoint, commit) or commit == checkpoint:
        raise GateError("APPROVAL_COMMIT_ORDER_INVALID")
    changed = set(_changed_paths(repo, commit))
    if changed != {event.path, DECISIONS_PATH} or event.path not in set(_added_paths(repo, commit)):
        raise GateError("APPROVAL_COMMIT_SCOPE_INVALID")
    if _commit_bytes(repo, commit, event.path) != _read_regular(repo, event.path):
        raise GateError("APPROVAL_EVENT_NOT_DURABLE")
    if _commit_bytes(repo, commit, DECISIONS_PATH) != _read_regular(repo, DECISIONS_PATH):
        raise GateError("HUMAN_DECISION_NOT_DURABLE")
    return commit


def _ensure_supported_project(repo: Path) -> None:
    gate = repo / GATE_PATH
    if gate.is_symlink() or not gate.is_file():
        raise GateError("UNSUPPORTED_PROJECT_STATE")
    legacy_state = repo / LEGACY_STATE_PATH
    if legacy_state.exists() or legacy_state.is_symlink():
        raise GateError("UNSUPPORTED_PROJECT_STATE")


def _blocked(
    package: Package | None,
    *reasons: str,
    checkpoint: str | None = None,
    approval_state: str = "unknown",
) -> Evaluation:
    return Evaluation(
        STATUS_BLOCKED,
        tuple(dict.fromkeys(reasons)),
        package.package_id if package else None,
        checkpoint,
        approval_state,
        None,
        ("read_only_recovery",),
        "approval_display_is_conversational_evidence_not_cryptographic_proof",
    )


def _build_bootstrap_evaluation(repo: Path, action: str) -> Evaluation:
    baseline = _validate_bootstrap_baseline(repo)
    scope_valid, scope_reasons = _bootstrap_scope(repo, baseline)
    allowed = ["discover", "prepare_approval", "read_only_recovery"]
    if scope_valid:
        allowed.insert(0, "bootstrap_checkpoint")
    if action == "bootstrap_checkpoint" and not scope_valid:
        return Evaluation(
            STATUS_DISCOVERY,
            tuple(("INITIAL_BASELINE_UNCOMMITTED", *scope_reasons)),
            None,
            None,
            "none",
            "discovery",
            tuple(allowed),
            "not_applicable_without_approval_event",
        )
    return Evaluation(
        STATUS_DISCOVERY,
        ("INITIAL_BASELINE_UNCOMMITTED",),
        None,
        None,
        "none",
        "discovery",
        tuple(allowed),
        "not_applicable_without_approval_event",
    )


def _build_evaluation(repo: Path, action: str) -> Evaluation:
    _ensure_supported_project(repo)
    if not _head_exists(repo):
        return _build_bootstrap_evaluation(repo, action)
    packages = _load_packages(repo)
    events_with_bytes = _load_events(repo)
    events = tuple(event for event, _ in events_with_bytes)
    if events or (repo / DECISIONS_PATH).is_file():
        _check_decision_alignment(repo, events)
    if not packages:
        if events:
            return _blocked(None, "ORPHANED_APPROVAL_EVENT")
        if _product_or_evidence(_unstaged_paths(repo) + _git_paths(repo, "diff", "--cached", "--name-only", "--no-renames")):
            return _blocked(None, "PRODUCT_OR_EVIDENCE_WITHOUT_PACKAGE")
        return Evaluation(
            STATUS_DISCOVERY,
            ("NO_APPROVAL_PACKAGE",),
            None,
            None,
            "none",
            "discovery",
            ("discover", "prepare_approval", "read_only_recovery"),
            "not_applicable_without_approval_event",
        )

    package = packages[-1]
    checkpoint = _checkpoint_for_package(repo, package)
    if checkpoint is None:
        dirty = _unstaged_paths(repo) + _git_paths(repo, "diff", "--cached", "--name-only", "--no-renames")
        if _product_or_evidence(dirty):
            return _blocked(package, "PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT", approval_state="prepared")
        return Evaluation(
            STATUS_AWAITING,
            ("PACKAGE_CHECKPOINT_MISSING",),
            package.package_id,
            None,
            "prepared",
            "awaiting_approval",
            ("pre_approval_checkpoint", "read_only_recovery"),
            "not_applicable_without_approval_event",
        )

    if _package_drift(repo, package.package_paths, checkpoint):
        return _blocked(package, "PACKAGE_CHANGED_AFTER_CHECKPOINT", checkpoint=checkpoint, approval_state="prepared")
    checkpoint_product = _product_or_evidence(_changed_paths(repo, checkpoint))
    if checkpoint_product:
        return _blocked(package, "CHECKPOINT_CONTAINS_PRODUCT_OR_EVIDENCE", checkpoint=checkpoint, approval_state="prepared")
    preapproval_product = _preapproval_product_changes(repo, checkpoint)
    if preapproval_product:
        return _blocked(package, "PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT", checkpoint=checkpoint, approval_state="prepared")

    candidates = [event for event in events if event.package_id == package.package_id]
    if not candidates:
        dirty = _unstaged_paths(repo) + _git_paths(repo, "diff", "--cached", "--name-only", "--no-renames")
        if _product_or_evidence(dirty):
            return _blocked(package, "PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL", checkpoint=checkpoint, approval_state="prepared")
        return Evaluation(
            STATUS_AWAITING,
            ("PRE_APPROVAL_CHECKPOINT_PRESENT", "APPROVAL_EVENT_ABSENT"),
            package.package_id,
            checkpoint,
            "prepared",
            "awaiting_approval",
            ("human_approval", "read_only_recovery"),
            "approval_display_is_conversational_evidence_not_cryptographic_proof",
        )
    if len(candidates) > 1:
        return _blocked(package, "MULTIPLE_ACTIVE_APPROVAL_EVENTS", checkpoint=checkpoint, approval_state="prepared")

    event = candidates[0]
    if event.checkpoint_sha != checkpoint:
        return _blocked(package, "APPROVAL_CHECKPOINT_MISMATCH", checkpoint=checkpoint, approval_state="prepared")
    if _package_drift(repo, event.package_paths, checkpoint):
        return _blocked(package, "PACKAGE_CHANGED_AFTER_CHECKPOINT", checkpoint=checkpoint, approval_state="prepared")

    approval_commit = _approval_commit(repo, event, checkpoint)
    if approval_commit is None:
        valid_scope, scope_reasons = _event_scope(repo, event, checkpoint)
        if not valid_scope:
            if action == "approval_checkpoint":
                return _blocked(package, *scope_reasons, checkpoint=checkpoint, approval_state="pending_checkpoint")
            return Evaluation(
                STATUS_AWAITING,
                tuple(("APPROVAL_EVENT_PENDING_COMMIT", *scope_reasons)),
                package.package_id,
                checkpoint,
                "pending_checkpoint",
                "awaiting_approval",
                ("read_only_recovery",),
                "approval_display_is_conversational_evidence_not_cryptographic_proof",
            )
        return Evaluation(
            STATUS_AWAITING,
            ("APPROVAL_EVENT_PENDING_COMMIT", "APPROVAL_CHECKPOINT_SCOPE_VALID"),
            package.package_id,
            checkpoint,
            "pending_checkpoint",
            "awaiting_approval",
            ("approval_checkpoint", "read_only_recovery"),
            "approval_display_is_conversational_evidence_not_cryptographic_proof",
        )

    approval_product = _product_or_evidence(_changed_paths(repo, approval_commit))
    if approval_product:
        return _blocked(package, "APPROVAL_COMMIT_CONTAINS_PRODUCT_OR_EVIDENCE", checkpoint=checkpoint, approval_state="prepared")
    return Evaluation(
        STATUS_IMPLEMENTATION,
        ("APPROVAL_EVENT_VALID", "PACKAGE_MATCHES_CHECKPOINT", "HUMAN_DECISION_REFERENCE_VALID", "PREAPPROVAL_SCOPE_CLEAN"),
        package.package_id,
        checkpoint,
        "approved",
        "implementation_allowed",
        ("change_product", "prove_result", "checkpoint", "read_only_recovery"),
        "approval_display_is_conversational_evidence_not_cryptographic_proof",
    )


def evaluate(candidate: Path, action: str) -> tuple[Evaluation, Path | None]:
    try:
        repo = _resolve_repo(candidate)
        return _build_evaluation(repo, action), repo
    except GateError as exc:
        return _blocked(None, *exc.reason_codes), None
    except (OSError, UnicodeError):
        return _blocked(None, "READ_ONLY_CHECK_FAILED"), None


def _payload(result: Evaluation, repo: Path | None) -> dict[str, Any]:
    forbidden = tuple(action for action in CRITICAL_ACTIONS if action not in result.allowed_actions)
    return {
        "schema_version": 1,
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "allowed_actions": list(result.allowed_actions),
        "forbidden_actions": list(forbidden),
        "package_id": result.package_id,
        "checkpoint_sha": result.checkpoint_sha,
        "approval_state": result.approval_state,
        "lifecycle": result.lifecycle,
        "human_evidence_boundary": result.human_evidence_boundary,
        "repo_root": str(repo) if repo is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only IskIn lifecycle policy gate")
    parser.add_argument("--repo", default=".", help="project directory or a child directory")
    parser.add_argument(
        "--action",
        choices=("status", *ACTIONS),
        default="status",
        help="action to authorize; status and read_only_recovery only report",
    )
    args = parser.parse_args(argv)
    result, repo = evaluate(Path(args.repo).expanduser(), args.action)
    payload = _payload(result, repo)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if args.action in {"status", "read_only_recovery"}:
        return 0
    if result.status == STATUS_BLOCKED:
        return 20
    return 0 if args.action in result.allowed_actions else 10


if __name__ == "__main__":
    raise SystemExit(main())
