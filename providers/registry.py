"""Load explicit provider provenance declarations from configuration."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from providers.contracts import ContractViolation, optional_text, require_mapping, require_text


class IndependenceClass(StrEnum):
    """Crawler/index provenance class defined by docs/PROVIDERS.md."""

    INDEPENDENT = "A"
    AGGREGATOR = "B"
    DERIVATIVE = "C"


@dataclass(frozen=True, slots=True)
class ProviderDeclaration:
    """Configured facts about a provider; none are inferred from API responses."""

    name: str
    display_name: str
    independence_class: IndependenceClass
    index_provenance: str
    caveat: str | None


def _parse_declaration(name: str, value: object) -> ProviderDeclaration:
    data = require_mapping(value, f"providers.{name}")
    class_value = require_text(
        data.get("independence_class"), f"providers.{name}.independence_class"
    )
    try:
        independence_class = IndependenceClass(class_value)
    except ValueError as error:
        raise ContractViolation(
            f"providers.{name}.independence_class must be one of A, B, or C"
        ) from error
    return ProviderDeclaration(
        name=name,
        display_name=require_text(data.get("display_name"), f"providers.{name}.display_name"),
        independence_class=independence_class,
        index_provenance=require_text(
            data.get("index_provenance"), f"providers.{name}.index_provenance"
        ),
        caveat=optional_text(data.get("caveat"), f"providers.{name}.caveat"),
    )


def load_registry(path: Path | None = None) -> dict[str, ProviderDeclaration]:
    """Load provider declarations in stable name order from JSON configuration."""

    registry_path = path or Path(__file__).with_name("registry.json")
    raw = cast(object, json.loads(registry_path.read_text(encoding="utf-8")))
    root = require_mapping(raw, "registry")
    providers = require_mapping(root.get("providers"), "registry.providers")
    return {
        name: _parse_declaration(name, providers[name])
        for name in sorted(providers)
    }
