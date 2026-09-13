"""Shared, typed response contract for provider adapters."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class ProviderStatus(StrEnum):
    """Outcome of one provider attempt."""

    OK = "ok"
    EMPTY = "empty"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Provider-neutral fields retained from a search result."""

    url: str
    title: str
    snippet: str | None


@dataclass(frozen=True, slots=True)
class ProviderError:
    """A structured provider failure that callers can report without guessing."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Decoded outcome from exactly one named provider."""

    provider: str
    status: ProviderStatus
    results: tuple[SearchResult, ...]
    error: ProviderError | None = None


class ContractViolation(ValueError):
    """Raised when a successful response no longer matches its recorded contract."""


def require_mapping(value: object, path: str) -> Mapping[str, object]:
    """Return a mapping or raise a path-specific contract error."""

    if not isinstance(value, Mapping):
        raise ContractViolation(f"{path} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ContractViolation(f"{path} must have string keys")
    return value


def require_list(value: object, path: str) -> Sequence[object]:
    """Return a JSON-style list or raise a path-specific contract error."""

    if not isinstance(value, list):
        raise ContractViolation(f"{path} must be an array")
    return value


def require_text(value: object, path: str) -> str:
    """Return a non-empty string or raise a path-specific contract error."""

    if not isinstance(value, str) or not value:
        raise ContractViolation(f"{path} must be a non-empty string")
    return value


def optional_text(value: object, path: str) -> str | None:
    """Decode an optional string while still rejecting shape drift."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractViolation(f"{path} must be a string or null")
    return value


def decode_items(
    *,
    provider: str,
    items: Sequence[object],
    title_key: str,
    snippet_key: str,
) -> ProviderResponse:
    """Decode the common object-list result shape used by three providers."""

    results: list[SearchResult] = []
    for index, raw_item in enumerate(items):
        path = f"response.results[{index}]"
        item = require_mapping(raw_item, path)
        results.append(
            SearchResult(
                url=require_text(item.get("url"), f"{path}.url"),
                title=require_text(item.get(title_key), f"{path}.{title_key}"),
                snippet=optional_text(item.get(snippet_key), f"{path}.{snippet_key}"),
            )
        )
    status = ProviderStatus.OK if results else ProviderStatus.EMPTY
    return ProviderResponse(provider=provider, status=status, results=tuple(results))


def degraded_http_response(provider: str, status_code: int) -> ProviderResponse:
    """Convert a non-success HTTP status into an explicit degraded outcome."""

    if status_code == 429:
        error = ProviderError(code="rate_limited", message="provider returned HTTP 429")
    else:
        error = ProviderError(code="http_error", message=f"provider returned HTTP {status_code}")
    return ProviderResponse(
        provider=provider,
        status=ProviderStatus.DEGRADED,
        results=(),
        error=error,
    )
