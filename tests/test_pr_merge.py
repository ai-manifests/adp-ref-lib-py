"""ADP spec Section 8 worked example — the PR merge scenario."""
from datetime import datetime, timedelta
from adp_manifest import (
    Vote, ReversibilityTier, StakeMagnitude, TerminationState,
    DissentConditionStatus, CalibrationScore, AgentRegistration,
    Proposal, ProposalAction, BlastRadius, DomainClaim, Justification,
    Stake, DissentCondition, DeliberationOrchestrator, DeliberationConfig,
    compute_weight,
)

DLB = "dlb_01HMXJ3E9R"
TEST_RUNNER = "did:adp:test-runner-v2"
SCANNER = "did:adp:security-scanner-v3"
LINTER = "did:adp:style-linter-v1"

AGENTS = [
    AgentRegistration(TEST_RUNNER, 0.90, CalibrationScore(0.85, 312, timedelta(days=18)), "code.correctness"),
    AgentRegistration(SCANNER, 0.85, CalibrationScore(0.83, 187, timedelta(days=12)), "security.policy"),
    AgentRegistration(LINTER, 0.30, CalibrationScore(0.72, 89, timedelta(days=4)), "code.style"),
]

ACTION = ProposalAction("merge_pull_request", "github.com/acme/api#4471", {"strategy": "squash"})
T0 = datetime(2026, 4, 11, 14, 32, 9)


def _proposals() -> dict[str, Proposal]:
    tr = Proposal(
        "prp_01", DLB, TEST_RUNNER, T0, ACTION, Vote.APPROVE, 0.86,
        DomainClaim("code.correctness", "mcp-manifest:test-runner-v2#authorities"),
        ReversibilityTier.PARTIALLY_REVERSIBLE,
        BlastRadius(("service:api", "consumers:web,mobile"), 12000, 90),
        Justification("All 1,847 tests pass.", ("journal:dlb_.../ev/9912",)),
        Stake("self", StakeMagnitude.HIGH, True),
        (DissentCondition.create("dc_tr_01", "if any test marked critical regresses"),
         DissentCondition.create("dc_tr_02", "if coverage delta is negative")),
    )
    sc = Proposal(
        "prp_02", DLB, SCANNER, T0, ACTION, Vote.REJECT, 0.79,
        DomainClaim("security.policy", "mcp-manifest:security-scanner-v3#authorities"),
        ReversibilityTier.PARTIALLY_REVERSIBLE,
        BlastRadius(("service:api",), 12000, 90),
        Justification("Auth module has untested paths.", ("scan:sast/run/4410",)),
        Stake("self", StakeMagnitude.HIGH, True),
        (DissentCondition.create("dc_ss_01", "if any code path in auth module remains untested"),
         DissentCondition.create("dc_ss_02", "if no security-focused test covers token validation")),
    )
    lt = Proposal(
        "prp_03", DLB, LINTER, T0, ACTION, Vote.APPROVE, 0.62,
        DomainClaim("code.style", "mcp-manifest:style-linter-v1#authorities"),
        ReversibilityTier.PARTIALLY_REVERSIBLE,
        BlastRadius(("service:api",), 12000, 90),
        Justification("2 minor naming deviations.", ("lint:eslint/run/7782",)),
        Stake("self", StakeMagnitude.MEDIUM, True),
        (DissentCondition.create("dc_sl_01", "if any public API name violates naming convention"),),
    )
    return {TEST_RUNNER: tr, SCANNER: sc, LINTER: lt}


def test_weights_match_spec():
    orch = DeliberationOrchestrator()
    proposals = _proposals()
    weights = orch.compute_weights(AGENTS, list(proposals.values()))
    assert 0.70 <= weights[TEST_RUNNER] <= 0.72
    assert 0.63 <= weights[SCANNER] <= 0.65
    assert 0.17 <= weights[LINTER] <= 0.19


def test_round_0_fails_threshold():
    orch = DeliberationOrchestrator()
    proposals = _proposals()
    weights = orch.compute_weights(AGENTS, list(proposals.values()))
    tally = orch.tally(proposals, weights, ReversibilityTier.PARTIALLY_REVERSIBLE)
    assert not tally.converged
    assert tally.participation_floor_met
    assert not tally.threshold_met
    assert 0.57 <= tally.approval_fraction <= 0.60


def test_after_belief_update_converges():
    orch = DeliberationOrchestrator()
    proposals = _proposals()
    weights = orch.compute_weights(AGENTS, list(proposals.values()))

    updated_scanner = (
        proposals[SCANNER]
        .with_dissent_condition("dc_ss_01", lambda dc: dc.falsify(1, TEST_RUNNER))
        .with_dissent_condition("dc_ss_02", lambda dc: dc.falsify(1, TEST_RUNNER))
        .revise(1, Vote.ABSTAIN, None, "Conditions falsified.")
    )
    updated = {**proposals, SCANNER: updated_scanner}

    assert updated_scanner.dissent_conditions[0].status == DissentConditionStatus.FALSIFIED
    assert updated_scanner.current_vote == Vote.ABSTAIN
    assert len(updated_scanner.revisions) == 1

    tally = orch.tally(updated, weights, ReversibilityTier.PARTIALLY_REVERSIBLE)
    assert tally.converged
    assert tally.approval_fraction == 1.0
    assert 0.57 <= tally.participation_fraction <= 0.60


def test_counterfactual_linter_abstains():
    orch = DeliberationOrchestrator()
    proposals = _proposals()
    weights = orch.compute_weights(AGENTS, list(proposals.values()))

    updated_scanner = proposals[SCANNER].revise(1, Vote.ABSTAIN, None, "Conditions falsified.")
    updated_linter = proposals[LINTER].revise(1, Vote.ABSTAIN, None, "Deferred.")
    updated = {**proposals, SCANNER: updated_scanner, LINTER: updated_linter}

    tally = orch.tally(updated, weights, ReversibilityTier.PARTIALLY_REVERSIBLE)
    assert not tally.converged
    assert not tally.participation_floor_met
    assert 0.45 <= tally.participation_fraction <= 0.48

    assert orch.determine_termination(tally, True) == TerminationState.PARTIAL_COMMIT
    assert orch.determine_termination(tally, False) == TerminationState.DEADLOCKED


def test_linter_is_the_margin():
    orch = DeliberationOrchestrator()
    proposals = _proposals()
    weights = orch.compute_weights(AGENTS, list(proposals.values()))

    scanner_abstains = proposals[SCANNER].revise(1, Vote.ABSTAIN, None, "")
    with_linter = {**proposals, SCANNER: scanner_abstains}
    without_linter = {**with_linter, LINTER: proposals[LINTER].revise(1, Vote.ABSTAIN, None, "")}

    assert orch.tally(with_linter, weights, ReversibilityTier.PARTIALLY_REVERSIBLE).converged
    assert not orch.tally(without_linter, weights, ReversibilityTier.PARTIALLY_REVERSIBLE).converged


def test_dissent_condition_amendment_append_only():
    proposals = _proposals()
    amended = proposals[SCANNER].with_dissent_condition(
        "dc_ss_01",
        lambda dc: dc.amend(1, "if any critical code path remains untested",
                            "Non-critical paths excluded.", TEST_RUNNER),
    )
    dc = amended.dissent_conditions[0]
    assert dc.status == DissentConditionStatus.AMENDED
    assert len(dc.amendments) == 1
    assert dc.condition == "if any code path in auth module remains untested"
    assert dc.amendments[0].new_condition == "if any critical code path remains untested"


def test_tier_escalation_raises_threshold():
    t1 = DeliberationOrchestrator.get_threshold(ReversibilityTier.PARTIALLY_REVERSIBLE)
    t2 = DeliberationOrchestrator.get_threshold(ReversibilityTier.IRREVERSIBLE)
    assert abs(t1 - 0.60) < 0.01
    assert abs(t2 - 0.667) < 0.01
    assert t2 > t1


def test_bootstrap_agent_has_zero_weight():
    cal = CalibrationScore(0.5, 0, timedelta(0))
    w = compute_weight(0.90, cal, "code.correctness", StakeMagnitude.HIGH)
    assert abs(w) < 1e-10
