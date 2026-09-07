#!/usr/bin/env python3
"""Read-only, deterministic lifecycle policy gate for an IskIn project.

The gate reads the local machine state and Git history.  It never writes the
worktree, index, telemetry, or any external system.  The approval event's
``package_displayed_in_previous_agent_turn`` field is a durable assertion made
by the orchestration layer; this program cannot cryptographically prove that a
human actually saw a conversational message.
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

SCHEMA_VERSION = 1
STATE_PATH = ".iskin/policy_state.json"
REGISTRY_PATH = "product-memory/approval-packages.md"
CHECKPOINT_PREFIX = "iskin: pre-approval checkpoint:"
CHECKPOINT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")

STATUS_DISCOVERY = "DISCOVERY_ALLOWED"
STATUS_AWAITING = "AWAITING_APPROVAL"
STATUS_IMPLEMENTATION = "IMPLEMENTATION_ALLOWED"
STATUS_BLOCKED = "PROCESS_BLOCKED"

ACTIONS = (
    "discover",
    "prepare_approval",
    "pre_approval_checkpoint",
    "human_approval",
    "change_product",
    "prove_result",
    "checkpoint",
    "read_only_recovery",
    "product_tests",
    "telemetry_write",
)
CRITICAL_ACTIONS = ("change_product", "prove_result", "checkpoint", "product_tests", "telemetry_write")
UNVERIFIABLE_REASONS = {
    "GIT_CONTEXT_UNAVAILABLE",
    "GIT_CHECK_FAILED",
    "REQUIRED_STATE_MISSING",
    "REQUIRED_STATE_UNREADABLE",
    "MACHINE_STATE_INVALID",
    "MACHINE_STATE_UNSUPPORTED",
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
        self.reason_codes = tuple(reason_codes)


@dataclass(frozen=True)
class State:
    lifecycle: str
    approval_state: str
    package_id: str | None
    package_paths: tuple[str, ...]
    approval_event: dict[str, Any] | None
    product_code_patterns: tuple[str, ...]
    product_evidence_patterns: tuple[str, ...]


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int


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


def _safe_pattern(value: Any) -> bool:
    if not _safe_relative_path(value):
        return False
    return not value.startswith("/")


def _string_list(value: Any, *, patterns: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != len(set(value)):
        raise GateError("MACHINE_STATE_INVALID")
    checker = _safe_pattern if patterns else _safe_relative_path
    if any(not checker(item) for item in value):
        raise GateError("MACHINE_STATE_INVALID")
    return tuple(value)


def _parse_state(raw: bytes) -> State:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise GateError("MACHINE_STATE_INVALID")
    if not isinstance(value, dict):
        raise GateError("MACHINE_STATE_INVALID")
    required = {"schema_version", "lifecycle", "approval_state", "package", "approval_event", "scope"}
    if set(value) != required or value["schema_version"] != SCHEMA_VERSION:
        raise GateError("MACHINE_STATE_UNSUPPORTED")
    lifecycle = value["lifecycle"]
    approval_state = value["approval_state"]
    if lifecycle not in {"discovery", "awaiting_approval", "implementation_allowed"}:
        raise GateError("MACHINE_STATE_INVALID")
    if approval_state not in {"none", "prepared", "approved"}:
        raise GateError("MACHINE_STATE_INVALID")

    package_value = value["package"]
    package_id: str | None = None
    package_paths: tuple[str, ...] = ()
    if package_value is not None:
        if not isinstance(package_value, dict) or set(package_value) != {"package_id", "package_paths"}:
            raise GateError("MACHINE_STATE_INVALID")
        package_id = package_value["package_id"]
        if not isinstance(package_id, str) or not PACKAGE_ID_RE.fullmatch(package_id):
            raise GateError("MACHINE_STATE_INVALID")
        package_paths = _string_list(package_value["package_paths"])
        expected_package = f"product-memory/approval-packages/{package_id}.md"
        if REGISTRY_PATH not in package_paths or expected_package not in package_paths:
            raise GateError("MACHINE_STATE_INVALID")

    approval_value = value["approval_event"]
    approval_event: dict[str, Any] | None = None
    if approval_value is not None:
        fields = {
            "package_id",
            "checkpoint_sha",
            "package_displayed_in_previous_agent_turn",
            "approval_question",
            "human_response",
            "actor",
            "implementation_authorized",
        }
        if not isinstance(approval_value, dict) or set(approval_value) != fields:
            raise GateError("MACHINE_STATE_INVALID")
        if not isinstance(approval_value["package_id"], str) or not PACKAGE_ID_RE.fullmatch(approval_value["package_id"]):
            raise GateError("MACHINE_STATE_INVALID")
        if not isinstance(approval_value["checkpoint_sha"], str) or not CHECKPOINT_SHA_RE.fullmatch(approval_value["checkpoint_sha"]):
            raise GateError("MACHINE_STATE_INVALID")
        for field in ("approval_question", "human_response", "actor"):
            if not isinstance(approval_value[field], str) or not approval_value[field].strip():
                raise GateError("MACHINE_STATE_INVALID")
        if approval_value["package_displayed_in_previous_agent_turn"] is not True or approval_value["implementation_authorized"] is not True:
            raise GateError("MACHINE_STATE_INVALID")
        approval_event = approval_value

    scope = value["scope"]
    if not isinstance(scope, dict) or set(scope) != {"product_code_paths", "product_evidence_paths"}:
        raise GateError("MACHINE_STATE_INVALID")
    product_code = _string_list(scope["product_code_paths"], patterns=True) or DEFAULT_PRODUCT_CODE_PATTERNS
    product_evidence = _string_list(scope["product_evidence_paths"], patterns=True) or DEFAULT_PRODUCT_EVIDENCE_PATTERNS

    if package_id is None:
        if lifecycle != "discovery" or approval_state != "none" or approval_event is not None:
            raise GateError("MACHINE_STATE_INVALID")
    elif approval_event is None:
        if lifecycle != "awaiting_approval" or approval_state != "prepared":
            raise GateError("MACHINE_STATE_INVALID")
    else:
        if lifecycle != "implementation_allowed" or approval_state != "approved":
            raise GateError("MACHINE_STATE_INVALID")
        if approval_event["package_id"] != package_id:
            raise GateError("MACHINE_STATE_INVALID")

    return State(
        lifecycle=lifecycle,
        approval_state=approval_state,
        package_id=package_id,
        package_paths=package_paths,
        approval_event=approval_event,
        product_code_patterns=tuple(product_code),
        product_evidence_patterns=tuple(product_evidence),
    )


def _run_git(repo: Path, *args: str) -> GitResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise GateError("GIT_CHECK_FAILED") from exc
    return GitResult(completed.stdout, completed.stderr, completed.returncode)


def _git_stdout(repo: Path, *args: str) -> str:
    result = _run_git(repo, *args)
    if result.returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return result.stdout


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
    except (OSError, UnicodeError) as exc:
        raise GateError("REQUIRED_STATE_UNREADABLE") from exc


def _head_has(repo: Path, relative: str) -> bool:
    result = _run_git(repo, "cat-file", "-e", f"HEAD:{relative}")
    if result.returncode == 0:
        return True
    if result.returncode == 128:
        return False
    raise GateError("GIT_CHECK_FAILED")


def _head_bytes(repo: Path, relative: str) -> bytes:
    result = _run_git(repo, "show", f"HEAD:{relative}")
    if result.returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return result.stdout.encode("utf-8")


def _commit_bytes(repo: Path, commit: str, relative: str) -> bytes:
    result = _run_git(repo, "show", f"{commit}:{relative}")
    if result.returncode != 0:
        raise GateError("GIT_CHECK_FAILED")
    return result.stdout.encode("utf-8")


def _commits(repo: Path, rev: str) -> list[str]:
    return [line.strip() for line in _git_stdout(repo, "rev-list", "--reverse", rev).splitlines() if line.strip()]


def _changed_paths(repo: Path, commit: str) -> tuple[str, ...]:
    output = _git_stdout(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit)
    return tuple(sorted(path for path in output.splitlines() if path))


def _commit_subject(repo: Path, commit: str) -> str:
    return _git_stdout(repo, "show", "-s", "--format=%s", commit).strip()


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _is_product_path(path: str, state: State) -> bool:
    if path == STATE_PATH or path.startswith(".iskin/"):
        return False
    return _matches(path, state.product_code_patterns)


def _is_evidence_path(path: str, state: State) -> bool:
    return _matches(path, state.product_evidence_patterns)


def _product_or_evidence(paths: Iterable[str], state: State) -> tuple[str, ...]:
    return tuple(sorted(path for path in paths if _is_product_path(path, state) or _is_evidence_path(path, state)))


def _status_paths(repo: Path) -> tuple[str, ...]:
    output = _git_stdout(repo, "status", "--porcelain=v1", "-z")
    paths: list[str] = []
    fields = output.split("\0")
    for field in fields:
        if not field:
            continue
        path = field[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return tuple(sorted(set(paths)))


def _package_files(repo: Path, state: State) -> tuple[str, ...]:
    missing = [path for path in state.package_paths if not (repo / path).is_file() or (repo / path).is_symlink()]
    if missing:
        raise GateError("PACKAGE_STATE_MISSING")
    registry = (repo / REGISTRY_PATH).read_text(encoding="utf-8")
    expected_reference = f"product-memory/approval-packages/{state.package_id}.md"
    if expected_reference not in registry:
        raise GateError("PACKAGE_REGISTRY_MISMATCH")
    package_path = repo / f"product-memory/approval-packages/{state.package_id}.md"
    package_text = package_path.read_text(encoding="utf-8")
    required_markers = (
        f"package_id: {state.package_id}",
        "### intent",
        "### граница MVP",
        "### outcomes",
        "### обязательные gates",
        "### существенные uncertainties",
    )
    if any(marker not in package_text for marker in required_markers):
        raise GateError("PACKAGE_INCOMPLETE")
    return state.package_paths


def _checkpoint_for_package(repo: Path, state: State) -> str | None:
    package_file = f"product-memory/approval-packages/{state.package_id}.md"
    if not _head_has(repo, package_file):
        return None
    added = _git_stdout(repo, "log", "--reverse", "--format=%H", "--diff-filter=A", "--", package_file).splitlines()
    if len(added) != 1:
        raise GateError("CHECKPOINT_NOT_UNIQUE")
    checkpoint = added[0].strip()
    if not checkpoint or not _commit_subject(repo, checkpoint).startswith(f"{CHECKPOINT_PREFIX} {state.package_id}"):
        raise GateError("CHECKPOINT_MARKER_MISSING")
    current_head = _git_stdout(repo, "rev-parse", "HEAD").strip()
    ancestry = _run_git(repo, "merge-base", "--is-ancestor", checkpoint, current_head)
    if ancestry.returncode != 0:
        raise GateError("CHECKPOINT_NOT_ANCESTOR")
    changed = set(_changed_paths(repo, checkpoint))
    if not set(state.package_paths).issubset(changed):
        raise GateError("CHECKPOINT_SCOPE_INCOMPLETE")
    return checkpoint


def _package_drift(repo: Path, state: State, checkpoint: str) -> bool:
    touched = set()
    for commit in _commits(repo, "HEAD"):
        if commit == checkpoint:
            continue
        if _run_git(repo, "merge-base", "--is-ancestor", commit, checkpoint).returncode == 0:
            continue
        if set(_changed_paths(repo, commit)) & set(state.package_paths):
            touched.add(commit)
    if touched:
        return True
    for path in state.package_paths:
        if _commit_bytes(repo, checkpoint, path) != (repo / path).read_bytes():
            return True
    return False


def _first_approval_commit(repo: Path, state: State, checkpoint: str) -> str | None:
    if state.approval_event is None:
        return None
    expected = json.dumps(
        {
            "package_id": state.package_id,
            "checkpoint_sha": state.approval_event["checkpoint_sha"],
        },
        sort_keys=True,
    )
    for commit in _commits(repo, "HEAD"):
        if commit == checkpoint:
            continue
        if _run_git(repo, "merge-base", "--is-ancestor", commit, checkpoint).returncode == 0:
            continue
        result = _run_git(repo, "show", f"{commit}:{STATE_PATH}")
        if result.returncode != 0:
            continue
        try:
            parsed = _parse_state(result.stdout.encode("utf-8"))
        except GateError:
            continue
        if parsed.approval_event is None:
            continue
        candidate = json.dumps(
            {"package_id": parsed.package_id, "checkpoint_sha": parsed.approval_event["checkpoint_sha"]},
            sort_keys=True,
        )
        if candidate == expected:
            return commit
    return None


def _preapproval_product_changes(repo: Path, state: State, checkpoint: str, approval_commit: str | None) -> tuple[str, ...]:
    commits = _commits(repo, "HEAD")
    findings: set[str] = set()
    for commit in commits:
        if commit == checkpoint:
            if _product_or_evidence(_changed_paths(repo, commit), state):
                findings.update(_product_or_evidence(_changed_paths(repo, commit), state))
            continue
        if _run_git(repo, "merge-base", "--is-ancestor", commit, checkpoint).returncode == 0:
            findings.update(_product_or_evidence(_changed_paths(repo, commit), state))
            continue
        if approval_commit is not None:
            if commit == approval_commit:
                findings.update(_product_or_evidence(_changed_paths(repo, commit), state))
                break
            if _run_git(repo, "merge-base", "--is-ancestor", commit, approval_commit).returncode == 0:
                findings.update(_product_or_evidence(_changed_paths(repo, commit), state))
        else:
            findings.update(_product_or_evidence(_changed_paths(repo, commit), state))
    return tuple(sorted(findings))


def _build_evaluation(repo: Path, state: State) -> Evaluation:
    package_id = state.package_id
    if package_id is None:
        dirty = _status_paths(repo)
        if any(_is_product_path(path, state) or _is_evidence_path(path, state) for path in dirty):
            return _blocked(state, "PRODUCT_OR_EVIDENCE_WITHOUT_PACKAGE")
        return Evaluation(
            STATUS_DISCOVERY,
            ("NO_APPROVAL_PACKAGE",),
            None,
            None,
            state.approval_state,
            state.lifecycle,
            ("discover", "prepare_approval", "read_only_recovery"),
            "not_applicable_without_approval_event",
        )

    _package_files(repo, state)
    checkpoint = _checkpoint_for_package(repo, state)
    dirty = set(_status_paths(repo))
    package_dirty = bool(dirty & set(state.package_paths))
    product_dirty = tuple(sorted(path for path in dirty if _is_product_path(path, state) or _is_evidence_path(path, state)))

    if checkpoint is None:
        if product_dirty:
            return _blocked(state, "PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT")
        if state.approval_event is not None:
            return _blocked(state, "APPROVAL_CHECKPOINT_MISSING")
        return Evaluation(
            STATUS_AWAITING,
            ("PACKAGE_CHECKPOINT_MISSING",),
            package_id,
            None,
            state.approval_state,
            state.lifecycle,
            ("pre_approval_checkpoint", "read_only_recovery"),
            "not_applicable_without_approval_event",
        )

    if _package_drift(repo, state, checkpoint) or package_dirty:
        return _blocked(state, "PACKAGE_CHANGED_AFTER_CHECKPOINT")
    changed_at_checkpoint = _product_or_evidence(_changed_paths(repo, checkpoint), state)
    if changed_at_checkpoint:
        return _blocked(state, "CHECKPOINT_CONTAINS_PRODUCT_OR_EVIDENCE")

    if state.approval_event is None:
        if product_dirty:
            return _blocked(state, "PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL")
        findings = _preapproval_product_changes(repo, state, checkpoint, None)
        if findings:
            return _blocked(state, "PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL")
        return Evaluation(
            STATUS_AWAITING,
            ("PRE_APPROVAL_CHECKPOINT_PRESENT", "APPROVAL_EVENT_ABSENT"),
            package_id,
            checkpoint,
            state.approval_state,
            state.lifecycle,
            ("human_approval", "read_only_recovery"),
            "approval_display_is_conversational_evidence_not_cryptographic_proof",
        )

    if state.approval_event["checkpoint_sha"] != checkpoint:
        return _blocked(state, "APPROVAL_CHECKPOINT_MISMATCH")
    approval_commit = _first_approval_commit(repo, state, checkpoint)
    if approval_commit is None:
        return _blocked(state, "APPROVAL_EVENT_NOT_DURABLE")
    findings = _preapproval_product_changes(repo, state, checkpoint, approval_commit)
    if findings or product_dirty and state.approval_event is None:
        return _blocked(state, "PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL")
    state_head = _head_bytes(repo, STATE_PATH)
    if state_head != _read_regular(repo, STATE_PATH):
        return _blocked(state, "APPROVAL_STATE_NOT_DURABLE")
    return Evaluation(
        STATUS_IMPLEMENTATION,
        ("APPROVAL_EVENT_VALID", "PACKAGE_MATCHES_CHECKPOINT", "PREAPPROVAL_SCOPE_CLEAN"),
        package_id,
        checkpoint,
        state.approval_state,
        state.lifecycle,
        ("change_product", "prove_result", "checkpoint", "read_only_recovery"),
        "approval_display_is_conversational_evidence_not_cryptographic_proof",
    )


def _blocked(state: State | None, *reasons: str) -> Evaluation:
    return Evaluation(
        STATUS_BLOCKED,
        tuple(dict.fromkeys(reasons)),
        state.package_id if state else None,
        None,
        state.approval_state if state else "unknown",
        state.lifecycle if state else None,
        ("read_only_recovery",),
        "approval_display_is_conversational_evidence_not_cryptographic_proof",
    )


def evaluate(candidate: Path) -> tuple[Evaluation, Path | None]:
    try:
        repo = _resolve_repo(candidate)
        raw = _read_regular(repo, STATE_PATH)
        state = _parse_state(raw)
        result = _build_evaluation(repo, state)
        expected_lifecycle = {
            STATUS_DISCOVERY: "discovery",
            STATUS_AWAITING: "awaiting_approval",
            STATUS_IMPLEMENTATION: "implementation_allowed",
        }.get(result.status)
        if expected_lifecycle is not None and state.lifecycle != expected_lifecycle:
            result = _blocked(state, "LIFECYCLE_STATE_MISMATCH")
        return result, repo
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
        help="action to authorize; status only reports the evaluated state",
    )
    args = parser.parse_args(argv)
    result, repo = evaluate(Path(args.repo).expanduser())
    payload = _payload(result, repo)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if args.action == "read_only_recovery" and not (set(result.reason_codes) & UNVERIFIABLE_REASONS):
        return 0
    if result.status == STATUS_BLOCKED:
        return 20
    if args.action == "status":
        return 0
    return 0 if args.action in result.allowed_actions else 10


if __name__ == "__main__":
    raise SystemExit(main())
