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
        self.temp_dir = tempfile.TemporaryDirectory(prefix="hermes-verify-repository-")
        self.root = Path(self.temp_dir.name)
        self.template = self.root / "package" / "template"
        self.template.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        verifier.ROOT = self.root
        verifier.TEMPLATE = self.template

    def tearDown(self) -> None:
        verifier.ROOT = self.original_root
        verifier.TEMPLATE = self.original_template
        self.temp_dir.cleanup()

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
