"""Optional, privacy-conscious Langfuse tracing for FRIIS."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping

logger = logging.getLogger(__name__)
_client: Any | None = None
_initialization_attempted = False


class _SafeSpan:
    def __init__(self, span: Any, name: str) -> None:
        self._span = span
        self._name = name

    def update(self, **kwargs: Any) -> None:
        try:
            self._span.update(**kwargs)
        except Exception as exc:
            logger.warning(
                "Langfuse observation update failed",
                extra={"observation_name": self._name, "error_type": type(exc).__name__},
            )


@contextmanager
def _safe_context(context: Any, *, name: str) -> Iterator[Any]:
    """Keep SDK exporter/context errors from changing application behavior."""
    try:
        value = context.__enter__()
    except Exception as exc:
        logger.warning(
            "Langfuse context could not be started",
            extra={"observation_name": name, "error_type": type(exc).__name__},
        )
        yield None
        return
    try:
        yield _SafeSpan(value, name) if value is not None else None
    except BaseException as exc:
        try:
            context.__exit__(type(exc), exc, exc.__traceback__)
        except Exception as tracing_exc:
            logger.warning(
                "Langfuse context could not be closed",
                extra={"observation_name": name, "error_type": type(tracing_exc).__name__},
            )
        raise
    else:
        try:
            context.__exit__(None, None, None)
        except Exception as exc:
            logger.warning(
                "Langfuse context could not be closed",
                extra={"observation_name": name, "error_type": type(exc).__name__},
            )


def _get_client() -> Any | None:
    """Load credentials before importing the SDK and initialize it once."""
    global _client, _initialization_attempted
    if _initialization_attempted:
        return _client
    _initialization_attempted = True
    try:
        from dotenv import load_dotenv

        load_dotenv()
        enabled = os.getenv("LANGFUSE_ENABLED", "true").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return None
        if not (
            os.getenv("LANGFUSE_PUBLIC_KEY")
            and os.getenv("LANGFUSE_SECRET_KEY")
        ):
            return None
        from langfuse import get_client

        _client = get_client()
    except Exception as exc:  # tracing must never stop FRIIS workflows
        logger.warning(
            "Langfuse initialization failed; tracing disabled",
            extra={"error_type": type(exc).__name__},
        )
        _client = None
    return _client


def is_tracing_enabled() -> bool:
    return _get_client() is not None


def fetch_prompt(
    *,
    name: str,
    prompt_type: Literal["chat", "text"],
    label: str | None,
) -> Any | None:
    """Fetch a managed prompt when Langfuse is configured."""
    from dotenv import load_dotenv

    load_dotenv(
        dotenv_path=Path(__file__).resolve().parents[1] / ".env",
        override=False,
    )
    enabled = os.getenv("LANGFUSE_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    has_public_key = bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
    has_secret_key = bool(os.getenv("LANGFUSE_SECRET_KEY"))
    if not enabled:
        return None
    if has_public_key != has_secret_key:
        raise RuntimeError(
            "Both LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required "
            "to load managed prompts."
        )
    if not has_public_key:
        return None

    client = _get_client()
    if client is None:
        raise RuntimeError("Langfuse is configured but its client is unavailable.")
    try:
        prompt = client.get_prompt(
            name,
            type=prompt_type,
            label=label,
        )
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            logger.warning(
                "Required Langfuse prompt was not found",
                extra={
                    "prompt_name": name,
                    "prompt_type": prompt_type,
                    "prompt_label": label,
                },
            )
            return None
        logger.error(
            "Langfuse prompt fetch failed",
            extra={
                "prompt_name": name,
                "prompt_type": prompt_type,
                "error_type": type(exc).__name__,
            },
        )
        raise RuntimeError(f"Unable to fetch Langfuse prompt '{name}'.") from exc
    if getattr(prompt, "is_fallback", False):
        raise RuntimeError(f"Langfuse returned a fallback for prompt '{name}'.")
    logger.info(
        "Loaded managed Langfuse prompt",
        extra={
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "prompt_type": prompt_type,
            "prompt_label": label,
        },
    )
    return prompt


@contextmanager
def observation(
    *,
    name: str,
    as_type: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    model: str | None = None,
    trace_context: dict[str, str] | None = None,
) -> Iterator[Any]:
    """Create an observation when configured, otherwise act as a no-op."""
    client = _get_client()
    if client is None:
        with nullcontext(None) as span:
            yield span
        return
    kwargs: dict[str, Any] = {"name": name, "as_type": as_type}
    if input is not None:
        kwargs["input"] = input
    if metadata:
        kwargs["metadata"] = metadata
    if model:
        kwargs["model"] = model
    if trace_context:
        kwargs["trace_context"] = trace_context
    try:
        context = client.start_as_current_observation(**kwargs)
    except Exception as exc:
        logger.warning(
            "Langfuse observation failed",
            extra={"observation_name": name, "error_type": type(exc).__name__},
        )
        context = nullcontext(None)
    with _safe_context(context, name=name) as span:
        yield span


@contextmanager
def trace_attributes(
    *,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    client = _get_client()
    if client is None:
        yield
        return
    try:
        from langfuse import propagate_attributes

        context = propagate_attributes(
            session_id=session_id,
            tags=tags,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Langfuse trace attributes failed",
            extra={"error_type": type(exc).__name__},
        )
        context = nullcontext()
    with _safe_context(context, name="trace-attributes"):
        yield


def record_scores(
    *,
    trace_id: str,
    scores: Mapping[str, float],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Attach numeric evaluation scores without affecting application results."""
    client = _get_client()
    if client is None:
        return

    for name, value in scores.items():
        try:
            client.create_score(
                name=name,
                value=float(value),
                trace_id=trace_id,
                data_type="NUMERIC",
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning(
                "Langfuse score creation failed",
                extra={
                    "score_name": name,
                    "error_type": type(exc).__name__,
                },
            )


def flush() -> None:
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:
            logger.warning(
                "Langfuse flush failed", extra={"error_type": type(exc).__name__}
            )
