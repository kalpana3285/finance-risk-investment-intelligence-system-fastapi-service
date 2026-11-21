"""Langfuse prompt names and metadata for FRIIS workflows.

Prompt content is managed in Langfuse; this catalog contains no local prompt
templates or fallback content.
"""

from __future__ import annotations

import ast
from typing import Any

PROMPTS: dict[str, dict[str, Any]] = {
    "finance-synthesis": {
        "name": "friis-finance-synthesis",
        "type": "chat",
        "langfuse_type": "text",
        "labels": ["production"],
        "description": "Synthesizes retrieved evidence into a cited FRIIS research response.",
        "variables": ["request_payload"],
    },
    "finance-tool-agent": {
        "name": "friis-finance-tool-agent",
        "type": "text",
        "labels": ["production"],
        "description": "Instructions for the read-only finance agent with structured data tools.",
        "variables": [],
    },
    "pdf-visual-caption": {
        "name": "friis-pdf-visual-caption",
        "type": "text",
        "labels": ["production"],
        "description": "Describes visible chart and diagram evidence in a PDF page.",
        "variables": ["page_image"],
    },
    "friis-query-result-evaluator": {
        "name": "friis-query-result-evaluator",
        "type": "chat",
        "langfuse_type": "text",
        "labels": ["production"],
        "description": "Calibrated scoring of query correctness, evidence support, relevance, and usefulness.",
        "variables": ["evaluation_payload"],
    },
    "finance-rag-evaluator": {
        "name": "friis-finance-rag-evaluator",
        "type": "chat",
        "langfuse_type": "text",
        "labels": ["production"],
        "description": "Calibrated rubric-based offline evaluation of evidence, task success, and risk.",
        "variables": ["evaluation_payload"],
    },
}


def get_prompt(key: str) -> dict[str, Any]:
    """Fetch and adapt a required managed Langfuse prompt."""
    try:
        catalog_entry = PROMPTS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown FRIIS prompt catalog key: {key}") from exc

    from services.langfuse_tracing import fetch_prompt

    label = next(iter(catalog_entry.get("labels", [])), None)
    remote_prompt = fetch_prompt(
        name=catalog_entry["name"],
        prompt_type=catalog_entry.get("langfuse_type", catalog_entry["type"]),
        label=label,
    )
    if remote_prompt is None:
        raise RuntimeError(
            f"Required Langfuse prompt '{catalog_entry['name']}' is unavailable. "
            "Enable Langfuse and configure valid credentials and prompt labels."
        )

    managed_prompt = {
        **catalog_entry,
        "source": "langfuse",
        "name": remote_prompt.name,
        "version": remote_prompt.version,
        "labels": list(remote_prompt.labels),
        "variables": list(remote_prompt.variables),
    }
    if catalog_entry["type"] == "chat":
        messages = _managed_chat_messages(catalog_entry, remote_prompt)
        if messages is None:
            raise RuntimeError(
                f"Langfuse prompt '{catalog_entry['name']}' is not a supported "
                "chat prompt."
            )
        managed_prompt["messages"] = messages
    else:
        compiled_prompt = remote_prompt.get_langchain_prompt()
        if not isinstance(compiled_prompt, str):
            raise RuntimeError(
                f"Langfuse prompt '{catalog_entry['name']}' must be a text prompt; "
                f"received {type(remote_prompt).__name__}."
            )
        managed_prompt["template"] = compiled_prompt
    return managed_prompt


def _managed_chat_messages(
    catalog_entry: dict[str, Any],
    remote_prompt: Any,
) -> list[dict[str, str]] | None:
    compiled_prompt = remote_prompt.get_langchain_prompt()
    if isinstance(compiled_prompt, list):
        messages: list[dict[str, str]] = []
        for item in compiled_prompt:
            if not isinstance(item, tuple) or len(item) != 2:
                return None
            role, content = item
            if not isinstance(role, str) or not isinstance(content, str):
                return None
            messages.append(
                {"role": _normalize_role(role), "content": content}
            )
        return messages if messages else None
    if not isinstance(compiled_prompt, str):
        return None

    raw_prompt = getattr(remote_prompt, "prompt", compiled_prompt)
    if not isinstance(raw_prompt, str):
        return None
    try:
        parsed_prompt = ast.literal_eval(raw_prompt)
    except (SyntaxError, ValueError):
        parsed_prompt = None

    expected_variables = catalog_entry.get("variables", [])
    if len(expected_variables) != 1:
        return None
    variable = expected_variables[0]
    placeholder = "{" + variable + "}"
    moustache_placeholder = "{{" + variable + "}}"

    if isinstance(parsed_prompt, list):
        messages = []
        user_message_count = 0
        for item in parsed_prompt:
            if not isinstance(item, dict):
                return None
            role = item.get("role")
            content = item.get("content")
            if not isinstance(role, str) or not isinstance(content, str):
                return None
            normalized_role = _normalize_role(role)
            if normalized_role == "user":
                if content.strip() not in {placeholder, moustache_placeholder}:
                    return None
                content = placeholder
                user_message_count += 1
            elif normalized_role not in {"system", "assistant"}:
                return None
            else:
                content = _escape_template_braces(content)
            messages.append({"role": normalized_role, "content": content})
        return messages if user_message_count == 1 else None

    text_prompt = raw_prompt.strip()
    if text_prompt.endswith(moustache_placeholder):
        text_prompt = text_prompt[: -len(moustache_placeholder)].rstrip()
    elif text_prompt.endswith(placeholder):
        text_prompt = text_prompt[: -len(placeholder)].rstrip()
    elif moustache_placeholder in text_prompt or placeholder in text_prompt:
        return None
    if not text_prompt:
        return None
    return [
        {"role": "system", "content": _escape_template_braces(text_prompt)},
        {"role": "user", "content": placeholder},
    ]


def _normalize_role(role: str) -> str:
    return {"human": "user", "ai": "assistant"}.get(role, role)


def _escape_template_braces(content: str) -> str:
    return content.replace("{", "{{").replace("}", "}}")
