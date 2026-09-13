"""Pure deterministic core for dSearch integrity verdicts."""

from core.budget import AppliedBudget, BudgetLevel, select_budget
from core.canonical import CanonicalizationError, canonicalize, canonicalize_url
from core.consensus import ConsensusReport, ConsensusStatus, compute_consensus, consensus_rate
from core.envelope import SearchEnvelope, build_envelope

__all__ = [
    "AppliedBudget",
    "BudgetLevel",
    "CanonicalizationError",
    "ConsensusReport",
    "ConsensusStatus",
    "SearchEnvelope",
    "build_envelope",
    "canonicalize",
    "canonicalize_url",
    "compute_consensus",
    "consensus_rate",
    "select_budget",
]
