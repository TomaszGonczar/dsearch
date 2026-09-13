"""Deterministic provider response contracts.

Provider modules decode recorded or caller-supplied HTTP responses. They deliberately do not
perform network requests; orchestration and transport belong to later issues.
"""

from providers.contracts import (
    ContractViolation,
    ProviderError,
    ProviderResponse,
    ProviderStatus,
    SearchResult,
)

__all__ = [
    "ContractViolation",
    "ProviderError",
    "ProviderResponse",
    "ProviderStatus",
    "SearchResult",
]
