"""Compatibility accessors for the application's manual Langfuse tracing."""

from services.langfuse_tracing import flush, is_tracing_enabled


class LangfuseCallbackManager:
    """Legacy facade; FRIIS traces explicit observations to avoid prompt capture."""

    def get_callback_handler(self, **_kwargs: object) -> None:
        """Return no auto-capture handler; use explicit observations instead."""
        return None

    def flush(self) -> None:
        """Export pending observations during orderly shutdown."""
        flush()


_manager = LangfuseCallbackManager()


def get_langfuse_manager() -> LangfuseCallbackManager:
    return _manager


__all__ = ["LangfuseCallbackManager", "get_langfuse_manager", "is_tracing_enabled"]
