"""Provider provenance is configuration, never inference."""

import json
from pathlib import Path

import pytest

from providers.contracts import ContractViolation
from providers.registry import IndependenceClass, load_registry


def test_shipped_registry_declares_independence_classes() -> None:
    registry = load_registry()

    assert {
        name: declaration.independence_class.value for name, declaration in registry.items()
    } == {"brave": "A", "exa": "A", "parallel": "A", "tavily": "B"}


def test_tavily_class_b_caveat_is_read_from_config(tmp_path: Path) -> None:
    caveat = "test proves this value came from configuration"
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "tavily": {
                        "display_name": "Tavily",
                        "independence_class": "B",
                        "index_provenance": "configured provenance",
                        "caveat": caveat,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    declaration = load_registry(path)["tavily"]

    assert declaration.independence_class is IndependenceClass.AGGREGATOR
    assert declaration.caveat == caveat


def test_invalid_independence_class_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "unknown": {
                        "display_name": "Unknown",
                        "independence_class": "inferred",
                        "index_provenance": "unknown",
                        "caveat": None,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractViolation, match="must be one of A, B, or C"):
        load_registry(path)
