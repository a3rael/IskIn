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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "package" / "template"

EXPECTED_TEMPLATE_FILES = {
    "AGENTS.md",
    "README.md",
    "process/README.md",
    "process/operating-model.md",
    "process/autonomy-policy.md",
    "process/action-selection.md",
    "process/quality-gates.md",
    "process/evidence-provenance.md",
    "process/fixtures/provenance-drift/README.md",
    "process/fixtures/provenance-drift/template/manifest.json",
    "process/fixtures/provenance-drift/template/proof-record.json",
    "process/fixtures/provenance-drift/template/report.md",
    "product-memory/README.md",
    "product-memory/intent.md",
    "product-memory/outcomes.md",
    "product-memory/uncertainties.md",
    "product-memory/decisions.md",
    "product-memory/evidence.md",
    "telemetry/README.md",
    "telemetry/run-log.md",
    "telemetry/metrics.md",
    ".hermes/skills/understand-state/SKILL.md",
    ".hermes/skills/choose-next-action/SKILL.md",
    ".hermes/skills/change-product/SKILL.md",
    ".hermes/skills/prove-result/SKILL.md",
    ".hermes/skills/challenge-result/SKILL.md",
    ".hermes/skills/control-pilot/SKILL.md",
}
EXPECTED_SKILLS = {
    "understand-state",
    "choose-next-action",
    "change-product",
    "prove-result",
    "challenge-result",
    "control-pilot",
}
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
        f"27 expected files; missing={missing}, unexpected={unexpected}",
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
        for name in ("intent.md", "outcomes.md", "uncertainties.md", "decisions.md", "evidence.md")
    ]
    filled: list[str] = []
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("<!--") and not stripped.endswith("-->"):
                filled.append(f"{path.relative_to(ROOT)}:{line_number}")
    return _check("product_memory_empty", not filled, f"filled_lines={filled}")


def check_skills() -> Check:
    skill_dirs = [path for path in (TEMPLATE / ".hermes/skills").iterdir() if path.is_dir()]
    actual_names = {path.name for path in skill_dirs}
    errors: list[str] = []
    if actual_names != EXPECTED_SKILLS:
        errors.append(f"names expected={sorted(EXPECTED_SKILLS)}, actual={sorted(actual_names)}")
    frontmatter_names: list[str] = []
    for directory in skill_dirs:
        path = directory / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing={path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---") or text.count("---") < 2:
            errors.append(f"frontmatter={path.relative_to(ROOT)}")
        match = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        if not match:
            errors.append(f"name={path.relative_to(ROOT)}")
        else:
            frontmatter_names.append(match.group(1))
        if "Completion criterion:" not in text:
            errors.append(f"completion_criterion={path.relative_to(ROOT)}")
    if len(frontmatter_names) != len(set(frontmatter_names)):
        errors.append("duplicate frontmatter names")
    return _check("project_skills", not errors, f"skills={len(skill_dirs)}, errors={errors}")


def _resolve_reference(source: Path, target: str) -> Path | None:
    target = target.strip().strip("<>")
    if not target or "<" in target or ">" in target or any(char in target for char in "*?[") or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    if target.startswith((".hermes/", "process/", "product-memory/", "telemetry/")):
        historical_root = ROOT / "experiments" / "budget-ios" / "source"
        if TEMPLATE in source.parents:
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
            broken.append(f"{source.relative_to(ROOT)} -> {target}")
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
        check_template_symlinks(),
        check_json(),
        check_product_memory_empty(),
        check_skills(),
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
