"""Exa response contract."""

from providers.contracts import (
    ProviderResponse,
    decode_items,
    degraded_http_response,
    require_list,
    require_mapping,
)

PROVIDER_NAME = "exa"


def parse_response(payload: object, *, status_code: int = 200) -> ProviderResponse:
    """Decode an Exa search response without performing network I/O."""

    if status_code != 200:
        return degraded_http_response(PROVIDER_NAME, status_code)
    root = require_mapping(payload, "response")
    items = require_list(root.get("results"), "response.results")
    return decode_items(
        provider=PROVIDER_NAME,
        items=items,
        title_key="title",
        snippet_key="text",
    )
