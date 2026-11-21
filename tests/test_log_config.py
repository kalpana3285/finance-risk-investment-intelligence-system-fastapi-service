import logging

import pytest

from config.log_config import ContextFormatter, setup_logging


def test_context_formatter_includes_trace_id() -> None:
    record = logging.LogRecord(
        name="friis",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Query processing started",
        args=(),
        exc_info=None,
    )
    record.query_id = "query-1"
    record.trace_id = "a" * 32

    formatted = ContextFormatter("%(message)s").format(record)

    assert '"query_id": "query-1"' in formatted
    assert f'"trace_id": "{"a" * 32}"' in formatted


def test_vercel_logging_uses_stdout_without_opening_a_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_handlers: list[logging.Handler] = []

    def capture_basic_config(**kwargs: object) -> None:
        handlers = kwargs["handlers"]
        assert isinstance(handlers, list)
        configured_handlers.extend(handlers)

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(logging, "basicConfig", capture_basic_config)

    setup_logging()

    assert len(configured_handlers) == 1
    assert type(configured_handlers[0]) is logging.StreamHandler
