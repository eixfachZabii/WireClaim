"""Everything that reads a Case and emits structured evidence -- never a Charge, a Limit,
or a Fair Value (ADR 0001, `docs/brainstorm/sebi/adr/0001-the-model-reads-the-engine-prices.md`).

    policy/    -- coverage verdicts, quote validation, and policy-text slicing
    memory.py  -- Channel B, the Price Memory anchor recovered from settled Games
    fraud_detection.py -- the shipped coverage detector that locks a Limit to zero

Strategy 2's own Channel A/C gathering (`src/strategies/strategy2/channels.py`,
`model.py`) lives with the rest of Strategy 2 rather than here, because it is
private to that one estimator; everything in this package is shared across more
than one caller. `src/pricing/engine.py` is the other half of the seam: it is the
only module allowed to turn evidence into the two numbers we are scored on.
"""
