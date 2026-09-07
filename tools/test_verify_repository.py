from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_repository as verifier


class VerifyRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_root = verifier.ROOT
        self.original_template = verifier.TEMPLATE
        self.original_runtime_skills = verifier.RUNTIME_SKILLS
        self.temp_dir = tempfile.TemporaryDirectory(prefix="hermes-verify-repository-")
        self.root = Path(self.temp_dir.name)
        self.template = self.root / "package" / "template"
        self.template.mkdir(parents=True)
        self.runtime_skills = self.root / "runtime" / "skills"
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        verifier.ROOT = self.root
        verifier.TEMPLATE = self.template
        verifier.RUNTIME_SKILLS = self.runtime_skills

    def tearDown(self) -> None:
        verifier.ROOT = self.original_root
        verifier.TEMPLATE = self.original_template
        verifier.RUNTIME_SKILLS = self.original_runtime_skills
        self.temp_dir.cleanup()

    def write_runtime_skill(self, name: str, *, version: str = "0.4.0-dev") -> None:
        trigger = verifier.REQUIRED_RUNTIME_SKILL_TRIGGERS[name]
        skill = self.runtime_skills / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            "---\n"
            f"name: {name}\n"
            f'description: "Use when {trigger}."\n'
            f"version: {version}\n"
            "---\n\n"
            f"# {name}\n\n"
            "Read `process/operating-model.md` before acting.\n\n"
            "Completion criterion: the requested bounded result is traceable to durable project sources.\n",
            encoding="utf-8",
        )

    def write_complete_runtime_bundle(self) -> None:
        for name in verifier.EXPECTED_RUNTIME_SKILLS:
            self.write_runtime_skill(name)

    def test_runtime_skill_bundle_requires_exact_names_and_version(self) -> None:
        self.write_complete_runtime_bundle()

        valid = verifier.check_runtime_skills()

        self.assertTrue(valid.passed, valid.detail)
        self.write_runtime_skill("iskin-understand-state", version="0.4.1")
        invalid = verifier.check_runtime_skills()
        self.assertFalse(invalid.passed)
        self.assertIn("version=", invalid.detail)

    def test_runtime_skill_bundle_rejects_malformed_or_unexpected_content(self) -> None:
        self.write_complete_runtime_bundle()
        target = self.runtime_skills / "iskin-prove-result" / "SKILL.md"
        target.write_text(
            target.read_text(encoding="utf-8")
            .replace("Use when collecting canonical evidence for an approved IskIn outcome.", "Use when proving things.")
            .replace("Completion criterion:", "Completion:")
            + "\nA run 7 result is not a valid bundle input.\n",
            encoding="utf-8",
        )
        (self.runtime_skills / "iskin-prove-result" / "notes.md").write_text("unexpected", encoding="utf-8")
        (self.runtime_skills / "iskin-prove-result" / "linked.md").symlink_to(target)

        result = verifier.check_runtime_skills()

        self.assertFalse(result.passed)
        self.assertIn("description=", result.detail)
        self.assertIn("completion_criterion=", result.detail)
        self.assertIn("product_data=", result.detail)
        self.assertIn("files expected=", result.detail)
        self.assertIn("symlinks=", result.detail)

    def test_v04_template_contract_requires_global_runtime_and_recovery(self) -> None:
        (self.template / "AGENTS.md").write_text(
            "Start with global `iskin-control-pilot`; recovery uses `iskin-understand-state`. "
            "Read `runtime/skills/`, `product-memory/`, `product-memory/approval-packages.md`, and `telemetry/`; "
            "use `process/git-checkpoint-recovery.md`; Git is mandatory.\n",
            encoding="utf-8",
        )
        recovery = self.template / "process" / "git-checkpoint-recovery.md"
        recovery.parent.mkdir(parents=True)
        recovery.write_text(
            "# Git checkpoint and recovery\n\n"
            "## Clean tree\nHEAD is the last stable checkpoint for the active outcome, lifecycle, evidence, and next action.\n\n"
            "## Dirty tree\ndirty means an interruption is possible; investigate changes, read-back side effects, and never blindly reset, delete, stage, or commit.\n\n"
            "## Pre-approval checkpoint\nA pre-approval checkpoint has package_id and package_paths, occurs before display, contains no product code or product evidence, and package_displayed_in_previous_agent_turn: true is recorded only later.\n\n"
            "## Checkpoint commit\nAfter a verified transition and read-back, check git diff --cached --check. checkpoint_sha is not written in the package.\n\n"
            "## Skill bundle\nRecord skill bundle revision; a textual skill change alone does not invalidate evidence. Stop on incompatible contracts and do not use automatic update.\n",
            encoding="utf-8",
        )
        package = self.template / "product-memory" / "approval-packages.md"
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(
            "registry only\n",
            encoding="utf-8",
        )
        package_schema = self.template / "product-memory" / "approval-packages" / "README.md"
        package_schema.parent.mkdir(parents=True, exist_ok=True)
        package_schema.write_text(
            "package_id package_paths intent и ценность граница MVP outcomes и наблюдаемое поведение "
            "обязательные gates и evidence существенные uncertainties, риски, зависимости и ограничения "
            "checkpoint_sha: не записывать в этот пакет\n",
            encoding="utf-8",
        )
        policy_dir = self.template / ".iskin"
        policy_dir.mkdir(parents=True, exist_ok=True)
        (policy_dir / "policy_gate.py").write_text(
            (self.original_template / ".iskin" / "policy_gate.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.assertFalse((self.original_template / ".iskin" / "policy_state.json").exists())

        valid = verifier.check_template_contract()

        self.assertTrue(valid.passed, valid.detail)
        (self.template / "AGENTS.md").write_text("run `hermes skills trust`\n", encoding="utf-8")
        invalid = verifier.check_template_contract()
        self.assertFalse(invalid.passed)
        self.assertIn("trust", invalid.detail)

    def test_v04_template_rejects_project_local_skill_trees(self) -> None:
        result = verifier.check_skills()
        self.assertTrue(result.passed, result.detail)
        local = self.template / ".agents" / "skills"
        local.mkdir(parents=True)
        (local / "unexpected.md").write_text("local", encoding="utf-8")
        result = verifier.check_skills()
        self.assertFalse(result.passed)
        self.assertIn("project-local skill trees", result.detail)

    def test_v04_template_gitignore_is_exact_and_enforced_by_git(self) -> None:
        path = self.template / ".gitignore"
        path.write_bytes(verifier.TEMPLATE_GITIGNORE.encode("utf-8"))

        for relative in verifier.GITIGNORE_IGNORED_PATHS + verifier.GITIGNORE_VISIBLE_PATHS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")

        result = verifier.check_template_gitignore()

        self.assertTrue(result.passed, result.detail)
        for relative in verifier.GITIGNORE_IGNORED_PATHS:
            checked = subprocess.run(
                ["git", "check-ignore", "--no-index", "--quiet", "--", relative],
                cwd=self.root,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, relative)
        for relative in verifier.GITIGNORE_VISIBLE_PATHS:
            checked = subprocess.run(
                ["git", "check-ignore", "--no-index", "--quiet", "--", relative],
                cwd=self.root,
                check=False,
            )
            self.assertNotEqual(checked.returncode, 0, relative)

    def test_v04_template_gitignore_rejects_extra_rules_and_noncanonical_format(self) -> None:
        path = self.template / ".gitignore"
        path.write_bytes((verifier.TEMPLATE_GITIGNORE + "node_modules/\n").encode("utf-8"))

        result = verifier.check_template_gitignore()

        self.assertFalse(result.passed)
        self.assertIn("approved LF contract", result.detail)

    def test_historical_v03_missing_links_are_narrowly_allowlisted(self) -> None:
        source = self.root / "docs" / "decisions" / "2026-09-06-v0.3-proved-accepted-boundary.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "[`old change`](package/template/.hermes/skills/change-product/SKILL.md)\n"
            "[`old proof`](package/template/.hermes/skills/prove-result/SKILL.md)\n",
            encoding="utf-8",
        )
        valid = verifier.check_internal_links()
        self.assertTrue(valid.passed, valid.detail)
        source.write_text(source.read_text(encoding="utf-8") + "[`bad`](package/template/missing.md)\n", encoding="utf-8")
        invalid = verifier.check_internal_links()
        self.assertFalse(invalid.passed)
        self.assertIn("package/template/missing.md", invalid.detail)

    def test_ignored_ds_store_outside_template_is_not_a_temporary_artifact(self) -> None:
        (self.root / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
        (self.root / ".DS_Store").write_bytes(b"ignored")

        result = verifier.check_forbidden_artifacts()

        self.assertTrue(result.passed, result.detail)

    def test_nonignored_temporary_artifact_is_detected(self) -> None:
        artifact = self.root / "build.zip"
        artifact.write_bytes(b"temporary")

        result = verifier.check_forbidden_artifacts()

        self.assertFalse(result.passed)
        self.assertIn("build.zip", result.detail)

    def test_staged_temporary_artifact_is_detected(self) -> None:
        artifact = self.root / "SHA256SUMS"
        artifact.write_bytes(b"temporary")
        subprocess.run(["git", "add", str(artifact)], cwd=self.root, check=True)

        result = verifier.check_forbidden_artifacts()

        self.assertFalse(result.passed)
        self.assertIn("SHA256SUMS", result.detail)

    def test_ignored_ds_store_inside_template_fails_exact_structure_check(self) -> None:
        (self.root / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
        unexpected = self.template / ".DS_Store"
        unexpected.write_bytes(b"ignored")

        result = verifier.check_template_structure()

        self.assertFalse(result.passed)
        self.assertIn(".DS_Store", result.detail)

    def test_git_inventory_failure_is_reported_as_fail(self) -> None:
        not_a_repository = self.root / "not-a-repository"
        not_a_repository.mkdir()
        with patch.object(verifier, "ROOT", not_a_repository), patch.dict(
            os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root)}
        ):
            result = verifier.check_forbidden_artifacts()

        self.assertFalse(result.passed)
        self.assertIn("git file inventory unavailable", result.detail)

    def test_git_inventory_command_error_is_reported_as_fail(self) -> None:
        with patch.object(verifier.subprocess, "run", side_effect=OSError("git unavailable")):
            result = verifier.check_forbidden_artifacts()

        self.assertFalse(result.passed)
        self.assertIn("git file inventory unavailable", result.detail)


if __name__ == "__main__":
    unittest.main()
