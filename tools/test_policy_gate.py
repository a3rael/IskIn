from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "package" / "template" / ".iskin" / "policy_gate.py"


class PolicyGateExecutableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-policy-gate-")
        self.repo = Path(self.tempdir.name) / "project"
        self.repo.mkdir()
        self._git("init", "--quiet")
        self._git("config", "user.name", "IskIn test")
        self._git("config", "user.email", "iskin-test@example.invalid")
        self._write(".iskin/policy_gate.py", GATE.read_bytes())
        self._write_state(self._state())
        self._commit("baseline")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def _write(self, relative: str, content: str | bytes) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def _state(
        self,
        *,
        package: dict[str, object] | None = None,
        lifecycle: str = "discovery",
        approval_state: str = "none",
        approval_event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "lifecycle": lifecycle,
            "approval_state": approval_state,
            "package": package,
            "approval_event": approval_event,
            "scope": {
                "product_code_paths": ["src/**"],
                "product_evidence_paths": ["evidence/**"],
            },
        }

    def _write_state(self, state: dict[str, object]) -> None:
        self._write(".iskin/policy_state.json", json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    def _package_state(self, package_id: str = "AP-20260907-policy-gate") -> dict[str, object]:
        return {
            "package_id": package_id,
            "package_paths": [
                "product-memory/approval-packages.md",
                f"product-memory/approval-packages/{package_id}.md",
                "product-memory/intent.md",
                "product-memory/outcomes.md",
                "product-memory/uncertainties.md",
            ],
        }

    def _write_package(self, package_id: str = "AP-20260907-policy-gate") -> None:
        package = self._package_state(package_id)
        reference = f"product-memory/approval-packages/{package_id}.md"
        self._write("product-memory/approval-packages.md", f"# Registry\n- {reference}\n")
        self._write(
            reference,
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
        )
        self._write("product-memory/intent.md", "# Intent\n")
        self._write("product-memory/outcomes.md", "# Outcomes\n")
        self._write("product-memory/uncertainties.md", "# Uncertainties\n")
        self._write_state(self._state(package=package, lifecycle="awaiting_approval", approval_state="prepared"))

    def _commit(self, message: str) -> str:
        self._git("add", "--", ".")
        self._git("commit", "--quiet", "-m", message)
        return self._git("rev-parse", "HEAD")

    def _checkpoint(self) -> str:
        self._write_package()
        return self._commit("iskin: pre-approval checkpoint: AP-20260907-policy-gate")

    def _approve(self, checkpoint: str, *, checkpoint_override: str | None = None) -> str:
        package = self._package_state()
        event = {
            "package_id": package["package_id"],
            "checkpoint_sha": checkpoint_override or checkpoint,
            "package_displayed_in_previous_agent_turn": True,
            "approval_question": "Утверждаете этот пакет и разрешаете перейти к реализации?",
            "human_response": "Да, утверждаю пакет и разрешаю реализацию.",
            "actor": "human",
            "implementation_authorized": True,
        }
        self._write_state(self._state(package=package, lifecycle="implementation_allowed", approval_state="approved", approval_event=event))
        return self._commit("approval event")

    def _run(self, *args: str, cwd: Path | None = None) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(GATE), "--repo", str(cwd or self.repo), *args],
            cwd=cwd or self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_empty_project_allows_discovery(self) -> None:
        code, payload = self._run("--action", "discover")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")
        self.assertEqual(payload["approval_state"], "none")

    def test_dirty_package_waits_for_checkpoint_but_denies_implementation(self) -> None:
        self._write_package()
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 10)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertIn("pre_approval_checkpoint", payload["allowed_actions"])

    def test_checkpoint_without_approval_awaits_human(self) -> None:
        checkpoint = self._checkpoint()
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 10)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertEqual(payload["checkpoint_sha"], checkpoint)
        self.assertIn("APPROVAL_EVENT_ABSENT", payload["reason_codes"])

    def test_valid_approval_allows_implementation(self) -> None:
        checkpoint = self._checkpoint()
        self._approve(checkpoint)
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")
        self.assertEqual(payload["checkpoint_sha"], checkpoint)

    def test_product_code_before_checkpoint_blocks(self) -> None:
        self._write("src/app.py", "print('old')\n")
        self._commit("product code before package")
        self._checkpoint()
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL", payload["reason_codes"])

    def test_product_evidence_before_checkpoint_blocks(self) -> None:
        self._write("evidence/run.json", "{}\n")
        self._commit("evidence before package")
        self._checkpoint()
        code, payload = self._run("--action", "prove_result")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")

    def test_checkpoint_containing_product_code_blocks(self) -> None:
        self._write("src/app.py", "print('too early')\n")
        self._checkpoint()
        code, payload = self._run("--action", "checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("CHECKPOINT_CONTAINS_PRODUCT_OR_EVIDENCE", payload["reason_codes"])

    def test_checkpoint_containing_product_evidence_blocks(self) -> None:
        self._write("evidence/run.json", "{}\n")
        self._checkpoint()
        code, payload = self._run("--action", "checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("CHECKPOINT_CONTAINS_PRODUCT_OR_EVIDENCE", payload["reason_codes"])

    def test_package_drift_after_approval_invalidates_approval(self) -> None:
        checkpoint = self._checkpoint()
        self._approve(checkpoint)
        self._write(
            "product-memory/approval-packages/AP-20260907-policy-gate.md",
            "\n".join(
                [
                    "package_id: AP-20260907-policy-gate",
                    "package_status: prepared",
                    "changed: after approval",
                    "### intent и ценность",
                    "### граница MVP",
                    "### outcomes и наблюдаемое поведение",
                    "### обязательные gates и evidence",
                    "### существенные uncertainties, риски, зависимости и ограничения",
                    "",
                ]
            ),
        )
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertIn("PACKAGE_CHANGED_AFTER_CHECKPOINT", payload["reason_codes"])

    def test_wrong_approval_checkpoint_is_denied(self) -> None:
        checkpoint = self._checkpoint()
        wrong = "0" * 40
        self._approve(checkpoint, checkpoint_override=wrong)
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertIn("APPROVAL_CHECKPOINT_MISMATCH", payload["reason_codes"])

    def test_unknown_machine_state_fails_closed(self) -> None:
        self._write_state({"schema_version": 999})
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("MACHINE_STATE_UNSUPPORTED", payload["reason_codes"])

    def test_missing_git_context_fails_closed(self) -> None:
        outside = Path(self.tempdir.name) / "not-a-repository"
        outside.mkdir()
        code, payload = self._run("--action", "change_product", cwd=outside)
        self.assertEqual(code, 20)
        self.assertIn("GIT_CONTEXT_UNAVAILABLE", payload["reason_codes"])

    def test_read_only_recovery_fails_closed_when_machine_state_is_missing(self) -> None:
        (self.repo / ".iskin/policy_state.json").unlink()
        code, payload = self._run("--action", "read_only_recovery")
        self.assertEqual(code, 20)
        self.assertIn("REQUIRED_STATE_MISSING", payload["reason_codes"])

    def test_valid_approval_allows_product_change_after_approval(self) -> None:
        checkpoint = self._checkpoint()
        self._approve(checkpoint)
        self._write("src/app.py", "print('after approval')\n")
        code, payload = self._run("--action", "change_product")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")

    def test_process_blocked_denies_implementation_proof_and_checkpoint(self) -> None:
        self._write("src/app.py", "print('too early')\n")
        self._checkpoint()
        for action in ("change_product", "prove_result", "checkpoint"):
            code, payload = self._run("--action", action)
            self.assertEqual(code, 20, action)
            self.assertEqual(payload["status"], "PROCESS_BLOCKED", action)

    def test_gate_does_not_change_files_index_or_head(self) -> None:
        checkpoint = self._checkpoint()
        self._approve(checkpoint)
        self._write("src/app.py", "print('uncommitted')\n")
        before_status = self._git("status", "--porcelain=v1")
        before_head = self._git("rev-parse", "HEAD")
        before_index = (self.repo / ".git" / "index").read_bytes()
        code, _ = self._run("--action", "change_product")
        self.assertEqual(code, 0)
        self.assertEqual(self._git("status", "--porcelain=v1"), before_status)
        self.assertEqual(self._git("rev-parse", "HEAD"), before_head)
        self.assertEqual((self.repo / ".git" / "index").read_bytes(), before_index)


if __name__ == "__main__":
    unittest.main()
