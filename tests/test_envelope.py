"""Attributed envelopes remain explicit and byte-stable."""

import random

import pytest

from core.budget import select_budget
from core.consensus import ConsensusStatus
from core.envelope import EnvelopeError, build_envelope
from providers.contracts import (
    ProviderError,
    ProviderResponse,
    ProviderStatus,
    SearchResult,
)
from providers.registry import load_registry


def result(url: str, title: str) -> SearchResult:
    return SearchResult(url=url, title=title, snippet=f"Snippet for {title}")


def response(provider: str, results: list[SearchResult]) -> ProviderResponse:
    return ProviderResponse(
        provider=provider,
        status=ProviderStatus.OK if results else ProviderStatus.EMPTY,
        results=tuple(results),
    )


def build(responses: list[ProviderResponse]) -> bytes:
    return build_envelope(
        query="deterministic query",
        providers_attempted=[item.provider for item in responses],
        responses=responses,
        registry=load_registry(),
        budget=select_budget(context_used=2_000, context_limit=10_000),
    ).to_bytes()


def test_shuffling_results_produces_identical_envelope_bytes() -> None:
    randomizer = random.Random(11)
    brave_results = [
        result("https://example.com/?utm_source=brave", "Shared from Brave"),
        result("https://brave.example", "Brave only"),
    ]
    exa_results = [
        result("http://www.example.com", "Shared from Exa"),
        result("https://exa.example", "Exa only"),
    ]
    expected = build([response("brave", brave_results), response("exa", exa_results)])

    for _ in range(50):
        shuffled_brave = randomizer.sample(brave_results, len(brave_results))
        shuffled_exa = randomizer.sample(exa_results, len(exa_results))
        shuffled_responses = [
            response("brave", shuffled_brave),
            response("exa", shuffled_exa),
        ]
        randomizer.shuffle(shuffled_responses)
        assert build(shuffled_responses) == expected


def test_empty_success_is_an_attributed_outcome_not_null() -> None:
    envelope = build_envelope(
        query="nothing found",
        providers_attempted=["brave", "exa"],
        responses=[response("brave", []), response("exa", [])],
        registry=load_registry(),
        budget=select_budget(context_used=0, context_limit=10_000),
    )
    data = envelope.to_data()

    assert data["providers_succeeded"] == ["brave", "exa"]
    assert data["errors"] == {}
    assert data["results"] == []
    assert isinstance(data["consensus"], dict)
    assert data["consensus"]["rate"] == 0.0
    assert data["warnings"] == ["zero_results:providers_returned_empty"]
    assert data["degraded"] is False


def test_missing_and_rate_limited_providers_degrade_with_causes() -> None:
    rate_limited = ProviderResponse(
        provider="brave",
        status=ProviderStatus.DEGRADED,
        results=(),
        error=ProviderError(code="rate_limited", message="provider returned HTTP 429"),
    )
    envelope = build_envelope(
        query="failed search",
        providers_attempted=["brave", "exa"],
        responses=[rate_limited],
        registry=load_registry(),
        budget=select_budget(context_used=9_000, context_limit=10_000),
    )
    data = envelope.to_data()

    assert data["providers_succeeded"] == []
    assert data["errors"] == {
        "brave": {"code": "rate_limited", "message": "provider returned HTTP 429"},
        "exa": {"code": "missing_response", "message": "attempted provider produced no outcome"},
    }
    assert data["warnings"] == [
        "consensus_unavailable:fewer_than_two_independent_providers",
        "provider_degraded:brave",
        "provider_degraded:exa",
        "zero_results:no_provider_succeeded",
    ]
    assert data["degraded"] is True


def test_disjoint_results_are_reported_as_measured_zero() -> None:
    envelope = build_envelope(
        query="disjoint",
        providers_attempted=["brave", "exa"],
        responses=[
            response("brave", [result("https://brave.example", "Brave")]),
            response("exa", [result("https://exa.example", "Exa")]),
        ],
        registry=load_registry(),
        budget=select_budget(context_used=0, context_limit=10_000),
    )

    assert envelope.consensus.status is ConsensusStatus.MEASURED
    assert envelope.consensus.rate == 0.0
    assert envelope.warnings == ("consensus_rate_zero:disjoint_results",)
    assert envelope.degraded is False


def test_envelope_records_applied_context_budget() -> None:
    envelope = build_envelope(
        query="budget",
        providers_attempted=["brave"],
        responses=[response("brave", [result("https://example.com", "Result")])],
        registry=load_registry(),
        budget=select_budget(context_used=95, context_limit=100),
    )

    assert envelope.to_data()["budget"] == {
        "level": "critical",
        "max_bytes": 2_048,
        "requested_bytes": 16_384,
        "context_used": 95,
        "context_limit": 100,
        "usage_basis_points": 9_500,
    }


def test_response_from_unattempted_provider_fails_loudly() -> None:
    with pytest.raises(EnvelopeError, match="not recorded as attempted"):
        build_envelope(
            query="invalid",
            providers_attempted=["brave"],
            responses=[response("exa", [result("https://example.com", "Result")])],
            registry=load_registry(),
            budget=select_budget(context_used=0, context_limit=100),
        )


def test_duplicate_provider_outcomes_fail_loudly() -> None:
    outcome = response("brave", [result("https://example.com", "Result")])
    with pytest.raises(EnvelopeError, match="duplicate outcomes"):
        build_envelope(
            query="invalid",
            providers_attempted=["brave"],
            responses=[outcome, outcome],
            registry=load_registry(),
            budget=select_budget(context_used=0, context_limit=100),
        )


@pytest.mark.parametrize(
    ("query", "attempted", "outcomes", "message"),
    [
        ("", ["brave"], [], "query must not be empty"),
        ("query", [""], [], "attempted provider names must not be empty"),
        (
            "query",
            ["brave"],
            [ProviderResponse(provider="", status=ProviderStatus.EMPTY, results=())],
            "provider name must not be empty",
        ),
    ],
)
def test_incomplete_attempt_identity_fails_loudly(
    query: str,
    attempted: list[str],
    outcomes: list[ProviderResponse],
    message: str,
) -> None:
    with pytest.raises(EnvelopeError, match=message):
        build_envelope(
            query=query,
            providers_attempted=attempted,
            responses=outcomes,
            registry=load_registry(),
            budget=select_budget(context_used=0, context_limit=100),
        )


def test_degraded_outcome_without_error_gets_an_explicit_unknown_cause() -> None:
    envelope = build_envelope(
        query="unknown failure",
        providers_attempted=["brave"],
        responses=[
            ProviderResponse(
                provider="brave",
                status=ProviderStatus.DEGRADED,
                results=(),
            )
        ],
        registry=load_registry(),
        budget=select_budget(context_used=0, context_limit=100),
    )

    assert envelope.to_data()["errors"] == {
        "brave": {
            "code": "unknown_provider_failure",
            "message": "provider degraded without an attributed error",
        }
    }


@pytest.mark.parametrize(
    "invalid_response",
    [
        ProviderResponse(
            provider="brave",
            status=ProviderStatus.DEGRADED,
            results=(result("https://example.com", "Result"),),
        ),
        ProviderResponse(
            provider="brave",
            status=ProviderStatus.EMPTY,
            results=(result("https://example.com", "Result"),),
        ),
        ProviderResponse(provider="brave", status=ProviderStatus.OK, results=()),
        ProviderResponse(
            provider="brave",
            status=ProviderStatus.EMPTY,
            results=(),
            error=ProviderError(code="impossible", message="error on success"),
        ),
    ],
)
def test_contradictory_provider_outcome_fails_loudly(
    invalid_response: ProviderResponse,
) -> None:
    with pytest.raises(EnvelopeError):
        build_envelope(
            query="invalid",
            providers_attempted=["brave"],
            responses=[invalid_response],
            registry=load_registry(),
            budget=select_budget(context_used=0, context_limit=100),
        )
