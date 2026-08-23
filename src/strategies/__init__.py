"""WireClaim Strategy Tracks: the router (`router.py`), the always-on blind floor
(`fast_path.py`), the active estimator (`strategy2/`) and its lower-priority tail-aware
comparison (`strategy4/`). `strategy1` and `strategy3` live in `src.legacy`.

`STRATEGY_PRIORITIES` lives here, and only here, because it is metadata about the tracks
themselves rather than about the router or the coordinator. It used to be declared in both
`strategy_router.py` and `submission_coordinator.py`, and the two copies had already drifted
apart: the router had Strategy 2 winning while the coordinator still ranked Strategy 3
above it, so our own submission logs labelled the winning track with the wrong priority.
"""

#: Higher wins. A source not listed here scores 0 and therefore loses to every known track,
#: which is the safe default for a typo in a `Proposal.source`. Keyed by `Proposal.source`,
#: a string tag -- not by module path, so `strategy1`/`strategy3` living in `src.legacy`
#: does not touch this dict.
#:
#: Strategy 2 remains top and is the only Proposal the live router may submit. Strategy 4
#: is deliberately second: it is recorded as a counterfactual after Strategy 2 has already
#: won, so the tail experiment can accumulate live evidence without changing a Game.
#: Strategies 1 and 3 are dormant legacy tracks; their values remain for old logs and
#: explicitly constructed test/backtest routers.
STRATEGY_PRIORITIES = {
    "strategy1": 1,
    "strategy3": 2,
    "strategy4": 2,
    "strategy2": 3,
}

__all__ = ["STRATEGY_PRIORITIES"]
