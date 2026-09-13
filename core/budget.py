"""Context-usage-aware deterministic summary budgets."""

from dataclasses import dataclass
from enum import StrEnum

DEFAULT_SUMMARY_BYTES = 16 * 1024
FAST_SUMMARY_BYTES = 8 * 1024
TIGHT_SUMMARY_BYTES = 4 * 1024
CRITICAL_SUMMARY_BYTES = 2 * 1024


class BudgetLevel(StrEnum):
    """Context pressure tier used to choose a summary cap."""

    NORMAL = "normal"
    TIGHT = "tight"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AppliedBudget:
    """The exact budget decision recorded in an envelope."""

    level: BudgetLevel
    max_bytes: int
    requested_bytes: int
    context_used: int
    context_limit: int
    usage_basis_points: int

    def to_data(self) -> dict[str, object]:
        return {
            "level": self.level.value,
            "max_bytes": self.max_bytes,
            "requested_bytes": self.requested_bytes,
            "context_used": self.context_used,
            "context_limit": self.context_limit,
            "usage_basis_points": self.usage_basis_points,
        }


def select_budget(
    *,
    context_used: int,
    context_limit: int,
    requested_bytes: int = DEFAULT_SUMMARY_BYTES,
) -> AppliedBudget:
    """Tighten a requested summary cap at 75% and 90% context usage."""

    if context_used < 0:
        raise ValueError("context_used must be non-negative")
    if context_limit <= 0:
        raise ValueError("context_limit must be positive")
    if requested_bytes <= 0:
        raise ValueError("requested_bytes must be positive")

    if context_used * 100 >= context_limit * 90:
        level = BudgetLevel.CRITICAL
        max_bytes = min(requested_bytes, CRITICAL_SUMMARY_BYTES)
    elif context_used * 100 >= context_limit * 75:
        level = BudgetLevel.TIGHT
        max_bytes = min(requested_bytes, TIGHT_SUMMARY_BYTES)
    else:
        level = BudgetLevel.NORMAL
        max_bytes = requested_bytes

    return AppliedBudget(
        level=level,
        max_bytes=max_bytes,
        requested_bytes=requested_bytes,
        context_used=context_used,
        context_limit=context_limit,
        usage_basis_points=(context_used * 10_000) // context_limit,
    )
