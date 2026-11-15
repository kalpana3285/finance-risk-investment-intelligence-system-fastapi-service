import logging

import pytest

from config.log_config import setup_logging


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
