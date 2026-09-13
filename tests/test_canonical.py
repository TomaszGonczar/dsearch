"""Canonical URL identity is deterministic and page-oriented."""

import pytest

from core.canonical import CanonicalizationError, canonicalize_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/page?utm_source=test", "https://example.com/page"),
        ("https://example.com/page?UTM_Source=test", "https://example.com/page"),
        ("https://www.example.com/page", "https://example.com/page"),
        ("http://example.com/page", "https://example.com/page"),
        ("example.com/page", "https://example.com/page"),
        ("https://example.com/page/", "https://example.com/page"),
        ("HTTPS://WWW.Example.COM/Case", "https://example.com/Case"),
        ("https://example.com/?b=2&a=1", "https://example.com?a=1&b=2"),
        ("https://example.com/page#section", "https://example.com/page"),
        ("https://example.com:443/page", "https://example.com/page"),
        ("http://example.com:80/page", "https://example.com/page"),
    ],
)
def test_canonicalization(url: str, expected: str) -> None:
    assert canonicalize_url(url) == expected


def test_query_order_and_tracking_decoration_have_one_identity() -> None:
    urls = {
        canonicalize_url("https://www.example.com/docs/?b=2&utm_medium=agent&a=1"),
        canonicalize_url("http://example.com/docs?a=1&b=2#top"),
    }

    assert urls == {"https://example.com/docs?a=1&b=2"}


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("", "must not be empty"),
        ("ftp://example.com/file", "scheme must be HTTP or HTTPS"),
        ("https://user:secret@example.com", "must not contain embedded credentials"),
        ("https://example.com:invalid", "invalid port"),
        ("https:///missing-host", "must include a hostname"),
    ],
)
def test_invalid_web_urls_fail_loudly(url: str, message: str) -> None:
    with pytest.raises(CanonicalizationError, match=message):
        canonicalize_url(url)
