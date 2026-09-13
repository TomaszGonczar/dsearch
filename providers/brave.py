"""Brave Search response contract."""

from providers.contracts import (
    ProviderResponse,
    decode_items,
    degraded_http_response,
    require_list,
    require_mapping,
)

PROVIDER_NAME = "brave"


def parse_response(payload: object, *, status_code: int = 200) -> ProviderResponse:
    """Decode a Brave web-search response without performing network I/O."""

    if status_code != 200:
        return degraded_http_response(PROVIDER_NAME, status_code)
    root = require_mapping(payload, "response")
    web = require_mapping(root.get("web"), "response.web")
    items = require_list(web.get("results"), "response.web.results")
    return decode_items(
        provider=PROVIDER_NAME,
        items=items,
        title_key="title",
        snippet_key="description",
    )
