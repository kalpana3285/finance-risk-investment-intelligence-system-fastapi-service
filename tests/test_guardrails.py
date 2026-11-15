from agents.control_plane import (
    EscalationPacket,
    OrchestrationResult,
)
from schemas import Citation, QueryStatus
from services.guardrails import GuardrailsValidator


def test_input_validation_rejects_empty_and_overlong_queries() -> None:
    assert not GuardrailsValidator.validate_input(" \t ").allowed
    assert not GuardrailsValidator.validate_input("q" * 4001).allowed
    assert GuardrailsValidator.validate_input("Assess policy risk").allowed


def test_default_output_scanner_redacts_pii_without_an_nlp_model() -> None:
    validator = GuardrailsValidator()

    decision = validator.validate_output("Contact jane.doe@example.com.")

    assert decision.pii_detected
    assert "jane.doe@example.com" not in decision.sanitized_text


def test_output_guardrails_redact_answer_citations_and_escalation_text() -> None:
    sensitive_value = "contact@example.com"

    def redact(text: str) -> str:
        return text.replace(sensitive_value, "[REDACTED]")

    validator = GuardrailsValidator(pii_scanner=redact)
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer=f"Contact {sensitive_value}.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
                excerpt=f"Email: {sensitive_value}",
            ),
        ),
        limitations=("Educational data.",),
        escalation=EscalationPacket(
            reason=f"Review {sensitive_value}.",
            requested_review=f"Contact {sensitive_value}.",
        ),
    )

    sanitized, pii_detected = validator.sanitize_result(result)

    assert pii_detected
    assert "[REDACTED]" in sanitized.answer
    assert "[REDACTED]" in sanitized.citations[0].excerpt
    assert "[REDACTED]" in sanitized.escalation.reason
    assert "[REDACTED]" in sanitized.escalation.requested_review
    assert any("redacted" in item.lower() for item in sanitized.limitations)
    assert sensitive_value not in repr(sanitized)
