"""Attributed, byte-stable search response envelopes."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.budget import AppliedBudget
from core.canonical import canonicalize_url
from core.consensus import ConsensusReport, ConsensusStatus, compute_consensus
from providers.contracts import ProviderError, ProviderResponse, ProviderStatus, SearchResult
from providers.registry import ProviderDeclaration


class EnvelopeError(ValueError):
    """Raised when provider outcomes contradict the attempted-search record."""


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """An error attributed to exactly one attempted provider."""

    provider: str
    code: str
    message: str

    def to_data(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class EnvelopeResult:
    """One canonical page with every provider attribution retained."""

    url: str
    title: str
    snippet: str | None
    providers: tuple[str, ...]
    independent_providers: tuple[str, ...]

    def to_data(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "providers": list(self.providers),
            "independent_providers": list(self.independent_providers),
        }


@dataclass(frozen=True, slots=True)
class SearchEnvelope:
    """The complete deterministic outcome of a search attempt."""

    query: str
    providers_attempted: tuple[str, ...]
    providers_succeeded: tuple[str, ...]
    errors: tuple[ProviderFailure, ...]
    results: tuple[EnvelopeResult, ...]
    consensus: ConsensusReport
    warnings: tuple[str, ...]
    degraded: bool
    budget: AppliedBudget
    schema_version: int = 1

    def to_data(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query": self.query,
            "providers_attempted": list(self.providers_attempted),
            "providers_succeeded": list(self.providers_succeeded),
            "errors": {failure.provider: failure.to_data() for failure in self.errors},
            "results": [result.to_data() for result in self.results],
            "consensus": self.consensus.to_data(),
            "warnings": list(self.warnings),
            "degraded": self.degraded,
            "budget": self.budget.to_data(),
        }

    def to_bytes(self) -> bytes:
        """Serialize without clock, locale, whitespace, or insertion-order dependence."""

        return json.dumps(
            self.to_data(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


def _validate_response(response: ProviderResponse) -> None:
    if response.status is ProviderStatus.DEGRADED and response.results:
        raise EnvelopeError(f"degraded provider {response.provider!r} cannot carry results")
    if response.status is ProviderStatus.EMPTY and response.results:
        raise EnvelopeError(f"empty provider {response.provider!r} cannot carry results")
    if response.status is ProviderStatus.OK and not response.results:
        raise EnvelopeError(f"successful provider {response.provider!r} must carry results")
    if response.status is not ProviderStatus.DEGRADED and response.error is not None:
        raise EnvelopeError(f"successful provider {response.provider!r} cannot carry an error")


def _indexed_responses(
    attempted: tuple[str, ...], responses: Sequence[ProviderResponse]
) -> dict[str, ProviderResponse]:
    indexed: dict[str, ProviderResponse] = {}
    for response in responses:
        if not response.provider:
            raise EnvelopeError("provider name must not be empty")
        if response.provider not in attempted:
            raise EnvelopeError(f"provider {response.provider!r} was not recorded as attempted")
        if response.provider in indexed:
            raise EnvelopeError(f"provider {response.provider!r} produced duplicate outcomes")
        _validate_response(response)
        indexed[response.provider] = response
    return indexed


def _failure(provider: str, error: ProviderError | None) -> ProviderFailure:
    if error is None:
        return ProviderFailure(
            provider=provider,
            code="unknown_provider_failure",
            message="provider degraded without an attributed error",
        )
    return ProviderFailure(provider=provider, code=error.code, message=error.message)


def _merge_results(
    responses: Mapping[str, ProviderResponse], consensus: ConsensusReport
) -> tuple[EnvelopeResult, ...]:
    grouped: dict[str, list[tuple[str, SearchResult]]] = {}
    for provider, response in sorted(responses.items()):
        if response.status is ProviderStatus.DEGRADED:
            continue
        for result in response.results:
            canonical_url = canonicalize_url(result.url)
            grouped.setdefault(canonical_url, []).append((provider, result))

    eligible = frozenset(consensus.eligible_providers)
    merged: list[EnvelopeResult] = []
    for canonical_url, entries in sorted(grouped.items()):
        providers = tuple(sorted({provider for provider, _result in entries}))
        _representative_provider, representative = min(
            entries,
            key=lambda entry: (
                entry[0],
                entry[1].title,
                entry[1].snippet or "",
                entry[1].url,
            ),
        )
        merged.append(
            EnvelopeResult(
                url=canonical_url,
                title=representative.title,
                snippet=representative.snippet,
                providers=providers,
                independent_providers=tuple(
                    provider for provider in providers if provider in eligible
                ),
            )
        )
    return tuple(merged)


def build_envelope(
    *,
    query: str,
    providers_attempted: Sequence[str],
    responses: Sequence[ProviderResponse],
    registry: Mapping[str, ProviderDeclaration],
    budget: AppliedBudget,
    warnings: Sequence[str] = (),
) -> SearchEnvelope:
    """Build an attributed envelope without I/O, clocks, or order-dependent output."""

    if not query:
        raise EnvelopeError("query must not be empty")
    if any(not provider for provider in providers_attempted):
        raise EnvelopeError("attempted provider names must not be empty")
    attempted = tuple(sorted(set(providers_attempted)))
    indexed = _indexed_responses(attempted, responses)
    succeeded = tuple(
        provider
        for provider, response in sorted(indexed.items())
        if response.status in {ProviderStatus.OK, ProviderStatus.EMPTY}
    )

    failures: list[ProviderFailure] = []
    for provider in attempted:
        response = indexed.get(provider)
        if response is None:
            failures.append(
                ProviderFailure(
                    provider=provider,
                    code="missing_response",
                    message="attempted provider produced no outcome",
                )
            )
        elif response.status is ProviderStatus.DEGRADED:
            failures.append(_failure(provider, response.error))
    error_tuple = tuple(failures)

    provider_urls = {
        provider: tuple(result.url for result in indexed[provider].results)
        for provider in succeeded
    }
    consensus = compute_consensus(provider_urls, registry)
    results = _merge_results(indexed, consensus)

    warning_set = set(warnings)
    warning_set.update(f"provider_degraded:{failure.provider}" for failure in error_tuple)
    if not results:
        if succeeded:
            warning_set.add("zero_results:providers_returned_empty")
        else:
            warning_set.add("zero_results:no_provider_succeeded")
    if consensus.status is ConsensusStatus.UNAVAILABLE:
        warning_set.add("consensus_unavailable:fewer_than_two_independent_providers")
    elif consensus.rate == 0.0 and results:
        warning_set.add("consensus_rate_zero:disjoint_results")

    return SearchEnvelope(
        query=query,
        providers_attempted=attempted,
        providers_succeeded=succeeded,
        errors=error_tuple,
        results=results,
        consensus=consensus,
        warnings=tuple(sorted(warning_set)),
        degraded=bool(error_tuple) or consensus.status is ConsensusStatus.UNAVAILABLE,
        budget=budget,
    )
