from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "package" / "template"
PACKAGE_ID = "AP-20260908-lifecycle"
PACKAGE_MD = f"product-memory/approval-packages/{PACKAGE_ID}.md"
PACKAGE_INDEX = f"product-memory/approval-packages/{PACKAGE_ID}.json"
OUTCOME_ID = "OUT-lifecycle"
GATE_ID = "GATE-local"
APPROVAL_EVENT = "AE-20260908-lifecycle"
DECISIONS = "product-memory/decisions.md"


class LifecycleEventSimulatorTests(unittest.TestCase):
    """Public-CLI simulator over a real Git repository and the full template."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="iskin-lifecycle-simulator-")
        root = Path(self.tempdir.name)
        self.repo = root / "installed-project"
        # This is the installed current template fixture; all lifecycle actions
        # below use the installed .iskin/policy_gate.py subprocess entrypoint.
        shutil.copytree(TEMPLATE, self.repo)
        self.git("init", "--quiet")
        self.git("config", "user.name", "IskIn lifecycle test")
        self.git("config", "user.email", "iskin-lifecycle@example.invalid")
        self._write_installation_metadata()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, relative: str, content: str | bytes) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def gate(self, action: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(self.repo / ".iskin" / "policy_gate.py"), "--repo", str(self.repo), "--action", action],
            cwd=self.repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def commit(self, message: str) -> str:
        self.git("commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD")

    def add_commit(self, paths: list[str], message: str) -> str:
        self.git("add", "--", *paths)
        self.assertEqual(self.git("diff", "--cached", "--check", check=False), "")
        return self.commit(message)

    def _write_installation_metadata(self) -> None:
        baseline = json.loads((self.repo / ".iskin/bootstrap-manifest.json").read_text(encoding="utf-8"))
        version = baseline["release_version"]
        self.write(".iskin/version", f"{version}\n")
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
        self.write(".iskin/installation-manifest.json", json.dumps(manifest, indent=2) + "\n")

    def bootstrap(self) -> str:
        code, payload = self.gate("status")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "BOOTSTRAP_REQUIRED")
        code, stage = self.gate("stage_bootstrap_baseline")
        self.assertEqual(code, 0, stage)
        paths = stage["allowed_paths"]
        self.assertEqual(paths, sorted(paths))
        self.git("add", "--", *paths)
        code, checkpoint = self.gate("bootstrap_checkpoint")
        self.assertEqual(code, 0, checkpoint)
        self.assertEqual(checkpoint["status"], "BOOTSTRAP_REQUIRED")
        sha = self.commit("chore: bootstrap iskin project baseline")
        for action in ("read_only_recovery", "status"):
            code, recovered = self.gate(action)
            self.assertEqual(code, 0, recovered)
            self.assertEqual(recovered["status"], "DISCOVERY_ALLOWED")
        return sha

    def prepare_package(self) -> str:
        self.write("product-memory/approval-packages.md", f"# Registry\n- {PACKAGE_MD}\n")
        package = "\n".join([
            f"package_id: {PACKAGE_ID}",
            "package_status: prepared",
            "### intent и ценность",
            "### граница MVP",
            "### outcomes и наблюдаемое поведение",
            "### обязательные gates и evidence",
            "### существенные uncertainties, риски, зависимости и ограничения",
            "",
        ])
        self.write(PACKAGE_MD, package)
        index = {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "revision": "1",
            "immutable_content": [{"path": PACKAGE_MD, "sha256": hashlib.sha256(package.encode()).hexdigest()}],
            "outcome_ids": [OUTCOME_ID],
            "gate_ids": [GATE_ID],
            "superseded_package": None,
        }
        self.write(PACKAGE_INDEX, json.dumps(index, indent=2) + "\n")
        for name, content in (
            ("intent.md", "# Intent\nPrepared\n"),
            ("outcomes.md", "# Outcomes\nPrepared\n"),
            ("uncertainties.md", "# Uncertainties\nPrepared\n"),
        ):
            self.write(f"product-memory/{name}", content)
        return self.add_commit(
            ["product-memory/approval-packages.md", PACKAGE_MD, PACKAGE_INDEX, "product-memory/intent.md", "product-memory/outcomes.md", "product-memory/uncertainties.md"],
            f"iskin: pre-approval checkpoint: {PACKAGE_ID}",
        )

    def approve(self, checkpoint: str) -> str:
        event = {
            "schema_version": 2,
            "event_type": "approval",
            "event_id": APPROVAL_EVENT,
            "package_id": PACKAGE_ID,
            "package_paths": [PACKAGE_MD, PACKAGE_INDEX],
            "checkpoint_sha": checkpoint,
            "package_displayed_in_previous_agent_turn": True,
            "approval_question": "Утверждаете этот пакет и разрешаете перейти к реализации?",
            "human_response": "Да, утверждаю пакет и разрешаю реализацию.",
            "actor": "human",
            "implementation_authorized": True,
            "human_decision_path": DECISIONS,
        }
        self.write(f"product-memory/approval-events/{APPROVAL_EVENT}.json", json.dumps(event, ensure_ascii=False, indent=2) + "\n")
        self.write(DECISIONS, "\n".join([
            "# Decisions", "",
            f"approval_event_id: {APPROVAL_EVENT}",
            f"approval_event_path: product-memory/approval-events/{APPROVAL_EVENT}.json",
            f"package_id: {PACKAGE_ID}",
            f"checkpoint_sha: {checkpoint}", "",
        ]))
        self.git("add", "--", f"product-memory/approval-events/{APPROVAL_EVENT}.json", DECISIONS)
        code, payload = self.gate("approval_checkpoint")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        return self.commit("iskin: approval checkpoint")

    def lifecycle_event(
        self,
        event_id: str,
        checkpoint: str,
        from_status: str,
        to_status: str,
        *,
        evidence_refs: list[str] | None = None,
        proof_refs: list[str] | None = None,
        human_decision_ref: str | None = None,
        actor: str = "hermes",
        reason: str = "verified transition",
        stage_extra: list[str] | None = None,
    ) -> tuple[str, dict[str, object]]:
        event_path = f"product-memory/lifecycle-events/{event_id}.json"
        event = {
            "schema_version": 1,
            "event_type": "lifecycle",
            "event_id": event_id,
            "outcome_id": OUTCOME_ID,
            "package_id": PACKAGE_ID,
            "package_checkpoint_sha": checkpoint,
            "from_status": from_status,
            "to_status": to_status,
            "actor": actor,
            "reason": reason,
            "evidence_refs": evidence_refs or [],
            "proof_refs": proof_refs or [],
            "human_decision_ref": human_decision_ref,
            "occurred_at_utc": "2026-09-08T12:00:00Z",
            "git_parent_sha": self.git("rev-parse", "HEAD"),
        }
        self.write(event_path, json.dumps(event, indent=2) + "\n")
        markers = "\n".join([
            f"<!-- iskin-lifecycle-event: {event_id} -->",
            f"<!-- iskin-outcome-id: {OUTCOME_ID} -->",
            f"<!-- iskin-status: {to_status} -->",
        ]) + "\n"
        self.write("product-memory/outcomes.md", f"# Outcomes\n{markers}")
        self.write("product-memory/evidence.md", f"# Evidence\n{markers}")
        paths = [event_path, "product-memory/outcomes.md", "product-memory/evidence.md"]
        if human_decision_ref:
            paths.append(human_decision_ref)
        paths.extend(evidence_refs or [])
        paths.extend(proof_refs or [])
        paths.extend(stage_extra or [])
        self.git("add", "--", *dict.fromkeys(paths))
        return event_path, self.gate("lifecycle_checkpoint")

    def test_full_lifecycle_with_recovery_at_boundaries(self) -> None:
        self.bootstrap()
        package_checkpoint = self.prepare_package()
        code, payload = self.gate("change_product")
        self.assertEqual(code, 10, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        approval_commit = self.approve(package_checkpoint)
        self.assertNotEqual(approval_commit, package_checkpoint)
        code, payload = self.gate("change_product")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")
        self.assertEqual(payload["lifecycle"], "approved")

        _, (_, pending) = self.lifecycle_event("LE-01", package_checkpoint, "approved", "in-progress")
        self.assertEqual(pending["status"], "IMPLEMENTATION_ALLOWED", pending)
        self.assertEqual(pending["lifecycle"], "approved")
        self.assertIn("lifecycle_checkpoint", pending["allowed_actions"])
        self.commit("iskin: lifecycle checkpoint LE-01")
        self.assertEqual(self.gate("read_only_recovery")[1]["lifecycle"], "in-progress")

        self.write("src/app.py", "def product():\n    return 'implemented'\n")
        self.git("add", "--", "src/app.py")
        code, product_checkpoint = self.gate("checkpoint")
        self.assertEqual(code, 0, product_checkpoint)
        self.commit("iskin: product checkpoint")
        self.assertEqual(self.gate("status")[1]["status"], "IMPLEMENTATION_ALLOWED")

        _, (_, pending) = self.lifecycle_event("LE-02", package_checkpoint, "in-progress", "evidence-pending")
        self.assertEqual(pending["status"], "IMPLEMENTATION_ALLOWED", pending)
        self.commit("iskin: lifecycle checkpoint LE-02")
        self.assertEqual(self.gate("read_only_recovery")[1]["lifecycle"], "evidence-pending")

        evidence = "evidence/run.json"
        proof = "evidence/proof-record.json"
        self.write(evidence, '{"run_id":"run-1","result":"pass"}\n')
        self.write(proof, json.dumps({
            "schema_version": 1,
            "status": "valid",
            "provenance_valid": True,
            "outcome_id": OUTCOME_ID,
            "package_id": PACKAGE_ID,
            "package_checkpoint_sha": package_checkpoint,
            "evidence_refs": [evidence],
        }) + "\n")
        _, (_, pending) = self.lifecycle_event("LE-03", package_checkpoint, "evidence-pending", "proved", evidence_refs=[evidence], proof_refs=[proof])
        self.assertEqual(pending["status"], "IMPLEMENTATION_ALLOWED", pending)
        self.commit("iskin: lifecycle checkpoint LE-03")
        self.assertEqual(self.gate("status")[1]["lifecycle"], "proved")

        decision = DECISIONS
        with (self.repo / decision).open("a", encoding="utf-8") as handle:
            handle.write("\nlifecycle_event_id: LE-04\ndecision: accepted\nactor: human\n")
        _, (_, pending) = self.lifecycle_event("LE-04", package_checkpoint, "proved", "accepted", human_decision_ref=decision, actor="human")
        self.assertEqual(pending["status"], "IMPLEMENTATION_ALLOWED", pending)
        self.commit("iskin: lifecycle checkpoint LE-04")
        final = self.gate("read_only_recovery")[1]
        self.assertEqual(final["lifecycle"], "accepted")
        self.assertEqual(self.git("status", "--porcelain=v1"), "")

    def _approved(self) -> str:
        self.bootstrap()
        checkpoint = self.prepare_package()
        self.approve(checkpoint)
        return checkpoint

    def test_unknown_outcome_and_wrong_from_status_are_blocked(self) -> None:
        checkpoint = self._approved()
        event_path = "product-memory/lifecycle-events/LE-unknown.json"
        event = {
            "schema_version": 1, "event_type": "lifecycle", "event_id": "LE-unknown",
            "outcome_id": "OUT-unknown", "package_id": PACKAGE_ID, "package_checkpoint_sha": checkpoint,
            "from_status": "approved", "to_status": "in-progress", "actor": "hermes", "reason": "test",
            "evidence_refs": [], "proof_refs": [], "human_decision_ref": None,
            "occurred_at_utc": "2026-09-08T12:00:00Z", "git_parent_sha": self.git("rev-parse", "HEAD"),
        }
        self.write(event_path, json.dumps(event) + "\n")
        self.write("product-memory/outcomes.md", "# Outcomes\n")
        self.write("product-memory/evidence.md", "# Evidence\n")
        self.git("add", "--", event_path, "product-memory/outcomes.md", "product-memory/evidence.md")
        code, payload = self.gate("lifecycle_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("UNKNOWN_OUTCOME", payload["reason_codes"])

    def test_invalid_transition_and_proved_without_evidence_fail_closed(self) -> None:
        checkpoint = self._approved()
        event_path = "product-memory/lifecycle-events/LE-skip.json"
        event = {
            "schema_version": 1, "event_type": "lifecycle", "event_id": "LE-skip",
            "outcome_id": OUTCOME_ID, "package_id": PACKAGE_ID, "package_checkpoint_sha": checkpoint,
            "from_status": "approved", "to_status": "evidence-pending", "actor": "hermes", "reason": "test",
            "evidence_refs": [], "proof_refs": [], "human_decision_ref": None,
            "occurred_at_utc": "2026-09-08T12:00:00Z", "git_parent_sha": self.git("rev-parse", "HEAD"),
        }
        self.write(event_path, json.dumps(event) + "\n")
        code, payload = self.gate("status")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PROCESS_BLOCKED")
        self.assertIn("LIFECYCLE_TRANSITION_INVALID", payload["reason_codes"])

        (self.repo / event_path).unlink()
        self.git("reset", "--quiet")
        self.lifecycle_event("LE-start", checkpoint, "approved", "in-progress")
        self.commit("start implementation")
        self.lifecycle_event("LE-pending", checkpoint, "in-progress", "evidence-pending")
        self.commit("await evidence")
        event["event_id"] = "LE-no-proof"
        event["from_status"] = "evidence-pending"
        event["to_status"] = "proved"
        event_path = "product-memory/lifecycle-events/LE-no-proof.json"
        self.write(event_path, json.dumps(event) + "\n")
        self.git("add", "--", event_path)
        code, payload = self.gate("lifecycle_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("PROOF_REFERENCES_REQUIRED", payload["reason_codes"])

    def test_package_drift_is_separate_from_projection_change(self) -> None:
        checkpoint = self._approved()
        self.write("product-memory/outcomes.md", "# Outcomes\nstatus: approved\n")
        self.git("add", "--", "product-memory/outcomes.md")
        self.commit("lifecycle projection only")
        code, payload = self.gate("change_product")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")

        package = self.repo / PACKAGE_MD
        package.write_text(package.read_text(encoding="utf-8") + "\nchanged specification\n", encoding="utf-8")
        self.git("add", "--", PACKAGE_MD)
        self.commit("invalid specification drift")
        code, payload = self.gate("change_product")
        self.assertEqual(code, 20, payload)
        self.assertIn("PACKAGE_CHANGED_AFTER_CHECKPOINT", payload["reason_codes"])

    def test_scope_projection_or_product_code_and_stale_proof_are_blocked(self) -> None:
        checkpoint = self._approved()
        self.write("src/unauthorized.py", "print('not lifecycle')\n")
        _, _ = self.lifecycle_event("LE-scope", checkpoint, "approved", "in-progress", stage_extra=["src/unauthorized.py"])
        self.git("add", "--", "src/unauthorized.py")
        code, payload = self.gate("lifecycle_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("LIFECYCLE_SCOPE_EXTRANEOUS", payload["reason_codes"])

        self.git("reset", "--quiet")
        (self.repo / "product-memory/lifecycle-events/LE-scope.json").unlink()
        self.write("product-memory/outcomes.md", "# Outcomes\n")
        self.write("product-memory/evidence.md", "# Evidence\n")
        self.git("add", "--", "product-memory/outcomes.md", "product-memory/evidence.md")
        self.commit("cleanup pending lifecycle test")
        self.lifecycle_event("LE-progress", checkpoint, "approved", "in-progress")
        self.commit("iskin: lifecycle checkpoint LE-progress")
        self.lifecycle_event("LE-pending", checkpoint, "in-progress", "evidence-pending")
        self.commit("iskin: lifecycle checkpoint LE-pending")
        evidence, proof = "evidence/stale.json", "evidence/stale-proof.json"
        self.write(evidence, "{}\n")
        self.write(proof, json.dumps({
            "schema_version": 1, "status": "invalidated", "provenance_valid": False,
            "outcome_id": OUTCOME_ID, "package_id": PACKAGE_ID,
            "package_checkpoint_sha": checkpoint, "evidence_refs": [evidence],
        }) + "\n")
        self.lifecycle_event("LE-stale", checkpoint, "evidence-pending", "proved", evidence_refs=[evidence], proof_refs=[proof])
        code, payload = self.gate("lifecycle_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("PROOF_REFERENCE_STALE_OR_INVALID", payload["reason_codes"])

    def test_event_mutation_deletion_or_orphan_projection_fail_closed(self) -> None:
        checkpoint = self._approved()
        self.lifecycle_event("LE-mutate", checkpoint, "approved", "in-progress")
        self.commit("iskin: lifecycle checkpoint LE-mutate")
        event = self.repo / "product-memory/lifecycle-events/LE-mutate.json"
        event.write_text(event.read_text(encoding="utf-8").replace("verified transition", "mutated"), encoding="utf-8")
        self.git("add", "--", str(event.relative_to(self.repo)))
        self.commit("illegal event mutation")
        code, payload = self.gate("status")
        self.assertEqual(code, 0)
        self.assertIn("LIFECYCLE_EVENT_MUTATED", payload["reason_codes"])

        self.git("reset", "--hard", "HEAD~1")
        self.git("rm", "--quiet", "product-memory/lifecycle-events/LE-mutate.json")
        self.commit("illegal event deletion")
        code, payload = self.gate("status")
        self.assertEqual(code, 0)
        self.assertIn("LIFECYCLE_EVENT_DELETED", payload["reason_codes"])

    def test_gate_is_read_only_and_legacy_state_is_unsupported(self) -> None:
        before = self.git("status", "--porcelain=v1")
        self.gate("read_only_recovery")
        after = self.git("status", "--porcelain=v1")
        self.assertEqual(before, after)
        self.write(".iskin/policy_state.json", '{"schema_version": 1}\n')
        self.git("add", "--", ".iskin/policy_state.json")
        self.commit("legacy state")
        code, payload = self.gate("change_product")
        self.assertEqual(code, 20)
        self.assertIn("UNSUPPORTED_PROJECT_STATE", payload["reason_codes"])

    def test_specification_revision_requires_new_approval_but_status_does_not(self) -> None:
        checkpoint = self._approved()
        self.write("product-memory/outcomes.md", "# Outcomes\nstatus: in-progress\n")
        self.git("add", "--", "product-memory/outcomes.md")
        self.commit("ordinary lifecycle projection")
        code, payload = self.gate("change_product")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "IMPLEMENTATION_ALLOWED")

        revision_id = f"{PACKAGE_ID}-r2"
        revision_md = f"product-memory/approval-packages/{revision_id}.md"
        revision_index = f"product-memory/approval-packages/{revision_id}.json"
        revision_text = "\n".join([
            f"package_id: {revision_id}", "package_status: prepared", "### intent и ценность",
            "### граница MVP расширена", "### outcomes и наблюдаемое поведение",
            "### обязательные gates и evidence",
            "### существенные uncertainties, риски, зависимости и ограничения", "",
        ])
        self.write(revision_md, revision_text)
        self.write(revision_index, json.dumps({
            "schema_version": 1, "package_id": revision_id, "revision": "2",
            "immutable_content": [{"path": revision_md, "sha256": hashlib.sha256(revision_text.encode()).hexdigest()}],
            "outcome_ids": [OUTCOME_ID], "gate_ids": [GATE_ID], "superseded_package": PACKAGE_ID,
        }, indent=2) + "\n")
        self.write("product-memory/approval-packages.md", f"# Registry\n- {PACKAGE_MD}\n- {revision_md}\n")
        self.add_commit(
            ["product-memory/approval-packages.md", revision_md, revision_index],
            f"iskin: pre-approval checkpoint: {revision_id}",
        )
        code, payload = self.gate("change_product")
        self.assertEqual(code, 10, payload)
        self.assertEqual(payload["status"], "AWAITING_APPROVAL")
        self.assertEqual(payload["package_id"], revision_id)

    def test_accepted_without_human_decision_is_blocked(self) -> None:
        checkpoint = self._approved()
        event_path = "product-memory/lifecycle-events/LE-no-human.json"
        event = {
            "schema_version": 1, "event_type": "lifecycle", "event_id": "LE-no-human",
            "outcome_id": OUTCOME_ID, "package_id": PACKAGE_ID, "package_checkpoint_sha": checkpoint,
            "from_status": "proved", "to_status": "accepted", "actor": "hermes", "reason": "test",
            "evidence_refs": [], "proof_refs": [], "human_decision_ref": None,
            "occurred_at_utc": "2026-09-08T12:00:00Z", "git_parent_sha": self.git("rev-parse", "HEAD"),
        }
        self.write(event_path, json.dumps(event) + "\n")
        self.write("product-memory/outcomes.md", "# Outcomes\n")
        self.write("product-memory/evidence.md", "# Evidence\n")
        self.git("add", "--", event_path, "product-memory/outcomes.md", "product-memory/evidence.md")
        code, payload = self.gate("lifecycle_checkpoint")
        self.assertEqual(code, 20)
        self.assertIn("HUMAN_DECISION_REQUIRED", payload["reason_codes"])


if __name__ == "__main__":
    unittest.main()
