"""Summary budget follows simulated context pressure."""

import pytest

from core.budget import BudgetLevel, select_budget


@pytest.mark.parametrize(
    ("used", "level", "max_bytes"),
    [
        (7_499, BudgetLevel.NORMAL, 16_384),
        (7_500, BudgetLevel.TIGHT, 4_096),
        (8_999, BudgetLevel.TIGHT, 4_096),
        (9_000, BudgetLevel.CRITICAL, 2_048),
        (10_500, BudgetLevel.CRITICAL, 2_048),
    ],
)
def test_budget_tightens_with_context_usage(
    used: int, level: BudgetLevel, max_bytes: int
) -> None:
    budget = select_budget(context_used=used, context_limit=10_000)

    assert budget.level is level
    assert budget.max_bytes == max_bytes
    assert budget.usage_basis_points == used


def test_budget_never_expands_a_smaller_request() -> None:
    budget = select_budget(context_used=9_500, context_limit=10_000, requested_bytes=1_024)

    assert budget.level is BudgetLevel.CRITICAL
    assert budget.max_bytes == 1_024


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"context_used": -1, "context_limit": 10}, "context_used"),
        ({"context_used": 0, "context_limit": 0}, "context_limit"),
        (
            {"context_used": 0, "context_limit": 10, "requested_bytes": 0},
            "requested_bytes",
        ),
    ],
)
def test_invalid_budget_inputs_fail_loudly(arguments: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        select_budget(**arguments)
