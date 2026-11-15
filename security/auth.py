"""Authentication contracts and request dependency for protected API routes."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Protocol
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"
    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE_REVIEWER = "compliance_reviewer"
    OPERATOR = "operator"


@dataclass(frozen=True)
class Principal:
    """Verified identity; portfolio access is denied unless explicitly granted."""

    subject: str
    roles: frozenset[Role]
    portfolio_ids: frozenset[int] = frozenset()
    all_portfolios_access: bool = False


class AuthenticationError(Exception):
    """Raised when a configured identity provider rejects a bearer token."""


class AuthenticationProviderError(Exception):
    """Raised when the external identity provider cannot verify a token."""


class Authenticator(Protocol):
    async def authenticate(self, token: str) -> Principal: ...


class OIDCAuthenticator:
    """Verify RS256 access tokens against an external OIDC JWKS endpoint."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        roles_claim: str = "roles",
        portfolio_ids_claim: str = "portfolio_ids",
        all_portfolios_claim: str = "all_portfolios_access",
        cache_seconds: int = 300,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not issuer or not audience:
            raise ValueError("OIDC issuer and audience are required")
        parsed_jwks_url = urlparse(jwks_url)
        if parsed_jwks_url.scheme != "https" or not parsed_jwks_url.netloc:
            raise ValueError("OIDC JWKS URL must be an absolute HTTPS URL")
        if cache_seconds <= 0 or timeout_seconds <= 0:
            raise ValueError("OIDC cache and timeout values must be positive")

        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self.roles_claim = roles_claim
        self.portfolio_ids_claim = portfolio_ids_claim
        self.all_portfolios_claim = all_portfolios_claim
        self.cache_seconds = cache_seconds
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None
        self._jwks: list[dict[str, object]] = []
        self._jwks_expires_at = 0.0
        self._jwks_lock = asyncio.Lock()

    async def authenticate(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise AuthenticationError("Unsupported access token algorithm")
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise AuthenticationError("Access token has no key identifier")
        except JWTError as exc:
            raise AuthenticationError("Malformed access token") from exc

        keys = await self._get_signing_keys()
        matching_key = next(
            (
                key
                for key in keys
                if key.get("kid") == kid
                and key.get("kty") == "RSA"
                and key.get("use", "sig") == "sig"
                and key.get("alg", "RS256") == "RS256"
            ),
            None,
        )
        if matching_key is None:
            keys = await self._get_signing_keys(force_refresh=True)
            matching_key = next(
                (
                    key
                    for key in keys
                    if key.get("kid") == kid
                    and key.get("kty") == "RSA"
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", "RS256") == "RS256"
                ),
                None,
            )
        if matching_key is None:
            raise AuthenticationError("No matching signing key was found")

        try:
            public_key = jwk.construct(matching_key, algorithm="RS256").to_pem()
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require_exp": True,
                    "require_iat": True,
                    "require_sub": True,
                },
            )
        except (JWTError, ValueError, TypeError) as exc:
            raise AuthenticationError("Access token validation failed") from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Access token subject is invalid")
        roles = self._extract_roles(claims)
        if not roles:
            raise AuthenticationError("Access token has no supported roles")
        portfolio_ids = self._extract_portfolio_ids(claims)
        all_portfolios_access = self._extract_boolean_claim(
            claims, self.all_portfolios_claim
        )
        return Principal(
            subject=subject,
            roles=roles,
            portfolio_ids=portfolio_ids,
            all_portfolios_access=all_portfolios_access,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _extract_roles(self, claims: dict[str, object]) -> frozenset[Role]:
        value = self._claim(claims, self.roles_claim)
        raw_roles = [value] if isinstance(value, str) else value
        if not isinstance(raw_roles, list):
            return frozenset()
        roles: set[Role] = set()
        for raw_role in raw_roles:
            if not isinstance(raw_role, str):
                continue
            try:
                roles.add(Role(raw_role))
            except ValueError:
                continue
        return frozenset(roles)

    def _extract_portfolio_ids(self, claims: dict[str, object]) -> frozenset[int]:
        value = self._claim(claims, self.portfolio_ids_claim)
        if not isinstance(value, list):
            return frozenset()
        portfolio_ids: set[int] = set()
        for raw_id in value:
            if isinstance(raw_id, int) and not isinstance(raw_id, bool) and raw_id > 0:
                portfolio_ids.add(raw_id)
        return frozenset(portfolio_ids)

    def _extract_boolean_claim(
        self, claims: dict[str, object], claim_name: str
    ) -> bool:
        return self._claim(claims, claim_name) is True

    @staticmethod
    def _claim(claims: dict[str, object], claim_name: str) -> object:
        if claim_name in claims:
            return claims[claim_name]
        value: object = claims
        for part in claim_name.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def _get_signing_keys(
        self, *, force_refresh: bool = False
    ) -> list[dict[str, object]]:
        async with self._jwks_lock:
            if not force_refresh and time.monotonic() < self._jwks_expires_at:
                return self._jwks
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
            try:
                response = await self._client.get(self.jwks_url)
                response.raise_for_status()
                document = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise AuthenticationProviderError(
                    "Identity provider signing keys are unavailable"
                ) from exc
            raw_keys = document.get("keys") if isinstance(document, dict) else None
            if not isinstance(raw_keys, list):
                raise AuthenticationProviderError(
                    "Identity provider returned an invalid JWKS document"
                )
            keys = [key for key in raw_keys if isinstance(key, dict)]
            if not keys:
                raise AuthenticationProviderError(
                    "Identity provider returned no signing keys"
                )
            self._jwks = keys
            self._jwks_expires_at = time.monotonic() + self.cache_seconds
            return self._jwks


class Auth0Authenticator(OIDCAuthenticator):
    """Auth0-specific RS256 verifier using the tenant's issuer and JWKS URLs."""

    def __init__(
        self,
        *,
        domain: str,
        audience: str,
        roles_claim: str = "https://friis-api/roles",
        portfolio_ids_claim: str = "https://friis-api/portfolio_ids",
        all_portfolios_claim: str = "https://friis-api/all_portfolios_access",
        cache_seconds: int = 300,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        normalized_domain = domain.strip().removeprefix("https://").removesuffix("/")
        parsed_domain = urlparse(f"https://{normalized_domain}")
        if (
            not normalized_domain
            or parsed_domain.hostname is None
            or parsed_domain.path
            or parsed_domain.query
            or parsed_domain.fragment
            or parsed_domain.username
            or parsed_domain.password
            or parsed_domain.port is not None
        ):
            raise ValueError("Auth0 domain must be a hostname without a URL path")
        super().__init__(
            issuer=f"https://{normalized_domain}/",
            audience=audience,
            jwks_url=f"https://{normalized_domain}/.well-known/jwks.json",
            roles_claim=roles_claim,
            portfolio_ids_claim=portfolio_ids_claim,
            all_portfolios_claim=all_portfolios_claim,
            cache_seconds=cache_seconds,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        self.domain = normalized_domain


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    authenticator: Authenticator | None = getattr(
        request.app.state, "authenticator", None
    )
    if authenticator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured.",
        )
    try:
        return await authenticator.authenticate(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthenticationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provider is temporarily unavailable.",
        ) from exc


def require_any_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[Principal]]:
    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if principal.roles.isdisjoint(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The caller does not have the required role.",
            )
        return principal

    return dependency
