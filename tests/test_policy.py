import pytest


def test_private_network_requires_explicit_site_policy():
    from fastmcp_gateway.policy import check_address

    with pytest.raises(ValueError, match="address"):
        check_address("10.1.2.3", [], development=False)
    assert check_address("10.1.2.3", ["10.1.2.0/24"], development=False) == "10.1.2.3"


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "224.0.0.1",
        "100.100.100.200",
        "::ffff:127.0.0.1",
    ],
)
def test_sensitive_addresses_cannot_be_authorized_by_broad_network(address):
    from fastmcp_gateway.policy import check_address

    with pytest.raises(ValueError):
        check_address(address, ["0.0.0.0/0", "::/0"], development=False)


def test_public_addresses_are_allowed():
    from fastmcp_gateway.policy import check_address

    assert check_address("93.184.216.34", [], development=False) == "93.184.216.34"
