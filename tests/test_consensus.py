"""Consensus measures rates over canonical URLs and class-A providers only."""

import json
import random
from pathlib import Path
from typing import Any

from core.consensus import ConsensusStatus, compute_consensus, consensus_rate
from providers.registry import load_registry


def test_consensus_rate_uses_canonical_urls() -> None:
    report = compute_consensus(
        {
            "brave": ["http://www.example.com/shared/?utm_source=brave", "https://a.example"],
            "exa": ["https://example.com/shared", "https://b.example"],
        },
        load_registry(),
    )

    assert report.status is ConsensusStatus.MEASURED
    assert report.corroborated_urls == ("https://example.com/shared",)
    assert report.corroborated_count == 1
    assert report.unique_url_count == 3
    assert report.rate == 1 / 3
    assert report.pairs[0].rate == 1 / 3


def test_disjoint_independent_results_report_rate_zero() -> None:
    provider_urls = {
        "brave": ["https://brave.example"],
        "exa": ["https://exa.example"],
    }
    report = compute_consensus(provider_urls, load_registry())

    assert report.status is ConsensusStatus.MEASURED
    assert report.rate == 0.0
    assert consensus_rate(provider_urls, load_registry()) == 0.0
    assert report.corroborated_urls == ()
    assert report.pairs[0].rate == 0.0


def test_one_class_a_plus_tavily_is_unavailable_not_zero() -> None:
    report = compute_consensus(
        {"brave": ["https://example.com"], "tavily": ["https://example.com"]},
        load_registry(),
    )

    assert report.status is ConsensusStatus.UNAVAILABLE
    assert report.rate is None
    assert report.eligible_providers == ("brave",)
    assert report.ineligible_providers == ("tavily",)


def test_duplicates_from_one_provider_do_not_manufacture_consensus() -> None:
    report = compute_consensus(
        {
            "brave": [
                "https://example.com/?utm_source=one",
                "http://www.example.com",
            ],
            "exa": ["https://different.example"],
        },
        load_registry(),
    )

    assert report.rate == 0.0
    assert report.unique_url_count == 2


def test_consensus_is_identical_across_shuffled_inputs() -> None:
    randomizer = random.Random(7)
    baseline = {
        "brave": ["https://example.com", "https://a.example", "https://b.example"],
        "exa": ["http://www.example.com/", "https://c.example", "https://d.example"],
        "parallel": ["https://example.com?utm_source=p", "https://e.example"],
    }
    expected = compute_consensus(baseline, load_registry()).to_data()

    for _ in range(30):
        shuffled = {
            provider: randomizer.sample(urls, len(urls))
            for provider, urls in baseline.items()
        }
        assert compute_consensus(shuffled, load_registry()).to_data() == expected


def test_wrong_consensus_fixture_remains_an_open_defect() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "weakspots" / "wrong_consensus.json"
    fixture: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = compute_consensus(fixture["provider_urls"], load_registry())

    assert fixture["defect_status"] == "open"
    assert fixture["known_wrong_consensus_url"] in report.corroborated_urls
    assert fixture["human_labelled_correct_url"] not in report.corroborated_urls
