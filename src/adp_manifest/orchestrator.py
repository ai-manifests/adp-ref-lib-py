from __future__ import annotations
from dataclasses import dataclass, field
from datetime import timedelta
from .types import (
    Proposal, Vote, ReversibilityTier, TerminationState,
    TallyResult, AgentRegistration, StakeMagnitude,
)
from .weighting import compute_weight


@dataclass(frozen=True)
class DeliberationConfig:
    max_rounds: int = 3
    participation_floor: float = 0.50
    domain_authority_veto_threshold: float = 0.80
    irreversible_min_authority: float = 0.70
    half_life_overrides: dict[str, timedelta] | None = None


class DeliberationOrchestrator:
    def __init__(self, config: DeliberationConfig | None = None):
        self._config = config or DeliberationConfig()

    def compute_weights(
        self,
        agents: list[AgentRegistration],
        proposals: list[Proposal],
    ) -> dict[str, float]:
        proposal_map = {p.agent_id: p for p in proposals}
        weights: dict[str, float] = {}
        for agent in agents:
            proposal = proposal_map.get(agent.agent_id)
            if proposal is None:
                continue
            weights[agent.agent_id] = compute_weight(
                authority=agent.authority,
                calibration=agent.calibration,
                decision_class=agent.decision_class,
                magnitude=proposal.stake.magnitude,
                half_life_overrides=self._config.half_life_overrides,
            )
        return weights

    def tally(
        self,
        proposals: dict[str, Proposal],
        weights: dict[str, float],
        tier: ReversibilityTier,
    ) -> TallyResult:
        approve_w = reject_w = abstain_w = 0.0

        for agent_id, proposal in proposals.items():
            weight = weights.get(agent_id, 0.0)
            vote = proposal.current_vote
            if vote == Vote.APPROVE:
                approve_w += weight
            elif vote == Vote.REJECT:
                reject_w += weight
            elif vote == Vote.ABSTAIN:
                abstain_w += weight

        total = approve_w + reject_w + abstain_w
        non_abstaining = approve_w + reject_w

        approval_frac = (approve_w / non_abstaining) if non_abstaining > 0 else 0.0
        participation_frac = (non_abstaining / total) if total > 0 else 0.0

        threshold = self.get_threshold(tier)
        threshold_met = approval_frac >= threshold
        floor_met = participation_frac >= self._config.participation_floor
        vetoes_clear = self._check_domain_vetoes(proposals, weights, tier)

        return TallyResult(
            approve_weight=approve_w,
            reject_weight=reject_w,
            abstain_weight=abstain_w,
            total_deliberation_weight=total,
            approval_fraction=approval_frac,
            participation_fraction=participation_frac,
            threshold_met=threshold_met,
            participation_floor_met=floor_met,
            domain_vetoes_clear=vetoes_clear,
            converged=threshold_met and floor_met and vetoes_clear,
        )

    def determine_termination(
        self, tally: TallyResult, has_reversible_subset: bool,
    ) -> TerminationState:
        if tally.converged:
            return TerminationState.CONVERGED
        return TerminationState.PARTIAL_COMMIT if has_reversible_subset else TerminationState.DEADLOCKED

    @staticmethod
    def get_threshold(tier: ReversibilityTier) -> float:
        if tier == ReversibilityTier.REVERSIBLE:
            return 0.50 + 1e-9
        if tier == ReversibilityTier.PARTIALLY_REVERSIBLE:
            return 0.60
        if tier == ReversibilityTier.IRREVERSIBLE:
            return 2.0 / 3.0
        return 0.50 + 1e-9

    def _check_domain_vetoes(
        self,
        proposals: dict[str, Proposal],
        weights: dict[str, float],
        tier: ReversibilityTier,
    ) -> bool:
        if tier == ReversibilityTier.REVERSIBLE:
            return True
        veto_threshold = (
            self._config.irreversible_min_authority
            if tier == ReversibilityTier.IRREVERSIBLE
            else self._config.domain_authority_veto_threshold
        )
        for agent_id, proposal in proposals.items():
            weight = weights.get(agent_id, 0.0)
            if weight >= veto_threshold and proposal.current_vote == Vote.REJECT:
                return False
        return True
