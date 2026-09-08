from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "package" / "template" / ".iskin" / "policy_gate.py"
TEMPLATE = ROOT / "package" / "template"
PACKAGE_ID = "AP-20260907-policy-gate"
EVENT_ID = "AE-20260907-policy-gate"
REGISTRY = "product-memory/approval-packages.md"
PACKAGE_PATH = f"product-memory/approval-packages/{PACKAGE_ID}.md"
PACKAGE_INDEX_PATH = f"product-memory/approval-packages/{PACKAGE_ID}.json"
EVENT_PATH = f"product-memory/approval-events/{EVENT_ID}.json"
DECISIONS = "product-memory/decisions.md"
PACKAGE_PATHS = (
    PACKAGE_PATH,
    PACKAGE_INDEX_PATH,
)


class PolicyGateExecutableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-policy-gate-")
        self.repo = Path(self.tempdir.name) / "project"
        shutil.copytree(TEMPLATE, self.repo)
        self._git("init", "--quiet")
        self._git("config", "user.name", "IskIn test")
        self._git("config", "user.email", "iskin-test@example.invalid")
        self._write_installation_metadata()
        baseline = json.loads((self.repo / ".iskin" / "bootstrap-manifest.json").read_text(encoding="utf-8"))
        paths = {entry["path"] for entry in baseline["files"]}
        paths.update({baseline["self_path"], ".iskin/version", ".iskin/installation-manifest.json"})
        self._git("add", "--", *sorted(paths))
        self._git("commit", "--quiet", "-m", "chore: bootstrap iskin project baseline")

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

    def _write_installation_metadata(self) -> None:
        baseline = json.loads((self.repo / ".iskin" / "bootstrap-manifest.json").read_text(encoding="utf-8"))
        version = baseline["release_version"]
        self._write(".iskin/version", f"{version}\n")
        expected = {
            entry["path"]: (self.repo / entry["path"]).read_bytes()
            for entry in baseline["files"]
            if not entry["path"].startswith(("product-memory/", "telemetry/"))
        }
        expected[".iskin/version"] = (self.repo / ".iskin/version").read_bytes()
        expected[baseline["self_path"]] = (self.repo / baseline["self_path"]).read_bytes()
        manifest = {
            "schema_version": 1,
            "release_version": version,
            "archive_sha256": "a" * 64,
            "files": [
                {"path": path, "sha256": hashlib.sha256(expected[path]).hexdigest()}
                for path in sorted(expected)
            ],
        }
        self._write(".iskin/installation-manifest.json", json.dumps(manifest, indent=2) + "\n")

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
        self._write(
            PACKAGE_INDEX_PATH,
            json.dumps(
                {
                    "schema_version": 1,
                    "package_id": PACKAGE_ID,
                    "revision": "1",
                    "immutable_content": [{"path": PACKAGE_PATH, "sha256": hashlib.sha256((self.repo / PACKAGE_PATH).read_bytes()).hexdigest()}],
                    "outcome_ids": ["OUT-policy-gate"],
                    "gate_ids": ["GATE-policy-gate"],
                    "superseded_package": None,
                },
                indent=2,
            )
            + "\n",
        )
        self._write("product-memory/intent.md", "# Intent\nPrepared\n")
        self._write("product-memory/outcomes.md", "# Outcomes\nPrepared\n")
        self._write("product-memory/uncertainties.md", "# Uncertainties\nPrepared\n")

    def _checkpoint(self) -> str:
        self._write_package()
        return self._commit(f"iskin: pre-approval checkpoint: {PACKAGE_ID}")

    def _event(self, *, checkpoint: str | None = None, event_id: str = EVENT_ID) -> dict[str, object]:
        return {
            "schema_version": 2,
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

    def test_bootstrap_fixture_is_not_preapproval_evidence(self) -> None:
        self._checkpoint()
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 10, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertNotIn("PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT", payload["reason_codes"])

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

    def test_preapproval_product_evidence_blocks(self) -> None:
        self._write("evidence/run.json", "{\"result\": \"unapproved\"}\n")
        self._commit("product evidence before package")
        self._checkpoint()
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("PRODUCT_OR_EVIDENCE_BEFORE_CHECKPOINT", payload["reason_codes"])

    def test_baseline_fixture_drift_after_bootstrap_is_blocked(self) -> None:
        fixture = self.repo / "process/fixtures/provenance-drift/template/proof-record.json"
        fixture.write_bytes(fixture.read_bytes() + b"drift after bootstrap\n")
        self._commit("unauthorized baseline fixture drift")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("BOOTSTRAP_BASELINE_HASH_MISMATCH", payload["reason_codes"])

    def test_bootstrap_marker_and_manifest_are_verified(self) -> None:
        self._git("commit", "--quiet", "--amend", "-m", "arbitrary historical boundary")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertIn("BOOTSTRAP_COMMIT_MISSING", payload["reason_codes"])

        self._git("reset", "--quiet", "HEAD@{1}")
        manifest_path = self.repo / ".iskin/bootstrap-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertIn("BOOTSTRAP_BASELINE_HASH_MISMATCH", payload["reason_codes"])

    def test_bootstrap_commit_scope_is_verified(self) -> None:
        self._write("unexpected-bootstrap-file.txt", "unexpected\n")
        self._git("add", "--", "unexpected-bootstrap-file.txt")
        self._git("commit", "--quiet", "--amend", "--no-edit")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertIn("BOOTSTRAP_COMMIT_SCOPE_INVALID", payload["reason_codes"])

    def test_dirty_or_staged_product_before_approval_is_blocked(self) -> None:
        checkpoint = self._checkpoint()
        self._write("src/app.py", "print('unapproved')\n")
        self._git("add", "--", "src/app.py")
        code, payload = self._run_gate("--action", "change_product")
        self.assertEqual(code, 20, payload)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertEqual(payload["checkpoint_sha"], checkpoint)
        self.assertIn("PRODUCT_OR_EVIDENCE_BEFORE_APPROVAL", payload["reason_codes"])

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


class BootstrapPolicyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-bootstrap-gate-")
        self.repo = Path(self.tempdir.name) / "project"
        shutil.copytree(TEMPLATE, self.repo)
        self._git("init", "--quiet")
        self._git("config", "user.name", "IskIn bootstrap test")
        self._git("config", "user.email", "iskin-bootstrap@example.invalid")
        self._write_installation_metadata()

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

    def _write_installation_metadata(self) -> None:
        baseline = json.loads((self.repo / ".iskin" / "bootstrap-manifest.json").read_text(encoding="utf-8"))
        version = baseline["release_version"]
        self._write(".iskin/version", f"{version}\n")
        expected = {
            entry["path"]: (self.repo / entry["path"]).read_bytes()
            for entry in baseline["files"]
            if not entry["path"].startswith(("product-memory/", "telemetry/"))
        }
        expected[".iskin/version"] = (self.repo / ".iskin/version").read_bytes()
        expected[baseline["self_path"]] = (self.repo / baseline["self_path"]).read_bytes()
        manifest = {
            "schema_version": 1,
            "release_version": version,
            "archive_sha256": "a" * 64,
            "files": [
                {"path": path, "sha256": hashlib.sha256(expected[path]).hexdigest()}
                for path in sorted(expected)
            ],
        }
        self._write(".iskin/installation-manifest.json", json.dumps(manifest, indent=2) + "\n")

    def _run_gate(self, *args: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(self.repo / ".iskin" / "policy_gate.py"), "--repo", str(self.repo), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def _snapshot(self) -> tuple[str, str, str]:
        status = self._git("status", "--porcelain=v1", "--untracked-files=all")
        staged = self._git("diff", "--cached", "--name-only", "--no-renames")
        head = self._git("rev-parse", "--verify", "HEAD", check=False)
        return status, staged, head

    def test_pristine_install_requires_authorized_staging(self) -> None:
        code, payload = self._run_gate("--action", "status")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")
        self.assertIn("INITIAL_BASELINE_UNCOMMITTED", payload["reason_codes"])
        self.assertNotIn("PRODUCT_OR_EVIDENCE_WITHOUT_PACKAGE", payload["reason_codes"])
        self.assertEqual(payload["allowed_actions"], ["read_only_recovery", "stage_bootstrap_baseline"])
        for action in ("discover", "prepare_approval", "bootstrap_checkpoint", "approval_checkpoint"):
            self.assertIn(action, payload["forbidden_actions"])
        for action in ("discover", "prepare_approval"):
            code, denied = self._run_gate("--action", action)
            self.assertEqual(code, 10, (action, denied))
            self.assertEqual(denied["status"], "BOOTSTRAP_REQUIRED")

        before = self._snapshot()
        code, stage_payload = self._run_gate("--action", "stage_bootstrap_baseline")
        self.assertEqual(code, 0, stage_payload)
        paths = stage_payload["allowed_paths"]
        self.assertEqual(paths, sorted(paths))
        self.assertTrue(paths)
        self.assertEqual(self._snapshot(), before)

        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 10, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")

        self._git("add", "--", paths[0])
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 20, payload)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self._git("reset", "--quiet")

        self._git("add", "--", *paths)
        code, payload = self._run_gate("--action", "stage_bootstrap_baseline")
        self.assertEqual(code, 10, payload)
        self.assertEqual(payload["allowed_actions"], ["read_only_recovery", "bootstrap_checkpoint"])

        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")
        self.assertEqual(payload["allowed_actions"], ["read_only_recovery", "bootstrap_checkpoint"])

        self._git("commit", "--quiet", "-m", "chore: bootstrap iskin project baseline")
        code, payload = self._run_gate("--action", "status")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")
        self.assertIn("NO_APPROVAL_PACKAGE", payload["reason_codes"])
        self.assertNotIn("bootstrap_checkpoint", payload["allowed_actions"])
        for action in ("change_product", "prove_result", "checkpoint", "approval_checkpoint"):
            code, payload = self._run_gate("--action", action)
            self.assertEqual(code, 10, (action, payload))
            self.assertEqual(payload["status"], "DISCOVERY_ALLOWED")

    def test_staged_bootstrap_recovers_after_interrupted_state(self) -> None:
        code, stage_payload = self._run_gate("--action", "stage_bootstrap_baseline")
        self.assertEqual(code, 0, stage_payload)
        paths = stage_payload["allowed_paths"]
        self._git("add", "--", *paths)
        self._write("unexpected.txt", "interrupted\n")

        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 20, payload)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("BOOTSTRAP_UNEXPECTED_FILE", payload["reason_codes"])

        (self.repo / "unexpected.txt").unlink()
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")

    def test_product_evidence_and_unexpected_files_fail_bootstrap_closed(self) -> None:
        for relative, content in (
            ("src/app.py", "print('product')\n"),
            ("evidence/run.json", "{}\n"),
            ("unexpected.txt", "unexpected\n"),
        ):
            with self.subTest(relative=relative):
                self._write(relative, content)
                code, payload = self._run_gate("--action", "bootstrap_checkpoint")
                self.assertEqual(code, 20)
                self.assertEqual(payload["status"], "PROCESS_BLOCKED")
                self.assertIn("BOOTSTRAP_UNEXPECTED_FILE", payload["reason_codes"])
                (self.repo / relative).unlink()

    def test_changed_or_missing_baseline_file_fails_bootstrap_closed(self) -> None:
        baseline_file = self.repo / "process" / "fixtures" / "provenance-drift" / "template" / "proof-record.json"
        original = baseline_file.read_bytes()
        baseline_file.write_bytes(original + b"changed\n")
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("BOOTSTRAP_BASELINE_HASH_MISMATCH", payload["reason_codes"])

        baseline_file.write_bytes(original)
        (self.repo / "README.md").unlink()
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("BOOTSTRAP_BASELINE_MISSING", payload["reason_codes"])

    def test_wrong_staged_scope_is_denied_but_exact_scope_is_allowed(self) -> None:
        self._git("add", "--", ".gitignore")
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("BOOTSTRAP_SCOPE_MISMATCH", payload["reason_codes"])

        self._git("reset", "--quiet")
        code, stage_payload = self._run_gate("--action", "stage_bootstrap_baseline")
        self.assertEqual(code, 0, stage_payload)
        self._git("add", "--", *stage_payload["allowed_paths"])
        code, payload = self._run_gate("--action", "bootstrap_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")

    def test_bootstrap_gate_is_read_only(self) -> None:
        before = self._snapshot()
        self._run_gate("--action", "status")
        self.assertEqual(self._snapshot(), before)


if __name__ == "__main__":
    unittest.main()