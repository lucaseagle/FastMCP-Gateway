import pytest

from fastmcp_gateway.discovery import discover


@pytest.mark.parametrize(
    "har", [[], {"log": []}, {"log": {"entries": {}}}, {"log": {"entries": None}}]
)
def test_malformed_har_envelopes_are_controlled_errors(har):
    with pytest.raises(ValueError):
        discover(har, "https://example.com", "example")


def test_malformed_entries_cannot_crash_discovery():
    har = {
        "log": {
            "entries": [
                None,
                {"request": None},
                {"request": {"method": "GET", "url": 123}},
                {"request": {"method": "GET", "url": "https://example.com/"}, "response": None},
            ]
        }
    }
    assert discover(har, "https://example.com", "example")["sites"][0]["operations"] == []
