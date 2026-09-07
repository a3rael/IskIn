#!/usr/bin/env python3
"""Full local release/install/bootstrap flow for the v0.4 gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "installer" / "build_release.py"
INSTALLER = ROOT / "installer" / "install-iskin.py"


class BootstrapInstallFlowTests(unittest.TestCase):
    def run_command(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args), cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )

    def gate(self, target: Path, action: str) -> tuple[int, dict[str, object]]:
        result = self.run_command(
            sys.executable,
            str(target / ".iskin" / "policy_gate.py"),
            "--repo",
            str(target),
            "--action",
            action,
            cwd=target,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_release_install_bootstrap_and_clean_discovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="iskin-bootstrap-flow-") as directory:
            root = Path(directory)
            release = root / "release"
            target = root / "target"
            build = self.run_command(
                sys.executable,
                str(BUILD),
                "--release-version",
                "0.4.0",
                "--output-dir",
                str(release),
                cwd=ROOT,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            archive = release / "iskin-v0.4.0.zip"
            archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            install = self.run_command(
                sys.executable,
                str(INSTALLER),
                "--archive",
                str(archive),
                "--release-version",
                "0.4.0",
                "--expected-sha256",
                archive_sha,
                "--target-path",
                str(target),
                "--init-git",
                cwd=ROOT,
            )
            self.assertEqual(install.returncode, 0, install.stderr)

            code, payload = self.gate(target, "status")
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")
            self.assertIn("INITIAL_BASELINE_UNCOMMITTED", payload["reason_codes"])
            self.assertEqual(payload["allowed_actions"], ["read_only_recovery", "stage_bootstrap_baseline"])

            code, stage_payload = self.gate(target, "stage_bootstrap_baseline")
            self.assertEqual(code, 0, stage_payload)
            paths = stage_payload["allowed_paths"]
            self.assertEqual(paths, sorted(paths))

            code, payload = self.gate(target, "bootstrap_checkpoint")
            self.assertEqual(code, 10, payload)
            self.assertNotIn("bootstrap_checkpoint", payload["allowed_actions"])

            staged = self.run_command("git", "add", "--", *paths, cwd=target)
            self.assertEqual(staged.returncode, 0, staged.stderr)
            code, payload = self.gate(target, "bootstrap_checkpoint")
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")
            self.assertIn("bootstrap_checkpoint", payload["allowed_actions"])

            commit = self.run_command(
                "git",
                "-c",
                "user.name=IskIn bootstrap test",
                "-c",
                "user.email=iskin-bootstrap@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "chore: bootstrap iskin project baseline",
                cwd=target,
            )
            self.assertEqual(commit.returncode, 0, commit.stderr)
            clean = self.run_command("git", "status", "--porcelain=v1", cwd=target)
            self.assertEqual(clean.stdout, "")
            remote = self.run_command("git", "remote", cwd=target)
            self.assertEqual(remote.stdout, "")
            code, payload = self.gate(target, "status")
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")
            self.assertIn("NO_APPROVAL_PACKAGE", payload["reason_codes"])
            code, payload = self.gate(target, "change_product")
            self.assertEqual(code, 10, payload)
            self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")

            package_id = "AP-20260907-bootstrap-history-boundary"
            package_path = target / "product-memory" / "approval-packages" / f"{package_id}.md"
            (target / "product-memory" / "approval-packages.md").write_text(
                f"# Registry\n- product-memory/approval-packages/{package_id}.md\n",
                encoding="utf-8",
            )
            package_path.write_text(
                "\n".join(
                    [
                        f"package_id: {package_id}",
                        "package_status: prepared",
                        "### intent и ценность",
                        "### граница MVP",
                        "### outcomes и наблюдаемое поведение",
                        "### обязательные gates и evidence",
                        "### существенные uncertainties, риски, зависимости и ограничения",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            for name in ("intent.md", "outcomes.md", "uncertainties.md"):
                (target / "product-memory" / name).write_text(f"# {name}\nPrepared\n", encoding="utf-8")
            package_commit = self.run_command(
                "git",
                "add",
                "--",
                "product-memory/approval-packages.md",
                f"product-memory/approval-packages/{package_id}.md",
                "product-memory/intent.md",
                "product-memory/outcomes.md",
                "product-memory/uncertainties.md",
                cwd=target,
            )
            self.assertEqual(package_commit.returncode, 0, package_commit.stderr)
            package_commit = self.run_command(
                "git",
                "-c",
                "user.name=IskIn bootstrap test",
                "-c",
                "user.email=iskin-bootstrap@example.invalid",
                "commit",
                "--quiet",
                "-m",
                f"iskin: pre-approval checkpoint: {package_id}",
                cwd=target,
            )
            self.assertEqual(package_commit.returncode, 0, package_commit.stderr)
            code, payload = self.gate(target, "change_product")
            self.assertEqual(code, 10, payload)
            self.assertEqual(payload["status"], "AWAITING_APPROVAL")
            self.assertIn("PRE_APPROVAL_CHECKPOINT_PRESENT", payload["reason_codes"])
            self.assertIn("APPROVAL_EVENT_ABSENT", payload["reason_codes"])


if __name__ == "__main__":
    unittest.main()
