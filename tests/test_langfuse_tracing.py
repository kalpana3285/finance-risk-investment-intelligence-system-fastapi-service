from services import langfuse_tracing


def test_record_scores_attaches_numeric_scores_to_trace(monkeypatch):
    class FakeLangfuseClient:
        def __init__(self) -> None:
            self.scores = []

        def create_score(self, **kwargs) -> None:
            self.scores.append(kwargs)

    client = FakeLangfuseClient()
    monkeypatch.setattr(langfuse_tracing, "_get_client", lambda: client)

    langfuse_tracing.record_scores(
        trace_id="a" * 32,
        scores={
            "faithfulness": 0.9,
            "answer_relevance": 0.8,
            "confidence": 0.7,
        },
        metadata={"query_id": "query-1"},
    )

    assert [score["name"] for score in client.scores] == [
        "faithfulness",
        "answer_relevance",
        "confidence",
    ]
    assert all(score["trace_id"] == "a" * 32 for score in client.scores)
    assert all(score["data_type"] == "NUMERIC" for score in client.scores)
    assert [score["value"] for score in client.scores] == [0.9, 0.8, 0.7]
