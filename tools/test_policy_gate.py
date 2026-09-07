from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "package" / "template" / ".iskin" / "policy_gate.py"
PACKAGE_ID = "AP-20260907-policy-gate"
EVENT_ID = "AE-20260907-policy-gate"
REGISTRY = "product-memory/approval-packages.md"
PACKAGE_PATH = f"product-memory/approval-packages/{PACKAGE_ID}.md"
EVENT_PATH = f"product-memory/approval-events/{EVENT_ID}.json"
DECISIONS = "product-memory/decisions.md"
PACKAGE_PATHS = (
    REGISTRY,
    PACKAGE_PATH,
    "product-memory/intent.md",
    "product-memory/outcomes.md",
    "product-memory/uncertainties.md",
)


class PolicyGateExecutableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-policy-gate-")
        self.repo = Path(self.tempdir.name) / "project"
        self.repo.mkdir()
        self._git("init", "--quiet")
        self._git("config", "user.name", "IskIn test")
        self._git("config", "user.email", "iskin-test@example.invalid")
        self._write(".iskin/policy_gate.py", GATE.read_bytes())
        self._write(REGISTRY, "# Registry\n")
        self._write(DECISIONS, "# Решения\n")
        self._write("product-memory/intent.md", "# Intent\n")
        self._write("product-memory/outcomes.md", "# Outcomes\n")
        self._write("product-memory/uncertainties.md", "# Uncertainties\n")
        self._commit("baseline")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def _write(self, relative: str, content: str | bytes) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def _commit(self, message: str) -> str:
        self._git("add", "--", ".")
        self._git("commit", "--quiet", "-m", message)
        return self._git("rev-parse", "HEAD")

    def _write_package(self) -> None:
        self._write(REGISTRY, f"# Registry\n- {PACKAGE_PATH}\n")
        self._write(
            PACKAGE_PATH,
            "\n".join(
                [
                    f"package_id: {PACKAGE_ID}",
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
        self._write("product-memory/intent.md", "# Intent\nPrepared\n")
        self._write("product-memory/outcomes.md", "# Outcomes\nPrepared\n")
        self._write("product-memory/uncertainties.md", "# Uncertainties\nPrepared\n")

    def _checkpoint(self) -> str:
        self._write_package()
        return self._commit(f"iskin: pre-approval checkpoint: {PACKAGE_ID}")

    def _event(self, *, checkpoint: str | None = None, event_id: str = EVENT_ID) -> dict[str, object]:
        return {
            "schema_version": 1,
            "event_type": "approval",
            "event_id": event_id,
            "package_id": PACKAGE_ID,
            "package_paths": list(PACKAGE_PATHS),
            "checkpoint_sha": checkpoint or self._git("rev-parse", "HEAD"),
            "package_displayed_in_previous_agent_turn": True,
            "approval_question": "Утверждаете этот пакет и разрешаете перейти к реализации?",
            "human_response": "Да, утверждаю пакет и разрешаю реализацию.",
            "actor": "human",
            "implementation_authorized": True,
            "human_decision_path": DECISIONS,
        }

    def _write_event(self, checkpoint: str) -> None:
        self._write(EVENT_PATH, json.dumps(self._event(checkpoint=checkpoint), ensure_ascii=False, indent=2) + "\n")

    def _write_pending_approval(self, checkpoint: str, *, decision_checkpoint: str | None = None) -> None:
        event = self._event(checkpoint=checkpoint)
        self._write(EVENT_PATH, json.dumps(event, ensure_ascii=False, indent=2) + "\n")
        decision_sha = decision_checkpoint or checkpoint
        self._write(
            DECISIONS,
            "\n".join(
                [
                    "# Решения",
                    "",
                    f"approval_event_id: {EVENT_ID}",
                    f"approval_event_path: {EVENT_PATH}",
                    f"package_id: {PACKAGE_ID}",
                    f"checkpoint_sha: {decision_sha}",
                    "",
                ]
            ),
        )

    def _stage_approval(self) -> None:
        self._git("add", "--", EVENT_PATH, DECISIONS)

    def _run_gate(self, *args: str, repo: Path | None = None) -> tuple[int, dict[str, object]]:
        target = repo or self.repo
        result = subprocess.run(
            [sys.executable, str(GATE), "--repo", str(target), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def _approve(self, checkpoint: str) -> str:
        self._write_pending_approval(checkpoint)
        self._stage_approval()
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        return self._commit("iskin: approval checkpoint")

    def test_empty_project_allows_discovery(self) -> None:
        code, payload = self._run_gate("--action", "discover")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")
        self.assertEqual(payload["approval_state"], "none")

    def test_package_only_in_working_tree_waits_for_checkpoint(self) -> None:
        self._write_package()
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 10)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertIn("PACKAGE_CHECKPOINT_MISSING", payload["reason_codes"])

    def test_checkpoint_without_approval_awaits_human(self) -> None:
        checkpoint = self._checkpoint()
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 10)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertEqual(payload["checkpoint_sha"], checkpoint)
        self.assertIn("APPROVAL_EVENT_ABSENT", payload["reason_codes"])

    def test_valid_staged_approval_scope_allows_only_approval_checkpoint(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        self._stage_approval()
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertIn("approval_checkpoint", payload["allowed_actions"])
        implementation_code, implementation = self._run_gate("--action", "change_product")
        self.assertEqual(implementation_code, 10)
        self.assertNotEqual(implementation["status"], "IMPLEMENTATION_ALLOWED")

    def test_approval_event_only_in_worktree_is_not_implementation_authority(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 10)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertIn("APPROVAL_SCOPE_EXTRANEOUS", payload["reason_codes"])

    def test_after_approval_checkpoint_implementation_is_allowed(self) -> None:
        checkpoint = self._checkpoint()
        approval_commit = self._approve(checkpoint)
        self.assertNotEqual(approval_commit, checkpoint)
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")
        self.assertEqual(payload["approval_state"], "approved")

    def test_approval_scope_with_product_code_is_denied(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        self._write("src/app.py", "print('too early')\n")
        self._stage_approval()
        self._git("add", "--", "src/app.py")
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("APPROVAL_SCOPE_EXTRANEOUS", payload["reason_codes"])

    def test_approval_scope_with_product_evidence_is_denied(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        self._write("evidence/run.json", "{}\n")
        self._stage_approval()
        self._git("add", "--", "evidence/run.json")
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("APPROVAL_SCOPE_EXTRANEOUS", payload["reason_codes"])

    def test_preapproval_product_code_blocks(self) -> None:
        self._write("src/app.py", "print('old')\n")
        self._commit("product code before package")
        self._checkpoint()
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT", payload["reason_codes"])

    def test_preapproval_checkpoint_containing_product_code_blocks(self) -> None:
        self._write_package()
        self._write("src/app.py", "print('too early')\n")
        self._commit(f"iskin: pre-approval checkpoint: {PACKAGE_ID}")
        code, payload = self._run_gate("--action", "checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("CHECKPOINT_CONTAINS_PRODUCT_OR_EVIDENCE", payload["reason_codes"])

    def test_package_drift_after_approval_invalidates_approval(self) -> None:
        checkpoint = self._checkpoint()
        self._approve(checkpoint)
        self._write(PACKAGE_PATH, self.repo.joinpath(PACKAGE_PATH).read_text(encoding="utf-8") + "changed after approval\n")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertIn("PACKAGE_CHANGED_AFTER_CHECKPOINT", payload["reason_codes"])

    def test_package_drift_between_checkpoint_and_approval_is_denied(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        package_file = self.repo / PACKAGE_PATH
        package_file.write_text(package_file.read_text(encoding="utf-8") + "post-checkpoint drift\n", encoding="utf-8")
        self._stage_approval()
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("PACKAGE_CHANGED_AFTER_CHECKPOINT", payload["reason_codes"])

    def test_machine_and_human_records_must_match(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint, decision_checkpoint="0" * 40)
        self._stage_approval()
        code, payload = self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("HUMAN_DECISION_REFERENCE_MISMATCH", payload["reason_codes"])

    def test_committed_orphaned_machine_event_is_blocked(self) -> None:
        checkpoint = self._checkpoint()
        self._write_event(checkpoint)
        self._git("add", "--", EVENT_PATH)
        self._commit("orphan approval event")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("HUMAN_DECISION_REFERENCE_MISSING", payload["reason_codes"])

    def test_unsupported_event_schema_is_blocked(self) -> None:
        checkpoint = self._checkpoint()
        self._write_event(checkpoint)
        event = json.loads((self.repo / EVENT_PATH).read_text(encoding="utf-8"))
        event["schema_version"] = 99
        (self.repo / EVENT_PATH).write_text(json.dumps(event) + "\n", encoding="utf-8")
        self._git("add", "--", EVENT_PATH)
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("UNSUPPORTED_PROJECT_STATE", payload["reason_codes"])

    def test_human_record_without_machine_event_is_blocked(self) -> None:
        checkpoint = self._checkpoint()
        self._write(
            DECISIONS,
            f"# Решения\n\napproval_event_id: {EVENT_ID}\napproval_event_path: {EVENT_PATH}\npackage_id: {PACKAGE_ID}\ncheckpoint_sha: {checkpoint}\n",
        )
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertIn("ORPHANED_HUMAN_DECISION", payload["reason_codes"])

    def test_unsupported_project_state_is_explicit(self) -> None:
        old = Path(self.tempdir.name) / "old-project"
        old.mkdir()
        subprocess.run(["git", "init", "--quiet", str(old)], check=True)
        result_code, payload = self._run_gate("--action", "change_product", repo=old)
        self.assertEqual(result_code, 20)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("UNSUPPORTED_PROJECT_STATE", payload["reason_codes"])

    def test_legacy_policy_state_is_unsupported(self) -> None:
        self._write(".iskin/policy_state.json", "{\"schema_version\": 1}\n")
        self._commit("legacy state")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20)
        self.assertIn("UNSUPPORTED_PROJECT_STATE", payload["reason_codes"])

    def test_recovery_reports_blocked_state_but_critical_action_fails(self) -> None:
        self._write("src/app.py", "print('unapproved')\n")
        recovery_code, recovery = self._run_gate("--action", "read_only_recovery")
        action_code, action = self._run_gate("--action", "change_product")
        self.assertEqual(recovery_code, 0)
        self.assertEqual(recovery["status"], "PROCESS_BLOCKED")
        self.assertEqual(action_code, 20)
        self.assertEqual(action["status"], "PROCESS_BLOCKED")

        self._write_package()
        self._commit(f"iskin: pre-approval checkpoint: {PACKAGE_ID}")
        self._write("src/app.py", "print('unapproved')\n")
        recovery_code, recovery = self._run_gate("--action", "read_only_recovery")
        action_code, action = self._run_gate("--action", "change_product")
        self.assertEqual(recovery_code, 0)
        self.assertEqual(recovery["status"], "PROCESS_BLOCKED")
        self.assertEqual(action_code, 20)
        self.assertEqual(action["status"], "PROCESS_BLOCKED")

    def test_gate_is_read_only(self) -> None:
        checkpoint = self._checkpoint()
        self._write_pending_approval(checkpoint)
        before_head = self._git("rev-parse", "HEAD")
        before_status = self._git("status", "--porcelain=v1")
        before_files = sorted(path.relative_to(self.repo).as_posix() for path in self.repo.rglob("*") if path.is_file())
        self._run_gate("--action", "approval_checkpoint")
        self.assertEqual(self._git("rev-parse", "HEAD"), before_head)
        self.assertEqual(self._git("status", "--porcelain=v1"), before_status)
        after_files = sorted(path.relative_to(self.repo).as_posix() for path in self.repo.rglob("*") if path.is_file())
        self.assertEqual(after_files, before_files)


if __name__ == "__main__":
    unittest.main()