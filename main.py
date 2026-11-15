"""ASGI entry point configured from the deployment environment."""

from app.factory import create_runtime_app

app = create_runtime_app()
