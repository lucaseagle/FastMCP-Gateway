import pytest
from pydantic import ValidationError


def site(**overrides):
    return dict(
        name="catalog",
        base_url="https://example.com",
        operations=[dict(name="search", path="/api/search", description="Search catalog")],
        **overrides,
    )


def test_unapproved_import_cannot_be_loaded():
    from fastmcp_gateway.config import GatewayConfig

    with pytest.raises(ValidationError, match="approved"):
        GatewayConfig.model_validate({"sites": [site(approved=False)]})


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "file:///etc/passwd",
        "https://169.254.169.254",
    ],
)
def test_invalid_origins_rejected(url):
    from fastmcp_gateway.config import GatewayConfig

    data = site(approved=True)
    data["base_url"] = url
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate({"sites": [data]})


@pytest.mark.parametrize(
    "path", ["//evil.com", "/../secret", "/%2e%2e/secret", "/api?token=x", "/api#fragment", "/a\\b"]
)
def test_ambiguous_operation_paths_rejected(path):
    from fastmcp_gateway.config import Operation

    with pytest.raises(ValidationError):
        Operation(name="read", path=path, description="Read approved data")


def test_production_settings_require_identity_provider():
    from fastmcp_gateway.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="production")
