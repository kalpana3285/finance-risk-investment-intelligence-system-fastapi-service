"""OAuth token exchange routes for Swagger UI."""

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Form, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_auth0_token_router(
    *,
    domain: str,
    audience: str,
    client_id: str,
) -> APIRouter:
    router = APIRouter()
    normalized_domain = domain.strip().removeprefix("https://").removesuffix("/")
    token_url = f"https://{normalized_domain}/oauth/token"

    @router.post("/auth/token", include_in_schema=False)
    async def exchange_authorization_code(
        grant_type: Annotated[str, Form()],
        client_id_from_request: Annotated[str, Form(alias="client_id")],
        code: Annotated[str, Form()],
        redirect_uri: Annotated[str, Form()],
        code_verifier: Annotated[str, Form()],
    ) -> Response:
        if grant_type != "authorization_code":
            return _oauth_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                error="unsupported_grant_type",
                description="Only authorization_code grant is supported.",
            )
        if client_id_from_request != client_id:
            return _oauth_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                error="invalid_client",
                description="OAuth client ID does not match the configured client.",
            )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                token_response = await client.post(
                    token_url,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": client_id,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "code_verifier": code_verifier,
                        "audience": audience,
                    },
                )
        except httpx.TimeoutException as exc:
            logger.warning(
                "Auth0 token exchange timed out",
                extra={
                    "event": "auth0.token_exchange.failed",
                    "error_type": type(exc).__name__,
                },
            )
            return _oauth_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                error="temporarily_unavailable",
                description="Auth0 token exchange is temporarily unavailable.",
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Auth0 token exchange failed",
                extra={
                    "event": "auth0.token_exchange.failed",
                    "error_type": type(exc).__name__,
                },
            )
            return _oauth_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                error="temporarily_unavailable",
                description="Auth0 token exchange is temporarily unavailable.",
            )

        if token_response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.warning(
                "Auth0 token exchange returned a server error",
                extra={
                    "event": "auth0.token_exchange.failed",
                    "status_code": token_response.status_code,
                },
            )
            return _oauth_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                error="temporarily_unavailable",
                description="Auth0 token exchange is temporarily unavailable.",
            )

        return Response(
            content=token_response.content,
            status_code=token_response.status_code,
            media_type="application/json",
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    return router


def _oauth_error(
    *,
    status_code: int,
    error: str,
    description: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
