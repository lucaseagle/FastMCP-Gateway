import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fastmcp_gateway.server import ExpiringJWTVerifier


@pytest.fixture(scope="module")
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return key, public


@pytest.mark.parametrize(
    "change",
    [
        {"exp": None},
        {"exp": 1},
        {"sub": None},
        {"sub": 123},
        {"iss": "https://evil.example"},
        {"aud": "another-service"},
        {"nbf": 9999999999},
        {"iat": 9999999999},
    ],
)
async def test_invalid_claims_fail_closed(keys, change):
    private, public = keys
    claims = {
        "iss": "https://id.example",
        "aud": "gateway",
        "sub": "alice",
        "exp": int(time.time()) + 60,
        "scope": "site:catalog:read",
    }
    claims.update(change)
    claims = {k: v for k, v in claims.items() if v is not None}
    token = jwt.encode(claims, private, algorithm="RS256")
    verifier = ExpiringJWTVerifier(
        public_key=public, issuer="https://id.example", audience="gateway", algorithm="RS256"
    )
    assert await verifier.verify_token(token) is None


async def test_valid_signed_scoped_token(keys):
    private, public = keys
    token = jwt.encode(
        {
            "iss": "https://id.example",
            "aud": "gateway",
            "sub": "alice",
            "exp": int(time.time()) + 60,
            "scope": "site:catalog:read",
        },
        private,
        algorithm="RS256",
    )
    verifier = ExpiringJWTVerifier(
        public_key=public, issuer="https://id.example", audience="gateway", algorithm="RS256"
    )
    result = await verifier.verify_token(token)
    assert result is not None
    assert result.scopes == ["site:catalog:read"]
