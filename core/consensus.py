"""Pairwise agreement over canonical URLs from explicitly independent providers."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from core.canonical import canonicalize_url
from providers.registry import IndependenceClass, ProviderDeclaration


class ConsensusStatus(StrEnum):
    """Whether a consensus rate was actually measurable."""

    MEASURED = "measured"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PairwiseAgreement:
    """Jaccard agreement for one pair of independent provider indexes."""

    provider_a: str
    provider_b: str
    intersection_count: int
    union_count: int
    rate: float

    def to_data(self) -> dict[str, object]:
        return {
            "provider_a": self.provider_a,
            "provider_b": self.provider_b,
            "intersection_count": self.intersection_count,
            "union_count": self.union_count,
            "rate": self.rate,
        }


@dataclass(frozen=True, slots=True)
class ConsensusReport:
    """Measured corroboration rate plus the pairwise evidence behind it."""

    status: ConsensusStatus
    rate: float | None
    corroborated_count: int
    unique_url_count: int
    corroborated_urls: tuple[str, ...]
    eligible_providers: tuple[str, ...]
    ineligible_providers: tuple[str, ...]
    pairs: tuple[PairwiseAgreement, ...]

    def to_data(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "rate": self.rate,
            "corroborated_count": self.corroborated_count,
            "unique_url_count": self.unique_url_count,
            "corroborated_urls": list(self.corroborated_urls),
            "eligible_providers": list(self.eligible_providers),
            "ineligible_providers": list(self.ineligible_providers),
            "pairs": [pair.to_data() for pair in self.pairs],
        }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compute_consensus(
    provider_urls: Mapping[str, Sequence[str]],
    registry: Mapping[str, ProviderDeclaration],
) -> ConsensusReport:
    """Measure corroborated URLs across configured class-A providers.

    Duplicate or decorated URLs from one provider count once. Class B, class C, and providers
    absent from configuration remain visible as ineligible but never contribute a trust mark.
    """

    canonical_by_provider = {
        provider: frozenset(canonicalize_url(url) for url in urls)
        for provider, urls in sorted(provider_urls.items())
    }
    eligible = tuple(
        provider
        for provider in canonical_by_provider
        if provider in registry
        and registry[provider].independence_class is IndependenceClass.INDEPENDENT
    )
    ineligible = tuple(provider for provider in canonical_by_provider if provider not in eligible)

    if len(eligible) < 2:
        unique_urls = set().union(*(canonical_by_provider[name] for name in eligible))
        return ConsensusReport(
            status=ConsensusStatus.UNAVAILABLE,
            rate=None,
            corroborated_count=0,
            unique_url_count=len(unique_urls),
            corroborated_urls=(),
            eligible_providers=eligible,
            ineligible_providers=ineligible,
            pairs=(),
        )

    pair_reports: list[PairwiseAgreement] = []
    for provider_a, provider_b in combinations(eligible, 2):
        urls_a = canonical_by_provider[provider_a]
        urls_b = canonical_by_provider[provider_b]
        intersection_count = len(urls_a & urls_b)
        union_count = len(urls_a | urls_b)
        pair_reports.append(
            PairwiseAgreement(
                provider_a=provider_a,
                provider_b=provider_b,
                intersection_count=intersection_count,
                union_count=union_count,
                rate=_ratio(intersection_count, union_count),
            )
        )

    occurrences: Counter[str] = Counter()
    for provider in eligible:
        occurrences.update(canonical_by_provider[provider])
    corroborated_urls = tuple(sorted(url for url, count in occurrences.items() if count >= 2))
    unique_url_count = len(occurrences)
    return ConsensusReport(
        status=ConsensusStatus.MEASURED,
        rate=_ratio(len(corroborated_urls), unique_url_count),
        corroborated_count=len(corroborated_urls),
        unique_url_count=unique_url_count,
        corroborated_urls=corroborated_urls,
        eligible_providers=eligible,
        ineligible_providers=ineligible,
        pairs=tuple(pair_reports),
    )


def consensus_rate(
    provider_urls: Mapping[str, Sequence[str]],
    registry: Mapping[str, ProviderDeclaration],
) -> float | None:
    """Return the measured rate directly, or ``None`` when measurement is unavailable."""

    return compute_consensus(provider_urls, registry).rate
