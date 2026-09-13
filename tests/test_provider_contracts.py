"""Offline contract tests for every provider response shape."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from providers import brave, exa, parallel, tavily
from providers.contracts import (
    ContractViolation,
    ProviderResponse,
    ProviderStatus,
    require_mapping,
)

FIXTURES = Path(__file__).parent / "fixtures" / "providers"
Parser = Callable[..., ProviderResponse]


def load_recording(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "parser", "provider", "expected_url"),
    [
        ("brave_search.json", brave.parse_response, "brave", "https://example.com/brave"),
        ("exa_search.json", exa.parse_response, "exa", "https://example.com/exa"),
        ("tavily_search.json", tavily.parse_response, "tavily", "https://example.com/tavily"),
        (
            "parallel_search.json",
            parallel.parse_response,
            "parallel",
            "https://example.com/parallel",
        ),
    ],
)
def test_recorded_provider_contract(
    fixture_name: str,
    parser: Parser,
    provider: str,
    expected_url: str,
) -> None:
    recording = load_recording(fixture_name)

    response = parser(recording["body"], status_code=recording["status_code"])

    assert recording["provider"] == provider
    assert response.provider == provider
    assert response.status is ProviderStatus.OK
    assert [result.url for result in response.results] == [expected_url]
    assert response.error is None


@pytest.mark.parametrize(
    ("parser", "empty_payload"),
    [
        (brave.parse_response, {"web": {"results": []}}),
        (exa.parse_response, {"results": []}),
        (tavily.parse_response, {"results": []}),
        (parallel.parse_response, {"results": []}),
    ],
)
def test_valid_empty_response_is_explicit(parser: Parser, empty_payload: object) -> None:
    response = parser(empty_payload)

    assert response.status is ProviderStatus.EMPTY
    assert response.results == ()
    assert response.error is None


@pytest.mark.parametrize(
    "parser",
    [brave.parse_response, exa.parse_response, tavily.parse_response, parallel.parse_response],
)
def test_server_error_degrades_instead_of_crashing(parser: Parser) -> None:
    response = parser({"unexpected": "error body"}, status_code=503)

    assert response.status is ProviderStatus.DEGRADED
    assert response.results == ()
    assert response.error is not None
    assert response.error.code == "http_error"


def test_brave_rate_limit_fixture_degrades_instead_of_crashing() -> None:
    recording = load_recording("brave_rate_limited.json")

    response = brave.parse_response(
        recording["body"], status_code=recording["status_code"]
    )

    assert response.status is ProviderStatus.DEGRADED
    assert response.results == ()
    assert response.error is not None
    assert response.error.code == "rate_limited"


@pytest.mark.parametrize(
    ("parser", "drifted_payload"),
    [
        (brave.parse_response, {"web": {}}),
        (exa.parse_response, {}),
        (tavily.parse_response, {}),
        (parallel.parse_response, {}),
    ],
)
def test_fixture_shape_drift_fails_loudly(parser: Parser, drifted_payload: object) -> None:
    with pytest.raises(ContractViolation, match="must be an array"):
        parser(drifted_payload)


def test_result_item_shape_drift_fails_loudly() -> None:
    with pytest.raises(ContractViolation, match=r"response.results\[0\]\.url"):
        exa.parse_response({"results": [{"title": "Missing URL", "text": None}]})


def test_optional_text_shape_drift_fails_loudly() -> None:
    with pytest.raises(ContractViolation, match=r"response.results\[0\]\.text"):
        exa.parse_response(
            {"results": [{"url": "https://example.com", "title": "Result", "text": 7}]}
        )


def test_parallel_excerpt_shape_drift_fails_loudly() -> None:
    with pytest.raises(ContractViolation, match="must contain only strings"):
        parallel.parse_response(
            {
                "results": [
                    {
                        "url": "https://example.com",
                        "title": "Result",
                        "excerpts": ["valid", 7],
                    }
                ]
            }
        )


def test_non_object_payload_fails_loudly() -> None:
    with pytest.raises(ContractViolation, match="response must be an object"):
        exa.parse_response([])


def test_non_string_mapping_keys_fail_loudly() -> None:
    with pytest.raises(ContractViolation, match="must have string keys"):
        require_mapping({1: "value"}, "response")
