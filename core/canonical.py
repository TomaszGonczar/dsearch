"""Deterministic canonicalization for web result URLs."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref",
        "source",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)


class CanonicalizationError(ValueError):
    """Raised when a value cannot identify a public HTTP(S) page."""


def _ensure_scheme(value: str) -> str:
    if value.startswith("//"):
        return f"https:{value}"
    if "://" not in value:
        return f"https://{value}"
    return value


def _canonical_host(hostname: str, port: int | None) -> str:
    host = hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        raise CanonicalizationError("URL must include a hostname")
    rendered_host = f"[{host}]" if ":" in host else host
    if port is None or port in {80, 443}:
        return rendered_host
    return f"{rendered_host}:{port}"


def canonicalize_url(url: str) -> str:
    """Return the stable page identity used by consensus.

    HTTP and HTTPS collapse to HTTPS, host case and ``www.`` are normalized, trailing slashes
    and fragments are removed, known tracking parameters are dropped, and remaining query
    pairs are sorted. Path case is retained because it can be significant on the origin.
    """

    value = url.strip()
    if not value:
        raise CanonicalizationError("URL must not be empty")
    parsed = urlsplit(_ensure_scheme(value))
    if parsed.scheme.lower() not in {"http", "https"}:
        raise CanonicalizationError("URL scheme must be HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise CanonicalizationError("URL must not contain embedded credentials")
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise CanonicalizationError("URL contains an invalid port") from error
    if hostname is None:
        raise CanonicalizationError("URL must include a hostname")

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    ]
    query = urlencode(sorted(query_pairs))
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", _canonical_host(hostname, port), path, query, ""))


def canonicalize(url: str) -> str:
    """Compatibility-sized public name for URL canonicalization."""

    return canonicalize_url(url)
