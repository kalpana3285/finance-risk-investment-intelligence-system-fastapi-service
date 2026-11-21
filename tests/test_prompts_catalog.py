from __future__ import annotations

from typing import Any

import pytest

from prompts.catalog import get_prompt
from services import langfuse_tracing


class FakeManagedPrompt:
    def __init__(
        self,
        *,
        name: str,
        version: int,
        labels: list[str],
        variables: list[str],
        messages: list[tuple[str, str]] | None = None,
        template: str | None = None,
        prompt_text: str | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.labels = labels
        self.variables = variables
        self._messages = messages
        self._template = template
        self.prompt = prompt_text

    def get_langchain_prompt(self) -> Any:
        return self._messages if self._messages is not None else self._template


def test_catalog_loads_managed_chat_prompt_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = FakeManagedPrompt(
        name="friis-finance-synthesis",
        version=7,
        labels=["production"],
        variables=["request_payload"],
        messages=[
            ("system", "Managed system prompt"),
            ("user", "{request_payload}"),
        ],
    )
    calls: list[dict[str, Any]] = []

    def fetch_prompt(**kwargs: Any) -> FakeManagedPrompt:
        calls.append(kwargs)
        return managed_prompt

    monkeypatch.setattr(langfuse_tracing, "fetch_prompt", fetch_prompt)

    prompt = get_prompt("finance-synthesis")

    assert calls == [
        {
            "name": "friis-finance-synthesis",
            "prompt_type": "text",
            "label": "production",
        }
    ]
    assert prompt["version"] == 7
    assert prompt["messages"] == [
        {"role": "system", "content": "Managed system prompt"},
        {"role": "user", "content": "{request_payload}"},
    ]


def test_catalog_loads_managed_text_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = FakeManagedPrompt(
        name="friis-finance-tool-agent",
        version=4,
        labels=["production"],
        variables=[],
        template="Managed tool-agent instructions",
    )
    monkeypatch.setattr(
        langfuse_tracing, "fetch_prompt", lambda **_kwargs: managed_prompt
    )

    prompt = get_prompt("finance-tool-agent")

    assert prompt["version"] == 4
    assert prompt["template"] == "Managed tool-agent instructions"


def test_catalog_uses_local_template_when_langfuse_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(langfuse_tracing, "fetch_prompt", lambda **_kwargs: None)

    prompt = get_prompt("finance-synthesis")

    assert prompt["version"] == 1
    assert prompt["name"] == "friis-finance-synthesis"


def test_catalog_does_not_hide_managed_prompt_fetch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fetch(**_kwargs: Any) -> None:
        raise RuntimeError("Langfuse prompt fetch failed")

    monkeypatch.setattr(langfuse_tracing, "fetch_prompt", fail_fetch)

    with pytest.raises(RuntimeError, match="Langfuse prompt fetch failed"):
        get_prompt("finance-synthesis")


def test_catalog_normalizes_text_prompt_with_chat_message_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = FakeManagedPrompt(
        name="friis-finance-synthesis",
        version=7,
        labels=["production"],
        variables=["request_payload"],
        template="Managed text prompt",
        prompt_text=(
            '[{"role":"system","content":"Managed system prompt"},'
            '{"role":"human","content":"{{request_payload}}"}]'
        ),
    )
    monkeypatch.setattr(
        langfuse_tracing, "fetch_prompt", lambda **_kwargs: managed_prompt
    )

    prompt = get_prompt("finance-synthesis")

    assert prompt["version"] == 7
    assert prompt["messages"] == [
        {"role": "system", "content": "Managed system prompt"},
        {"role": "user", "content": "{request_payload}"},
    ]


def test_catalog_adapts_plain_text_prompt_as_system_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = FakeManagedPrompt(
        name="friis-finance-synthesis",
        version=7,
        labels=["production"],
        variables=["request_payload"],
        template="Managed system prompt",
        prompt_text="Managed system prompt",
    )
    monkeypatch.setattr(
        langfuse_tracing, "fetch_prompt", lambda **_kwargs: managed_prompt
    )

    prompt = get_prompt("finance-synthesis")

    assert prompt["messages"] == [
        {"role": "system", "content": "Managed system prompt"},
        {"role": "user", "content": "{request_payload}"},
    ]


def test_rag_evaluator_uses_langfuse_production_text_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = FakeManagedPrompt(
        name="friis-finance-rag-evaluator",
        version=3,
        labels=["production"],
        variables=["evaluation_payload"],
        messages=[
            ("system", "Managed evaluator rubric"),
            ("user", "{evaluation_payload}"),
        ],
    )
    calls: list[dict[str, Any]] = []

    def fetch_prompt(**kwargs: Any) -> FakeManagedPrompt:
        calls.append(kwargs)
        return managed_prompt

    monkeypatch.setattr(langfuse_tracing, "fetch_prompt", fetch_prompt)

    prompt = get_prompt("finance-rag-evaluator")

    assert prompt["version"] == 3
    assert calls == [
        {
            "name": "friis-finance-rag-evaluator",
            "prompt_type": "text",
            "label": "production",
        }
    ]


def test_fetch_prompt_uses_configured_type_and_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_prompt = type(
        "Prompt",
        (),
        {"name": "friis-finance-rag-evaluator", "version": 2},
    )()

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        def get_prompt(self, name: str, **kwargs: Any) -> object:
            self.calls.append((name, kwargs))
            return managed_prompt

    client = FakeClient()
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-test")
    monkeypatch.setattr(langfuse_tracing, "_get_client", lambda: client)

    prompt = langfuse_tracing.fetch_prompt(
        name="friis-finance-rag-evaluator",
        prompt_type="chat",
        label="evaluation",
    )

    assert prompt is managed_prompt
    assert client.calls == [
        (
            "friis-finance-rag-evaluator",
            {"type": "chat", "label": "evaluation"},
        )
    ]


def test_fetch_prompt_rejects_partial_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")

    with pytest.raises(RuntimeError, match="Both LANGFUSE_PUBLIC_KEY"):
        langfuse_tracing.fetch_prompt(
            name="friis-finance-synthesis",
            prompt_type="chat",
            label="production",
        )


def test_fetch_prompt_uses_local_fallback_for_missing_prompt(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class MissingPromptError(Exception):
        status_code = 404

    class FakeClient:
        def get_prompt(self, _name: str, **_kwargs: Any) -> None:
            raise MissingPromptError

    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-test")
    monkeypatch.setattr(langfuse_tracing, "_get_client", lambda: FakeClient())

    assert (
        langfuse_tracing.fetch_prompt(
            name="friis-pdf-visual-caption",
            prompt_type="text",
            label="production",
        )
        is None
    )
    assert "local catalog will be used" in caplog.text
