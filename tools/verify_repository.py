#!/usr/bin/env python3
"""Read-only checks for the ИскИн repository development tree.

This is a repository-development verifier, not an installer and not a
Budget-product verifier. It uses only the Python standard library and does
not write files or access the network.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "package" / "template"
RUNTIME_SKILLS = ROOT / "runtime" / "skills"

EXPECTED_TEMPLATE_FILES = {
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "process/README.md",
    "process/operating-model.md",
    "process/autonomy-policy.md",
    "process/action-selection.md",
    "process/quality-gates.md",
    "process/evidence-provenance.md",
    "process/git-checkpoint-recovery.md",
    "process/fixtures/provenance-drift/README.md",
    "process/fixtures/provenance-drift/template/manifest.json",
    "process/fixtures/provenance-drift/template/proof-record.json",
    "process/fixtures/provenance-drift/template/report.md",
    "product-memory/README.md",
    "product-memory/intent.md",
    "product-memory/outcomes.md",
    "product-memory/uncertainties.md",
    "product-memory/approval-packages.md",
    "product-memory/approval-packages/README.md",
    "product-memory/decisions.md",
    "product-memory/evidence.md",
    "telemetry/README.md",
    "telemetry/run-log.md",
    "telemetry/metrics.md",
}
EXPECTED_RUNTIME_SKILLS = {
    "iskin-understand-state",
    "iskin-choose-next-action",
    "iskin-change-product",
    "iskin-prove-result",
    "iskin-challenge-result",
    "iskin-control-pilot",
}
HISTORICAL_MISSING_LINKS = {
    (
        "docs/decisions/2026-09-06-v0.3-proved-accepted-boundary.md",
        "package/template/.hermes/skills/change-product/SKILL.md",
    ),
    (
        "docs/decisions/2026-09-06-v0.3-proved-accepted-boundary.md",
        "package/template/.hermes/skills/prove-result/SKILL.md",
    ),
}
RUNTIME_SKILL_VERSION = "0.4.0-dev"
TEMPLATE_GITIGNORE = (
    "# Operating-system metadata\n"
    ".DS_Store\n"
    "._*\n"
    "Thumbs.db\n"
    "Desktop.ini\n"
    "\n"
    "# Editor temporary files\n"
    "*.swp\n"
    "*.swo\n"
    "*~\n"
)
GITIGNORE_IGNORED_PATHS = (
    "package/template/.DS_Store",
    "package/template/nested/.DS_Store",
    "package/template/._root-metadata",
    "package/template/nested/._nested-metadata",
    "package/template/Thumbs.db",
    "package/template/nested/Thumbs.db",
    "package/template/Desktop.ini",
    "package/template/nested/Desktop.ini",
    "package/template/editor.swp",
    "package/template/nested/editor.swp",
    "package/template/editor.swo",
    "package/template/nested/editor.swo",
    "package/template/backup~",
    "package/template/nested/backup~",
)
GITIGNORE_VISIBLE_PATHS = (
    "package/template/.env",
    "package/template/.vscode/settings.json",
    "package/template/build/example.txt",
    "package/template/ordinary-untracked.txt",
)
REQUIRED_RUNTIME_SKILL_TRIGGERS = {
    "iskin-understand-state": "entering an IskIn project, starting a new session, recovering after interruption, or facing unclear state",
    "iskin-choose-next-action": "selecting exactly one next action after a confirmed IskIn state recovery",
    "iskin-change-product": "making one bounded change for an active IskIn outcome",
    "iskin-prove-result": "collecting canonical evidence for an approved IskIn outcome",
    "iskin-challenge-result": "an established challenge trigger requires independent critical review",
    "iskin-control-pilot": "orchestrating an IskIn cycle or starting a new session",
}
RUNTIME_PRODUCT_DATA = re.compile(r"\bbudget\b|\bp\d+-\d+\b|\brun[-_ ]?\d+\b", re.IGNORECASE)
FORBIDDEN_PACKAGE_CONTENT = re.compile(
    r"budget|p0-0[1-5]|\bg[1-5]\b|swift|xcode|xctest|xcuitest|budgetapp|₽|руб",
    re.IGNORECASE,
)
SECRET_FILE = re.compile(
    r"^(?:\.env(?:\..*)?|auth\.json|credentials(?:\..*)?|.*\.(?:pem|key))$",
    re.IGNORECASE,
)
PRIVATE_KEY_MARKER = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
ACCESS_KEY_MARKER = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
SECRET_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"']?([A-Za-z0-9+/=_-]{20,})",
    re.IGNORECASE,
)
TEMP_FILE_SUFFIXES = {".pyc", ".pyo", ".xcresult", ".zip"}
TEMP_FILE_NAMES = {"SHA256SUMS"}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


class RepositoryFileDiscoveryError(RuntimeError):
    """Git could not provide the repository file inventory."""


def _check(name: str, passed: bool, detail: str) -> Check:
    return Check(name, passed, detail)


def _all_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RepositoryFileDiscoveryError(f"git file inventory unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or "git ls-files returned a non-zero status"
        raise RepositoryFileDiscoveryError(f"git file inventory unavailable: {detail}")

    files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise RepositoryFileDiscoveryError(f"git returned an unsafe path: {relative}")
        files.append(ROOT / relative)
    return sorted(files)


def check_template_structure() -> Check:
    actual = {path.relative_to(TEMPLATE).as_posix() for path in TEMPLATE.rglob("*") if path.is_file()}
    missing = sorted(EXPECTED_TEMPLATE_FILES - actual)
    unexpected = sorted(actual - EXPECTED_TEMPLATE_FILES)
    return _check(
        "template_structure",
        not missing and not unexpected,
        f"{len(EXPECTED_TEMPLATE_FILES)} expected files; missing={missing}, unexpected={unexpected}",
    )


def check_template_gitignore() -> Check:
    path = TEMPLATE / ".gitignore"
    errors: list[str] = []
    try:
        if path.is_symlink() or not path.is_file():
            errors.append("missing or non-regular package/template/.gitignore")
        elif path.read_bytes() != TEMPLATE_GITIGNORE.encode("utf-8"):
            errors.append("package/template/.gitignore bytes are not the approved LF contract")
    except (OSError, UnicodeError) as exc:
        return _check("template_gitignore", False, f"cannot read .gitignore: {exc}")

    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="iskin-gitignore-probe-") as directory:
                probe = Path(directory)
                (probe / ".gitignore").write_bytes(TEMPLATE_GITIGNORE.encode("utf-8"))
                init = subprocess.run(
                    ["git", "init", "--quiet", str(probe)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if init.returncode != 0:
                    errors.append("isolated git probe could not initialize repository")
                else:
                    for relative in GITIGNORE_IGNORED_PATHS + GITIGNORE_VISIBLE_PATHS:
                        target = probe / relative.removeprefix("package/template/")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(b"probe")
                    for relative in GITIGNORE_IGNORED_PATHS:
                        probe_relative = relative.removeprefix("package/template/")
                        result = subprocess.run(
                            ["git", "check-ignore", "--no-index", "--quiet", "--", probe_relative],
                            cwd=probe,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False,
                        )
                        if result.returncode != 0:
                            errors.append(f"approved ignored path is visible: {relative}")
                    for relative in GITIGNORE_VISIBLE_PATHS:
                        probe_relative = relative.removeprefix("package/template/")
                        result = subprocess.run(
                            ["git", "check-ignore", "--no-index", "--quiet", "--", probe_relative],
                            cwd=probe,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False,
                        )
                        if result.returncode == 0:
                            errors.append(f"unapproved visible path is ignored: {relative}")
        except OSError as exc:
            errors.append(f"isolated git probe unavailable: {exc}")
    return _check(
        "template_gitignore",
        not errors,
        f"approved_patterns=7, ignored_paths={len(GITIGNORE_IGNORED_PATHS)}, visible_paths={len(GITIGNORE_VISIBLE_PATHS)}, errors={errors}",
    )


def check_template_symlinks() -> Check:
    symlinks = [path.relative_to(ROOT).as_posix() for path in TEMPLATE.rglob("*") if path.is_symlink()]
    return _check("template_symlinks", not symlinks, f"symlinks={symlinks}")


def check_json() -> Check:
    paths = [
        TEMPLATE / "process/fixtures/provenance-drift/template/manifest.json",
        TEMPLATE / "process/fixtures/provenance-drift/template/proof-record.json",
    ]
    errors: list[str] = []
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return _check("template_json", not errors, f"checked={len(paths)}, errors={errors}")


def check_product_memory_empty() -> Check:
    files = [
        TEMPLATE / "product-memory" / name
        for name in ("intent.md", "outcomes.md", "uncertainties.md", "approval-packages.md", "decisions.md", "evidence.md")
    ]
    filled: list[str] = []
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("<!--") and not stripped.endswith("-->"):
                filled.append(f"{path.relative_to(ROOT)}:{line_number}")
    return _check("product_memory_empty", not filled, f"filled_lines={filled}")


def check_template_contract() -> Check:
    agents = TEMPLATE / "AGENTS.md"
    recovery = TEMPLATE / "process" / "git-checkpoint-recovery.md"
    package = TEMPLATE / "product-memory" / "approval-packages.md"
    package_schema = TEMPLATE / "product-memory" / "approval-packages" / "README.md"
    errors: list[str] = []
    try:
        agents_text = agents.read_text(encoding="utf-8")
        recovery_text = recovery.read_text(encoding="utf-8")
        package_text = package.read_text(encoding="utf-8")
        package_schema_text = package_schema.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _check("template_contract", False, f"cannot read contract: {exc}")

    required_agents = (
        "iskin-control-pilot",
        "iskin-understand-state",
        "runtime/skills/",
        "process/git-checkpoint-recovery.md",
        "product-memory/",
        "product-memory/approval-packages.md",
        "telemetry/",
        "Git",
    )
    for marker in required_agents:
        if marker not in agents_text:
            errors.append(f"AGENTS missing={marker}")

    required_recovery = (
        "HEAD",
        "last stable checkpoint",
        "active outcome",
        "lifecycle",
        "evidence",
        "next action",
        "dirty",
        "interruption",
        "read-back",
        "side effects",
        "reset",
        "delete",
        "stage",
        "commit",
        "verified transition",
        "git diff --cached --check",
        "skill bundle revision",
        "textual skill change",
        "incompatible",
        "automatic update",
        "pre-approval checkpoint",
        "package_id",
        "package_paths",
        "product code",
        "product evidence",
        "checkpoint_sha",
        "package_displayed_in_previous_agent_turn: true",
    )
    recovery_text_lower = recovery_text.lower()
    for marker in required_recovery:
        if marker.lower() not in recovery_text_lower:
            errors.append(f"recovery missing={marker}")

    required_package = (
        "package_id",
        "package_paths",
        "intent и ценность",
        "граница MVP",
        "outcomes и наблюдаемое поведение",
        "обязательные gates и evidence",
        "существенные uncertainties, риски, зависимости и ограничения",
        "checkpoint_sha: не записывать в этот пакет",
    )
    for marker in required_package:
        if marker.lower() not in package_schema_text.lower():
            errors.append(f"approval_package missing={marker}")

    for path in TEMPLATE.rglob("*.md"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "hermes skills trust" in line and not re.search(
                r"не является|не выполняй|not an? (?:installation|setup) step|not required",
                line,
                re.IGNORECASE,
            ):
                errors.append(f"trust_installation={path.relative_to(ROOT)}:{line_number}")
    return _check("template_contract", not errors, f"errors={errors}")


def check_skills() -> Check:
    present = [
        path.relative_to(ROOT).as_posix()
        for path in (TEMPLATE / ".hermes" / "skills", TEMPLATE / ".agents" / "skills")
        if path.exists() or path.is_symlink()
    ]
    return _check(
        "project_skills",
        not present,
        f"project-local skill trees expected=[]; present={present}",
    )


def check_telemetry_empty() -> Check:
    path = TEMPLATE / "telemetry" / "run-log.md"
    try:
        filled = [
            f"{path.relative_to(ROOT)}:{line_number}"
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("<!--") and not line.rstrip().endswith("-->")
        ]
    except (OSError, UnicodeError) as exc:
        return _check("telemetry_empty", False, f"cannot read telemetry: {exc}")
    return _check("telemetry_empty", not filled, f"filled_lines={filled}")


def check_runtime_skills() -> Check:
    actual_dirs = {path.name for path in RUNTIME_SKILLS.iterdir() if path.is_dir()} if RUNTIME_SKILLS.is_dir() else set()
    actual_files = {
        path.relative_to(RUNTIME_SKILLS).as_posix()
        for path in RUNTIME_SKILLS.rglob("*")
        if path.is_file()
    } if RUNTIME_SKILLS.is_dir() else set()
    expected_files = {f"{name}/SKILL.md" for name in EXPECTED_RUNTIME_SKILLS}
    errors: list[str] = []
    if actual_dirs != EXPECTED_RUNTIME_SKILLS:
        errors.append(f"names expected={sorted(EXPECTED_RUNTIME_SKILLS)}, actual={sorted(actual_dirs)}")
    if actual_files != expected_files:
        errors.append(f"files expected={sorted(expected_files)}, actual={sorted(actual_files)}")

    symlinks = [path.relative_to(ROOT).as_posix() for path in RUNTIME_SKILLS.rglob("*") if path.is_symlink()] if RUNTIME_SKILLS.is_dir() else []
    if symlinks:
        errors.append(f"symlinks={symlinks}")

    frontmatter_names: list[str] = []
    for name in sorted(EXPECTED_RUNTIME_SKILLS):
        path = RUNTIME_SKILLS / name / "SKILL.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---") or text.count("---") < 2:
            errors.append(f"frontmatter={path.relative_to(ROOT)}")
            continue
        frontmatter_name = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
        if not frontmatter_name or frontmatter_name.group(1) != name:
            errors.append(f"name={path.relative_to(ROOT)}")
        else:
            frontmatter_names.append(frontmatter_name.group(1))
        version = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
        if not version or version.group(1) != RUNTIME_SKILL_VERSION:
            errors.append(f"version={path.relative_to(ROOT)}")
        description = re.search(r'^description:\s*["\']?(.*?)["\']?\s*$', text, re.MULTILINE)
        required_trigger = REQUIRED_RUNTIME_SKILL_TRIGGERS[name]
        if not description or not description.group(1).startswith("Use when ") or required_trigger not in description.group(1):
            errors.append(f"description={path.relative_to(ROOT)}")
        if "Completion criterion:" not in text:
            errors.append(f"completion_criterion={path.relative_to(ROOT)}")
        if "process/" not in text:
            errors.append(f"process_reference={path.relative_to(ROOT)}")
        if RUNTIME_PRODUCT_DATA.search(text):
            errors.append(f"product_data={path.relative_to(ROOT)}")
    if len(frontmatter_names) != len(set(frontmatter_names)):
        errors.append("duplicate frontmatter names")
    return _check("runtime_skill_bundle", not errors, f"skills={len(actual_dirs)}, errors={errors}")


def _resolve_reference(source: Path, target: str) -> Path | None:
    target = target.strip().strip("<>")
    if not target or "<" in target or ">" in target or any(char in target for char in "*?[") or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    if target.startswith((".hermes/", "process/", "product-memory/", "telemetry/")):
        historical_root = ROOT / "experiments" / "budget-ios" / "source"
        if TEMPLATE in source.parents:
            return (TEMPLATE / target.rstrip("/" )).resolve()
        if RUNTIME_SKILLS in source.parents:
            return (TEMPLATE / target.rstrip("/" )).resolve()
        if historical_root in source.parents:
            if target.startswith(".hermes/skills/"):
                return (historical_root / "hermes-skills" / target.removeprefix(".hermes/skills/").rstrip("/" )).resolve()
            if target == ".hermes/skills/":
                return (historical_root / "hermes-skills").resolve()
            return (historical_root / target.rstrip("/" )).resolve()
        return None
    if target.startswith(("docs/", "package/", "installer/", "tools/")):
        return (ROOT / target.rstrip("/")).resolve()
    return (source.parent / target.rstrip("/")).resolve()


def check_internal_links() -> Check:
    references: list[tuple[Path, str]] = []
    documents = [path for path in ROOT.rglob("*.md") if ".git" not in path.parts]
    for source in documents:
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)#]+)", text):
            references.append((source, target))
        for target in re.findall(r"(?<!`)`([^`]+)`", text):
            if target.startswith((".hermes/", "process/", "product-memory/", "telemetry/", "docs/", "package/", "installer/", "tools/")):
                references.append((source, target))
    broken: list[str] = []
    checked = 0
    for source, target in references:
        resolved = _resolve_reference(source, target)
        if resolved is None:
            continue
        checked += 1
        if not resolved.exists():
            reference = (source.relative_to(ROOT).as_posix(), target)
            if reference not in HISTORICAL_MISSING_LINKS:
                broken.append(f"{reference[0]} -> {target}")
    return _check("internal_links", not broken, f"checked={checked}, broken={broken}")


def check_forbidden_package_content() -> Check:
    hits: list[str] = []
    for path in TEMPLATE.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN_PACKAGE_CONTENT.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{line_number}")
    return _check("package_forbidden_content", not hits, f"hits={hits}")


def check_forbidden_artifacts() -> Check:
    findings: list[str] = []
    try:
        files = _all_files()
    except RepositoryFileDiscoveryError as exc:
        return _check("temporary_artifacts", False, str(exc))
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        release_installer_copy = path.name == "install-iskin.py" and relative != "installer/install-iskin.py"
        if path.name == ".DS_Store" or path.name.startswith("._") or path.name in TEMP_FILE_NAMES or release_installer_copy or path.suffix.lower() in TEMP_FILE_SUFFIXES:
            findings.append(path.relative_to(ROOT).as_posix())
        if "__pycache__" in path.parts:
            findings.append(path.relative_to(ROOT).as_posix())
    return _check("temporary_artifacts", not findings, f"findings={sorted(set(findings))}")


def check_unexpected_symlinks() -> Check:
    symlinks = [path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if ".git" not in path.parts and path.is_symlink()]
    return _check("repository_symlinks", not symlinks, f"symlinks={symlinks}")


def check_secret_files_and_markers() -> Check:
    findings: list[str] = []
    try:
        files = _all_files()
    except RepositoryFileDiscoveryError as exc:
        return _check("secret_private_data_heuristics", False, str(exc))
    for path in files:
        if SECRET_FILE.fullmatch(path.name) and path.name != ".env.example":
            findings.append(path.relative_to(ROOT).as_posix())
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if PRIVATE_KEY_MARKER.search(text) or ACCESS_KEY_MARKER.search(text) or SECRET_ASSIGNMENT.search(text):
            findings.append(path.relative_to(ROOT).as_posix())
    return _check("secret_private_data_heuristics", not findings, f"findings={findings}")


def run_checks() -> list[Check]:
    return [
        check_template_structure(),
        check_template_gitignore(),
        check_template_symlinks(),
        check_json(),
        check_product_memory_empty(),
        check_telemetry_empty(),
        check_template_contract(),
        check_skills(),
        check_runtime_skills(),
        check_internal_links(),
        check_forbidden_package_content(),
        check_forbidden_artifacts(),
        check_unexpected_symlinks(),
        check_secret_files_and_markers(),
    ]


def main() -> int:
    checks = run_checks()
    for result in checks:
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name}: {result.detail}")
    failed = [result for result in checks if not result.passed]
    print(f"SUMMARY: {'PASS' if not failed else 'FAIL'} checks={len(checks)} failed={len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
