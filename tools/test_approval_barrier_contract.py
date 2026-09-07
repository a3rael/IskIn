from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PROCESS = ROOT / "package" / "template" / "process"
DECISIONS_TEMPLATE = ROOT / "package" / "template" / "product-memory" / "decisions.md"
APPROVAL_PACKAGES_TEMPLATE = ROOT / "package" / "template" / "product-memory" / "approval-packages.md"
APPROVAL_PACKAGE_SCHEMA_TEMPLATE = ROOT / "package" / "template" / "product-memory" / "approval-packages" / "README.md"
POLICY_GATE_TEMPLATE = ROOT / "package" / "template" / ".iskin" / "policy_gate.py"
RUNTIME_SKILLS = ROOT / "runtime" / "skills"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ApprovalBarrierContractTests(unittest.TestCase):
    def test_discovery_is_not_approval_and_one_gate_covers_the_package(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")

        required = (
            "Discovery включает",
            "не являются утверждением intent, approval package или разрешением реализации",
            "один целиком собранный approval package",
            "продуктовый intent и ценность",
            "границу MVP: что входит и что не входит",
            "outcomes и их наблюдаемое поведение",
            "обязательные product gates и требуемое evidence",
            "существенные uncertainties и риски",
            "Этот пакет утверждается одним human gate",
            "отсутствие возражений approval не создают",
        )
        for marker in required:
            self.assertIn(marker, policy)

    def test_positive_approval_is_a_separate_question_with_both_parts(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")

        self.assertIn("Утверждаете этот пакет и разрешаете перейти к реализации?", policy)
        self.assertIn("Формулировка вопроса может быть эквивалентной", policy)
        self.assertIn("отдельным, прямым и явно содержать обе части", policy)
        self.assertIn("явно подтверждать и утверждение полного пакета, и разрешение реализации", policy)

    def test_durable_approval_uses_append_only_event_and_decisions_reference(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        decisions = read(DECISIONS_TEMPLATE)

        for marker in (
            "approval_event_id",
            "approval_event_path",
            "package_id",
            "checkpoint_sha",
        ):
            self.assertIn(marker, decisions)
        for marker in (
            "product-memory/approval-events/<event_id>.json",
            "human_response",
            "actor",
            "implementation_authorized: true",
        ):
            self.assertIn(marker, policy)
        self.assertIn("product-memory/decisions.md", policy)
        self.assertIn("append-only", policy)

    def test_negative_approval_scenarios_are_explicitly_blocked(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        action_selection = read(TEMPLATE_PROCESS / "action-selection.md")

        negative_scenarios = (
            "Ответ на уточняющий вопрос",
            "выбор варианта",
            "согласие с отдельной формулировкой",
            "отсутствие возражений",
            "заполненному intent",
            "До такого явного ответа реализация",
            "создание product evidence до этого события запрещены",
        )
        for marker in negative_scenarios:
            self.assertTrue(marker in policy or marker in action_selection, marker)

    def test_dirty_unapproved_recovery_is_process_blocked(self) -> None:
        recovery = read(TEMPLATE_PROCESS / "git-checkpoint-recovery.md")
        understand = read(RUNTIME_SKILLS / "iskin-understand-state" / "SKILL.md")

        self.assertIn("process-blocked", recovery)
        self.assertIn("без подтверждённого approval event", recovery)
        self.assertIn("не продолжает реализацию", recovery)
        self.assertIn("не создаёт product proof", recovery)
        self.assertIn("checkpoint", recovery)
        self.assertIn("process-blocked", understand)
        self.assertIn("without a confirmed approval event", understand)
        self.assertIn("do not continue implementation, product proof, or checkpoint creation", understand)
        self.assertIn("не удаляет, не откатывает и не stage-ит", recovery)

    def test_preapproval_package_has_immutable_checkpoint_contract(self) -> None:
        registry = read(APPROVAL_PACKAGES_TEMPLATE)
        package = read(APPROVAL_PACKAGE_SCHEMA_TEMPLATE)
        recovery = read(TEMPLATE_PROCESS / "git-checkpoint-recovery.md")

        self.assertIn("registry", registry)
        self.assertIn("approval-packages/<package_id>.md", registry)

        for marker in (
            "package_id",
            "package_paths",
            "intent и ценность",
            "граница MVP",
            "outcomes и наблюдаемое поведение",
            "обязательные gates и evidence",
            "существенные uncertainties, риски, зависимости и ограничения",
            "checkpoint_sha: не записывать в этот пакет",
        ):
            self.assertIn(marker, package)

        for marker in (
            "pre-approval checkpoint",
            "показа человеку",
            "не содержит продуктового кода",
            "не содержит product evidence",
            "пакет существует только в dirty tree",
            "checkpoint с продуктовым кодом непригоден",
        ):
            self.assertIn(marker, recovery)

    def test_approval_requires_displayed_package_and_following_human_turn(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        recovery = read(TEMPLATE_PROCESS / "git-checkpoint-recovery.md")
        decisions = read(DECISIONS_TEMPLATE)

        for marker in (
            "показывает человеку весь пакет",
            "package ID",
            "checkpoint SHA",
            "следующем человеческом ходе",
            "не показан",
            "package_displayed_in_previous_agent_turn: true",
            "approval_question",
        ):
            self.assertTrue(marker in policy or marker in recovery or marker in decisions, marker)

    def test_generic_and_technical_grants_are_not_lifecycle_approval(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        action_selection = read(TEMPLATE_PROCESS / "action-selection.md")

        for marker in (
            "«продолжай работу»",
            "технического действия",
            "не является lifecycle approval",
            "не предлагает вариант ответа, утверждающий не показанный пакет",
        ):
            self.assertTrue(marker in policy or marker in action_selection, marker)

    def test_package_drift_invalidates_previous_approval(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        recovery = read(TEMPLATE_PROCESS / "git-checkpoint-recovery.md")

        for marker in (
            "каждого package_path",
            "байтово совпадает",
            "прежний approval недействителен",
            "новый package ID",
            "новый checkpoint",
            "новый human approval",
            "история не переписывается",
        ):
            self.assertTrue(marker.lower() in policy.lower() or marker.lower() in recovery.lower(), marker)

    def test_executable_policy_gate_has_versioned_read_only_contract(self) -> None:
        gate = read(POLICY_GATE_TEMPLATE)
        for marker in (
            "Read-only, deterministic lifecycle policy gate",
            "DISCOVERY_ALLOWED",
            "AWAITING_APPROVAL",
            "IMPLEMENTATION_ALLOWED",
            "PROCESS_BLOCKED",
            "BOOTSTRAP_REQUIRED",
            "MACHINE_STATE_UNSUPPORTED",
            "GIT_CHECK_FAILED",
            "approval_display_is_conversational_evidence_not_cryptographic_proof",
            "approval_checkpoint",
            "bootstrap_checkpoint",
            "stage_bootstrap_baseline",
            "INITIAL_BASELINE_UNCOMMITTED",
            "BOOTSTRAP_BASELINE",
            "UNSUPPORTED_PROJECT_STATE",
            "product-memory/approval-events",
            "--action",
        ):
            self.assertIn(marker, gate)

    def test_all_six_global_skills_call_or_require_the_gate(self) -> None:
        required_by_skill = {
            "iskin-control-pilot": ("policy_gate.py", "read_only_recovery", "stage_bootstrap_baseline", "allowed_paths", "--action checkpoint"),
            "iskin-understand-state": ("policy_gate.py", "read_only_recovery", "stage_bootstrap_baseline", "allowed_paths", "PROCESS_BLOCKED"),
            "iskin-choose-next-action": ("policy_gate.py", "read_only_recovery", "stage_bootstrap_baseline", "allowed_paths"),
            "iskin-change-product": ("policy_gate.py", "--action change_product", "any other exit"),
            "iskin-prove-result": ("policy_gate.py", "--action prove_result", "product checks"),
            "iskin-challenge-result": ("policy_gate.py", "read-only diagnosis", "telemetry writes"),
        }
        for skill_name, markers in required_by_skill.items():
            text = read(RUNTIME_SKILLS / skill_name / "SKILL.md")
            for marker in markers:
                self.assertIn(marker, text, f"{skill_name}: {marker}")

    def test_all_six_global_skills_enforce_the_barrier(self) -> None:
        required_by_skill = {
            "iskin-control-pilot": (
                "complete approval package",
                "implementation_authorized: true",
                "discovery response",
                "pre-approval checkpoint",
            ),
            "iskin-understand-state": (
                "approval state",
                "Never infer approval",
                "process-blocked",
                "pre-approval checkpoint",
            ),
            "iskin-choose-next-action": (
                "append-only approval event",
                "select only discovery",
                "does not treat a discovery response as approval",
                "checkpoint commit",
            ),
            "iskin-change-product": (
                "complete approved approval package",
                "implementation_authorized: true",
                "any other exit",
                "pre-approval checkpoint",
            ),
            "iskin-prove-result": (
                "complete approved approval package",
                "implementation_authorized: true",
                "any other exit",
                "pre-approval checkpoint",
            ),
        }
        for skill_name, markers in required_by_skill.items():
            text = read(RUNTIME_SKILLS / skill_name / "SKILL.md")
            for marker in markers:
                self.assertIn(marker, text, f"{skill_name}: {marker}")


if __name__ == "__main__":
    unittest.main()