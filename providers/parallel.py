"""Parallel Search response contract."""

from collections.abc import Sequence
from typing import cast

from providers.contracts import (
    ContractViolation,
    ProviderResponse,
    ProviderStatus,
    SearchResult,
    degraded_http_response,
    require_list,
    require_mapping,
    require_text,
)

PROVIDER_NAME = "parallel"


def parse_response(payload: object, *, status_code: int = 200) -> ProviderResponse:
    """Decode a Parallel search response without performing network I/O."""

    if status_code != 200:
        return degraded_http_response(PROVIDER_NAME, status_code)
    root = require_mapping(payload, "response")
    items = require_list(root.get("results"), "response.results")
    results: list[SearchResult] = []
    for index, raw_item in enumerate(items):
        path = f"response.results[{index}]"
        item = require_mapping(raw_item, path)
        raw_excerpts = require_list(item.get("excerpts"), f"{path}.excerpts")
        if not all(isinstance(excerpt, str) for excerpt in raw_excerpts):
            raise ContractViolation(f"{path}.excerpts must contain only strings")
        excerpts = cast(Sequence[str], raw_excerpts)
        snippet = "\n".join(excerpts) or None
        results.append(
            SearchResult(
                url=require_text(item.get("url"), f"{path}.url"),
                title=require_text(item.get("title"), f"{path}.title"),
                snippet=snippet,
            )
        )
    status = ProviderStatus.OK if results else ProviderStatus.EMPTY
    return ProviderResponse(provider=PROVIDER_NAME, status=status, results=tuple(results))
