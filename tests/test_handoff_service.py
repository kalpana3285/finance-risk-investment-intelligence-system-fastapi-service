import pytest

from handoff import handoff_service


def test_evaluate_confidence_value_applies_normalized_threshold():
    assert handoff_service.evaluate_confidence_value(0.39)["trigger"] is True
    assert handoff_service.evaluate_confidence_value(0.4)["trigger"] is False


def test_send_handoff_email_uses_configured_smtp(monkeypatch):
    monkeypatch.setattr(handoff_service, "load_dotenv", lambda: None)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USERNAME", "friis")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("APPLICATION_EMAIL", "friis@example.test")
    monkeypatch.setenv("SUPPORT_EMAIL", "support@example.test")
    sent_messages = []

    class FakeSMTP:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            assert username == "friis"
            assert password == "test-password"

        def sendmail(self, sender, recipient, message):
            sent_messages.append((sender, recipient, message))

    def create_smtp(host, port):
        assert host == "smtp.example.test"
        assert port == 2525
        return FakeSMTP()

    monkeypatch.setattr(handoff_service.smtplib, "SMTP", create_smtp)

    handoff_service.send_handoff_email(
        {
            "reference_id": "HO-test",
            "trace_id": "trace-test",
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "priority": "high",
            "trigger_reason": "faithfulness below 0.6",
            "user_metadata": {"email": "Not included"},
            "session_id": "Not included",
            "query_history": "Query ID: query-test",
            "generated_answer": "Withheld",
            "evaluation_scores": {
                "faithfulness": 0.2,
                "relevance": 0.8,
                "confidence": 30,
            },
            "retrieved_chunks": "Withheld",
            "conversation_flow": "Query ID: query-test",
        }
    )

    assert len(sent_messages) == 1
    assert sent_messages[0][:2] == (
        "friis@example.test",
        "support@example.test",
    )
    assert "trace-test" in sent_messages[0][2]
