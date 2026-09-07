from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PROCESS = ROOT / "package" / "template" / "process"
DECISIONS_TEMPLATE = ROOT / "package" / "template" / "product-memory" / "decisions.md"
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

    def test_durable_approval_uses_existing_decisions_source(self) -> None:
        policy = read(TEMPLATE_PROCESS / "autonomy-policy.md")
        decisions = read(DECISIONS_TEMPLATE)

        for marker in (
            "package_ref",
            "question",
            "human_response",
            "actor",
            "implementation_authorized: true",
        ):
            self.assertIn(marker, decisions)
        self.assertIn("product-memory/decisions.md", policy)
        self.assertIn("package_ref", policy)
        self.assertIn("отдельный формат хранения или новый файл для этого не создаётся", policy)

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

    def test_all_five_global_skills_enforce_the_barrier(self) -> None:
        required_by_skill = {
            "iskin-control-pilot": (
                "complete approval package",
                "implementation_authorized: true",
                "discovery response",
            ),
            "iskin-understand-state": (
                "approval state",
                "Never infer approval",
                "process-blocked",
            ),
            "iskin-choose-next-action": (
                "durable approval event",
                "select only discovery",
                "does not treat a discovery response as approval",
            ),
            "iskin-change-product": (
                "complete approved approval package",
                "implementation_authorized: true",
                "insufficient authority",
            ),
            "iskin-prove-result": (
                "complete approved approval package",
                "implementation_authorized: true",
                "cannot receive canonical product proof",
            ),
        }
        for skill_name, markers in required_by_skill.items():
            text = read(RUNTIME_SKILLS / skill_name / "SKILL.md")
            for marker in markers:
                self.assertIn(marker, text, f"{skill_name}: {marker}")


if __name__ == "__main__":
    unittest.main()