# adp-manifest

A Python reference implementation of the **Agent Deliberation Protocol (ADP)** specification — the consensus protocol that multi-agent systems use to reach calibrated, falsifiable decisions together. ADP defines proposals, weights, tallies, falsification, termination, and reversibility tiers.

This library is one of several reference implementations ([TypeScript](https://git.marketally.com/ai-manifests/adp-ref-lib-ts)) of the same spec. The spec itself is at [adp-manifest.dev](https://adp-manifest.dev) and is the source of truth; this library implements what the spec says.

Zero runtime dependencies. Requires Python 3.10+.

> **Looking for a runnable agent?** This library is the protocol core — data types, weighting math, and an in-memory orchestrator. For a full federation-ready agent runtime with HTTP endpoints, journal persistence, Ed25519 signing, signed calibration snapshots, ACB pricing, and MCP integration, install [`@ai-manifests/adp-agent`](https://www.npmjs.com/package/@ai-manifests/adp-agent) (TypeScript/Node).

## Install

```bash
pip install adp-manifest
```

Or from source:

```bash
git clone https://git.marketally.com/ai-manifests/adp-ref-lib-py.git
cd adp-ref-lib-py
pip install -e .
```

## Quick example

```python
from adp_manifest import (
    DeliberationOrchestrator,
    DeliberationConfig,
    Proposal,
    Stake,
    Justification,
    Vote,
    StakeMagnitude,
    CalibrationScore,
    compute_weight,
)

proposal = Proposal(
    agent_id="did:adp:test-runner-v1",
    domain="code.correctness",
    vote=Vote.APPROVE,
    confidence=0.82,
    stake=Stake(magnitude=StakeMagnitude.MEDIUM, domain="code.correctness"),
    justification=Justification(rationale="all tests pass", evidence_refs=[]),
    dissent_conditions=[],
)

calibration = CalibrationScore(value=0.78, sample_size=42)
weight = compute_weight(proposal, calibration)
# weight ≈ 0.82 × 0.78 × stake_factor(MEDIUM) × sample_size_discount(42)
```

## API

All public symbols are exported from the `adp_manifest` package root.

### Enums & primitive types

`Vote`, `ReversibilityTier`, `DissentConditionStatus`, `TerminationState`, `StakeMagnitude`

### Protocol types

`Proposal`, `ProposalAction`, `BlastRadius`, `DomainClaim`, `Justification`, `Stake`, `DissentCondition`, `VoteRevision`, `Amendment`, `CalibrationScore`, `AgentRegistration`, `TallyResult`

### Weighting functions

- `compute_weight(proposal, calibration)` — canonical proposal weight per ADP §4.2
- `compute_decay(age, half_life)` — time decay of calibration evidence
- `stake_factor(magnitude)` — maps `StakeMagnitude` to its numeric factor
- `apply_sample_size_discount(weight, n)` — Wilson-interval sample-size discount

### Orchestrator

- `DeliberationOrchestrator` — in-memory state machine that runs a deliberation through proposal → tally → falsification → termination. Takes a `DeliberationConfig`. Intended for prototypes, tests, and embedded-in-process use. For production distributed deliberation, see [`@ai-manifests/adp-agent`](https://www.npmjs.com/package/@ai-manifests/adp-agent) (TypeScript/Node).

## Testing

```bash
pip install -e .[dev]
pytest
```

## Spec

This library implements the Agent Deliberation Protocol specification. Read the spec at [adp-manifest.dev](https://adp-manifest.dev). If the spec and this library disagree, the spec is correct and this is a bug.

## License

Apache-2.0 — see [`LICENSE`](LICENSE) for the full license text and [`NOTICE`](NOTICE) for attribution.
