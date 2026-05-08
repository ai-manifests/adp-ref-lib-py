from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable


class Vote(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ReversibilityTier(Enum):
    REVERSIBLE = "reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class DissentConditionStatus(Enum):
    ACTIVE = "active"
    FALSIFIED = "falsified"
    AMENDED = "amended"
    WITHDRAWN = "withdrawn"


class TerminationState(Enum):
    CONVERGED = "converged"
    PARTIAL_COMMIT = "partial_commit"
    DEADLOCKED = "deadlocked"


class StakeMagnitude(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class CalibrationScore:
    value: float
    sample_size: int
    staleness: timedelta


@dataclass(frozen=True)
class AgentRegistration:
    agent_id: str
    authority: float
    calibration: CalibrationScore
    decision_class: str


@dataclass(frozen=True)
class Amendment:
    round: int
    new_condition: str
    reason: str
    triggered_by: str


@dataclass(frozen=True)
class DissentCondition:
    id: str
    condition: str
    status: DissentConditionStatus = DissentConditionStatus.ACTIVE
    amendments: tuple[Amendment, ...] = ()
    tested_in_round: int | None = None
    tested_by: str | None = None

    @staticmethod
    def create(id: str, condition: str) -> DissentCondition:
        return DissentCondition(id=id, condition=condition)

    def falsify(self, round: int, tested_by: str) -> DissentCondition:
        return DissentCondition(
            id=self.id, condition=self.condition,
            status=DissentConditionStatus.FALSIFIED,
            amendments=self.amendments,
            tested_in_round=round, tested_by=tested_by,
        )

    def amend(self, round: int, new_condition: str, reason: str, triggered_by: str) -> DissentCondition:
        amendment = Amendment(round, new_condition, reason, triggered_by)
        return DissentCondition(
            id=self.id, condition=self.condition,
            status=DissentConditionStatus.AMENDED,
            amendments=self.amendments + (amendment,),
            tested_in_round=round, tested_by=triggered_by,
        )

    def withdraw(self) -> DissentCondition:
        return DissentCondition(
            id=self.id, condition=self.condition,
            status=DissentConditionStatus.WITHDRAWN,
            amendments=self.amendments,
            tested_in_round=self.tested_in_round,
            tested_by=self.tested_by,
        )


@dataclass(frozen=True)
class VoteRevision:
    round: int
    prior_vote: Vote
    new_vote: Vote
    prior_confidence: float | None
    new_confidence: float | None
    reason: str
    timestamp: datetime


@dataclass(frozen=True)
class ProposalAction:
    kind: str
    target: str
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BlastRadius:
    scope: tuple[str, ...]
    estimated_users_affected: int
    rollback_cost_seconds: int


@dataclass(frozen=True)
class DomainClaim:
    domain: str
    authority_source: str


@dataclass(frozen=True)
class Justification:
    summary: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class Stake:
    declared_by: str
    magnitude: StakeMagnitude
    calibration_at_stake: bool


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    deliberation_id: str
    agent_id: str
    timestamp: datetime
    action: ProposalAction
    vote: Vote
    confidence: float
    domain_claim: DomainClaim
    reversibility_tier: ReversibilityTier
    blast_radius: BlastRadius
    justification: Justification
    stake: Stake
    dissent_conditions: tuple[DissentCondition, ...]
    revisions: tuple[VoteRevision, ...] = ()

    @property
    def current_vote(self) -> Vote:
        return self.revisions[-1].new_vote if self.revisions else self.vote

    @property
    def current_confidence(self) -> float | None:
        return self.revisions[-1].new_confidence if self.revisions else self.confidence

    def revise(self, round: int, new_vote: Vote, new_confidence: float | None, reason: str) -> Proposal:
        revision = VoteRevision(
            round=round,
            prior_vote=self.current_vote,
            new_vote=new_vote,
            prior_confidence=self.current_confidence,
            new_confidence=new_confidence,
            reason=reason,
            timestamp=datetime.utcnow(),
        )
        return Proposal(
            proposal_id=self.proposal_id, deliberation_id=self.deliberation_id,
            agent_id=self.agent_id, timestamp=self.timestamp, action=self.action,
            vote=self.vote, confidence=self.confidence,
            domain_claim=self.domain_claim, reversibility_tier=self.reversibility_tier,
            blast_radius=self.blast_radius, justification=self.justification,
            stake=self.stake,
            dissent_conditions=self.dissent_conditions,
            revisions=self.revisions + (revision,),
        )

    def with_dissent_condition(self, condition_id: str, update: Callable[[DissentCondition], DissentCondition]) -> Proposal:
        new_conditions = tuple(
            update(dc) if dc.id == condition_id else dc
            for dc in self.dissent_conditions
        )
        if all(dc.id != condition_id for dc in self.dissent_conditions):
            raise ValueError(f"Dissent condition '{condition_id}' not found.")
        return Proposal(
            proposal_id=self.proposal_id, deliberation_id=self.deliberation_id,
            agent_id=self.agent_id, timestamp=self.timestamp, action=self.action,
            vote=self.vote, confidence=self.confidence,
            domain_claim=self.domain_claim, reversibility_tier=self.reversibility_tier,
            blast_radius=self.blast_radius, justification=self.justification,
            stake=self.stake,
            dissent_conditions=new_conditions,
            revisions=self.revisions,
        )


@dataclass(frozen=True)
class TallyResult:
    approve_weight: float
    reject_weight: float
    abstain_weight: float
    total_deliberation_weight: float
    approval_fraction: float
    participation_fraction: float
    threshold_met: bool
    participation_floor_met: bool
    domain_vetoes_clear: bool
    converged: bool
