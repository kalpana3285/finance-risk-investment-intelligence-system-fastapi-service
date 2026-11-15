from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from security.auth import (
    Auth0Authenticator,
    AuthenticationError,
    AuthenticationProviderError,
    Role,
)

NAMESPACE = "https://friis-api"


def _b64url(value: int) -> str:
    encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


@pytest.fixture
def key_pair() -> tuple[str, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_numbers = private_key.public_key().public_numbers()
    jwks_key = {
        "kid": "auth0-test-key",
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(public_numbers.n),
        "e": _b64url(public_numbers.e),
    }
    return private_pem, jwks_key


def _token(private_key: str, **claim_overrides: Any) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": "https://friis-test.us.auth0.com/",
        "aud": "https://api.example.test/friis",
        "sub": "auth0|analyst-123",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        f"{NAMESPACE}/roles": ["analyst"],
        f"{NAMESPACE}/portfolio_ids": [1, 2],
        f"{NAMESPACE}/all_portfolios_access": False,
    }
    claims.update(claim_overrides)
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "auth0-test-key"},
    )


@pytest.fixture
def auth0(
    key_pair: tuple[str, dict[str, str]],
) -> tuple[Auth0Authenticator, str, httpx.AsyncClient]:
    private_key, jwks_key = key_pair

    def handle_jwks(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://friis-test.us.auth0.com/.well-known/jwks.json"
        return httpx.Response(200, json={"keys": [jwks_key]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_jwks))
    authenticator = Auth0Authenticator(
        domain="friis-test.us.auth0.com",
        audience="https://api.example.test/friis",
        client=client,
    )
    return authenticator, private_key, client


@pytest.mark.asyncio
async def test_auth0_token_is_verified_and_namespaced_claims_are_mapped(
    auth0: tuple[Auth0Authenticator, str, httpx.AsyncClient],
) -> None:
    authenticator, private_key, client = auth0
    principal = await authenticator.authenticate(_token(private_key))

    assert principal.subject == "auth0|analyst-123"
    assert principal.roles == frozenset({Role.ANALYST})
    assert principal.portfolio_ids == frozenset({1, 2})
    assert principal.all_portfolios_access is False
    await client.aclose()


@pytest.mark.asyncio
async def test_auth0_rejects_wrong_audience_and_unrecognized_roles(
    auth0: tuple[Auth0Authenticator, str, httpx.AsyncClient],
) -> None:
    authenticator, private_key, client = auth0
    wrong_audience = _token(private_key, aud="https://other.example.test/api")
    with pytest.raises(AuthenticationError):
        await authenticator.authenticate(wrong_audience)

    no_supported_role = _token(
        private_key, **{f"{NAMESPACE}/roles": ["unknown-role"]}
    )
    with pytest.raises(AuthenticationError, match="no supported roles"):
        await authenticator.authenticate(no_supported_role)
    await client.aclose()


@pytest.mark.asyncio
async def test_auth0_accepts_roles_documented_by_supplied_guide(
    key_pair: tuple[str, dict[str, str]],
) -> None:
    private_key, jwks_key = key_pair
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"keys": [jwks_key]})
        )
    )
    authenticator = Auth0Authenticator(
        domain="friis-test.us.auth0.com",
        audience="https://api.example.test/friis",
        client=client,
    )
    admin = await authenticator.authenticate(
        _token(private_key, **{f"{NAMESPACE}/roles": ["admin"]})
    )
    user = await authenticator.authenticate(
        _token(private_key, **{f"{NAMESPACE}/roles": ["user"]})
    )
    assert admin.roles == frozenset({Role.ADMIN})
    assert user.roles == frozenset({Role.USER})
    await client.aclose()


@pytest.mark.asyncio
async def test_auth0_signing_key_outage_is_distinct_from_invalid_token(
    key_pair: tuple[str, dict[str, str]],
) -> None:
    private_key, _ = key_pair
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503))
    )
    authenticator = Auth0Authenticator(
        domain="friis-test.us.auth0.com",
        audience="https://api.example.test/friis",
        client=client,
    )
    with pytest.raises(AuthenticationProviderError):
        await authenticator.authenticate(_token(private_key))
    await client.aclose()


def test_auth0_domain_rejects_urls_with_paths_or_non_host_parts() -> None:
    with pytest.raises(ValueError):
        Auth0Authenticator(
            domain="https://tenant.example.test/path",
            audience="api",
        )
    with pytest.raises(ValueError):
        Auth0Authenticator(
            domain="tenant.example.test:443",
            audience="api",
        )
