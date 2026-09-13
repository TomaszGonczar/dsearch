"""Tavily response contract.

Index independence is intentionally absent here. It is load-bearing configuration in
``providers/registry.json`` and must never be inferred from a response payload.
"""

from providers.contracts import (
    ProviderResponse,
    decode_items,
    degraded_http_response,
    require_list,
    require_mapping,
)

PROVIDER_NAME = "tavily"


def parse_response(payload: object, *, status_code: int = 200) -> ProviderResponse:
    """Decode a Tavily search response without performing network I/O."""

    if status_code != 200:
        return degraded_http_response(PROVIDER_NAME, status_code)
    root = require_mapping(payload, "response")
    items = require_list(root.get("results"), "response.results")
    return decode_items(
        provider=PROVIDER_NAME,
        items=items,
        title_key="title",
        snippet_key="content",
    )
