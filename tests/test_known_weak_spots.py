"""Executable records of measured weak spots that later work must not hide."""

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "weakspots"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_wrong_consensus_fixture_documents_open_precision_defect() -> None:
    fixture = load_fixture("wrong_consensus.json")
    wrong_url = fixture["known_wrong_consensus_url"]
    correct_url = fixture["human_labelled_correct_url"]
    occurrences = {
        url: sum(url in urls for urls in fixture["provider_urls"].values())
        for url in (wrong_url, correct_url)
    }

    assert fixture["expected_defect"] == "popular_wrong_page_is_corroborated"
    assert occurrences[wrong_url] == 2
    assert occurrences[correct_url] == 1
    assert fixture["defect_status"] == "open"


def test_measured_degenerate_queries_do_not_create_a_zero_case() -> None:
    fixture = load_fixture("nonzero_consensus.json")
    rates = [measurement["rate"] for measurement in fixture["measurements"]]

    assert fixture["source"] == "docs/EXPERIMENT-OVERLAP.md section 3"
    assert rates == [0.321, 0.28, 0.2, 0.4, 0.154]
    assert min(rates) > 0
